"""
STEP 4 of our ML project: Serve the model as an API.

WHAT this file does:
    Puts our trained model behind a web address so ANY program can ask it for
    a price -- not just you, typing commands on this laptop.

WHY this matters:
    Right now the model is a file (house_price_model.joblib) sitting on your
    disk. A file is useless to a website, a phone app, or another team. They
    cannot "run your Python script". They CAN send a web request.

    Turning a model into a web service is called SERVING or INFERENCE.

THE SMALLEST POSSIBLE VERSION:
    This is the beginner version -- one model, one endpoint, no Kedro.
    In Part 2 the same idea is done properly inside the Kedro project
    (see house-price/src/house_price/main.py), where it can also RETRAIN.

JARGON
    API       A "website for other programs" instead of for humans.
    Endpoint  One address on that API, e.g. /predict.
    GET       "Give me something."
    POST      "Here is data, do something with it."
    JSON      The text format APIs speak. Looks just like a Python dict.
"""

import joblib
import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, Field

# --- 1. Load the model ONCE, when the file is first run ---
# WHY once: reading from disk is slow. We do it a single time and keep the
# model in memory, so every prediction afterwards is instant.
model = joblib.load("house_price_model.joblib")

app = FastAPI(title="Simple House Price API")


# --- 2. Describe what a valid request looks like ---
# Pydantic checks the incoming JSON for us. If someone forgets a field or sends
# text where a number belongs, FastAPI rejects it with a clear message BEFORE
# our model ever sees it. Free input validation -- you write zero if-statements.
class House(BaseModel):
    size_sqft: float = Field(..., gt=0)     # gt=0 means "must be greater than 0"
    num_bedrooms: int = Field(..., ge=0)    # ge=0 means "must be 0 or more"
    age_years: float = Field(..., ge=0)


# --- 3. The endpoints (the "doors" into our service) ---
@app.get("/health")
def health():
    """A heartbeat. Cloud platforms call this to check the app is alive."""
    return {"status": "ok"}


@app.post("/predict")
def predict(house: House):
    """Take one house, return one predicted price."""
    # The model expects a table with the same 3 columns, in the same order,
    # that it was trained on. So we build a one-row table.
    features = pd.DataFrame(
        [
            {
                "size_sqft": house.size_sqft,
                "num_bedrooms": house.num_bedrooms,
                "age_years": house.age_years,
            }
        ]
    )
    price = float(model.predict(features)[0])
    return {"predicted_price": round(price, 2), "currency": "USD"}


# --- HOW TO RUN IT ---
#   pip install fastapi uvicorn
#   uvicorn serve_model:app --reload
#
# "serve_model:app" means: in the file serve_model.py, use the variable `app`.
# --reload restarts the server automatically when you edit the file.
#
# Then open http://127.0.0.1:8000/docs in your browser.
# FastAPI generates a full interactive test page for free -- you can click
# "Try it out" and send a house without writing any code at all.
#
# Or from a terminal:
#   curl -X POST http://127.0.0.1:8000/predict ^
#        -H "Content-Type: application/json" ^
#        -d "{\"size_sqft\":2000,\"num_bedrooms\":3,\"age_years\":10}"
