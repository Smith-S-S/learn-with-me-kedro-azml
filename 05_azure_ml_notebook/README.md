# Part 5 — Azure ML + Notebooks (Beginner's Guide)

> Goal: move the **house-price Kedro project** off your laptop and into Azure,
> and run it from a **browser notebook** in the cloud.
> This is much simpler and much cheaper than the AKS cluster in Part 4.

---

## A) What is Azure Machine Learning (Azure ML)?

Azure ML is Azure's **workspace for data science**. Instead of "one laptop with
Python on it", you get one place in the cloud that holds:

| Thing | What it is |
|---|---|
| **Compute** | Cloud machines to run your code (can be turned off when idle) |
| **Notebooks** | JupyterLab / VS Code in your browser, already on that machine |
| **Datastores** | Pointers to cloud storage where your data lives |
| **Jobs** | Records of every training run you did — code, params, results |
| **Models** | A registry of trained models, versioned |
| **Endpoints** | A URL that serves your model's predictions |

For this part we only use the first two. The rest arrive naturally later.

**Why bother, when the laptop works?**
- Your teammate opens the same workspace and sees the same environment.
- You can rent a 64-GB machine for 20 minutes, then switch it off.
- Every run is recorded — no more "which version gave R² 0.993?".
- Your laptop can be closed; the cloud machine keeps running.

---

## B) The 4 words for this part

| Word | Simple meaning | Costs money? |
|---|---|---|
| **Workspace** | The top-level container for all your ML stuff | No (the workspace itself is free) |
| **Compute Instance** | *Your personal* cloud VM, with Jupyter installed | **Yes — per hour while running** |
| **Compute Cluster** | A pool of VMs that auto-scales to 0 when idle | Yes, but $0 when idle |
| **Job** | A run of your code, submitted and recorded by Azure ML | Yes, while it runs |

> **Compute Instance vs Compute Cluster:** an *instance* is a machine you sit at
> and type on (a cloud laptop) — it keeps billing until you **stop** it. A
> *cluster* is a machine you *send work to*; it starts up, runs, and shrinks back
> to zero nodes automatically. Use the **instance** for learning (this part),
> the **cluster** for real training jobs later.

⚠️ **The #1 beginner bill shock in Azure ML is a Compute Instance left running
overnight.** Stopping it costs you nothing and loses nothing — the disk is kept.
There is an auto-shutdown setting; turn it on. We do that below.

---

## C) Create the workspace

### Option 1 — Portal (visual, good the first time)
1. https://portal.azure.com → search **"Azure Machine Learning"** → **Create**.
2. **Resource group**: create a new one, `rg-azureml-demo` (one folder per
   experiment — same habit as Part 3/4).
3. **Workspace name**: `mlw-house-price`.
4. **Region**: `Central India` (or whatever is near you).
5. Leave storage/key-vault/app-insights on their defaults — Azure creates those
   supporting resources for you automatically.
6. **Review + create** → **Create**. Takes ~2 minutes.

### Option 2 — CLI (repeatable, what you'll actually use later)
```bash
# The ML commands aren't in the base CLI; add them once.
az extension add --name ml
az extension update --name ml       # if you added it a while ago

az group create --name rg-azureml-demo --location centralindia

az ml workspace create \
  --name mlw-house-price \
  --resource-group rg-azureml-demo

# Save the defaults so you can stop repeating -g and -w on every command
az configure --defaults group=rg-azureml-demo workspace=mlw-house-price

az ml workspace show -o table
```

Then open **https://ml.azure.com** — that's the Azure ML Studio, a separate site
from the main portal. Pick your workspace.

---

## D) Create a Compute Instance

### Portal way
In ml.azure.com → **Compute** → **Compute instances** → **+ New**:
- **Name**: `ci-house-price` (must be globally unique-ish; add your initials)
- **Virtual machine size**: `Standard_DS11_v2` (2 cores / 14 GB) — plenty here.
  Cheaper still: `Standard_E2s_v3` or any 2-core option.
