# Part 7.1 — One Project, Two Places: `kedro run` locally, `kedro azureml run` on Azure

The goal of this part is a project where **both** of these work, with no flags,
no `export`, and no editing files in between:

```bash
kedro run           # runs on your laptop, plain files on disk, no Azure, no cost
kedro azureml run   # runs on Azure ML, reads/writes Azure Blob Storage
```

Getting there meant fixing **three** separate bugs. They stacked on top of each
other, so each fix revealed the next one — which is why the error message kept
changing. That is normal, and worth getting used to.

---

## The three errors, in the order they appeared

### Error 1 — `Must provide either a connection_string or account_name`

```
DatasetError:
unable to connect to account for Must provide either a connection_string or
account_name with credentials!!.
Failed to instantiate dataset 'house_data' of type
'kedro_datasets.pandas.csv_dataset.CSVDataset'.
```

**Reason.** The storage key lived only on the laptop. The job ran on Azure.

`conf/base/credentials.yml` contained `azure_blob: {}` — an empty dict. The real
credentials were in `conf/local/credentials.yml`, which `.amlignore` deliberately
blocks from upload. So the container found the name `azure_blob` but nothing
inside it.

Running `AZURE_STORAGE_ACCOUNT_KEY="..." kedro azureml run` does **not** help.
That sets the variable on *your* shell. kedro-azureml reads it
(`cli_functions.py:32`) but only forwards it inside its own private
`KEDRO_AZURE_RUNNER_CONFIG` blob for temp-storage — it never re-exports it as a
plain `AZURE_STORAGE_ACCOUNT_KEY` that your catalog can read.

---

### Error 2 — `Unable to find credentials 'azure_blob'`

```
KeyError: "Unable to find credentials 'azure_blob': check your data catalog and
credentials configuration."
```

**Reason.** `.amlignore` had a bare line:

```gitignore
credentials.yml
```

Ignore patterns **without a slash are unanchored** — they match at *every* depth.
So that one line blocked `conf/base/credentials.yml` too: the one file the remote
job actually needs. The container had no credentials file at all, so the name
`azure_blob` did not exist anywhere.

Note how the message got *worse* as things got *better*: error 1 meant "found the
key, it was empty", error 2 meant "the file is gone entirely". Progress.

> **How to check this yourself** — do not guess which pattern matched:
>
> ```python
> from azure.ai.ml._utils._asset_utils import get_ignore_file
> import os
> ig = get_ignore_file(os.getcwd())
> print(ig.is_file_excluded(os.path.join(os.getcwd(), "conf/base/credentials.yml")))
> # True = Azure will never see this file
> ```

---

### Error 3 — `ContainerNotFound`

This one was **hiding behind the other two**. It could not appear until
authentication actually started working.

```
DatasetError: house_data: Failed while saving data to dataset
CSVDataset(filepath=PurePosixPath('mlwhousestoraged045abdff.dfs.core.windows.net/data/01_raw/house_data.csv'),
protocol='abfs', ...).
ErrorCode:ContainerNotFound
```

Look closely at that resolved `filepath`. The container name `kedro-temp` is
**missing**, and the *hostname* has taken its place.

**Reason.** The catalog used the URL form from the Azure docs:

```yaml
filepath: abfs://kedro-temp@mlwhousestoraged045abdff.dfs.core.windows.net/data/01_raw/house_data.csv
```

Kedro parses filepaths with fsspec's `infer_storage_options` and then keeps only
**host + path** (`kedro/io/core.py`, `_parse_filepath`). The `kedro-temp@` part is
silently discarded. adlfs then reads the leftover hostname as the container name,
looks for a container literally called `mlwhousestoraged045abdff.dfs.core.windows.net`,
and does not find one.

Proof, run locally:

```python
from kedro.io.core import _parse_filepath

_parse_filepath("abfs://kedro-temp@mlwhousestoraged045abdff.dfs.core.windows.net/data/x.csv")
# {'protocol': 'abfs', 'path': 'mlwhousestoraged045abdff.dfs.core.windows.net/data/x.csv'}  <-- container gone

_parse_filepath("abfs://kedro-temp/data/x.csv")
# {'protocol': 'abfs', 'path': 'kedro-temp/data/x.csv'}                                     <-- correct
```

