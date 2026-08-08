# Azure ML + Kedro — Simple Explanation

## First: Think About Your Kedro Project

You have something like:

```text
house-price/
│
├── conf/
│   └── base/
│       └── parameters.yml
│
├── src/
│   └── house_price/
│       ├── pipelines/
│       │   └── house_price/
│       │       ├── nodes.py
│       │       └── pipeline.py
│       │
│       └── settings.py
│
└── pyproject.toml
```

Your Kedro pipeline is roughly:

```text
create_house_data
       ↓
   split_data
       ↓
   train_model
       ↓
 evaluate_model
```

Now Azure ML provides the infrastructure to **run and track this**.

---

# 1. Workspace = Your Azure ML Project

Think:

> **Workspace = the big container for your ML work**

You created:

```text
mlw-house-price
```

Inside that workspace you can have:

```text
mlw-house-price
│
├── Jobs
├── Experiments
├── Compute
├── Environments
├── Models
├── Endpoints
└── Data
```

So your Kedro project might live in GitHub, while Azure ML Workspace manages the ML resources and runs.

### Simple analogy

Kedro:

```text
house-price/
```

Azure ML:

```text
mlw-house-price/
```

They are **not the same thing**.

---

# 2. Job = ONE Execution

This is probably the most confusing one.

A **job is simply one time you run something**.

Imagine you execute:

```bash
kedro run
```

Today.

That execution is one run of your pipeline.

Tomorrow you change something and run:

```bash
kedro run
```

again.

That's another run.

In Azure ML, each execution can be represented as a **job**.

For example:

```text
Job #1
---------
create data
↓
split data
↓
train model
↓
evaluate

RMSE = 52000
```

Then you change your model:

```text
Job #2
---------
create data
↓
split data
↓
train model
↓
evaluate

RMSE = 43000
```

Now you have:

```text
Job 1 → RMSE 52000
Job 2 → RMSE 43000
```

That's useful because you can compare your runs.

### In Kedro terms

Think:

```bash
kedro run
```

=

```text
ONE JOB / RUN
```

> This is not technically identical in every detail, but it is a very useful mental model.

---

# 3. Experiment = A Group of Jobs

This is where people usually get confused.

An **experiment is not the actual execution**.

It is basically a **label/group for related jobs**.

Imagine you're trying different models.

### Experiment

```text
house-price-model
```

Inside it:

```text
house-price-model
│
├── Job 1 → Linear Regression → RMSE 52,000
├── Job 2 → Random Forest     → RMSE 43,000
├── Job 3 → XGBoost           → RMSE 38,000
└── Job 4 → Random Forest     → RMSE 41,000
```

Now Azure ML lets you compare them.

So:

```text
Experiment
    │
    ├── Job 1
    ├── Job 2
    ├── Job 3
    └── Job 4
```

### Very simple

```text
Experiment = folder
Job        = file inside the folder
```

> Not literally a filesystem folder/file, but this is a good mental model.

---

# 4. Kedro Example

Suppose your Kedro pipeline has:

```text
house_price_pipeline
```

You run it with:

```bash
kedro run
```

You get:

```text
train_model
    ↓
RandomForest
    ↓
RMSE = 38,500
```

Then you change:

```yaml
model_options:
  model_type: linear_regression
```

and run again.

You get:

```text
train_model
    ↓
LinearRegression
    ↓
RMSE = 52,100
```

Azure ML could organize this as:

```text
Experiment: house-price-model
│
├── Job: random-forest
│      └── RMSE = 38,500
│
└── Job: linear-regression
       └── RMSE = 52,100
```

Now you know which run performed better.

---

# 5. Environment = The Software Your Job Needs

This is another important one.

Suppose your Kedro code contains:

```python
import pandas
import sklearn
import numpy
```

Your computer needs those libraries.

Maybe you need:

```text
Python 3.10
Kedro
pandas
numpy
scikit-learn
```

That collection of software is your **environment**.

Think:

> **Environment = the computer's software setup needed to run my code.**

For example:

```text
Environment: house-price-env

Python 3.10
Kedro
pandas
numpy
scikit-learn
```

Azure ML can create/use this environment when running a job.

---

# Why Do We Need an Environment?

Imagine your laptop has:

```text
Python 3.10
pandas 2.x
scikit-learn 1.x
Kedro 1.x
```

But your teammate has:

```text
Python 3.12
pandas 1.x
scikit-learn 0.x
Kedro different version
```

Your code might work for you but fail for them.

Environment solves this problem.

You say:

> "Whenever this job runs, use this exact software setup."

For example:

```text
Python 3.10
Kedro 1.0
pandas 2.2
scikit-learn 1.5
numpy 2.x
```

Now Azure ML knows exactly what software should be available when your job runs.
