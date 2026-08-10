# Connecting your API to APIM — the step Part 6 skipped

> **The honest gap.** Part 6 explained what APIM *is* and gave you a policy file,
> then said *"replace this with your backend address."* But your API only ran on
> `localhost`, and **APIM cannot reach your laptop.** So the two halves never
> actually met.
>
> This file closes that gap using **only what you know through Part 8 (Docker)**.
> No Azure Artifacts, no AKS, nothing from later parts.

---

## Why `localhost` can never work

This is the whole problem in one picture:

```
   YOUR LAPTOP                          AZURE
   ┌────────────────────┐               ┌──────────────────┐
   │ uvicorn            │               │      APIM        │
   │ 127.0.0.1:8000     │      ✗        │                  │
   │                    │◄─ ─ ─ ─ ─ ─ ─ ┤ "call the        │
   │ behind your router │   impossible  │  backend"        │
   │ behind a firewall  │               │                  │
   └────────────────────┘               └──────────────────┘
```

Three separate reasons, any one of which is fatal:

| Reason | What it means |
|---|---|
| **`localhost` is relative** | `127.0.0.1` means *"the machine I am on."* If APIM tried it, APIM would be calling **itself**. |
| **Your laptop has no public address** | It sits behind your router doing NAT. There is no address on the internet that resolves to it. |
| **Your firewall blocks inbound** | Even with an address, nothing incoming is allowed in. That is a feature, not a fault. |

> **The rule:** APIM is a service running in Azure's network. Its backend must be
> something **reachable from the public internet** (or from a VNet APIM is joined
> to). "On my machine" is never an option.

So the real question isn't *"how do I connect APIM to my API?"* It's:

> ### **"Where do I put my API so that it has an address?"**

And you already have the answer — **Part 8 gave you a container image.** A
container image is precisely a thing you can run *somewhere else*.

---

## Three places to put it

| | Where | Effort | HTTPS | Cost | Good for |
|---|---|---|---|---|---|
| **A** | **Dev tunnel** (still on your laptop) | 5 min | ✅ free | free | Seeing APIM work **today**, no deploy |
| **B** | **Azure Container Instances (ACI)** | 15 min | ❌ http only | ~$1.50/day | **The natural next step after Docker** |
| **C** | **App Service for Containers** | 20 min | ✅ free | ~$13/month | A real, stable URL |

Start with **A** to prove the wiring, then move to **B**. That order means you
debug one thing at a time.

---

## Route A — Dev tunnel (prove it works before deploying anything)

A dev tunnel gives your **already-running local server** a temporary public
HTTPS address. Microsoft makes the tool; it needs no container and no deploy.

```bash
winget install Microsoft.devtunnel      # once
devtunnel user login

# in one terminal: run the API as usual
cd house-price
uvicorn house_price.main:app --app-dir src --port 8000

# in another terminal: expose it
devtunnel host -p 8000 --allow-anonymous
```

You get a URL like:
```
https://abc123xy-8000.uks1.devtunnels.ms
```

**That is a real public address**, and APIM can reach it. Use it as your backend
while you learn, then throw it away.

> ⚠️ **Learning only.** The URL dies when you Ctrl-C, `--allow-anonymous` means
> anyone with the link can call your API, and every request still runs on your
> laptop. Never leave one running unattended.

---

## Route B — Azure Container Instances (the Docker payoff)

This is the one worth doing properly. You built an image in Part 8; ACI runs a
single container and hands it a public DNS name. No orchestration, no cluster.

### ⚠️ First: your image has no model in it

Before deploying, understand what will happen. Your `.dockerignore` excludes
`data/`, so the image contains **no trained model**. Deploy as-is and:

```json
GET  /health   →  {"status":"ok","model_loaded":false}
POST /predict  →  503  "No trained model available."
```

That's `main.py` behaving exactly as designed — honestly reporting it has
nothing to serve. Two ways to fix it with what you know now:

**Fix 1 — let the container train itself (no rebuild).**
You already built the endpoint for this in Part 6:

```bash
curl -X POST http://<your-address>:8000/pipeline/run
```

It runs the Kedro pipeline *inside the container*, then reloads the model. Ten
seconds later `/predict` works. Perfect for a demo — but the model lives only in
that container's disk and dies with it.

**Fix 2 — bake a model into the image.** Train locally first, then let just the
model through by adding a negation to `.dockerignore`:

```gitignore
data/
!data/06_models/**          # let the trained model in
```

Rebuild, and every container starts model-ready. Simple and self-contained — the
cost is that you rebuild the image for every retrain.

> **Use Fix 1 for now.** Fix 2 couples your image to one model version, and
> there is a better answer later involving shared storage. For learning, having
> the container train itself is the fastest path to a working `/predict`.

