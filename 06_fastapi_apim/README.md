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

---

# First, properly: what ARE these two things?

Before any commands, let's slow down on the two words your organization uses
every day. Both exist to solve a problem you only feel once a company gets big.

## ADFS — the company's own passport office

### The problem it solves
Imagine your company has 50 internal apps: payroll, expenses, the HR portal, the
ML platform. The naive design gives each one its own username and password.

That is a disaster:
- You memorise 50 passwords, so you reuse one weak password everywhere.
- Someone leaves the company and IT must remember to delete 50 accounts. They
  miss three. Those three are now unlocked doors, forever.
- Each app stores passwords, so each app is a place passwords can leak from.

### The fix: one place that proves who you are
**ADFS (Active Directory Federation Services)** is a Microsoft server your
company runs **itself**, usually inside its own building. It has exactly one
job: *check who you are, once, and then vouch for you to everything else.*

> **Think of it as a passport office.**
> You prove your identity to the passport office **one time**, with real
> documents. It gives you a **passport**. After that, every border guard in the
> world trusts the passport — they never re-check your birth certificate. They
> only check the passport is genuine and unexpired.

In this analogy:
- **Passport office** = ADFS
- **Passport** = the **token** (a JWT)
- **Border guard** = APIM
- **The country you're entering** = your FastAPI

Now when someone leaves the company, IT disables **one** account in Active
Directory and every single app locks them out at once. That is the whole point.

### What "Federation" means (the F in ADFS)
Federation is just a fancy word for **"I trust your passport office."**

Two companies, or a company and Microsoft's cloud, agree in advance to trust
each other's tokens. So a token issued by *your company's* ADFS is accepted by
*Microsoft's* cloud services, without Microsoft ever seeing your password.

That is why many organizations run **both**: ADFS on-premises for staff logins,
**federated** up to Entra ID so cloud apps work too.

### Why would a company keep ADFS instead of moving to the cloud?

| Reason | What it means in practice |
|---|---|
| **Regulation** | Banks, insurers and consultancies are often required to keep identity data inside their own walls. |
| **Data sovereignty** | Passwords and staff records never leave the building. |
| **Existing investment** | It already works, and identity is the scariest thing to migrate. |
| **Custom rules** | Fine-grained control over exactly which claims go into a token. |

### ADFS vs Entra ID, side by side

| | **ADFS** | **Entra ID** |
|---|---|---|
| Where it runs | Your company's own servers | Microsoft's cloud |
| Who maintains it | Your IT team (patching, backups, uptime) | Microsoft |
| Old name | — | Azure AD |
| Cost | Servers + staff time | Per-user licence |
| Setup for you | Company already did it | Company already did it |
| **How APIM checks its tokens** | **Identical** | **Identical** |

That last row is the point worth remembering: **you do not learn two systems.**
Both hand out standard JWTs. The APIM policy is the same; only one URL differs.

---

## APIM — the front desk

### The problem it solves
Every API needs the same boring, security-critical chores:

1. Check the caller is who they claim to be
2. Stop one caller flooding the service
3. Write down who called what, for auditing
4. Hide the real server address from the internet
5. Keep old versions working when you release a new one

Now imagine your company has 30 APIs. Without APIM, **all 30 teams write all 5
of those things themselves.** They will each get it slightly wrong, in different
ways, and nobody will know which ones are wrong until there's a breach.

### The fix: do it once, in front of everything
**APIM (Azure API Management)** is a managed service that sits **in front of**
your APIs. Every call goes to APIM first. APIM does the boring chores, then
forwards only the calls that survived.

> **Think of it as a hotel front desk.**
> Guests don't wander straight to the rooms. They stop at reception, which
> checks their booking, hands over a key card that only opens *their* room,
> writes their arrival in the log, and turns away anyone without a reservation.
> The rooms themselves have no idea any of this happened.

Your FastAPI is the room. It just does its job, assuming whoever knocked was
already checked.

### What APIM actually does for you

