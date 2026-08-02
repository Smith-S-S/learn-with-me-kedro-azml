# Part 2 — The Same Project, Now as a Kedro Pipeline

In Part 1 we had two loose scripts. Here we rebuild the **exact same** house-price
project as a proper **Kedro pipeline**. The math is identical; the *organisation*
is professional. This structure is what makes the later Azure/Docker/DevOps steps
possible.

## What is Kedro? (in one picture)

Think of a factory assembly line. Raw materials go in one end, a finished product
comes out the other, and each station does one job:

```
 params ─┐
         ▼
 [1] create_house_data ──► house_data.csv
                               │
                               ▼
 [2] split_data ──► X_train / X_test / y_train / y_test
                               │
                               ▼
 [3] train_model ──► regressor.pickle  (the trained model)
                               │
                               ▼
 [4] evaluate_model ──► metrics.json  (MAE + R²)
```

Kedro = the tool that builds and runs this assembly line for you. You just
describe the stations; Kedro works out the order and moves data between them.

## The 4 words you MUST know (from your documentation)

| Word | Simple meaning | Where it lives in our project |
|------|----------------|-------------------------------|
| **Node** | One worker function that does one job | `nodes.py` |
| **Pipeline** | The wiring that connects nodes in order | `pipeline.py` |
| **Catalog / io** | The "address book" saying where data is stored | `conf/base/catalog.yml` |
| **Parameters / config** | The settings dials (loaded by `OmegaConfigLoader`) | `conf/base/parameters.yml` |

Two more from your keywords, so you recognise them:
- **Runner** — the engine that actually executes the pipeline (`kedro run` uses
  the default `SequentialRunner`; there are parallel ones too).
- **Session / Context** — Kedro's "manager" that loads your config, catalog and
  pipelines and runs one job from start to finish. You rarely touch these
  directly; `kedro run` sets them up for you.
- **Hooks** — optional "extra instructions" that run at set moments (e.g. right
  before/after a node). We don't need them yet, but this is where things like
  "log every run to Azure" will plug in later.

## The folder map (only the files that matter)

```
house-price/
├─ conf/base/
│  ├─ catalog.yml         # WHERE data is stored (the address book)
│  └─ parameters.yml      # SETTINGS (n_houses, test_size, features, target...)
├─ src/house_price/
│  ├─ pipeline_registry.py    # finds & registers all pipelines automatically
│  └─ pipelines/house_price_pipeline/
│     ├─ nodes.py         # the 4 worker functions (the "what to do")
│     └─ pipeline.py      # wires the 4 nodes together (the "in what order")
└─ data/                  # outputs land here, sorted into numbered folders
   ├─ 01_raw/house_data.csv
   ├─ 06_models/regressor.pickle/<timestamp>/...
   └─ 08_reporting/metrics.json
```

> Those numbered `data/` folders (01_raw, 06_models, 08_reporting...) are a Kedro
> convention. They keep raw data, models, and reports from getting mixed up.

## How the pieces talk to each other

1. `pipeline.py` says: run `create_house_data` with inputs `params:n_houses` and
   `params:seed`, and call its output `house_data`.
2. Kedro looks up `house_data` in `catalog.yml` → "oh, that's a CSV at
   `data/01_raw/house_data.csv`" → saves it there.
3. The next node asks for `house_data` → Kedro loads that same CSV back. And so on.

You never write `read_csv` or `to_csv` yourself. **That decoupling is the whole
point** — later we swap the catalog to point at Azure cloud storage and *not a
single line of Python changes.*

## How to run it

```bash
cd house-price
kedro run                          # runs the whole pipeline
kedro run --node=train_model_node  # run just one station
kedro registry list                # see available pipelines
```

