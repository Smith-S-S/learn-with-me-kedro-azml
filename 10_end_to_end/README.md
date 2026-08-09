# Part 10 — Putting it all together

Nine parts, nine working pieces. But right now they are **nine separate demos**,
not a system:

- The Docker image (Part 8) has no trained model in it.
- The Kubernetes manifests (Part 4) run the *pipeline*, not the *API*.
- The APIM policy (Part 6) points at a backend address that doesn't exist.
- The Azure ML job (Part 7) trains a model that nothing ever picks up.

This part connects them. At the end you'll have **one running system** that a
colleague can send a house to and get a price back — with the model retrained on
a schedule, without anyone touching it.

---

## The target

```
   ┌──────────┐   git push
   │   You    │──────────────┐
   └──────────┘              │
                             ▼
                  ┌─────────────────────┐
                  │ Part 8: docker build│
                  │      ↓ push         │
                  │   Part 8: ACR       │◄──── base image from MCR
                  └──────────┬──────────┘      packages from Part 9 feed
                             │ pulled by
                             ▼
   ┌─────────────────────────────────────────────┐
   │              AKS cluster (Part 4)           │
   │                                             │
   │  ┌───────────────────┐   ┌───────────────┐  │
   │  │ Deployment        │   │ CronJob       │  │
   │  │ 3× FastAPI pods   │   │ nightly       │  │
   │  │ (serving)         │   │ retrain       │  │
   │  └─────────┬─────────┘   └───────┬───────┘  │
   │            │ ClusterIP           │          │
   └────────────┼─────────────────────┼──────────┘
                │                     │ writes model
                ▼                     ▼
        ┌───────────────┐    ┌──────────────────┐
        │  APIM (P6)    │    │  Blob Storage    │
        │  ADFS tokens  │    │  regressor.pickle│
        └───────┬───────┘    └────────┬─────────┘
                │                     │ loaded at pod startup
                ▼                     └────────────► (back to the pods)
          Your colleague's app
```

Four connections to make. **Three are easy. One is the interesting one.**

| # | Connection | Difficulty |
|---|---|---|
| 1 | Code → image → ACR | Easy (Part 8 did it) |
| 2 | ACR → AKS | Easy (one `az` command) |
| 3 | AKS → APIM | Easy (a backend URL) |
| 4 | **Training → serving: how does the API get the model?** | **The real problem** |

---

## ⚠️ Connection 4 first, because everything depends on it

### The problem nobody warns you about

Your `.dockerignore` excludes `data/`. That was correct — you don't want a
500 MB image or a stale model baked in.

But it means **the image contains no model at all**. Start that container on AKS
and `main.py` does exactly what we designed it to do:

```json
GET /health   →  {"status":"ok","model_loaded":false}
POST /predict →  503  "No trained model available."
```

Not a bug — the container is honestly reporting it has nothing to serve. But
your API is useless until the model gets there.

**Training happens in one place. Serving happens in another. Something has to
carry the model between them.** That is the piece none of the nine parts covered.

### Three ways to solve it

| | How | Good | Bad |
|---|---|---|---|
| **A. Bake it in** | `COPY` the model into the image | Dead simple; image is self-contained; exact rollback | Rebuild + redeploy for *every* retrain |
| **B. Blob Storage** | Catalog points at Azure Blob; pods load at startup | **`main.py` never changes**; retrain without rebuilding | Needs credentials in the cluster |
| **C. Azure ML registry** | Training registers a model; API downloads by version | Proper lineage, stage promotion | Most moving parts |

**We'll use B**, because it finally cashes a cheque written back in Part 2:

> *"When the model later moves to Azure Blob Storage, `main.py` does not change
> at all. Only `catalog.yml` does."*

That's about to be literally true.

### Doing it

**1. Create the storage:**
```bash
az storage account create \
  --name housepricemodels \
  --resource-group my-ml-rg \
  --sku Standard_LRS

az storage container create \
  --name models \
  --account-name housepricemodels
```