**Rule: with Kedro, always write `abfs://<container>/<path>`.** The account name
comes from `credentials:`, never from the filepath.

---

## The changes

Six files. Everything below is the final, working state.

### 1. `.amlignore` — stop blocking the file Azure needs

```diff
 .env
 *.pem
 *.key
-credentials.yml
+# NOTE: no global `credentials.yml` rule here. That pattern is unanchored, so it
+# also blocked conf/base/credentials.yml -- which the remote job NEEDS, and which
+# holds no secret (only a ${oc.env:...} reference). The real secrets are the
+# conf/local/ files above, and they stay blocked.
```

The rules that matter are kept and are **anchored** to `conf/local/`:

```gitignore
# SECRETS & LOCAL OVERRIDES -- keep conf/local/ dir so Kedro can find it, but block specific files
conf/local/credentials*
conf/local/*.key
conf/local/*.pem
conf/local/catalog.yml

.env
```

### 2. `conf/base/credentials.yml` — uploaded, but holds no secret

```yaml
# conf/base/ ships to Azure; conf/local/ is blocked by .amlignore. So this file
# is the only place the remote job can learn about the storage account.
#
# The KEY ITSELF is never written here -- only a reference to an environment
# variable, which Kedro resolves at runtime.
azure_blob:
  account_name: mlwhousestoraged045abdff
  account_key: ${oc.env:AZURE_STORAGE_ACCOUNT_KEY}
```

This file is safe to upload precisely because `${oc.env:...}` is a *reference*.
The secret itself never leaves your machine.

### 3. `conf/base/catalog.yml` — container-first abfs paths

```yaml
house_data:
  type: pandas.CSVDataset
  filepath: abfs://kedro-temp/data/01_raw/house_data.csv
  credentials: azure_blob

regressor:
  type: pickle.PickleDataset
  filepath: abfs://kedro-temp/data/06_models/regressor.pickle
  versioned: true
  credentials: azure_blob

metrics:
  type: json.JSONDataset
  filepath: abfs://kedro-temp/data/08_reporting/metrics.json
  credentials: azure_blob
```

### 4. `conf/local/catalog.yml` — the local override

This is what makes `kedro run` work with no Azure at all. It **fully replaces**
the matching entries in `conf/base` (Kedro's catalog merge is destructive at the
top-level key, not a deep merge):

```yaml
house_data:
  type: pandas.CSVDataset
  filepath: data/01_raw/house_data.csv
  credentials: null

regressor:
  type: pickle.PickleDataset
  filepath: data/06_models/regressor.pickle
  versioned: true
  credentials: null

metrics:
  type: json.JSONDataset
  filepath: data/08_reporting/metrics.json
  credentials: null
```

`.amlignore` blocks this file, so Azure never sees it and falls back to the abfs
paths in `conf/base`. **One project, two behaviours.**

### 5. `requirements.txt`

```diff
 kedro-datasets
+python-dotenv    # settings.py reads .env so `kedro azureml run` needs no exports
```

---

## 6. `src/house_price/settings.py` — the piece that makes it automatic

This is the interesting one, so it gets its own section.

### What was added

```python
# =============================================================================
# CREDENTIALS PLUMBING -- so a bare `kedro azureml run` just works
# -----------------------------------------------------------------------------
# Kedro imports this module during bootstrap, BOTH on your laptop (before the
# plugin submits the job) and inside the Azure container (before the catalog is
# built). That makes it the one place that can serve both sides.
#
# LOCALLY: read .env, so you never have to `export` anything by hand.
# ON AZURE: .env is deliberately not uploaded (.amlignore) -- but kedro-azureml
#   already ships the key inside its own KEDRO_AZURE_RUNNER_CONFIG blob, so we
#   just unpack it back into AZURE_STORAGE_ACCOUNT_KEY. That is the variable
#   conf/base/credentials.yml interpolates with ${oc.env:...}.
# =============================================================================
import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parents[2] / ".env")
except ImportError:
    # Only needed on your laptop. The Azure container has no .env to read (it is
    # blocked in .amlignore), so python-dotenv is deliberately NOT a dependency
    # of the Azure ML environment -- don't fail the job over a missing import.
    pass

if not os.getenv("AZURE_STORAGE_ACCOUNT_KEY"):
    _runner_config = os.getenv("KEDRO_AZURE_RUNNER_CONFIG")
    if _runner_config:
        _key = json.loads(_runner_config).get("storage_account_key")
        if _key:
            os.environ["AZURE_STORAGE_ACCOUNT_KEY"] = _key
```

