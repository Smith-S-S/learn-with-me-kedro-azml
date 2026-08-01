# Part 6 — FastAPI + Azure APIM (with ADFS / Entra ID login)

In Part 2 we built a Kedro pipeline. In this part we put a **front door** on it,
and then a **security guard** in front of that door.

```
   Someone's app
        |
        |  1. asks ADFS / Entra ID for a token
        v
   [ ADFS / Entra ID ]  ---- issues a signed token (JWT) ---->
        |
        |  2. calls the API, showing the token
        v
   [ Azure APIM ]        <-- the security guard. Checks the token, counts calls
        |
        |  3. only valid calls get through
        v
   [ FastAPI (main.py) ] <-- your code. Loads the model, returns a price
        |
        v
   [ Kedro model ]
```

## Why two layers? Can't FastAPI just check the password itself?

It could — but you would rewrite that logic in every service you ever build, and
get it slightly wrong each time. APIM does it **once**, for **all** your APIs.

| Job | Who does it | Why there |
|-----|-------------|-----------|
| Check who you are | **APIM** | One place, one policy, every API protected the same way |
| Block callers who spam you | **APIM** | Stops overload *before* it reaches your code |
| Hide your real server address | **APIM** | The world never learns your Kubernetes IP |
| Predict a house price | **FastAPI** | This is your actual business logic |

The rule of thumb: **APIM handles "should this call happen at all", FastAPI
handles "what is the answer".**

---

## The words your organization is using

| Word | What it actually means |
|------|------------------------|
| **APIM** | Azure API Management. A managed "front desk" that sits in front of your APIs. |
| **ADFS** | Active Directory Federation Services. A Microsoft **server your company runs itself**, usually in its own data centre, that logs employees in and hands out tokens. The older, on-premises way. |
| **Entra ID** | The cloud version of the same idea (it used to be called Azure AD). |
| **JWT** | JSON Web Token. A blob of text that says "this caller is Sam, from Finance, and this expires at 4pm" — signed so it cannot be faked. |
| **Claim** | One fact inside the token: your name, your groups, when it expires. |
| **Audience (`aud`)** | Who the token was *made for*. Stops a token meant for the HR app being reused on yours. |
| **Issuer (`iss`)** | Who *made* the token. Must be your ADFS/Entra, not some random server. |
| **Backend** | APIM's word for "the real API hiding behind me" — our FastAPI. |
| **Policy** | An XML file telling APIM what to do on each call. This is where the security lives. |

> **Why is your org on ADFS and not Entra ID?**
> Very common in banks, insurers, and consultancies. ADFS runs inside the company
> network, so identity never leaves the building — which regulators like. Many
> companies run both: ADFS for staff, federated up to Entra ID for cloud apps.
> **The good news: APIM validates tokens from either one the exact same way.**
> Only one URL in the policy changes.

---

## How a token actually gets checked (no magic)

1. ADFS signs the token with a **private key** that only ADFS has.
2. ADFS publishes the matching **public key** at a well-known URL.
3. APIM downloads that public key and uses it to verify the signature.
4. If the signature checks out, the token is genuine and was not edited.

APIM does steps 2–4 for you. You just tell it *where* to look — that is the
`<openid-config url="..."/>` line in the policy below.

| Identity provider | The URL you point APIM at |
|---|---|
| **ADFS** (on-premises) | `https://adfs.yourcompany.com/adfs/.well-known/openid-configuration` |
| **Entra ID** (cloud) | `https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration` |

---

## The policy file

See **`apim-policy.xml`** in this folder — it is fully commented, line by line.
The important part is small:

```xml
<validate-jwt header-name="Authorization" failed-validation-httpcode="401">
    <openid-config url="https://adfs.yourcompany.com/adfs/.well-known/openid-configuration" />
    <audiences><audience>api://house-price</audience></audiences>
</validate-jwt>
```

Read it as a sentence: *"Look in the Authorization header for a token. Check it
against our ADFS. It must have been issued for `api://house-price`. If any of
that fails, reply 401 and never call the backend."*

**401 vs 403** — worth knowing:
- **401 Unauthorized** = "I don't know who you are." (no token / bad token)
- **403 Forbidden** = "I know who you are, and you're not allowed." (valid token, wrong group)

---

## Protecting the dangerous endpoint

Remember the four doors in `main.py`:

| Endpoint | Who should reach it | Why |
|---|---|---|
| `GET /health` | **Anyone** — no token | Kubernetes and APIM probe this constantly. If it needed a token, they could not check the app is alive. |
| `POST /predict` | Any valid token | Normal business use. |
| `GET /metrics` | Any valid token | Reveals model quality — mildly sensitive. |
| `POST /pipeline/run` | **Admins only** | It retrains the model and burns real compute. This is the one that can cost you money or wreck a good model. |