- **Schedule / idle shutdown**: turn on **"Stop after 30 minutes of inactivity"**.
  Do this. It is the setting that saves you money.

### CLI way
```bash
az ml compute create \
  --name ci-house-price \
  --type computeinstance \
  --size Standard_DS11_v2 \
  --idle-time-before-shutdown-minutes 30
```

Useful lifecycle commands:
```bash
az ml compute list -o table
az ml compute stop  --name ci-house-price     # ← billing stops, disk kept
az ml compute start --name ci-house-price
az ml compute delete --name ci-house-price --yes

# You can use this too

az ml compute show -n ci-house-price -g rg-azureml-demo -w mlw-house-price
```

Wait for **Status: Running** (3–5 minutes).

---

## E) Get the Kedro project onto it

The compute instance is a real Linux machine. In ml.azure.com → **Notebooks**,
click the **Terminal** icon (or **Compute → Applications → Terminal**). You now
have a shell on a cloud VM.

**Route 1 — git clone (the right way, once the project is in a repo)**
👉 **Full walkthrough in [`GITHUB_SETUP.md`](GITHUB_SETUP.md)** — authentication
(SSH key or PAT), where to clone, and how to push your changes back to the
parent repo. Do that first if your project is already in a repo, then come back
here for section F.

> **Why it's a separate file:** git authentication has nothing to do with Azure
> ML — it's the same on any Linux machine. Keeping it out means this guide stays
> about Azure ML, and you can hand `GITHUB_SETUP.md` to someone on its own.

**Route 2 — upload (fine for right now, no repo yet)**
In the **Notebooks** tab, use the **Upload folder** button and upload
`house-price`. Skip `.venv` and `data/` — the venv is Windows-specific and won't
work on Linux, and the data regenerates itself.

> **What is `~/cloudfiles/code/`?** It's a shared file share mounted into every
> compute instance in the workspace. Files there survive stopping/deleting the
> instance and are visible to your teammates. Anything you save *outside*
> `cloudfiles` lives only on that VM's local disk and is lost if it's deleted.

---

## F) Run the pipeline in the cloud

In the terminal on the compute instance:

```bash
cd ~/cloudfiles/code/Users/$USER/house-price

# Azure ML ships several conda environments. This one has Python 3.10+ and
# the usual data-science stack already installed.
conda activate azureml_py310_sdkv2

pip install -r requirements.txt      # kedro, kedro-datasets, pandas, sklearn...

python -m kedro run
```

You should see the same 4 nodes run as on your laptop —
`create_house_data → split_data → train_model → evaluate_model` — and **R² ≈ 0.993**.

Check the outputs the catalog declared:
```bash
cat data/08_reporting/metrics.json
ls -R data/06_models/          # versioned model folders (timestamped)
```

> Note `python -m kedro` rather than plain `kedro` — same trick as on Windows,
> and it works everywhere, so just keep the habit.

### Seeing the pipeline graph here (Kedro Viz on a compute instance)

You can draw the pipeline on the compute instance too — but reaching it needs one
Azure-specific step that catches everyone.

```bash
python -m kedro viz run --host 0.0.0.0 --port 4141 --no-browser
```

`--host 0.0.0.0` is required. The default (`127.0.0.1`) means *"only this
machine"*, so nothing outside the VM could ever connect.

But `0.0.0.0` is **not an address you visit.** You reach the compute instance
through Azure's proxy URL, where **the port is part of the hostname**:

```
https://<compute-instance-name>-<port>.<region>.instances.azureml.ms/
```

For our `ci-house-price` instance in `centralindia` on port 4141:

```
https://ci-house-price-4141.centralindia.instances.azureml.ms/
```

Note it's **https**, and there's **no `:4141` at the end** — the port lives in
the name. Typing `http://<instance>:4141` will never work, and that is the usual
reason "Kedro Viz won't load on Azure."

⏳ Also: wait for **`Kedro Viz started successfully`** before opening the URL.
`Starting Kedro Viz ...` appears instantly but the server needs another 10–30
seconds.