### 1. Push the image (Part 8, recap)
```bash
cd house-price
docker build -t house-price-api:1.0 .
docker tag house-price-api:1.0 mycompanyacr.azurecr.io/house-price-api:1.0
az acr login --name mycompanyacr
docker push mycompanyacr.azurecr.io/house-price-api:1.0
```

### 2. Let ACI read from your private registry
ACI isn't logged into your ACR, so give it credentials:

```bash
az acr update --name mycompanyacr --admin-enabled true
az acr credential show --name mycompanyacr        # note username + password
```

> Admin credentials are the *simple* way, not the *right* way — a managed
> identity is better and comes with the Entra ID part. Fine for learning; don't
> ship it.

### 3. Run the container
```bash
az container create \
  --resource-group my-ml-rg \
  --name house-price-api \
  --image mycompanyacr.azurecr.io/house-price-api:1.0 \
  --registry-login-server mycompanyacr.azurecr.io \
  --registry-username <from step 2> \
  --registry-password <from step 2> \
  --dns-name-label house-price-demo \
  --ports 8000 \
  --cpu 1 --memory 1.5
```

`--dns-name-label` is the important flag — **it's what gives you an address**:

```
http://house-price-demo.eastus.azurecontainer.io:8000
```

### 4. Check it before involving APIM
```bash
az container show --name house-price-api --resource-group my-ml-rg \
  --query "ipAddress.fqdn" -o tsv

curl http://house-price-demo.eastus.azurecontainer.io:8000/health
# {"status":"ok","model_loaded":false}

curl -X POST http://house-price-demo.eastus.azurecontainer.io:8000/pipeline/run
# wait ~15s, then:
curl http://house-price-demo.eastus.azurecontainer.io:8000/health
# {"status":"ok","model_loaded":true}     ← now it can serve
```

**Do not move on until this works.** If APIM fails later, you want to already
know the backend is healthy.

Logs, when it doesn't:
```bash
az container logs --name house-price-api --resource-group my-ml-rg
```

---

## Now import the API into APIM

Part 6 told you to use `--specification-url`. **That has the same problem as
everything else** — APIM has to fetch that URL, so it must be reachable.

You don't need a running server at all. FastAPI can produce the spec straight
from your Python.

### Use `export_openapi.py` (in this folder)

```bash
cd house-price
python ../06_fastapi_apim/export_openapi.py
```

```
FastAPI produced OpenAPI 3.1.0
Wrote openapi-3.0.json as OpenAPI 3.0.3
Endpoints included:
  /health
  /predict
  /metrics
  /pipeline/run
```

### Why that script exists — a real gotcha

**FastAPI 0.140+ emits OpenAPI 3.1.0. APIM's importer expects 3.0.x.**

And you cannot just change the version string, because the documents genuinely
differ. Your `Field(..., gt=0)` on `size_sqft` produces:

```jsonc
// OpenAPI 3.1 (what FastAPI gives you)
{ "exclusiveMinimum": 0 }                          // a NUMBER

// OpenAPI 3.0 (what APIM wants)
{ "minimum": 0.0, "exclusiveMinimum": true }       // a BOOLEAN + minimum
```

Setting `FastAPI(openapi_version="3.0.3")` **does not work** — it's ignored, and
`app.openapi_version` still reads `3.1.0`. The script rewrites the constructs
properly instead.

### Import from the file
```bash
az apim api import \
  --resource-group my-ml-rg \
  --service-name house-price-apim \
  --path houseprice \
  --api-id house-price-api \
  --specification-format OpenApiJson \
  --specification-path 06_fastapi_apim/openapi-3.0.json
```

**`--specification-path`, not `--specification-url`.** A local file — nothing
needs to be reachable. 👉 GET Deeper [`Import_PI_into_APIM.md`](Import_PI_into_APIM.md)

All four endpoints appear in APIM, generated from your Python type hints. That's
the payoff Part 6 promised, now actually achievable.

> **Or just do it by hand.** It's four endpoints. APIM → APIs → *+ Add API* →
> *HTTP* → add `/health`, `/predict`, `/metrics`, `/pipeline/run`. If the import
> gives you trouble, this takes five minutes and skips the whole 3.1 problem.

---

## Point APIM at your backend

Open `apim-policy.xml` and replace the placeholder:

```xml
<!-- before -->
<set-backend-service base-url="https://house-price-api.internal.company.com" />

<!-- after, for ACI -->
<set-backend-service base-url="http://house-price-demo.eastus.azurecontainer.io:8000" />

<!-- after, for a dev tunnel -->
<set-backend-service base-url="https://abc123xy-8000.uks1.devtunnels.ms" />
```

Paste the policy into **APIM → APIs → house-price-api → Design → Inbound
processing → `</>`**.

