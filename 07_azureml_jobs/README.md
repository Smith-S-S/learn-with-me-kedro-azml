# Part 7 — Azure ML Jobs: running the pipeline in the cloud and *seeing* it

In Part 5 we met the Azure ML **workspace** and notebooks. This part uses the
piece you actually asked about: the **Jobs** section — where you submit work,
watch it run, and see your pipeline drawn as a clickable flowchart.

---

## What a "job" actually is

Right now, `python -m kedro run` runs **on your laptop**. Close the lid and it
stops. Your colleague can't see it. There's no record it ever happened.

A **job** is one piece of work you hand to Azure:

> *"Run this command, on that computer, using these files."*

Azure then:
1. finds a machine (or starts one),
2. copies your code onto it,
3. runs your command,
4. saves the outputs, logs, and metrics,
5. **switches the machine off** so you stop paying.

You are not running anything on your laptop. You're **describing work and
posting it to Azure.** Your laptop can go to sleep — the job carries on.

### Why this is worth the trouble

| On your laptop | As an Azure ML job |
|---|---|
| Stops when you close the lid | Runs on Azure's machine |
| Limited to your CPU/RAM | Any size machine, including GPUs |
| No record of what ran | Every run recorded forever |
| "What settings did I use last Tuesday?" | Stored with the run |
| Colleagues can't see it | Everyone sees the same dashboard |
| Nothing to show an auditor | Full history: who, what, when, what came out |

That last row is why regulated companies insist on it.

---

## "But I can just open a terminal and run it" — the honest answer

This is the right question to ask, and the answer starts with: **you are correct.**

If you create a **compute instance**, open its terminal, and type
`python -m kedro run`, it works. You get the same model, the same `metrics.json`,
the same R² of 0.993. Nothing about that is wrong or fake.

So why bother with jobs at all?

### First, what a compute instance actually is
A **compute instance is a rented laptop.** It is one virtual machine, assigned to
you personally, that you log into and type commands on.

That is genuinely useful — it's a bigger machine than yours, it sits next to your
data, and it has Azure permissions built in. But notice what it *isn't*: it's
still just **a computer with a terminal**. Running Kedro there is the same act as
running it on your own laptop. **The laptop simply moved to Azure.**

That solves the "my machine is too small" problem. It solves none of the others.

### What the terminal doesn't give you

When you type `python -m kedro run` in that terminal, here is what does **not**
happen:

| What's missing | Why it hurts later |
|---|---|
| **No record** | Nothing in the Jobs list. In three weeks, no way to prove the run happened or see what it produced. |
| **No code snapshot** | Azure never saw your code. You edited `nodes.py` afterwards, so what actually ran is now unknowable. |
| **No environment record** | You `pip install`ed something once to make it work. Nobody knows what. See below — this is the big one. |
| **No metrics history** | You cannot compare last night's R² against tonight's, because neither was stored. |
| **No graph** | Nothing to click. The pipeline UI comes from a *pipeline job*, not from a terminal. |
| **Nobody else can see it** | It happened inside your personal VM. Your colleague has no view of it. |
| **Can't be automated** | A CronJob or a CI pipeline cannot "type into your terminal". A job can be submitted by a machine. |
| **Dies with the connection** | Lose your network and the foreground process can be killed. (`nohup` or `tmux` works around it — but you have to remember.) |

### The one that actually bites people: environment drift

This is worth its own paragraph, because it is the most common real failure.

On a compute instance you install things by hand. `pip install evidently` here,
`pip install mlflow` there, over weeks. It works — for you, on that machine.

Then three months later someone must reproduce your result, and:
- nobody knows which packages were installed, or at which versions;
- the instance was deleted to save money, taking the answer with it;
- or *you* upgraded something and your own pipeline now behaves differently, and
  you have no baseline to compare against.

A job cannot drift, because its environment is **declared in the YAML**:

```yaml
environment: azureml://registries/azureml/environments/sklearn-1.5.../labels/latest
command: pip install -r requirements.txt && python -m kedro run
```

Run it today or in two years — same declared environment, same code snapshot,
same result. **The YAML is the record.** Nothing depends on what a particular
machine happens to have installed.

### And the money difference

