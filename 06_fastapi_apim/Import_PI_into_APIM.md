## Import the API into APIM

FastAPI automatically generates an OpenAPI specification describing our API.

We use that specification to create the API in Azure API Management (APIM).

### 1. Generate the OpenAPI file

We don't need a running server to generate the OpenAPI file.

From the project root:

```bash
cd house-price
python ../06_fastapi_apim/export_openapi.py
```

The script produces:

```text
FastAPI produced OpenAPI 3.1.0
Wrote openapi-3.0.json as OpenAPI 3.0.3

Endpoints included:
  /health
  /predict
  /metrics
  /pipeline/run
```

The generated file is:

```text
06_fastapi_apim/openapi-3.0.json
```

### 2. Why do we need `export_openapi.py`?

Newer versions of FastAPI generate an OpenAPI 3.1.x document.

For this project, we want an OpenAPI 3.0.3 document because APIM's importer may reject some OpenAPI 3.1 schema constructs.

For example, OpenAPI 3.1 can represent `exclusiveMinimum` differently from OpenAPI 3.0:

```json
// OpenAPI 3.1
{
  "exclusiveMinimum": 0
}
```

OpenAPI 3.0 uses:

```json
// OpenAPI 3.0
{
  "minimum": 0.0,
  "exclusiveMinimum": true
}
```

So we don't simply change the version number.

`export_openapi.py` converts the FastAPI-generated specification into a valid OpenAPI 3.0.3 document.

### 3. Import the OpenAPI file into APIM

We use `--specification-path` because the OpenAPI file is already on our computer.

```bash
az apim api import \
  --resource-group rg-azureml-demo \
  --service-name house-price-apim \
  --path houseprice \
  --api-id house-price-api \
  --specification-format OpenApiJson \
  --specification-path 06_fastapi_apim/openapi-3.0.json
```

This tells APIM:

> "Here is the description of my API. Create these endpoints."

APIM imports:

```text
GET  /health
POST /predict
GET  /metrics
POST /pipeline/run
```

### 4. Why use `--specification-path`?

`--specification-path` means:

> "The OpenAPI file is on my local computer."

The flow is:

```text
Your computer
     |
     | openapi-3.0.json
     ↓
Azure CLI
     |
     ↓
Azure APIM
```

We don't need to make the OpenAPI file publicly available.

### 5. What about `--specification-url`?

There is another option:

```text
--specification-url
```

This means:

> "The OpenAPI file is available at this URL. Download it."

For example:

```bash
az apim api import \
  --resource-group rg-azureml-demo \
  --service-name house-price-apim \
  --path houseprice \
  --api-id house-price-api \
  --specification-format OpenApiJson \
  --specification-url https://example.com/openapi-3.0.json
```

We did **not** use this method for our setup.

The important difference is:

```text
--specification-path
→ OpenAPI file is on your computer

--specification-url
→ OpenAPI file is available from a URL
```

Do not normally use both at the same time. Choose one.

For our project, we use:

```text
--specification-path
```

### 6. Tell APIM where the real FastAPI backend is

Importing the OpenAPI file tells APIM **what endpoints exist**.

It does not tell APIM where the actual FastAPI application is running.

Our FastAPI application is running through a Dev Tunnel:

```text
https://6cprkb5p-8000.jpe1.devtunnels.ms
```

Set this as the APIM backend/service URL:

```bash
az apim api update \
  --resource-group rg-azureml-demo \
  --service-name house-price-apim \
  --api-id house-price-api \
  --service-url https://6cprkb5p-8000.jpe1.devtunnels.ms
```

The important option is:

```text
--service-url
```

It means:

> "When APIM receives an API request, send it to this backend."

### 7. The difference between the two commands

These two commands do two different jobs.

#### OpenAPI import

```bash
az apim api import \
  --resource-group rg-azureml-demo \
  --service-name house-price-apim \
  --path houseprice \
  --api-id house-price-api \
  --specification-format OpenApiJson \
  --specification-path 06_fastapi_apim/openapi-3.0.json
```

Means:

> **"What APIs do I have?"**

APIM learns:

```text
/health
/predict
/metrics
/pipeline/run
```

#### Backend configuration

```bash
az apim api update \
  --resource-group rg-azureml-demo \
  --service-name house-price-apim \
  --api-id house-price-api \
  --service-url https://6cprkb5p-8000.jpe1.devtunnels.ms
```

Means:

> **"Where is my real API running?"**

APIM learns:

```text
Backend:
https://6cprkb5p-8000.jpe1.devtunnels.ms
```

### 8. Final architecture

After both steps, the setup looks like this:

```text
                    Azure APIM
                        |
                        |
              /houseprice/health
              /houseprice/predict
              /houseprice/metrics
              /houseprice/pipeline/run
                        |
                        ↓
                  Service URL
                        |
                        ↓
        https://6cprkb5p-8000.jpe1.devtunnels.ms
                        |
                        ↓
                   Dev Tunnel
                        |
                        ↓
                     Docker
                        |
                        ↓
                    FastAPI
                        |
                        ↓
                   ML Model
```

### 9. Test the backend directly

Before testing through APIM, make sure FastAPI itself works:

```bash
curl -i https://6cprkb5p-8000.jpe1.devtunnels.ms/health
```

Expected:

```json
{
  "status": "ok",
  "model_loaded": false
}
```

This proves:

```text
Dev Tunnel → FastAPI
```

is working.

### 10. Test through APIM

APIM requires a subscription key because:

```text
subscriptionRequired: true
```

Use your APIM subscription key:

```bash
curl -i \
  -H "Ocp-Apim-Subscription-Key: YOUR_APIM_SUBSCRIPTION_KEY" \
  https://house-price-apim.azure-api.net/houseprice/health
```

The flow is now:

```text
Client
   |
   | /houseprice/health
   ↓
Azure APIM
   |
   | Check subscription key
   |
   | Forward to service URL
   ↓
Dev Tunnel
   |
   ↓
FastAPI
   |
   | /health
   ↓
{"status":"ok","model_loaded":false}
```

### 11. The important idea to remember

There are **three separate things**:

```text
1. OpenAPI file
   ↓
   Tells APIM what endpoints exist.

2. Service URL
   ↓
   Tells APIM where FastAPI is running.

3. Subscription key
   ↓
   Proves that the caller is allowed to use APIM.
```

So:

```text
OpenAPI file
    = WHAT does my API have?

Service URL
    = WHERE is my API?

Subscription key
    = WHO is allowed to call it?
```