> ⚠️ **`http://` not `https://` for ACI.** ACI gives you a plain HTTP address.
> APIM will call it happily, but the APIM→backend hop is unencrypted. Acceptable
> while learning; for anything real use Route C (App Service, free HTTPS) or put
> the backend inside a VNet.

---

## Test it — the failing test first

The only test that proves the guard works is the one that **must be rejected**:

```bash
# NO token -> must be 401
curl -i https://house-price-apim.azure-api.net/houseprice/predict \
  -H "Content-Type: application/json" \
  -d '{"size_sqft":2000,"num_bedrooms":3,"age_years":10}'
```

If that returns a **price instead of 401**, your policy isn't applied — and you
have an open API. **A security layer you never tested is a security layer you do
not have.**

Then the one that should succeed:
```bash
curl -X POST https://house-price-apim.azure-api.net/houseprice/predict \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"size_sqft":2000,"num_bedrooms":3,"age_years":10}'
# {"predicted_price":465276.13,"currency":"USD"}
```

And the one that should pass with no token at all, by design:
```bash
curl https://house-price-apim.azure-api.net/houseprice/health
# {"status":"ok","model_loaded":true}    ← RULE 1 in the policy
```

> 🔑 **You need a token for the middle test, and you don't have one yet.** That's
> the Entra ID part. Until then, comment out the `<validate-jwt>` block to prove
> the *plumbing* works, then put it back. Test the pipe before you test the tap.

---

## Route C — App Service (when you want real HTTPS)

```bash
az appservice plan create \
  --name house-price-plan --resource-group my-ml-rg --is-linux --sku B1

az webapp create \
  --resource-group my-ml-rg --plan house-price-plan \
  --name house-price-api-demo \
  --deployment-container-image-name mycompanyacr.azurecr.io/house-price-api:1.0

az webapp config appsettings set \
  --resource-group my-ml-rg --name house-price-api-demo \
  --settings WEBSITES_PORT=8000
```

You get **`https://house-price-api-demo.azurewebsites.net`** — free certificate,
stable name, restarts on crash.

> `WEBSITES_PORT=8000` is essential and easy to miss. App Service defaults to
> port 80; our container listens on 8000. Without it you get a blank page or a
> 502 with no useful error.

---

## Common problems

| What you see | What it means |
|---|---|
| APIM returns **500** or **BackendConnectionFailure** | The backend URL is wrong or unreachable. `curl` it directly first. |
| APIM works, `/predict` returns **503** | Backend is healthy but has no model. Call `POST /pipeline/run`, or use Fix 2. |
| ACI stuck in **Waiting** / **Pulling** | Wrong registry credentials, or admin user not enabled on ACR. |
| ACI `Terminated` immediately | The container crashed. `az container logs` — usually a missing dependency. |
| Import fails on the spec | The 3.1 vs 3.0 issue. Use `export_openapi.py`, or add the endpoints by hand. |
| Everything 401, even `/health` | Your policy is missing the `/health` exception (RULE 1 in `apim-policy.xml`). |
| Dev tunnel URL stopped working | It's temporary and dies with the process. Restart `devtunnel host`. |
| App Service shows a blank page | You forgot `WEBSITES_PORT=8000`. |

---

## 💸 Costs and cleanup

| Thing | Cost |
|---|---|
| Dev tunnel | Free |
| ACI (1 vCPU, 1.5 GB) | ~$0.06/hour ≈ **$1.50/day if left running** |
| App Service B1 | ~$13/month |
| APIM Consumption | ~$3.50 per million calls |
| APIM Developer | **~$50/month, billed idle** |

```bash
az container delete --name house-price-api --resource-group my-ml-rg --yes
az webapp delete --name house-price-api-demo --resource-group my-ml-rg
az apim delete --name house-price-apim --resource-group my-ml-rg --yes
```

> ACI bills **per second while it exists**, running or not. Delete it, don't just
> ignore it.

---

## What you now understand

- **APIM can't reach `localhost`** — not a config problem, a networking fact.
  Your API needs a public address before APIM can be put in front of it.
- **A container image is what makes that easy.** Part 8 wasn't a detour; it's
  what lets you run the same API somewhere with an address.
- **ACI = one container with a DNS name.** The smallest possible "somewhere."
- **You can export the OpenAPI spec without running a server**, and import it
  with `--specification-path` — no reachable URL needed.
- **FastAPI emits 3.1, APIM wants 3.0**, and the difference is real, not
  cosmetic.
- **Test the rejection first.** An untested policy is not a policy.

## Still missing

1. **A real token** — `<validate-jwt>` has nothing issuing tokens yet.
2. **Managed identity** instead of ACR admin credentials.
3. **Somewhere durable for the model** — right now it lives inside one container
   and dies with it.
4. **More than one copy** — ACI runs a single container with no restarts or
   scaling. That's what Kubernetes is for.