| | **Compute instance** | **Compute cluster (jobs)** |
|---|---|---|
| Who it's for | Just you | Any job that's submitted |
| When it bills | **The whole time it is "Running"** — coding, on a call, at lunch, asleep | **Only while a job runs** |
| Idle cost | ~$0.27/hr on `DS3_v2` ≈ **$195/month** if left on | **$0** at `--min-instances 0` |
| Who turns it off | **You. By hand.** (Set auto-shutdown!) | Azure, automatically |

Forgetting to stop a compute instance is *the* most common way people get a
surprise Azure bill. The cluster switching itself off is not a small convenience.

### So: which should you use?

Both. They're not rivals — they're different phases of the same work:

| Use the **terminal** when... | Submit a **job** when... |
|---|---|
| Exploring, debugging, trying an idea | The result matters to someone else |
| You want the answer in 10 seconds | You need to prove what ran |
| A quick `kedro run --nodes train_model_node` | It should happen on a schedule |
| Poking at data in a notebook | You want the pipeline graph |
| Iterating fast on code that's still broken | It's going to production |

> **The rule of thumb:**
> **Terminal = the workbench. Job = the record.**
> Develop in the terminal, where fast and messy is exactly right. Submit a job
> for anything you'd need to *repeat, defend, schedule, or hand to someone else*.

And they combine — the compute instance is an excellent place to *submit jobs
from*. `az` is already installed and already logged in:

```bash
# on the compute instance terminal:
python -m kedro run                                  # quick check, 10 seconds
az ml job create --file pipeline-job.yml             # the real, recorded run
```

That's the normal working pattern: iterate in the terminal until it's right,
then submit it as a job so it counts.

### The honest downside of jobs
So the terminal isn't just a worse option — it's genuinely better for some things:

- **Jobs are slower to start.** Upload the code, queue, boot the cluster: 2–5
  minutes before your first line of output. The terminal answers instantly.
- **Debugging is clumsier.** A typo costs you a full submit-and-wait cycle
  instead of two seconds.
- **More moving parts.** YAML, environments, compute names — all of which can be
  wrong in their own ways.

Which is exactly why you develop in the terminal first. **Get it working there,
then submit it as a job.** Nobody should be debugging a typo through a
five-minute feedback loop.

---

## The vocabulary

| Word | Plain meaning |
|---|---|
| **Workspace** | Your Azure ML "project folder" in the cloud. Holds everything below. |
| **Job** | One run of one piece of work. Also called a **run**. |
| **Experiment** | A named folder grouping related jobs, so you can compare them. |
| **Compute** | The machine that runs the job. |
| **Compute instance** | **A rented laptop.** One VM, yours personally, that you log into and type in. Bills the whole time it's on. |
| **Compute cluster** | A pool of machines that starts when a job arrives and **switches off when idle**. Jobs run here. |
| **Environment** | The container image + libraries the job runs inside. |
| **Command job** | The simple kind: one command, **one box** in the UI. |
| **Pipeline job** | Several steps wired together — **this is the one that draws the graph**. |
| **Studio** | The Azure ML web UI at <https://ml.azure.com>. |

### The three job types

| Type | What it does | Draws a graph? |
|---|---|---|
| **Command job** | Runs one command | ❌ one box only |
| **Pipeline job** | Runs several linked steps | ✅ **yes** |
| **Sweep job** | Runs the same thing many times with different settings, to find the best | ✅ shows all trials |

**For the pipeline UI you want a pipeline job.** We'll do a command job first
because it's simpler, then the pipeline job.

---

## Setup (do this once)

### 1. Install the Azure ML CLI extension
The base `az` command doesn't know about ML. Add the extension:

```bash
az extension add --name ml
az extension update --name ml     # if you already had it
```

### 2. Log in and pick your subscription
```bash
az login
az account set --subscription "<your-subscription-name>"
```

### 3. Create a resource group and workspace
A **resource group** is just a labelled box holding related Azure things, so you
can delete them all together later.

```bash
az group create --name my-ml-rg --location eastus

az ml workspace create ^
  --name my-ml-workspace ^
  --resource-group my-ml-rg
```
> This takes a few minutes — it quietly creates storage, a key vault, and more.

### 4. Stop retyping the same two flags
Every `az ml` command wants `--resource-group` and `--workspace-name`. Set them
once as defaults:

