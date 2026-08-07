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

## The vocabulary

| Word | Plain meaning |
|---|---|
| **Workspace** | Your Azure ML "project folder" in the cloud. Holds everything below. |
| **Job** | One run of one piece of work. Also called a **run**. |
| **Experiment** | A named folder grouping related jobs, so you can compare them. |
| **Compute** | The machine that runs the job. |
| **Compute cluster** | A machine that starts when work arrives and **switches off when idle**. |
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

### 5. Create a compute cluster — **read the `--min-instances 0` note**
```bash
az ml compute create ^
  --name cpu-cluster ^
  --type amlcompute ^
  --size Standard_DS3_v2 ^
  --min-instances 0 ^
  --max-instances 2 ^
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
> That is the cluster booting, not a hang. Worth it.

---

## Run 1: a command job (the simple one)

```bash
# copy the ignore file so we don't upload .venv
copy 07_azureml_jobs\.amlignore house-price\

cd house-price
az ml job create --file ../07_azureml_jobs/command-job.yml
```

Azure prints a chunk of JSON. The bit you want is `name` — a random-looking id
like `sincere_pin_abc123xyz`. That's the job's handle.

### Watch it run
```bash
az ml job stream --name sincere_pin_abc123xyz
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

```bash
cd house-price
az ml job create --file ../07_azureml_jobs/pipeline-job.yml
```

Open <https://ml.azure.com> → **Jobs** → **house-price-training** → your run.

You'll see this, drawn for you:

```
   ┌──────────────────────┐     ┌──────────────────┐     ┌──────────────────────┐
   │ 1. Create house data │ ──► │ 2. Train model   │ ──► │ 3. Evaluate model    │
   └──────────────────────┘     └──────────────────┘     └──────────────────────┘
```

### Where the arrows come from
**You never draw the picture.** You wrote this in the YAML:

```yaml
train_model:
  inputs:
    house_data: ${{parent.jobs.prepare_data.outputs.house_data}}
```

That says *"my input is step 1's output."* Azure reads it, works out that
`prepare_data` must finish first, and **generates the arrow**.

This is the same idea as Kedro: in `pipeline.py` you say a node's input is
another node's output, and Kedro figures out the order. Azure ML does exactly
the same thing, and then draws it.

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

```bash
pip install kedro-azureml        # version 1.0.0, needs Python 3.9-3.12

cd house-price
kedro azureml init ^
  --azure-subscription-id <sub-id> ^
  --resource-group my-ml-rg ^
  --workspace-name my-ml-workspace ^
  --experiment-name house-price-training ^
  --cluster-name cpu-cluster

kedro azureml run
```

The graph in the Studio then mirrors your Kedro pipeline **exactly** — including
`say_hi_at_start_node` and `say_hi_at_end_node`.

**So why write the YAML by hand at all?** Because when the plugin misbehaves —
and plugins do — you need to know what it was generating for you. The YAML is
the thing that actually runs; the plugin is a convenience on top.

---

## Common problems

| What you see | What it means |
|---|---|
| `az ml` not recognised | Extension missing: `az extension add --name ml` |
| Job sits in **Queued** for minutes | Normal. Cluster is starting from zero. |
| Job stuck **Queued** forever | `--max-instances` is 0, or your quota is exhausted. Check `az ml compute show --name cpu-cluster`. |
| Upload takes forever | `.amlignore` missing — you're uploading `.venv/`. |
| `AuthorizationFailed` | Wrong subscription: `az account set --subscription "..."` |
| Step fails with `ModuleNotFoundError` | The environment lacks a library. Add it to `requirements.txt` (the command does `pip install -r requirements.txt`). |
| Steps run but no graph appears | You submitted `command-job.yml`. Only `type: pipeline` draws a graph. |
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