**2. Change *only* `conf/base/catalog.yml`:**
```yaml
regressor:
  type: pickle.PickleDataset
  filepath: abfs://models/regressor.pickle    # was data/06_models/regressor.pickle
  credentials: azure_blob
  versioned: true
```

**3. Add the credentials to `conf/local/credentials.yml`** (already gitignored
*and* dockerignored — check that, then check it again):
```yaml
azure_blob:
  account_name: housepricemodels
  connection_string: ${oc.env:AZURE_STORAGE_CONNECTION_STRING}
```

**4. Add the filesystem driver** to `requirements.txt`:
```
adlfs        # lets Kedro read/write abfs:// paths
```

**Now stop and notice what didn't happen.** You didn't touch `main.py`,
`nodes.py`, or `pipeline.py`. The training job writes to Blob and the API reads
from Blob, and neither knows. That is the entire point of the catalog, and it
took nine parts to get somewhere it actually pays off.

---

## Step by step

### 1. Build and push the image (Part 8)
```bash
cd house-price
docker build -t house-price-api:1.0 .
docker tag house-price-api:1.0 mycompanyacr.azurecr.io/house-price-api:1.0
az acr login --name mycompanyacr
docker push mycompanyacr.azurecr.io/house-price-api:1.0
```

### 2. Let AKS pull from ACR
```bash
az aks update \
  --name my-aks-cluster \
  --resource-group my-ml-rg \
  --attach-acr mycompanyacr
```

> **What this fixes before it happens:** without it, your pods sit in
> `ImagePullBackOff` forever. AKS can see the image but isn't allowed to pull it.
> This one command grants that permission — it is not optional.

### 3. Put the storage secret in the cluster
```bash
CONN=$(az storage account show-connection-string \
  --name housepricemodels --query connectionString -o tsv)

kubectl create secret generic azure-storage \
  --from-literal=connection-string="$CONN"
```

> The secret lives in the cluster; the image stays clean. This is the same rule
> as Part 9's `--mount=type=secret`: **credentials travel at run time, never
> build time.**

### 4. Deploy the API
```bash
kubectl apply -f 10_end_to_end/api-deployment.yaml

kubectl get pods -w          # wait for 3/3 Running
kubectl logs -l app=house-price-api --tail=20
```

Test it without exposing anything publicly:
```bash
kubectl port-forward service/house-price-api 8000:80

curl http://localhost:8000/health
# {"status":"ok","model_loaded":true}    ← the moment it all works
```

`model_loaded: true` means the pod reached Blob Storage and loaded the model.
That single field is your end-to-end proof.

### 5. Train, so there's something to load
If Blob is empty, `model_loaded` will be `false`. Fill it with a Part 7 job:

```bash
cd house-price
az ml job create --file ../07_azureml_jobs/pipeline-job.yml
```

Because the catalog now points at Blob, this job writes the model **straight to
where the API reads from**. Connection 4, done.

### 6. Point APIM at the cluster (Part 6)
In `06_fastapi_apim/apim-policy.xml`, replace the placeholder backend:

```xml
<set-backend-service base-url="https://house-price.internal.mycompany.com" />
```

with your ingress or internal load balancer address (see the notes at the bottom
of `api-deployment.yaml`). Then the full chain works:

```bash
curl -X POST https://house-price-apim.azure-api.net/houseprice/predict \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"size_sqft":2000,"num_bedrooms":3,"age_years":10}'
# {"predicted_price":465276.13,"currency":"USD"}
```

**That number came all the way through**: APIM checked the token → forwarded to
the AKS Service → a pod ran the model it loaded from Blob → answer back out.

---

## Closing the loop: automatic retraining

Everything above is still a one-time deploy. The point of MLOps is that it keeps
working without you.

### The cycle

```
   Part 4 CronJob (2am nightly)
            │
            ▼
   kedro run  ──►  new model written to Blob Storage
            │
            ▼
   Part 1 check_drift.py  ──►  did the data actually change?
            │
            ▼
   API pods pick up the new model
```

### The bit that catches people: pods don't notice