```bash
az configure --defaults group=my-ml-rg workspace=my-ml-workspace
```
All commands below assume you've done this. If you skip it, add both flags to
every command.

### 5. Create the compute — a cluster, an instance, or both

A job needs a machine to run on. You have **two options**, and they both work for
every job in this part. Create either one (or both — they cost nothing extra to
merely exist).

#### Option A — a compute **cluster** (the default for real runs)
```bash
az ml compute create \
  --name cpu-cluster \
  --type amlcompute \
  --size Standard_DS3_v2 \
  --min-instances 0 \
  --max-instances 2 \
  --idle-time-before-scale-down 120
```

| Flag | What it means |
|---|---|
| `--type amlcompute` | A cluster that scales itself up and down |
| `--size Standard_DS3_v2` | 4 cores, 14 GB RAM — fine for our tiny model |
| **`--min-instances 0`** | **Scale to ZERO when idle. This is the one that saves you money.** |
| `--max-instances 2` | Never start more than 2 machines |
| `--idle-time-before-scale-down 120` | Switch off after 2 minutes idle |

> 💸 **`--min-instances 0` is the single most important flag in this part.**
> With `0`, an idle cluster costs **nothing**. Set it to `1` and you pay
> ~$150–200/month for a machine sitting doing nothing. This is *the* classic
> surprise Azure bill, and it catches people constantly.
>
> The trade-off: a cold cluster takes **2–5 minutes** to start your first job.
> That is the cluster booting, not a hang.

#### Option B — a compute **instance** (faster while you're learning)
You may already have `ci-house-price` from Part 5. If not:

```bash
az ml compute create \
  --name ci-house-price \
  --type computeinstance \
  --size Standard_DS11_v2 \
  --idle-time-before-shutdown-minutes 30
```

> ⚠️ **`--idle-time-before-shutdown-minutes` is the instance's version of
> `--min-instances 0`.** It is **not on by default**. Without it, the machine
> bills every hour until you stop it by hand.

An instance must be **Running** before it can accept a job — it does not start
itself:
```bash
az ml compute show --name ci-house-price --query "state" -o tsv   # want: Running
az ml compute start --name ci-house-price                          # if not
```

#### Which should you use?

| | **Cluster** (`cpu-cluster`) | **Instance** (`ci-house-price`) |
|---|---|---|
| Start-up delay | **2–5 min** (boots from zero) | **None** — already running |
| Cost when idle | **$0** | Bills until you stop it |
| Machines | Up to `--max-instances` | Always exactly 1 |
| Best for | Real runs, schedules, teams | **Debugging, fast retries, learning** |

> **The practical pattern:** use the **instance** while you're getting a job to
> work — a typo costs you seconds instead of five minutes. Switch to the
> **cluster** once it runs clean. Same YAML either way; only the compute changes.
>
> More detail: [`USING_COMPUTE_INSTANCE.md`](USING_COMPUTE_INSTANCE.md)

---

## Run 1: a command job (the simple one)

### Step 1 — copy the ignore file (once)
```bash
copy 07_azureml_jobs\.amlignore house-price\
```
Without it, Azure falls back to `.gitignore` and you may upload `.venv/` —
hundreds of megabytes on **every** submit.

### Step 2 — submit it

`command-job.yml` already says `compute: azureml:cpu-cluster`, so the plain
command uses the **cluster**. To use the **instance** instead, override it with
`--set` — no file editing needed.

**On the cluster** (uses the YAML as written):
```bash
cd house-price
az ml job create --file ../07_azureml_jobs/command-job.yml
```

**On the compute instance** (override at submit time):
```bash
cd house-price
az ml job create \
  --file ../07_azureml_jobs/command-job.yml \
  --set compute=azureml:ci-house-price
```

> **What `--set` does:** it patches one value in the YAML *for this submission
> only*. The file on disk is untouched, so the same YAML still targets the
> cluster next time. One definition, two targets.

> 🐚 **Line-continuation characters differ by shell** — this trips people up:
> | Shell | Character |
> |---|---|
> | Bash / Git Bash / the compute instance terminal | `\` |
> | Windows CMD | `^` |
> | PowerShell | `` ` `` (backtick) |
>
> Or just put the whole command on **one line** and avoid the problem entirely.