### Why `settings.py` and not somewhere else

Kedro imports `settings.py` during **bootstrap** — before the config loader
builds the catalog, and before the plugin submits anything. And critically, that
happens on *both* machines. It is the only file that runs early enough in both
places, which is why the same twelve lines can serve the laptop and the container.

### The trick, in one sentence

kedro-azureml *already* puts your storage key inside every step, as JSON in an
env var called `KEDRO_AZURE_RUNNER_CONFIG` (see `kedro_azureml/generator.py:237`).
It just never exposes it under the name your catalog is looking for. So we unpack
it ourselves.

```
YOUR LAPTOP                                    AZURE CONTAINER
-----------                                    ---------------
.env                                           (no .env -- blocked by .amlignore)
  |                                                  |
  | load_dotenv()                                    | KEDRO_AZURE_RUNNER_CONFIG
  v                                                  | {"storage_account_key": "..."}
AZURE_STORAGE_ACCOUNT_KEY                            v
  |                                            json.loads() -> AZURE_STORAGE_ACCOUNT_KEY
  |                                                  |
  +--------------------+   +------------------------+
                       v   v
        conf/base/credentials.yml
        account_key: ${oc.env:AZURE_STORAGE_ACCOUNT_KEY}
```

Note the order: the `.env` value wins if present, so on your laptop your own key
is always used. The unpack only fires when the variable is absent — which is
exactly the container's situation.

### Why the `try/except ImportError`

`python-dotenv` is **not** in `07_azureml_jobs/conda.yml`, so it is not installed
in the Azure ML environment. Without the guard, `settings.py` would raise
`ModuleNotFoundError` at bootstrap and **every node would fail** — a much worse
error than the one we set out to fix. The container has no `.env` to read anyway,
so skipping the import there is correct, not a workaround.

### The pre-existing patch below it

Untouched, but worth knowing it is there — it lets the plugin target a
**compute instance** instead of a cluster:

```python
try:
    from azure.ai.ml.entities import ComputeInstance

    if not hasattr(ComputeInstance, "min_instances"):
        ComputeInstance.min_instances = property(lambda self: 1)
        ComputeInstance.max_instances = property(lambda self: 1)
except ImportError:
    pass
```

kedro-azureml reads `.min_instances` / `.max_instances` off the compute, but only
to print a log line. A `ComputeInstance` has neither, so the run dies with
`AttributeError`. A compute instance is exactly one node, so reporting 1 and 1 is
honest.

---

## Running it

### Locally — `kedro run`

```bash
cd house-price
kedro run
```

**What you need:** nothing beyond `pip install -r requirements.txt`. No Azure
login, no key, no network. `conf/local/catalog.yml` sends everything to `data/`.

Verified output:

```
INFO     Mean Absolute Error: $11,494
INFO     R^2 score: 0.993 (closer to 1.0 is better)
INFO     Completed 6 out of 6 tasks
INFO     Pipeline execution completed successfully in 0.5 sec.
```

Files produced on disk:

```
data/01_raw/house_data.csv
data/06_models/regressor.pickle/2026-08-14T12.38.25.794Z/regressor.pickle
data/08_reporting/metrics.json
```

### On Azure — `kedro azureml run`

```bash
cd house-price
kedro azureml run
```

**What you need:**

| Requirement | Where it comes from |
|---|---|
| `.env` with `AZURE_STORAGE_ACCOUNT_KEY=...` | your machine only, never uploaded |
| Azure login | `az login` — the SDK uses `DefaultAzureCredential` |
| The `kedro-house-price` environment | `az ml environment create --file 07_azureml_jobs/environment.yml ...` |
| The `kedro-temp` container | must already exist in the storage account |
| Compute `ci-house-price` | must be **running** — a stopped instance just queues |