| Job | What it means | What you'd otherwise write |
|---|---|---|
| **Authentication** | Verify the token is genuine | JWT signature + expiry + audience checks, in every API |
| **Rate limiting** | "Max 100 calls a minute" | A counter, shared across all your servers |
| **Caching** | Repeat questions answered instantly | Your own cache layer |
| **Logging** | Every call recorded | Logging plumbing in every service |
| **Hiding the backend** | The world never learns your real server address | A separate reverse proxy |
| **Versioning** | `/v1` and `/v2` live side by side | Routing logic in your app |
| **Transformation** | Rewrite headers, strip fields | Middleware in every API |

### The name for this pattern
APIM is an **API gateway**. "Gateway" is the general term — APIM is Azure's
specific product. AWS calls theirs API Gateway; open-source ones include Kong
and Nginx. Same idea everywhere: **one guarded door in front of many services.**

---

## Putting it together: one call, start to finish

A colleague's web app wants a price for a 2000 sqft house. Here is every step:

```
1. App    -> ADFS      "I'm the pricing web app. Here's my secret. Give me a token."
2. ADFS   -> App       "Verified. Here's a JWT. It expires in 1 hour."
                        Inside: who you are, your groups, expiry, and a SIGNATURE.

3. App    -> APIM      POST /predict  {"size_sqft":2000,...}
                       Header:  Authorization: Bearer eyJhbGciOi...

4. APIM                Opens the token. Fetches ADFS's PUBLIC KEY (once, then caches).
                       Checks: signature genuine? not expired? audience = our API?
                       Checks: has this caller exceeded 100 calls/min?
                       -> any failure: reply 401 or 429. FastAPI is NEVER contacted.

5. APIM   -> FastAPI   Forwards the call to the real backend.
6. FastAPI             Runs model.predict(). Returns 465276.13.
7. APIM   -> App       Passes the answer back, stripping internal headers.
```

**Step 4 is the whole value.** A bad caller is stopped by Azure's infrastructure
before it ever touches your Python. Your code never sees the attack.

### How the signature check works (no magic involved)
This is the one piece of cryptography worth understanding:

1. ADFS signs each token with a **private key** only ADFS possesses.
2. ADFS publishes the matching **public key** at a public URL.
3. APIM downloads that public key and uses it to verify the signature.
4. The public key can only **check** signatures, never **create** them.

So an attacker can download the public key too — and it does them no good. They
still cannot forge a token, because they don't have the private key. And if they
edit even one character of a real token, the signature stops matching.

That published URL is exactly the `<openid-config url="..."/>` line in the
policy. You are telling APIM: *"here is where to find the passport office's
official stamp, so you can recognise a real passport."*

---

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
az apim create \
  --name house-price-apim \
  --resource-group rg-azureml-demo \
  --publisher-name "My Company" \
  --publisher-email [EMAIL_ADDRESS] \
  --sku-name Consumption \
  --location eastus
```

### 3. Import your API into APIM

> 🛑 **Stop — this step and the two after it need your API to have a public
> address, and `localhost` will not do.** APIM runs in Azure and cannot reach
> your laptop.
>
> **👉 Work through [`CONNECTING_API_TO_APIM.md`](CONNECTING_API_TO_APIM.md)
> instead.** It covers where to actually put the API (dev tunnel, Azure Container
> Instances, or App Service), how to export the OpenAPI spec **without a running
> server**, and the FastAPI-3.1-vs-APIM-3.0 problem that breaks the import below.
>
> The commands here are the shape of the thing; that file is the working version.

```bash
# FastAPI publishes an OpenAPI spec at /openapi.json describing every endpoint.
# APIM can read that file and configure itself -- no manual endpoint entry.
# NOTE: --specification-url needs a URL APIM CAN REACH. See the file above for
# the offline alternative (--specification-path).
az apim api import \
  --resource-group rg-azureml-demo \
  --service-name house-price-apim \
  --path houseprice \
  --specification-format OpenApi \
  --specification-url https://hmk5m4mn-8000.jpe1.devtunnels.ms/openapi.json \
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
**Azure ML Jobs** — we hand this pipeline to Azure to run on its own machines,
and watch it draw itself as a clickable flowchart in the Azure ML Studio.
Docker follows in Part 8.