Azure prints a chunk of JSON. The bit you want is `name` — a random-looking id
like `sincere_pin_abc123xyz`. That's the job's handle.

### Watch it run
```bash
az ml job stream --name sincere_pin_abc123xyz
```

You get this from --name sincere_pin_abc123xyz

```bash
house-price/jobs/===> upbeat_car_dr7p4sd00x <===", "inputs": {}, "name": "upbeat_car_dr7p4sd00x", "outputs": { "default": { "mode": "rw_mount"
```

This tails the logs live in your terminal — you'll see the same Kedro output you
get locally, only it's happening on a machine in Azure.

### Other useful commands
```bash
az ml job list --output table          # recent jobs
az ml job show --name <job-name>       # full details
az ml job cancel --name <job-name>     # stop a runaway job (and the billing)
az ml job download --name <job-name>   # pull the outputs down to your laptop
```

In the Studio (<https://ml.azure.com> → **Jobs**) this appears as **one box**.
That's correct — a command job *is* one step. Now for the graph.

---

## Run 2: the pipeline job — **this is the one with the UI**

Same two choices, but ⚠️ **the property name is different.** A pipeline job has
no top-level `compute:` — its machine is set under `settings.default_compute`,
which applies to every step at once.

**On the cluster** (uses the YAML as written):
```bash
cd house-price
az ml job create --file ../07_azureml_jobs/pipeline-job.yml
```

**On the compute instance:**
```bash
cd house-price
az ml job create \
  --file ../07_azureml_jobs/pipeline-job.yml \
  --set settings.default_compute=azureml:ci-house-price
```

| Job type | What to override |
|---|---|
| Command job | `--set compute=azureml:<name>` |
| **Pipeline job** | `--set settings.default_compute=azureml:<name>` |

> Using `--set compute=...` on a pipeline job **silently does nothing useful** —
> it adds a property the schema doesn't read there, and your steps still run on
> whatever `settings.default_compute` says. If a job lands on the wrong machine,
> this is the first thing to check.

> **One step, one machine:** you can also give an individual step its own
> `compute:` — cheap CPU for data prep, expensive GPU for training. Anything set
> on a step wins over `settings.default_compute`.

Open <https://ml.azure.com> → **Jobs** → **house-price-training** → your run.

You'll see this, drawn for you:

```
   ┌──────────────────────┐     ┌────────────────────────┐
   │ 1. Create house data │ ──► │ 2. Train and evaluate  │
   └──────────────────────┘     └────────────────────────┘
```

### Where the arrows come from
**You never draw the picture.** You wrote this in the YAML:

```yaml
train_and_evaluate:
  inputs:
    house_data: ${{parent.jobs.prepare_data.outputs.house_data}}
```

That says *"my input is step 1's output."* Azure reads it, works out that
`prepare_data` must finish first, and **generates the arrow**.

This is the same idea as Kedro: in `pipeline.py` you say a node's input is
another node's output, and Kedro figures out the order. Azure ML does exactly
the same thing, and then draws it.

### ⚠️ Why two boxes and not three — where you're *allowed* to cut

This is the part that bites everyone the first time, so it's worth understanding
rather than copying.

**Each step runs as a separate process, on a separate machine.** Nothing stays
in memory between them. So anything crossing a step boundary has to be a dataset
Kedro actually **writes to disk** — meaning something declared in
`conf/base/catalog.yml`.

Our catalog declares exactly three:

| Declared in catalog (survives a step) | Only in memory (dies with the process) |
|---|---|
| `house_data` (CSV) | `welcome_message` |
| `regressor` (pickle) | `X_train`, `X_test` |
| `metrics` (JSON) | `y_train`, `y_test` |

So the "obvious" one-node-per-box split **fails**, and here are the exact errors:

```bash
kedro run --nodes create_house_data_node
# ValueError: Pipeline input(s) {'welcome_message'} not found in the DataCatalog
#   -> say_hi_at_start_node produces it, in memory. Include that node too.

kedro run --nodes evaluate_model_node
# ValueError: Pipeline input(s) {'X_test', 'y_test'} not found in the DataCatalog
#   -> split_data_node produces them, in memory. Keep split/train/evaluate together.
```

> **The rule: group nodes so every step starts and ends on a catalog entry.**
>
> Test any grouping locally *before* submitting it — it takes seconds instead of
> minutes, and the error message is identical:
> ```bash
> python -m kedro run --nodes say_hi_at_start_node,create_house_data_node
> ```

#### Want three boxes? Persist the intermediate data.
Nothing stops you — you just have to make `X_test`/`y_test` real files. Add to
`conf/base/catalog.yml`:

```yaml
X_test:
  type: pandas.CSVDataset
  filepath: data/05_model_input/X_test.csv

y_test:
  type: pandas.CSVDataset
  filepath: data/05_model_input/y_test.csv
```

Now `evaluate_model_node` can be its own step. **This is the real lesson:** how
finely you can split an Azure ML pipeline is decided by your Kedro catalog, not
by the YAML.

### What you can click on

| In the UI | What it gives you |
|---|---|
| **A box** | That step's logs, duration, inputs, outputs |
| **Green / red border** | Instantly shows *which* step failed |
| **Outputs + logs tab** | Every file the step produced |
| **Metrics tab** | Charts of anything you logged (see below) |
| **Code tab** | The exact snapshot of code that ran |
| **Overview → Reused** | Steps that were **cached** and skipped |

### Why splitting into steps is worth it

1. **You see where it broke.** One red box, instead of one red job and 2,000
   lines of log to read.
2. **Caching.** Change only step 3 and re-run — Azure **reuses** steps 1 and 2
   instead of redoing them. On real data this saves hours and real money.
3. **Different machines per step.** Cheap CPU box for data prep, expensive GPU
   for training. Add `compute:` to an individual step.
4. **Parallelism.** Steps that don't depend on each other run **at the same
   time**, worked out automatically from the inputs and outputs.

---

## Making metrics show up as charts

By default the UI shows logs but no numbers. To get charts on the **Metrics**
tab, log values with **MLflow** — Azure ML wires it up automatically inside a
job, so there's no configuration.

In `nodes.py`, the `evaluate_model` function becomes:

```python
def evaluate_model(model, X_test, y_test) -> dict:
    predictions = model.predict(X_test)
    mae = float(mean_absolute_error(y_test, predictions))
    r2 = float(r2_score(y_test, predictions))

    # NEW: send the numbers to Azure ML so they appear in the Metrics tab.
    # Inside an Azure ML job this "just works" -- Azure sets the tracking
    # address for you. Run it locally and it quietly logs to a local folder,
    # so this line is safe in both places.
    import mlflow
    mlflow.log_metric("mae", mae)
    mlflow.log_metric("r2", r2)

    return {"mae": mae, "r2": r2}
```

Add `mlflow` to `requirements.txt`. Now every run records its scores, and the
Studio will plot **r2 across all your runs** so you can see whether last night's
retrain actually improved anything — which is precisely the drift question from
Part 1, finally answerable with real evidence.

---

## The shortcut: `kedro-azureml`

Look at `pipeline-job.yml` and you'll notice clumsy `cp` commands shuffling
files between Kedro's folders and Azure's input/output folders. I left them
visible **on purpose**, so you can see the handover happening.

You don't have to write them. The `kedro-azureml` plugin reads your Kedro
pipeline and **generates the Azure ML pipeline for you** — one Azure ML step per
Kedro node, with all the wiring derived from your catalog:

### Step 1 — install it
```bash
pip install kedro-azureml        # v1.0.0, needs Python 3.9-3.12
```
Also add `kedro-azureml` to `house-price/requirements.txt`, or the machine
running the job won't have it.

### Step 2 — `kedro azureml init`

⚠️ **The five main arguments are POSITIONAL, not named flags.** There is no
`--subscription-id` or `--cluster-name` option. The order is fixed:

```
kedro azureml init [OPTIONS] SUBSCRIPTION_ID RESOURCE_GROUP WORKSPACE_NAME EXPERIMENT_NAME CLUSTER_NAME
```

```bash
cd house-price

kedro azureml init \
  00000000-0000-0000-0000-000000000000 \   # 1. SUBSCRIPTION_ID
  rg-azureml-demo \                        # 2. RESOURCE_GROUP
  mlw-house-price \                        # 3. WORKSPACE_NAME
  house-price-training \                   # 4. EXPERIMENT_NAME
  cpu-cluster \                            # 5. CLUSTER_NAME (or ci-house-price)
  --azureml-environment kedro-house-price@latest \
  --use-pipeline-data-passing
```

> 😌 **`init` is completely safe.** It only writes a local config file,
> `conf/base/azureml.yml`. It creates nothing in Azure and costs nothing, so run
> it, look at the file it produced, and re-run with different values freely.

#### The options that matter

| Option | What it does |
|---|---|
| `--use-pipeline-data-passing` | **The important one** — see below |
| `-a` / `-c` | The alternative: your own storage account + container for intermediate data |
| `--azureml-environment`, `--aml-env` | Which environment the steps run in |
| `-d`, `--docker-image` | Use a Docker image instead (that's Part 8) |

### 🎯 `--use-pipeline-data-passing` — the flag that fixes our two-box problem

Remember why our hand-written `pipeline-job.yml` could only manage **two** boxes:
`welcome_message`, `X_test` and `y_test` are MemoryDatasets, and memory doesn't
survive between machines.

**This flag solves exactly that.** It tells the plugin to move intermediate
datasets between steps using Azure ML's built-in pipeline data passing — so every
Kedro node can become its own step, with **no catalog changes and no `cp` glue**.

It is an either/or:

| Choice | What you must supply |
|---|---|
| `--use-pipeline-data-passing` | Nothing else. Azure ML's own storage handles it. |
| Neither flag | `-a <storage-account> -c <container>` — your own Blob Storage |

> ⚠️ The plugin's docs mark pipeline data passing **EXPERIMENTAL**. Fine for
> learning; check it still suits you before depending on it for production.

### Step 3 — ⚠️ the environment needs Kedro in it

This is the most likely thing to fail, so read it before you run.

A **curated** environment like
`azureml://registries/azureml/environments/sklearn-1.5/labels/latest` contains
scikit-learn and pandas — but **not `kedro` and not `kedro-azureml`**. The plugin
runs `kedro azureml execute ...` on the machine, so you'd get:

```
ModuleNotFoundError: No module named 'kedro'
```

Our hand-written YAML dodged this because its command starts with
`pip install -r requirements.txt`. **The plugin does not do that for you.**

So build a small environment that has them. `environment.yml`:

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
az ml environment create --file environment.yml
```

Then pass `--azureml-environment kedro-house-price@latest` to `init`.

### Step 4 — run it
```bash
kedro azureml run
```

### Using a compute instance instead of a cluster
The fifth positional is called `CLUSTER_NAME`, but it simply becomes
`compute_name` in `azureml.yml` — and Azure ML accepts a compute instance as a
job target. So `ci-house-price` works there.

Two caveats: the instance must be **Running** (otherwise the run sits in Queued
forever), and being single-node it runs the steps **one after another** instead of
in parallel. For this project that's a fine trade for the instant start-up.

The graph in the Studio then mirrors your Kedro pipeline **exactly** — six boxes,
one per node, including `say_hi_at_start_node` and `say_hi_at_end_node`.

Compare that with what we built by hand:

| | Hand-written `pipeline-job.yml` | `kedro-azureml` |
|---|---|---|
| Boxes in the graph | **2** (catalog boundaries only) | **6** — one per node |
| Intermediate data | You persist it in `catalog.yml` | Handled by pipeline data passing |
| `cp` / `mkdir` glue | You write it | None |
| Stays in sync with `pipeline.py` | ❌ you update the YAML by hand | ✅ generated each run |

**So why write the YAML by hand at all?** Because when the plugin misbehaves —
and plugins do — you need to know what it was generating for you. The YAML is
the thing that actually runs; the plugin is a convenience on top. You've now hit
the exact wall (`MemoryDataset` between machines) that the plugin exists to
solve, which is the best possible moment to let it take over.

---

## Common problems

| What you see | What it means |
|---|---|
| `az ml` not recognised | Extension missing: `az extension add --name ml` |
| Job sits in **Queued** for minutes | Normal. Cluster is starting from zero. |
| Job stuck **Queued** forever (cluster) | `--max-instances` is 0, or your quota is exhausted. Check `az ml compute show --name cpu-cluster`. |
| Job stuck **Queued** forever (instance) | The instance is **Stopped**. Jobs don't start it for you: `az ml compute start --name ci-house-price`. |
| `--set compute=...` seems ignored on a pipeline job | Wrong property. Pipeline jobs use `--set settings.default_compute=azureml:<name>`. |
| `kedro azureml init` → `no such option: --cluster-name` | The five main arguments are **positional**, not flags. See the signature above. |
| `kedro azureml run` → `ModuleNotFoundError: No module named 'kedro'` | Your `--azureml-environment` is a curated image without Kedro in it. Build the custom environment shown above. |
| Plugin run fails on an intermediate dataset | You passed neither `--use-pipeline-data-passing` nor `-a`/`-c`, so there's nowhere to put data between steps. |
| Job ran on the cluster when you wanted the instance | The `--set` didn't apply — check the shell continuation character (`\` bash, `^` cmd, `` ` `` PowerShell). A broken continuation silently drops the rest of the command. |
| Upload takes forever | `.amlignore` missing — you're uploading `.venv/`. |
| `AuthorizationFailed` | Wrong subscription: `az account set --subscription "..."` |
| Step fails with `ModuleNotFoundError` | The environment lacks a library. Add it to `requirements.txt` (the command does `pip install -r requirements.txt`). |
| Steps run but no graph appears | You submitted `command-job.yml`. Only `type: pipeline` draws a graph. |
| **`Could not open requirements file: 'requirements.txt'`** | **The `code:` path is wrong.** It is resolved relative to **the YAML file's folder**, not your terminal. From `07_azureml_jobs/`, use `code: ../house-price` — `code: .` would upload the `.md` files instead. Confirm via Studio → your job → **Code** tab. |
| **`ValueError: Pipeline input(s) {...} not found in the DataCatalog`** | **You cut the pipeline at a MemoryDataset.** That name is produced by a node you left out of this step. Group nodes so every step starts and ends on a catalog entry — see "Why two boxes and not three" above. |
| **`cp: cannot create ... No such file or directory`** | The `data/` folders don't exist on the machine — `data/` is excluded from the upload by `.amlignore` (or `.gitignore`'s `data/**`). Add `mkdir -p data/01_raw data/06_models data/08_reporting` before the `cp`. |
| Pipeline fails with **"Failed nodes: /prepare_data"** | That's just the parent telling you *which child* failed. Open the child job in the Studio for the real error — the parent never shows it. |
| `path not found` on the `cp` lines | A Kedro node wrote somewhere unexpected. Check the step's log to see what was actually produced. |

