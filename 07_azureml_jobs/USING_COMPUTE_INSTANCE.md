# Part 7 (extra) — Running jobs on a **Compute Instance** instead of a Cluster

> **Your question:** the README's step 5 creates a compute *cluster*. Can we just
> use the compute *instance* we already made in Part 5?
>
> **Short answer: yes.** A compute instance is a fully supported job target,
> including for pipeline jobs (the ones that draw the graph).
>
> This file shows how, and — more usefully — **when you should and shouldn't.**
> Nothing in `README.md` changes. Everything here is an *alternative* to its
> step 5.

---

## First: why does the README use a cluster then?

Not because the instance can't do it. Because for **the thing jobs are for**, the
cluster is the better default:

| | **Compute cluster** | **Compute instance** |
|---|---|---|
| Nodes | Single **or multi**-node | **Single node only** |
| Autoscales when you submit a job | ✅ | ❌ |
| Scales to **zero** when idle | ✅ | ❌ (you stop it, or set idle shutdown) |
| Automatic job scheduling | ✅ | ✅ |
| CPU and GPU | ✅ | ✅ |
| Shared by the team | ✅ | Assigned to **one person** |

*(This table is Microsoft's own capability comparison — see Sources at the end.)*

The two rows that decide it:

1. **Scales to zero.** A cluster at `--min-instances 0` costs **nothing** between
   jobs. A compute instance bills the whole time it's Running, whether a job is
   using it or not.
2. **Single node.** A compute instance is one machine, so pipeline steps that
   *could* run in parallel won't. On our 3-step pipeline that hardly matters. On
   a real one, it does.

So the cluster is the right default. But it isn't the right choice for
*everything* — which is the interesting part.

---

## When the compute instance is genuinely the better choice

There's one real advantage, and it's a big one while you're learning:

> ### 🚀 No cold start
> A cluster at zero nodes must **boot a machine** before your job starts —
> **2–5 minutes, every time**, if it has scaled down since your last run.
>
> A compute instance is already running. Your job starts **immediately.**

When you're debugging a job — fixing a typo, resubmitting, fixing another typo —
that difference is the whole experience. Ten iterations on a cluster is 30+
minutes of staring at "Queued". On a running compute instance it's seconds.

| Use the **compute instance** when... | Use the **cluster** when... |
|---|---|
| Debugging a job definition, resubmitting often | It's a real/scheduled run |
| The instance is already running anyway | Nothing is running right now |
| Small, quick jobs (like ours) | Big jobs, or ones needing a bigger machine |
| You want the answer *now* | You want it *cheap* |
| Learning what jobs even do | Production, CI/CD, or a team shares it |

**The practical pattern:** develop the job on your compute instance until it
runs clean, then point it at the cluster for the real thing. Same YAML — only
the compute name changes.

---

## The steps

### Step 1 — Have a compute instance, and make sure it's **Running**

If you followed Part 5 you already have `ci-house-price`. Otherwise:

```bash
az ml compute create ^
  --name ci-house-price ^
  --type computeinstance ^
  --size Standard_DS11_v2 ^
  --idle-time-before-shutdown-minutes 30
```

> ⚠️ **`--idle-time-before-shutdown-minutes` is the compute instance's version of
> `--min-instances 0`.** It's the setting that stops an idle machine billing you
> all weekend. Set it. It is not on by default.

**Check it's actually running** — a stopped instance cannot accept jobs, and the
error you get doesn't obviously say so:

```bash
az ml compute show --name ci-house-price --query "state" -o tsv
# want: Running
```

Start it if needed (takes 2–3 minutes):
```bash
az ml compute start --name ci-house-price
```

### Step 2 — Submit the job to it

Here's the neat part: **you don't have to edit the YAML files at all.** Override
the compute at submit time with `--set`:

**Command job:**
```bash
cd house-price
az ml job create --file ../07_azureml_jobs/command-job.yml ^
  --set compute=azureml:ci-house-price
```
OR

```bash
az ml job create --file ../07_azureml_jobs/command-job.yml \
  --set compute=azureml:ci-house-price
```

**Pipeline job** (the one that draws the graph) — the property is nested under
`settings`:
```bash
cd house-price
az ml job create --file ../07_azureml_jobs/pipeline-job.yml ^
  --set settings.default_compute=azureml:ci-house-price
```
OR

```bash
cd house-price
az ml job create --file ../07_azureml_jobs/pipeline-job.yml \
  --set settings.default_compute=azureml:ci-house-price
```

`--set` patches one value in the YAML for this submission only. The files on disk
stay exactly as they are, so the same YAML still works against the cluster
tomorrow. **This is why we don't edit the files** — one definition, two targets.

### Step 3 — Watch it, same as before

```bash
az ml job stream --name <job-name>
```

Everything else is identical: the job appears in the Studio's **Jobs** list, the
pipeline job still draws its clickable graph, metrics still land on the Metrics
tab, and the git commit is still recorded. **The compute target changes nothing
about what a job *is*.**

### Step 4 (optional) — Make it permanent

If you decide you want the instance as the standing default, copy the YAML rather
than editing the originals:

```bash
copy 07_azureml_jobs\pipeline-job.yml 07_azureml_jobs\pipeline-job-ci.yml
```
and in the copy change:
```yaml
settings:
  default_compute: azureml:ci-house-price     # was azureml:cpu-cluster
```

---

## ⚠️ `kedro azureml run` crashes on a compute instance — and how to fix it

Everything above applies to **`az ml job create`**, which happily accepts a
compute instance. The **`kedro-azureml` plugin is different** — it crashes:

```
AttributeError: 'ComputeInstance' object has no attribute 'min_instances'
```

### Why it happens

I traced it. In `kedro_azureml/client.py`, lines 54–57:

```python
logger.info(
    f"Creating job on cluster {cluster.name} ({cluster.size}, min instances: {cluster.min_instances}, "
    f"max instances: {cluster.max_instances})"
)

pipeline_job = ml_client.jobs.create_or_update(     # ← the real work
    self.azure_pipeline,
    experiment_name=config.experiment_name,
    compute=cluster,
)
```

The plugin assumes your compute is an **AmlCompute cluster**, which has
`min_instances` and `max_instances`. A `ComputeInstance` is a single machine — it
has no such thing, so the f-string raises before anything is submitted.

### 🎉 The good news: it's *only a log message*

Search the whole package and `min_instances` appears in **exactly one place** —
that logging line. Nowhere else:

```bash
grep -rn "min_instances\|max_instances" .venv/Lib/site-packages/kedro_azureml/
# client.py:55   ...min instances: {cluster.min_instances}...
# client.py:56   ...max instances: {cluster.max_instances})"
```

The actual submission passes `compute=cluster` — the **object itself** — and
Azure ML accepts a compute instance there perfectly well.

**So this isn't a real incompatibility. A cosmetic log line is blocking a job
that would otherwise run.**

### Fix 1 — Use a cluster (supported, no patching)

The honest recommendation for anything that matters. Create one that costs
nothing when idle:

```bash
az ml compute create \
  --name cpu-cluster --type amlcompute --size Standard_DS3_v2 \
  --min-instances 0 --max-instances 2

kedro azureml init <sub-id> rg-azureml-demo mlw-house-price \
  house-price-training cpu-cluster --use-pipeline-data-passing
```

You lose the instant start-up; you gain the supported path and $0 idle cost.

### Fix 2 — Patch it, and keep your compute instance ✅ *(tested)*

If you want the instance's instant start-up, give `ComputeInstance` the two
attributes the log line is looking for.

**Add this to `src/house_price/settings.py`:**

```python
# =============================================================================
# WORKAROUND: let `kedro azureml run` target a COMPUTE INSTANCE
# -----------------------------------------------------------------------------
# kedro-azureml assumes the compute is an AmlCompute CLUSTER and reads
# .min_instances / .max_instances off it -- but ONLY to print a log message
# (kedro_azureml/client.py lines 54-57). A ComputeInstance has neither, so the
# run dies with:
#     AttributeError: 'ComputeInstance' object has no attribute 'min_instances'
#
# A compute instance really is exactly one node, so reporting 1 and 1 is honest.
# Kedro imports this settings module during bootstrap, which happens before the
# plugin submits anything -- so the patch is in place by the time it's needed.
# =============================================================================
try:
    from azure.ai.ml.entities import ComputeInstance

    if not hasattr(ComputeInstance, "min_instances"):
        ComputeInstance.min_instances = property(lambda self: 1)
        ComputeInstance.max_instances = property(lambda self: 1)
except ImportError:
    pass  # azure-ai-ml not installed locally; nothing to patch
```

Then run as normal:
```bash
kedro azureml run
```

**Why `settings.py`?** Kedro imports `<package>.settings` during
`bootstrap_project` (see `kedro/framework/project/__init__.py:451`), which runs
*before* the plugin's submit code. Verified on this project — the module is in
`sys.modules` after bootstrap.

**Verified output of the patch:**
```
AmlCompute has min_instances     : False
ComputeInstance has min_instances: False
after patch                      : True
reads on a real object -> name=ci-house-price size=Standard_DS11_v2 min=1 max=1

THE LOG LINE NOW WORKS:
Creating job on cluster ci-house-price (Standard_DS11_v2, min instances: 1, max instances: 1)
```

> ⚠️ **What this does and doesn't promise.** It fixes the crash, which is a
> logging bug. It does **not** make the plugin *officially* support compute
> instances — a future version could depend on cluster behaviour for real. Keep
> the patch, but don't be shocked if an upgrade needs a rethink.

### Fix 3 — Edit the library directly (works, but fragile)

Open `.venv/Lib/site-packages/kedro_azureml/client.py` and simplify line 54:

```python
logger.info(f"Creating job on compute {cluster.name} ({cluster.size})")
```

Effective and honest, but **every `pip install --upgrade` wipes it**, and
teammates won't have it. Fix 2 lives in your repo and travels with the project.

---

## 🔎 Two more things in your `azureml.yml` worth checking

While tracing the crash I read the generated config. Two things there will bite
you *after* the crash is fixed.

### 1. `--docker-image` and `--azureml-environment` are different slots

If you ran `init` with `--docker-image azureml://registries/...`, you get:

```yaml
  environment_name: ~                                                   # empty
docker:
  image: azureml://registries/azureml/environments/sklearn-1.5/labels/latest
```

That's the wrong slot. Here's `generator.py:137-145` deciding what to use:

```python
def _resolve_azure_environment(self):
    if image := (self.docker_image or (self.config.docker.image if self.config.docker else None)):
        return Environment(image=image)          # ← treats it as a DOCKER IMAGE
    else:
        return self.aml_env or self.config.azure.environment_name
```

**`docker.image` wins**, and an `azureml://` URI is not a Docker image reference —
Azure will try to pull a container literally named `azureml://registries/...`.

**Fix:** use `--azureml-environment` (or `--aml-env`), not `--docker-image`. Or
edit `azureml.yml` directly:

```yaml
azure:
  environment_name: kedro-house-price@latest
docker:
  image: ~          # ← must be empty, or it takes priority
```

### 1b. ⚠️ No `azureml:` prefix in `environment_name`

This one costs an hour if you don't know it. These look interchangeable. **They
are not:**

```yaml
environment_name: azureml:kedro-house-price@latest   # ❌ 404s
environment_name: kedro-house-price@latest           # ✅ works
```

The `azureml:` prefix is the convention in **`az ml job` YAML files** (like our
`pipeline-job.yml`) — there it's correct and required. But kedro-azureml passes
this string **straight to the Python SDK**, which treats the whole thing as the
environment *name*. So it goes looking for an environment literally called
`azureml:kedro-house-price`, doesn't find it, and 404s.

The error gives you nothing to work with:

```
ResourceNotFoundError: (UserError) System.Net.Http.HttpConnectionResponseContent
  ...in _environment_versions_operations.py, get_next
```

Reproduced against a live workspace, same environment, prefix the only difference:

```
OK    get(name='kedro-house-price',         label='latest') -> version 1
FAIL  get(name='azureml:kedro-house-price', label='latest') -> ResourceNotFoundError
```

**Rule of thumb:** `azureml:` in `az ml` YAML files, **bare name** in
`azureml.yml`. Same for the compute — `cluster_name: "ci-house-price"`, no prefix.

### 2. The curated `sklearn-1.5` environment has no Kedro in it

Whichever slot you use, `sklearn-1.5` contains scikit-learn and pandas — **not
`kedro` or `kedro-azureml`**. The plugin runs `kedro azureml execute ...` on the
machine, so you'll get `ModuleNotFoundError: No module named 'kedro'`.

Our hand-written `pipeline-job.yml` dodged this because its command starts with
`pip install -r requirements.txt`. **The plugin does not do that for you.** Build
a custom environment that includes them — see the `environment.yml` / `conda.yml`
in [`README.md`](README.md#step-3).

---

## ✅ The full working sequence (after the `settings.py` patch)

You've added the patch. Here is the whole run, in order.

### Step 1 — Build an environment that contains Kedro

Do this **first** — `init` only writes a config file, but `run` will fail
immediately without an environment that has `kedro` in it.

`environment.yml`:
```yaml
$schema: https://azuremlschemas.azureedge.net/latest/environment.schema.json
name: kedro-house-price
image: mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu20.04:latest
conda_file: conda.yml
```

`conda.yml`:
```yaml
name: kedro-house-price
channels: [conda-forge]
dependencies:
  - python=3.12
  - pip
  - pip:
      - kedro
      - kedro-azureml
      - kedro-datasets
      - pandas
      - scikit-learn
```

```bash
az ml environment create --file environment.yml \
  --resource-group rg-azureml-demo --workspace-name mlw-house-price
```

### Step 2 — Run `init` with the right flags

```bash
cd house-price

kedro azureml init \
  1268fd42-f434-4927-a1a6-632642e6d7de \
  rg-azureml-demo \
  mlw-house-price \
  house-price-training \
  ci-house-price \
  --azureml-environment kedro-house-price@latest \
  --use-pipeline-data-passing
```

Note what changed from your earlier attempt: **`--azureml-environment`, not
`--docker-image`.**

#### Two rules the CLI enforces

Straight from `cli.py`, these raise a `UsageError` before anything happens:

| Rule | The error if you break it |
|---|---|
| **Exactly one** of `--docker-image` / `--azureml-environment` | *"You cannot specify both"* / *"You must specify either"* |
| **Either** `--use-pipeline-data-passing` **or** both `-a` and `-c` | *"You need to specify storage account (-a) and container name (-c) or enable pipeline data passing"* |

> 📌 **`init` overwrites `conf/base/azureml.yml` without asking.** No prompt, no
> backup. That's convenient for re-running — but any hand edits you made to that
> file are gone. Edit the file *or* re-run `init`, not both.

#### Why `--azureml-environment` also changes *how your code gets there*

This is a subtle but important side effect. From `cli.py`:

```python
"code_directory": "." if azureml_environment else "~",
```

| Flag you used | `code_directory` | What it means |
|---|---|---|
| `--azureml-environment` | `"."` | **Code upload flow.** Your local project is uploaded per run. The environment only needs Kedro + libraries. |
| `--docker-image` | `~` | **Docker flow.** Your code is expected to already be *inside* the image. |

For our purposes the **code upload flow is what you want** — edit `nodes.py`,
re-run, and the change ships. No image rebuild.

### Step 3 — Check the generated config before running

```bash
cat conf/base/azureml.yml
```

Four things to confirm:

```yaml
azure:
  environment_name: kedro-house-price@latest   # ✅ set, not ~
  code_directory: .                                    # ✅ code upload flow
  pipeline_data_passing:
    enabled: True                                      # ✅ MemoryDatasets survive
  compute:
    __default__:
      cluster_name: "ci-house-price"                   # ✅ your compute instance
docker:
  image: ~                                             # ✅ MUST be empty
```

> ⚠️ **If `docker.image` has a value, it wins** and `environment_name` is ignored
> entirely (`generator.py:_resolve_azure_environment`). This is the single most
> likely thing to still be wrong.

### Step 4 — Make sure the instance is running, then go

```bash
az ml compute show --name ci-house-price \
  --resource-group rg-azureml-demo --workspace-name mlw-house-price \
  --query "state" -o tsv                    # want: Running

az ml compute start --name ci-house-price   # if it isn't

kedro azureml run
```

If the patch is working, you'll see the log line that used to crash:

```
Creating job on cluster ci-house-price (Standard_DS11_v2, min instances: 1, max instances: 1)
```

Then the job appears in **ml.azure.com → Jobs → house-price-training**, drawn as
**one box per Kedro node** — the six-box graph the hand-written YAML couldn't
produce.

### ⚠️ One trap: `init` creates an *empty* `.amlignore`

If you don't already have one, `init` writes an **empty** `.amlignore`. And an
empty `.amlignore` excludes **nothing** — while still taking precedence over
`.gitignore`. Net result: your entire `.venv` uploads on every run.

If `.amlignore` already exists, `init` leaves it alone and prints a yellow
warning instead. So:

```bash
# make sure a REAL one is in place before running init
copy 07_azureml_jobs\.amlignore house-price\
```

Check it isn't empty:
```bash
cat .amlignore | head -3    # should show real rules, not nothing
```

---

## 💸 The cost difference, honestly

This is the part that actually matters, so here it is with numbers.

| Scenario | Compute instance | Cluster at `min-instances 0` |
|---|---|---|
| Running a 5-minute job | ~$0.02 | ~$0.02 **+ 2–5 min boot** |
| Idle for 8 hours (a workday) | **~$2.20** | **$0** |
| Left on all weekend by accident | **~$17** | **$0** |
| Left on for a month | **~$195** | **$0** |

The compute is the same price *per hour*. The difference is entirely **what
happens when you're not using it** — and that's where real bills come from.

> ⚠️ **Stopping a compute instance does not make it completely free.** You stop
> paying for compute hours, but you still pay for its **disk, public IP, and load
> balancer**. Small, but not zero. To get to actually-zero, delete it — which is
> safe as long as your work is in `~/cloudfiles/` or pushed to git
> (see [`../05_azure_ml_notebook/GITHUB_SETUP.md`](../05_azure_ml_notebook/GITHUB_SETUP.md)).

**The habit worth forming:**
```bash
az ml compute list -o table     # run this before you finish for the day
```

---

## Things that will catch you out

| What you see | What it means |
|---|---|
| Job stuck in **Queued** forever | The instance is **Stopped**. Jobs don't start it for you. `az ml compute start`. |
| Job queued behind another job | Single node — it runs one thing at a time. The cluster would have started a second machine. |
| Instance feels sluggish while a job runs | Your terminal and the job share **one machine**. That's the trade-off. |
| Pipeline steps run one after another | Expected. Single node = no parallelism, even for independent steps. |
| `Compute not found` | Wrong name, or it's in a different workspace. `az ml compute list -o table`. |
| It worked, then stopped working next morning | Idle shutdown did its job. Start it again. |
| Bill higher than expected | The instance was Running all week. This is the #1 Azure ML surprise bill. |
| **`AttributeError: 'ComputeInstance' object has no attribute 'min_instances'`** | **`kedro azureml run` only** — the plugin assumes a cluster. It's a logging bug, not a real incompatibility. See the section above: patch `settings.py`, or use a cluster. |
| `kedro azureml run` → `ModuleNotFoundError: No module named 'kedro'` | Your environment has no Kedro. Curated images like `sklearn-1.5` don't include it. |
| Azure can't pull an image called `azureml://registries/...` | You passed an environment URI to `--docker-image`. Use `--azureml-environment`, and set `docker.image: ~`. |
| **`ResourceNotFoundError: (UserError) System.Net.Http.HttpConnectionResponseContent`** in `_environment_versions_operations` | **Drop the `azureml:` prefix.** In `azureml.yml` use `environment_name: kedro-house-price@latest`, **not** `azureml:kedro-house-price@latest`. See below. |
| **`No module named 'cachetools'`** → *"Failed to load kedro_azureml.cli commands"* → **`Error: No such command 'azureml'`** | **kedro-azureml imports `cachetools` but doesn't declare it as a dependency** (its own packaging bug). Add `cachetools` to `conda.yml`, rebuild the environment, re-run. It works on your laptop only because cachetools happens to be installed there. |

---

## The third option nobody mentions: serverless compute

There's a middle path that skips this decision entirely — **serverless compute**.
You create no compute at all; Azure provides it per job and bills only for the
run. Microsoft's own docs recommend it over creating a cluster.

In the YAML, you simply leave the compute out, or:
```yaml
settings:
  default_compute: azureml:serverless
```

It's worth knowing about, though creating the cluster yourself (as the README
does) is more explicit — and being explicit is better while you're learning what
these pieces are.

---

## So, to answer the question directly

- **Can a compute instance run jobs?** Yes — command jobs and pipeline jobs both.
- **Why does the README use a cluster?** Because it scales to zero (costs nothing
  idle) and can use several machines. That's the right default for real runs.
- **Should you use the instance?** While learning and debugging — **yes**, because
  it starts instantly. Just remember it bills while it's on.
- **Do you have to pick one forever?** No. `--set` switches target per submission
  without touching a single file.

---

## Sources
- [Understand compute targets — Azure ML](https://learn.microsoft.com/en-us/azure/machine-learning/concept-compute-target)
  (the training-targets and cluster-vs-instance capability tables)
- [Manage a compute instance](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-manage-compute-instance)
- [Serverless compute](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-use-serverless-compute)