(If `kedro` isn't found on your PATH, use `python -m kedro run` — same thing.)

## What changed vs Part 1?

| Part 1 (loose scripts) | Part 2 (Kedro) |
|------------------------|----------------|
| `read_csv` / `to_csv` scattered in code | declared once in `catalog.yml` |
| settings hard-coded in Python | tidy in `parameters.yml` |
| you run scripts in the right order by hand | Kedro works out the order |
| hard to move to the cloud | change the catalog → runs on Azure |

---
---
##### Later Use for Hook Development
---
---

## How to add Hook
#### Kedro: Running Logic at the Start and End of a Pipeline

### Option 1: Kedro Hooks ⭐ (Recommended)

Kedro provides a built-in **Hooks** lifecycle that lets you execute code before and after a pipeline run. This is the recommended approach for logging or performing setup/cleanup tasks.

#### Create a Hooks Class

**File:** `src/house_price/hooks.py`

```python
import logging
from kedro.framework.hooks import hook_impl


class PipelineLoggingHooks:
    @hook_impl
    def before_pipeline_run(self):
        logging.getLogger(__name__).info(
            "===============> pipeline is starting <====================="
        )

    @hook_impl
    def after_pipeline_run(self):
        logging.getLogger(__name__).info(
            "===============> pipeline is ended <====================="
        )
```

#### Register the Hook

**File:** `src/house_price/settings.py`

```python
from house_price.hooks import PipelineLoggingHooks

HOOKS = (PipelineLoggingHooks(),)
```

#### Benefits

- No extra nodes required.
- No need to pass data between nodes.
- Runs automatically for every pipeline execution.
- Keeps pipeline logic separate from operational logging.

> **Recommended:** This completely replaces `say_hi_at_start_node` and `say_hi_at_end_node`.

---

## Option 2: Pipeline Tags

Kedro supports **tags** on nodes.

Example use cases:

- Run only data preparation nodes.
- Run only training nodes.
- Skip specific groups of nodes.

Example:

```bash
kedro run --tags=train
```

### Limitations

- Tags **do not control execution order**.
- They are intended for selecting subsets of nodes, not for running code before or after a pipeline.

> **Not recommended** for start/end logging.

---

## Option 3: Separate Pipelines

You can organize your workflow into multiple pipelines and combine them in `pipeline_registry.py`.

Example:

```python
def register_pipelines():
    start_pipeline = create_start_pipeline()
    main_pipeline = create_main_pipeline()
    end_pipeline = create_end_pipeline()

    return {
        "__default__": start_pipeline + main_pipeline + end_pipeline
    }
```

### Notes

- `start_pipeline` can contain startup tasks.
- `main_pipeline` contains the core data processing and model training.
- `end_pipeline` contains cleanup or final reporting tasks.

### Limitation

Kedro executes nodes based on **data dependencies**, not simply by the order in which pipelines are added. If these pipelines are independent and do not share datasets, this approach may not guarantee strict start → main → end execution.

---

# Recommendation

| Option | Use Case | Recommended |
|---------|----------|-------------|
| **Hooks** | Logging, setup, cleanup before/after pipeline execution | ⭐⭐⭐⭐⭐ |
| **Pipeline Tags** | Running subsets of nodes | ⭐⭐ |
| **Separate Pipelines** | Organizing large projects into logical pipelines | ⭐⭐⭐ |

For logging messages such as **"Pipeline started"** and **"Pipeline ended"**, **Kedro Hooks** are the cleanest and most idiomatic solution.

---

# The API layer — `src/house_price/main.py`

Until now, the only way to use this pipeline was to sit at this computer and type
`python -m kedro run`. That is fine for you, but useless for anyone else. A
website, a mobile app, or another team cannot type commands on your laptop.

`main.py` adds a **FastAPI** app so any program can use the model over the web —
including **triggering a retrain with an API call**.

## The four doors

| Endpoint | Type | What it does | Protect it? |
|---|---|---|---|
| `/health` | GET | "Are you alive?" | **No token** — Kubernetes and APIM must reach it |
| `/predict` | POST | One house in, one price out | Valid token |
| `/metrics` | GET | The last training MAE and R² | Valid token |
| `/pipeline/run` | POST | **Retrains the model** | **Admins only** |

## Run it

```bash
cd house-price
.venv\Scripts\activate
uvicorn house_price.main:app --app-dir src --reload
```

Open <http://127.0.0.1:8000/docs> for the auto-generated test page.

```bash
curl -X POST http://127.0.0.1:8000/predict ^
     -H "Content-Type: application/json" ^
     -d "{\"size_sqft\":2000,\"num_bedrooms\":3,\"age_years\":10}"
# {"predicted_price":465276.13,"currency":"USD"}

curl -X POST http://127.0.0.1:8000/pipeline/run
# {"status":"accepted","detail":"Pipeline retraining started."}
```

## Three design decisions worth understanding

### 1. It loads the model *through the Kedro catalog*
`main.py` never opens a pickle file by hand with a hard-coded path. It asks
Kedro: *"give me the regressor."*

```python
with KedroSession.create(project_path=PROJECT_ROOT) as session:
    context = session.load_context()
    return context.catalog.load("regressor")
```

**Why this matters:** our catalog entry is `versioned: true`, so Kedro keeps a
timestamped copy of every model ever trained — and `.load()` returns the newest
one automatically. And when the model later moves to Azure Blob Storage,
**`main.py` does not change at all.** Only `catalog.yml` does. That is the whole
payoff of the catalog, finally cashing out.

### 2. Retraining runs in the background, and returns `202`
Training takes time. If we trained *inside* the request, the caller would sit
waiting and eventually time out. So we accept the job and answer immediately:

```python
background_tasks.add_task(_run_pipeline)
return {"status": "accepted"}
```

`202 Accepted` means **"I have started, but I am not finished."**
Returning `200 OK` would be a lie — it promises the work is already done.

> **Kedro gotcha:** a `KedroSession` is **single-use** — one `.run()` per
> session. So `_run_pipeline()` opens a brand new session on every call. This is
> by design, not a workaround.

### 3. A missing model does not crash the server
On startup we *try* to load the model. If there isn't one yet, we log a warning
and keep running, and `/predict` returns **503 Service Unavailable**.

**Why:** a fresh deployment legitimately has no model yet. Crashing on boot
would put the container in a restart loop. `503` correctly means "I'm alive but
not ready" — as opposed to `500`, which means "I broke."

## Verified output

```
GET  /health          -> {"status":"ok","model_loaded":true}
POST /predict         -> {"predicted_price":465276.13,"currency":"USD"}
GET  /metrics         -> {"mae":11494.25,"r2":0.9929}
POST /pipeline/run    -> {"status":"accepted",...}   (new model version written)
```
---
# The WHY -> *Model Loading* <- Without Lifespan vs With Lifespan

## Without Lifespan

```python
model = joblib.load("model.joblib")

app = FastAPI()
```

### Flow

```
Start server
    |
    Load model
    |
    Error happens ❌
    |
    Server crashes
```

### Example

```
model.joblib is missing
```

Result:

```
FileNotFoundError

API never starts
```

---

# With Lifespan

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    try:
        model = load_model()
    except Exception:
        model = None

    yield
```

### Flow

```
Start server
    |
    Try loading model
    |
    Error happens
    |
    Catch error
    |
    Server still starts ✅
```

### Example

```
model.joblib is missing
```

Result:

```
Warning: model not found
```

API starts:

```
GET /health  -> OK

/predict -> "Model not available"
```

---

# Simple Difference

| | Without Lifespan | With Lifespan |
|---|---|---|
| Model loading error | Application crashes | Error can be handled |
| Server startup control | No | Yes |
| Shutdown handling | No | Yes |
| Production usage | Less flexible | Recommended |
---

# Next up (Part 3)
We create an **Azure account** and learn the **Azure CLI** hands-on, so we have
somewhere to send this pipeline. Later we'll use the `kedro-azureml` plugin to
run this very pipeline on Azure Machine Learning.

Then in **Part 6** we put **Azure APIM** in front of this FastAPI app, so only
callers holding a valid **ADFS / Entra ID** token can reach it.