> **Side effect of restoring `conf/local/catalog.yml`:** the plugin used to stop
> and ask *"Configuration folder ... contains only empty files. Continue?"*. That
> prompt was correct — `conf/local/` really did contain nothing but empty files.
> Now that the override has real content, the prompt is gone and the run is
> non-interactive again.

Verified run [`nifty_net_lwm97jw074`](https://ml.azure.com/runs/nifty_net_lwm97jw074):

```
Completed    say_hi_at_start_node
Completed    create_house_data_node
Completed    split_data_node
Completed    train_model_node
Completed    evaluate_model_node
Completed    say_hi_at_end_node

Pipeline finished successfully
```

Written to blob storage — identical numbers to the local run, because the seed is
fixed in `parameters.yml`:

```
kedro-temp/data/01_raw/house_data.csv                                        3751 bytes
kedro-temp/data/06_models/regressor.pickle/2026-08-14T11.35.01.109Z/...       644 bytes
kedro-temp/data/08_reporting/metrics.json  -> {"mae": 11494.25, "r2": 0.9929}
```

---

## Local vs Azure at a glance

| | `kedro run` | `kedro azureml run` |
|---|---|---|
| Kedro env used | `local` (overrides `base`) | `base` only — `conf/local` is not uploaded |
| Catalog in effect | `conf/local/catalog.yml` | `conf/base/catalog.yml` |
| Data location | `data/` on disk | `abfs://kedro-temp/data/` |
| Credentials needed | none | `azure_blob` from `conf/base/credentials.yml` |
| Key source | `.env` via `load_dotenv` | `KEDRO_AZURE_RUNNER_CONFIG` unpack |
| Where compute runs | your laptop | `ci-house-price` compute instance |
| Cost | zero | compute + storage |
| Speed | ~0.5 s | ~9 min (container start dominates) |

The mental model: **`conf/base` is the truth the cloud sees; `conf/local` is your
laptop's private override.** `.amlignore` is what enforces the split.

---

## Debugging checklist for next time

When an Azure job fails, work in this order:

1. **Get the real log**, not the truncated CLI traceback:
   ```python
   from azure.ai.ml import MLClient
   from azure.identity import DefaultAzureCredential
   ml = MLClient(DefaultAzureCredential(), SUB_ID, "rg-azureml-demo", "mlw-house-price")
   # which node failed?
   for c in ml.jobs.list(parent_job_name="<pipeline_run_id>"):
       print(c.status, c.display_name, c.name)
   ml.jobs.download("<failed_child_name>", download_path="joblogs", all=True)
   # then read joblogs/artifacts/user_logs/std_log.txt
   ```
2. **Did the file even upload?** Use the `get_ignore_file` snippet above. An
   unanchored `.amlignore` pattern is invisible until you test it.
3. **Read the resolved `filepath` in the error**, not the one in your YAML. Error 3
   was solvable purely by noticing the container name had vanished.
4. **Reproduce config resolution locally** before spending 9 minutes on a job:
   ```python
   from kedro.config import OmegaConfigLoader
   cl = OmegaConfigLoader(conf_source="conf", base_env="base", default_run_env="local")
   print(cl["credentials"])
   print(cl["catalog"])
   ```

---

## Two things still worth doing

- **Rotate the storage key.** It was pasted into a chat during debugging. Portal →
  Storage account → *Security + networking* → *Access keys* → *Rotate key1*, then
  update `.env`. Nothing else in the repo hardcodes it, so this costs one line.
- **Outgrow the account key.** `--env-var` and this whole plumbing exist because
  we are passing a shared secret around. The grown-up version: give
  `ci-house-price` a managed identity, grant it **Storage Blob Data Contributor**
  on the storage account, and drop `account_key` from `credentials.yml` entirely.
  `DefaultAzureCredential` then handles auth and there is no secret anywhere —
  no `.env`, no unpacking, no rotation.
