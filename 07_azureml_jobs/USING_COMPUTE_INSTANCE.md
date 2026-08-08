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