---

## 💸 Costs and cleanup

| Thing | Cost |
|---|---|
| Workspace itself | Free |
| Cluster **idle at `--min-instances 0`** | **$0** |
| `Standard_DS3_v2` while running | ~$0.27/hour |
| Storage of job snapshots and outputs | Pennies at this size |

```bash
# scale the cluster to zero (should already be, but confirm)
az ml compute update --name cpu-cluster --min-instances 0

# or delete everything in one go
az group delete --name my-ml-rg --yes --no-wait
```

> Always check **Jobs → Running** before you finish for the day. A forgotten job
> on a large machine is the other classic surprise bill.

---

## What you now understand
- A **job** is work you hand to Azure: it finds a machine, runs it, records
  everything, and switches the machine off.
- A **compute instance is a rented laptop**; typing `kedro run` in its terminal
  gives the same model but **no record, no snapshot, no graph, and no automation**
  — and it bills while idle. **Terminal = the workbench, job = the record.**
- **Command job** = one box. **Pipeline job** = the flowchart you wanted.
- The **arrows are generated** from `inputs`/`outputs` references — you describe
  the plumbing, Azure draws the picture. Exactly like Kedro.
- Splitting into steps buys you **visible failures, caching, per-step machines,
  and parallelism**.
- **`--min-instances 0`** is the flag that stops idle clusters billing you.
- **MLflow** logging turns metrics into charts across runs.
- **`kedro-azureml`** generates all of this from your existing Kedro pipeline.

## Next up (Part 8)
**Docker** — the jobs above borrowed a Microsoft-maintained environment. In Part
8 we build **our own** container image, so the job runs with exactly our
libraries at exactly our versions.