`main.py` loads the model **once**, at startup (that's the `lifespan` function).
A new model in Blob does **not** reach a running pod. Three options:

| Option | Command | Notes |
|---|---|---|
| **Restart the pods** | `kubectl rollout restart deployment/house-price-api` | Simplest. Zero downtime — readiness probes hold traffic until new pods are ready. |
| **Call your own endpoint** | `POST /pipeline/run` | It already reloads the model afterwards. But it retrains *inside the pod* — fine for a demo, wrong for production. |
| **Reload on a timer** | Add a background task | More code, no restarts. |

**Use the restart.** Add it as the last line of the CronJob, and the readiness
probes you configured make it invisible to callers.

### Wire drift detection in
Part 1 built `check_drift.py` and never connected it to anything. Here's its job:
have the nightly CronJob run the drift check *first*, and only retrain if drift
is real. Retraining on unchanged data burns money and risks replacing a good
model with a marginally worse one.

---

## Where each part ended up

| Part | Its job in the running system |
|---|---|
| 1 — Model + drift | The maths, and the nightly "should we retrain?" check |
| 2 — Kedro | The pipeline, and the catalog that made the Blob swap a one-line change |
| 3 — Azure CLI | Every `az` command above |
| 4 — Kubernetes | CronJob retrains; **Deployment serves** (added here) |
| 5 — Azure ML notebooks | Where you develop and debug before submitting |
| 6 — FastAPI + APIM | The door, and the guard on it |
| 7 — Azure ML Jobs | Recorded, reproducible training runs |
| 8 — Docker + ACR | The image every pod runs |
| 9 — Azure Artifacts | Where the image's Python packages came from |

Nothing was busywork. Every part is load-bearing.

---

## Common problems

| What you see | What it means |
|---|---|
| Pods stuck `ImagePullBackOff` | You skipped `az aks update --attach-acr`. |
| Pods `Running` but `model_loaded: false` | Blob is empty (run a training job), or the secret is wrong. Check `kubectl logs`. |
| `CreateContainerConfigError` | The `azure-storage` secret doesn't exist, or the key name doesn't match `connection-string`. |
| Pods restart in a loop | Liveness probe too aggressive, or the app crashes at startup. `kubectl logs --previous`. |
| APIM returns 500 | It can't reach the cluster. A ClusterIP Service is private — you need an ingress or internal load balancer. |
| Works via `port-forward`, not via APIM | Confirms the pods are fine and it's the APIM→cluster network path. |
| New model trained, API still serves the old one | Expected. The pods loaded at startup — `kubectl rollout restart`. |

---

## 💸 Costs — this part is the expensive one

Everything running at once, unlike earlier parts:

| Thing | Cost |
|---|---|
| AKS cluster (2× `Standard_B2s`) | ~$70/month |
| ACR Basic | ~$5/month |
| Storage account | Pennies |
| APIM Consumption | ~$3.50 per million calls |
| APIM Developer | **~$50/month, billed idle** |

```bash
# Cheapest pause: scale the pods to zero, keep everything else
kubectl scale deployment/house-price-api --replicas=0

# Stop the AKS cluster entirely (biggest saving)
az aks stop --name my-aks-cluster --resource-group my-ml-rg

# Full teardown
az group delete --name my-ml-rg --yes --no-wait
```

> ⚠️ **Do not leave an AKS cluster running after finishing this part.** It is the
> single most expensive thing in this whole tutorial, and unlike a compute
> instance it has no idle-shutdown setting.

---

## What's still missing (deliberately)

Being honest about what this system does *not* yet have:

1. **Real tokens.** The APIM policy validates ADFS/Entra tokens, but you don't
   have an app registration issuing them yet. → **Part 11**
2. **Automation.** Every step above was typed by hand. A `git push` should do it.
   → **Part 12**
3. **Security scanning.** Nothing checks your dependencies or code for known
   vulnerabilities. → **Part 12** (Fortify, SonarQube, Mend)
4. **A real inference pipeline.** Batch scoring still doesn't exist as a Kedro
   pipeline — inference lives only in `main.py`.

## Next up (Part 11)
**Microsoft Entra ID** — register the API as an application, define its scopes
and roles, and issue a real token. Then the Part 6 policy stops being a template
and starts actually rejecting people.
