# Part 1 — Your First Machine Learning Project

This is the smallest possible "real" ML project. We predict **house prices**.

## The big idea in one sentence
We give a computer lots of example houses (with their prices), and it learns
the pattern so it can guess the price of a house it has never seen.

## The two steps

### Step 1: `generate_data.py` — make a dummy dataset
We invent 200 fake houses. For each house we know:
- `size_sqft`   — how big it is
- `num_bedrooms`— how many bedrooms
- `age_years`   — how old it is

We then calculate a `price` using a **hidden rule** we made up:

```
price = 50,000 + 200*size + 10,000*bedrooms - 1,500*age + a little randomness
```

We save this to `house_data.csv`.

> Why fake data? Because we KNOW the hidden rule, we can later check if the
> model was smart enough to rediscover it. Great for learning.

### Step 2: `train_model.py` — teach the model
1. **Load** the CSV.
2. **Split** the data: 80% to learn from ("training"), 20% kept secret for a
   fair test ("testing"). This stops the model from just memorising answers.
3. **Train** a `LinearRegression` model — it draws the best straight-line
   relationship between the inputs and the price.
4. **Evaluate** on the 20% it never saw:
   - **MAE** (Mean Absolute Error): on average, how many dollars we're off by.
   - **R²** (R-squared): 1.0 = perfect, 0.0 = useless. We got ~0.99 = excellent.
5. **Save** the trained model to `house_price_model.joblib` so it can be reused
   without retraining.

## How to run it
```bash
python generate_data.py    # creates house_data.csv
python train_model.py      # trains, evaluates, and saves the model
```

## What we learned (the payoff)
Our hidden rule vs. what the model discovered on its own:

| Thing            | Hidden rule | Model learned |
|------------------|-------------|---------------|
| per square foot  | 200         | ~200          |
| per bedroom      | 10,000      | ~10,900       |
| per year of age  | -1,500      | ~-1,489       |
| base price       | 50,000      | ~47,040       |

Close matches = the model genuinely learned the pattern. 🎉

---

# Step 3 (new): Watching for DRIFT with Evidently

## The problem nobody warns beginners about
You trained a model. It scored R² = 0.99. You are proud. You ship it.

**A year later it is quietly wrong — and nothing has crashed.**

Why? Because the model only knows the world it was shown. If the houses people
buy today are bigger, newer and more expensive than the houses in your training
CSV, the model is answering a question it was never taught. There is no error
message. Predictions just get worse and worse.

That silent change in the incoming data is called **drift**.
**Evidently** is a free Python library that detects it and draws you a report.

## The two words you need

| Word | Plain meaning |
|------|---------------|
| **Reference data** | The OLD data. Your baseline — usually the training data. |
| **Current data** | The NEW data arriving today, that you want to judge. |
| **Data drift** | The *input* columns changed (houses got bigger). |
| **Target drift** | The *answer* column changed (prices went up). |
| **p-value** | A score 0→1: how likely is this difference just random luck? **Below 0.05 = a real change = DRIFT.** |

Drift is always a **comparison of two datasets**. You cannot detect drift from
one dataset alone — you always need "before" and "after".

## The two new files

### `generate_new_data.py` — pretend a year has passed
Makes a second CSV (`house_data_new.csv`) with deliberately different houses:

| Column | Old data (training) | New data (today) | What happened |
|--------|--------------------|------------------|---------------|
| `size_sqft` | 500 – 3500 | 1800 – 4500 | houses got bigger |
| `num_bedrooms` | 1 – 5 | 3 – 6 | more bedrooms |
| `age_years` | 0 – 40 | 0 – 12 | houses much newer |
| price per sqft | $200 | $260 | market got expensive |

The average house went from **2,026 sqft / $455,038** to **3,158 sqft / $907,767**.
We *caused* this drift on purpose so we can watch Evidently catch it.

### `check_drift.py` — let Evidently compare them
Three real lines of work:

```python
report = Report([DataDriftPreset()])                      # pick the checks
result = report.run(reference_data=old, current_data=new) # compare
result.save_html("drift_report.html")                     # draw the report
```

A **Preset** is a ready-made bundle of checks, so you don't have to choose
statistical tests by hand. `DataDriftPreset` runs a suitable test on every column
automatically.

## How to run it
```bash
pip install evidently          # one time only

python generate_new_data.py    # creates house_data_new.csv (the "today" data)
python check_drift.py          # compares old vs new, writes drift_report.html
```

Then **open `drift_report.html` in your browser** — it is an interactive page with
a chart per column showing the old distribution vs the new one side by side.

