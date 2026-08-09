# Azure + Kedro MLOps Tutorial — everything we've built so far

A beginner's end-to-end path from *"a Python script that predicts house prices"*
to *"a trained, monitored, containerised model behind a guarded API on Azure."*

Every part is a folder with its own `README.md`, plain-language explanations, and
every command annotated.

---

## What you've actually built

Not a list of tutorials — one system, assembled a piece at a time:

```
                                    ┌──────────────────────────┐
                                    │   Part 1: the model      │
                                    │   LinearRegression       │
                                    │   R² = 0.993             │
                                    └────────────┬─────────────┘
                                                 │ reorganised into
                                                 ▼
   ┌───────────────────────┐        ┌──────────────────────────┐
   │ Part 1: Evidently     │◄───────┤   Part 2: Kedro pipeline │
   │ drift detection       │  data  │   6 nodes + catalog      │
   └───────────────────────┘        └────────────┬─────────────┘
                                                 │ runs on
                        ┌────────────────────────┼────────────────────────┐
                        ▼                        ▼                        ▼
             ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
             │ Part 4: Kubernetes │  │ Part 5: compute    │  │ Part 7: Azure ML   │
             │ Job + CronJob      │  │ instance + notebook│  │ Jobs (the graph)   │
             └────────────────────┘  └────────────────────┘  └────────────────────┘
                                                 │ produces a model, served by
                                                 ▼
                                    ┌──────────────────────────┐
                                    │  Part 6: FastAPI main.py │
                                    │  /predict /health        │
                                    │  /metrics /pipeline/run  │
                                    └────────────┬─────────────┘
                                                 │ guarded by
                                                 ▼
                                    ┌──────────────────────────┐
                                    │  Part 6: Azure APIM      │
                                    │  ADFS / Entra ID tokens  │
                                    └──────────────────────────┘

              packaged by Part 8 (Docker → ACR) · dependencies from Part 9 (Azure Artifacts)
```

---

## The parts

| # | Part | Folder | What it gave you | Status |
|---|---|---|---|---|
| 1 | First ML project + drift + serving | [`01_simple_ml_project/`](01_simple_ml_project/) | A trained model, Evidently drift reports, a tiny FastAPI | ✅ |
| 2 | Kedro pipeline | [`house-price/`](house-price/) ([tutorial](house-price/TUTORIAL.md)) | Nodes, catalog, parameters, Kedro Viz, `main.py` API | ✅ |
| 3 | Azure account + CLI | [`03_azure_cli/`](03_azure_cli/) | `az` basics, resource groups | ✅ |
| 4 | Kubernetes / AKS | [`04_kubernetes/`](04_kubernetes/) | Job + CronJob for scheduled retraining | ✅ |
| 5 | Azure ML + notebooks | [`05_azure_ml_notebook/`](05_azure_ml_notebook/) | Workspace, compute instance, [git workflow](05_azure_ml_notebook/GITHUB_SETUP.md) | ✅ |
| 6 | FastAPI + APIM + ADFS | [`06_fastapi_apim/`](06_fastapi_apim/) | The API and the security guard in front of it | ✅ |
| 7 | Azure ML Jobs | [`07_azureml_jobs/`](07_azureml_jobs/) | Recorded runs, the pipeline graph, [compute instance option](07_azureml_jobs/USING_COMPUTE_INSTANCE.md) | ✅ |
| 8 | Docker | [`08_docker/`](08_docker/) | Image from MCR, multi-stage build, push to ACR | ✅ |
| 9 | Azure Artifacts | [`09_azure_artifacts/`](09_azure_artifacts/) | Private package feed, dependency-confusion defence | ✅ |
| **10** | **Putting it all together** | [`10_end_to_end/`](10_end_to_end/) | **The whole system, actually connected** | 👈 **you are here** |
| 11 | Microsoft Entra ID | — | Real tokens for the APIM policy | ⬜ |
| 12 | Azure DevOps CI + security scans | — | Build, scan (Fortify / SonarQube / Mend), deploy | ⬜ |

---

## The ideas worth remembering

Each part left behind one thing that matters more than its commands:

| Part | The idea |
|---|---|
| 1 | **Drift is a comparison of two datasets.** A model rots silently; nothing crashes. |
| 2 | **The catalog decouples code from storage.** Move to Azure Blob and your Python never changes. |
| 4 | **A pipeline is a Job, not a Deployment** — it finishes, so it shouldn't restart. |
| 5 | **`~/cloudfiles` survives; the local disk doesn't.** Push to git or lose it. |
| 6 | **APIM answers "should this call happen"; FastAPI answers "what's the result".** |
| 7 | **Terminal = the workbench, job = the record.** And you can only split a Kedro pipeline at catalog boundaries. |
| 8 | **Layer caching is why `requirements.txt` is copied before the code.** |
| 9 | **`index-url`, never `extra-index-url`** — one word between safe and dependency confusion. |

---

## Quick reference

```bash
# --- Part 1: the plain scripts ---
cd 01_simple_ml_project
python generate_data.py && python train_model.py
python generate_new_data.py && python check_drift.py   # drift_report.html
uvicorn serve_model:app --reload                       # http://127.0.0.1:8000/docs

# --- Part 2: the Kedro pipeline ---
cd house-price
python -m kedro run
python -m kedro viz run                                # wait ~30s for "started successfully"
uvicorn house_price.main:app --app-dir src --reload

# --- Part 7: Azure ML jobs ---
az ml job create --file ../07_azureml_jobs/pipeline-job.yml
az ml job stream --name <job-name>

# --- Part 8: the container ---
cd house-price
docker build -t house-price-api:1.0 .
docker run -p 8000:8000 house-price-api:1.0
```

### Environment on this machine

| Thing | Version |
|---|---|
| Python | 3.12 |
| Kedro | **1.5.0** (not 0.19 — some older tutorials won't match) |
| kedro-viz | 12.4.0 |
| FastAPI | 0.140+ (use `lifespan`, not the deprecated `@app.on_event`) |
| scikit-learn | 1.7.1 |
| Azure CLI | 2.87 with the `ml` extension |

> `kedro` isn't on PATH here — use **`python -m kedro`** everywhere.

---

## 💸 The three ways this tutorial can cost you money

Every part has its own cleanup section, but these are the ones that actually bite:

| Thing | Damage | Prevention |
|---|---|---|
| **Compute instance left Running** | ~$195/month | `--idle-time-before-shutdown-minutes 30` |
| **Cluster with `--min-instances 1`** | ~$150-200/month | Always `--min-instances 0` |
| **APIM Developer tier** | ~$50/month, billed idle | Use Consumption tier, or delete it |

```bash
az ml compute list -o table          # run before you finish for the day
az group delete --name <rg> --yes    # the nuclear option
```

---

## Where this is going

**Part 10** connects everything into one running system. **Part 11** issues the
real tokens that the Part 6 APIM policy validates. **Part 12** automates the whole
thing in Azure DevOps with security scanning, so a `git push` does all of it.