That last row is why the policy has a **second, stricter rule** on
`/pipeline/run` that checks for an admin group claim. Protecting `/predict` but
leaving `/pipeline/run` open is the classic mistake — the cheap endpoint is
guarded and the expensive one is wide open.

---

## Hands-on

### 1. Run FastAPI locally first
Always prove the API works *before* adding the security layer, or you will not
know which of the two broke.

```bash
cd house-price
.venv\Scripts\activate
uvicorn house_price.main:app --app-dir src --reload
```

Open <http://127.0.0.1:8000/docs> — FastAPI writes an interactive test page for
you, for free. Click **Try it out** on `/predict`.

Or from the terminal:
```bash
curl -X POST http://127.0.0.1:8000/predict ^
     -H "Content-Type: application/json" ^
     -d "{\"size_sqft\":2000,\"num_bedrooms\":3,\"age_years\":10}"
```
Expected: `{"predicted_price":465276.13,"currency":"USD"}`

### 2. Create the APIM instance
> ⚠️ **This costs money.** The Developer tier is ~$50/month and takes **30–45
> minutes** to create — that is normal, not a hang. Consumption tier is
> pay-per-call and much cheaper for learning. Delete it when you are done.

```bash
# Consumption tier = cheapest for learning (pay per call, no monthly fee)
az apim create ^
  --name house-price-apim ^
  --resource-group my-ml-rg ^
  --publisher-name "My Company" ^
  --publisher-email you@example.com ^
  --sku-name Consumption ^
  --location eastus
```

### 3. Import your API into APIM
```bash
# FastAPI publishes an OpenAPI spec at /openapi.json describing every endpoint.
# APIM can read that file and configure itself -- no manual endpoint entry.
az apim api import ^
  --resource-group my-ml-rg ^
  --service-name house-price-apim ^
  --path houseprice ^
  --specification-format OpenApi ^
  --specification-url http://<your-backend-address>/openapi.json ^
  --api-id house-price-api
```

This is a genuinely nice payoff: because FastAPI auto-generates `/openapi.json`
from your Python type hints, **APIM configures itself from your code.**

### 4. Apply the policy
Paste `apim-policy.xml` into the Azure Portal:
**APIM → APIs → house-price-api → Design → Inbound processing → `</>`**

### 5. Test that security actually works
The only test that matters is the one that should **fail**:

```bash
# No token -> must be rejected with 401
curl -i https://house-price-apim.azure-api.net/houseprice/predict ^
     -H "Content-Type: application/json" ^
     -d "{\"size_sqft\":2000,\"num_bedrooms\":3,\"age_years\":10}"
```
If that returns a price instead of `401`, your policy is not applied. **A
security layer you never tested is a security layer you do not have.**

```bash
# With a token -> should succeed
curl -X POST https://house-price-apim.azure-api.net/houseprice/predict ^
     -H "Authorization: Bearer <your-token>" ^
     -H "Content-Type: application/json" ^
     -d "{\"size_sqft\":2000,\"num_bedrooms\":3,\"age_years\":10}"
```

---

## Common problems

| What you see | Almost always means |
|---|---|
| `401` with a valid token | The `audience` in the policy does not match the `aud` claim in your token. Paste the token into <https://jwt.ms> and compare. |
| `401` on every call | APIM cannot reach the ADFS discovery URL. On-prem ADFS is often not reachable from Azure — you need a VNet, a gateway, or Entra federation. |
| Works locally, `500` via APIM | APIM cannot reach your backend. Check the backend URL and that the container is actually running. |
| `/health` also returns 401 | You applied the JWT policy at API level without excluding `/health`. Kubernetes will now kill your pods. |
| Token rejected right after issuing | Clock skew between ADFS and Azure. Check time sync on the ADFS server. |

---

## 💸 Costs and cleanup

| Thing | Cost |
|---|---|
| APIM Consumption | ~$3.50 per million calls, no monthly fee |
| APIM Developer | ~$50/month, **billed even when idle** — the classic surprise bill |
| APIM Standard/Premium | $700+/month — production only, never for learning |

```bash
# Delete when finished -- do not skip this
az apim delete --name house-price-apim --resource-group my-ml-rg --yes
```

---

## What you now understand
- An **API** turns a model file into something any program can use.
- **Inference** = using a trained model. **Training** = making one.
- **APIM** is a guard in front of your API; **FastAPI** is the API itself.
- **ADFS** and **Entra ID** both hand out **JWTs**; APIM verifies them with a
  public key it downloads automatically.
- The expensive endpoint (`/pipeline/run`) needs *stricter* rules than the cheap
  one — and `/health` needs *no* rules at all.

## Next up (Part 7)
**Docker** — we package this FastAPI app into a container image so it runs the
same on your laptop, in Kubernetes, and in Azure. That container is what APIM
will point at as its backend.