## What you should see
All 4 columns flagged as drifted (this is the real output):

```
Columns that drifted: 4 out of 4
That is 100% of all columns.

  size_sqft       p-value=6.75e-20     (K-S p_value           ) -> DRIFT!
  age_years       p-value=1.30e-43     (K-S p_value           ) -> DRIFT!
  price           p-value=3.36e-63     (K-S p_value           ) -> DRIFT!
  num_bedrooms    p-value=0.00e+00     (chi-square p_value    ) -> DRIFT!
```

Two things worth noticing:

- **`6.75e-20` is scientific notation** for 0.0000000...675 — far below 0.05, so
  the change is definitely real and not random luck.
- **Evidently picked a different test per column, by itself.** `K-S`
  (Kolmogorov–Smirnov) for columns of continuous numbers; `chi-square` for
  `num_bedrooms`, because it only takes a few whole values so it behaves like a
  set of categories. You did not have to know that — the Preset chose for you.

## So what do you DO about drift?
Detecting it is only half the job. The response is almost always:

1. **Retrain** the model on the fresh data, then
2. **Redeploy** the retrained model, and
3. **Keep checking** — on a schedule, forever.

That "on a schedule, forever" part is exactly why the rest of this tutorial
exists: a Kedro pipeline (Part 2) run by a Kubernetes CronJob (Part 4) on Azure
retrains the model every night without a human remembering to do it.

## Key words you now understand
- **Feature**: an input column (size, bedrooms, age).
- **Target/Label**: the thing we predict (price).
- **Training**: the learning step (`.fit()`).
- **Model**: the trained "brain" that makes predictions (`.predict()`).
- **MAE / R²**: scores that tell us how good the model is.
- **Drift**: the new data no longer looks like the training data.
- **Reference vs Current**: the "before" and "after" datasets you compare.
- **Evidently**: the library that does the comparing and draws the report.

---

# Step 4 (new): Serving the model as an API

## The problem
Your model is a **file** on your disk. A file is useless to a website, a phone
app, or another team — they cannot "run your Python script."

The fix is to put the model behind a **web address**, so any program anywhere
can send it a house and get a price back. This is called **serving**, and using
a trained model to answer a question is called **inference**.

> **Training vs inference** — the two halves of ML:
> **Training** = learning from examples (slow, done occasionally).
> **Inference** = answering one question (fast, done constantly).

## `serve_model.py` — the smallest possible API

```bash
pip install fastapi uvicorn
uvicorn serve_model:app --reload
```

`serve_model:app` means "in the file `serve_model.py`, use the variable `app`".
`--reload` restarts the server whenever you edit the file.

Then open **<http://127.0.0.1:8000/docs>** in your browser. FastAPI writes a
complete interactive test page for you, **for free**, just from your Python type
hints. Click "Try it out" and send a house without writing a line of code.

| Endpoint | Type | What it does |
|---|---|---|
| `/health` | GET | "Are you alive?" — used by cloud platforms to check the app |
| `/predict` | POST | Send one house, get one price |

Testing it from the terminal:
```bash
curl -X POST http://127.0.0.1:8000/predict ^
     -H "Content-Type: application/json" ^
     -d "{\"size_sqft\":2000,\"num_bedrooms\":3,\"age_years\":10}"
```
```json
{"predicted_price":465276.13,"currency":"USD"}
```

That is the **same number** `train_model.py` printed for the same house — proof
the API is really using our trained model.

## The free gift: input validation
We described a valid house once, with `Field(..., gt=0)` meaning "greater than
zero". FastAPI now rejects bad data automatically, before the model ever sees
it — you write **zero** if-statements:

```bash
# sending a negative size and forgetting age_years:
{"detail":[
  {"loc":["body","size_sqft"], "msg":"Input should be greater than 0"},
  {"loc":["body","age_years"], "msg":"Field required"}
]}
```

## Files in this folder

| File | What it does |
|------|--------------|
| `generate_data.py` | Makes the original training data (`house_data.csv`) |
| `train_model.py` | Trains + evaluates + saves `house_price_model.joblib` |
| `generate_new_data.py` | Makes drifted "today" data (`house_data_new.csv`) |
| `check_drift.py` | Evidently compares the two → `drift_report.html` |
| `serve_model.py` | FastAPI app that serves the model over HTTP |

## Next up
In Part 2 we rebuild this exact project using **Kedro** — a tool that organises
ML code into a clean, professional "pipeline". Same math, better structure.