> Full Kedro Viz guide — flags, `--autoreload`, and troubleshooting — is in
> [`house-price/TUTORIAL.md`](../house-price/TUTORIAL.md).

---

## G) Using an actual Notebook with Kedro

Notebooks are great for *exploring* the data your pipeline produced. Kedro has a
built-in extension so a notebook can reach into your project.

In **Notebooks** → **+ → Create new file** → `explore.ipynb`.
Top-right, set **Compute** = `ci-house-price` and **Kernel** =
`Python 3.10 - SDK v2`.

Cell 1:
```python
%cd ~/cloudfiles/code/Users/<your-user>/house-price
%load_ext kedro.ipython
```

That single line gives you four variables for free:

| Variable | What it holds |
|---|---|
| `catalog` | The data catalog — load any dataset by name |
| `context` | Project config, including `parameters` |
| `session` | Lets you run pipelines from the notebook |
| `pipelines` | All registered pipelines |

Cell 2 — look at the data and the model your pipeline produced:
```python
df = catalog.load("house_data")
df.head()
```

```python
metrics = catalog.load("metrics")
print(metrics)

model = catalog.load("regressor")      # loads the LATEST version automatically
print("coefficients:", model.coef_, "intercept:", model.intercept_)
```

Cell 3 — run the pipeline from inside the notebook:
```python
session.run()                          # or session.run(pipeline_name="__default__")
```

> **Rule of thumb:** notebooks for *looking*, Kedro nodes for *doing*. If a
> notebook cell becomes something you want to run every time, move it into
> `src/house_price/pipelines/.../nodes.py` and add it to the pipeline. That
> discipline is the whole reason we used Kedro instead of one giant notebook.

---

## H) Where this is heading (so the picture connects)

You've now run the pipeline three ways: laptop, Kubernetes-shaped (Part 4), and
Azure ML compute — and your code moves between laptop and cloud through git. The
remaining parts wire it all together:

| Part | What it adds |
|---|---|
| 6 — FastAPI + APIM | A guarded web address so other programs can use the model |
| 7 — Azure ML Jobs | Submit runs to a *compute cluster* and see the pipeline graph |
| 8 — Docker | Seal the project into an image (fixes "works on my machine" for real) |
| 9 — Azure Artifacts | A private, scanned home for your Python packages |
| 10 — Entra ID | Who is allowed to do what (identity & permissions) |
| 11 — Azure DevOps CI | Build + scan + deploy automatically on every push |

**Part 7 is the direct sequel to this one.** A compute instance is a machine you
sit at and type on; a **job** is work you *submit*, which runs on a cluster that
scales to zero and records everything — including, thanks to
[`GITHUB_SETUP.md`](GITHUB_SETUP.md), the exact git commit that ran.

---

## I) 🧹 Cleanup

```bash
# Cheapest option: just stop the compute instance, keep everything else
az ml compute stop --name ci-house-price

# Full teardown: deletes workspace, storage, key vault, compute — everything
az group delete --name rg-azureml-demo --yes --no-wait
az group list -o table          # confirm it's gone
```

> A stopped compute instance costs ~nothing (you still pay a few cents for its
> disk). A running one bills every hour. **Stop it when you close the laptop.**

---

## J) Cost & sanity cheat sheet

| Item | Charge |
|---|---|
| Workspace | Free (its storage account costs pennies) |
| Compute instance — running | Per hour, ~₹8–20/hr for a small size |
| Compute instance — stopped | Disk only, negligible |
| Compute cluster — idle at 0 nodes | Free |
| Notebooks / Studio UI | Free |

```bash
az ml compute list -o table        # ← run this before you walk away
```

---

## Next up (Part 6)
**FastAPI + Azure APIM** — we put a web address on the model so other programs
can use it, then a security guard (APIM, checking **ADFS / Entra ID** tokens) in
front of that address.

Then **Part 7 — Azure ML Jobs** picks this part straight back up: instead of
typing `kedro run` in a terminal, you *submit* the pipeline as a recorded job and
watch it draw itself as a clickable graph.

---
