"""
main.py -- the FastAPI "front door" for our Kedro project.

WHAT THIS FILE IS
    Up to now, the only way to use our model was to sit at this computer and
    type `python -m kedro run`. That is fine for you, but useless for anyone
    else -- a website, a mobile app, or another team cannot "type a command"
    on your laptop.

    An API fixes that. It puts our model behind a web address (a URL) so ANY
    program, anywhere, can send it a house and get a price back.

THE FOUR DOORS (endpoints) WE OPEN

    GET  /health         "Are you alive?"          -- used by Kubernetes & APIM
    POST /predict        "Price this house."       -- the actual inference
    GET  /metrics        "How good is the model?"  -- reads the last training scores
    POST /pipeline/run   "Retrain yourself."       -- triggers the Kedro pipeline

JARGON, IN PLAIN WORDS
    API        A set of web addresses another program can call. Not a website
               for humans -- a website for other software.
    Endpoint   One such address, e.g. /predict.
    GET/POST   GET = "give me something" (no data sent). POST = "here is some
               data, do something with it."
    JSON       The text format APIs use to send data. Looks like a Python dict.
    Inference  A fancy word for "using a trained model to make a prediction".
               Training = learning. Inference = answering.
    Uvicorn    The little web server that actually runs FastAPI.

WHY THIS FILE LIVES INSIDE THE KEDRO PROJECT
    Because it reuses the Kedro catalog. It does NOT reopen the pickle file by
    hand with a hard-coded path -- it asks Kedro "give me the regressor", and
    Kedro handles where that file lives. So when the model moves to Azure Blob
    Storage in a later part, THIS FILE DOES NOT CHANGE. Only catalog.yml does.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from kedro.framework.session import KedroSession
from kedro.framework.startup import bootstrap_project
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# The Kedro project root = three folders up from this file
# (src/house_price/main.py -> src/house_price -> src -> project root).
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# bootstrap_project tells Kedro "this folder is a Kedro project" and reads
# pyproject.toml. It must run ONCE before we can open any KedroSession.
bootstrap_project(PROJECT_ROOT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Code that runs ONCE when the server boots, and once when it shuts down.

    Everything BEFORE `yield` runs at startup; everything AFTER runs at
    shutdown. We use it to load the model a single time, because reading a
    model from disk is slow and we do not want to repeat it on every request.

    (Older tutorials use `@app.on_event("startup")`. That is deprecated now --
    this `lifespan` function is the modern replacement.)
    """
    global _model
    try:
        _model = _load_model()
        logger.info("Model loaded successfully.")
    except Exception as exc:
        # We do NOT crash the server. A missing model is a normal state for a
        # fresh deployment -- you can call POST /pipeline/run to create one.
        logger.warning("Could not load a model at startup: %s", exc)
        _model = None

    yield  # <-- the server runs and serves requests here

    logger.info("Shutting down.")


app = FastAPI(
    title="House Price API",
    description="Predict house prices and retrain the Kedro pipeline over HTTP.",
    version="1.0.0",
    lifespan=lifespan,
)

app.openapi_version = "3.0.3"

# =============================================================================
# THE SHAPE OF THE DATA (Pydantic models)
# -----------------------------------------------------------------------------
# Pydantic checks incoming JSON for us. If someone sends a house with a missing
# field, or text where a number belongs, FastAPI rejects it automatically with a
# clear error -- our model code never sees the bad data. This is free validation.
# =============================================================================
class HouseRequest(BaseModel):
    """One house we want a price for."""

    size_sqft: float = Field(..., gt=0, description="Floor area in square feet")
    num_bedrooms: int = Field(..., ge=0, description="Number of bedrooms")
    age_years: float = Field(..., ge=0, description="Age of the house in years")

    # This example shows up in the auto-generated docs page. Nice touch for users.
    model_config = {
        "json_schema_extra": {
            "example": {"size_sqft": 2000, "num_bedrooms": 3, "age_years": 10}
        }
    }


class PredictionResponse(BaseModel):
    """What we send back."""

    predicted_price: float
    currency: str = "USD"


# =============================================================================
# LOADING THE MODEL
# =============================================================================
def _load_model():
    """Ask the Kedro catalog for the newest trained model.

    Our catalog entry has `versioned: true`, so Kedro keeps a timestamped copy
    of every model it ever trained. Calling .load() gives us the LATEST one
    without us needing to know the timestamp.
    """
    with KedroSession.create(project_path=PROJECT_ROOT) as session:
        context = session.load_context()
        return context.catalog.load("regressor")


# The trained model is cached in this one variable, shared by every request, so
# we do not re-read it from disk each time. `lifespan` above fills it at startup.
_model = None


# =============================================================================
# THE ENDPOINTS
# =============================================================================
@app.get("/health")
def health():
    """DOOR 1: a heartbeat check.

    Kubernetes and Azure APIM call this constantly to decide whether this copy
    of the app is healthy enough to receive traffic. It must be fast and must
    never touch the model.
    """
    return {"status": "ok", "model_loaded": _model is not None}


@app.post("/predict", response_model=PredictionResponse)
def predict(house: HouseRequest):
    """DOOR 2: the actual inference -- turn one house into one price."""
    if _model is None:
        # 503 = "Service Unavailable". The correct code for "I am running but
        # not ready yet", as opposed to 500 which means "I crashed".
        raise HTTPException(
            status_code=503,
            detail="No trained model available. Call POST /pipeline/run first.",
        )

    # The model was trained on a table with these three columns IN THIS ORDER.
    # We must hand it the same shape, or the numbers get mixed up.
    import pandas as pd

    features = pd.DataFrame(
        [
            {
                "size_sqft": house.size_sqft,
                "num_bedrooms": house.num_bedrooms,
                "age_years": house.age_years,
            }
        ]
    )

    predicted = float(_model.predict(features)[0])
    return PredictionResponse(predicted_price=round(predicted, 2))


@app.get("/metrics")
def get_metrics():
    """DOOR 3: report how good the current model is (MAE and R^2).

    Reads the metrics.json that the evaluate_model node wrote during training.
    """
    try:
        with KedroSession.create(project_path=PROJECT_ROOT) as session:
            context = session.load_context()
            return context.catalog.load("metrics")
    except Exception as exc:
        raise HTTPException(
            status_code=404, detail=f"No metrics found yet: {exc}"
        )


def _run_pipeline():
    """The retraining job itself. Runs in the background, not in the request."""
    logger.info("Pipeline run starting...")
    # NOTE: a KedroSession is single-use -- you get ONE .run() per session.
    # So we open a brand new session for every retrain. This is by design.
    with KedroSession.create(project_path=PROJECT_ROOT) as session:
        session.run(pipeline_name="__default__")

    # After retraining, swap in the fresh model so /predict uses it immediately.
    global _model
    _model = _load_model()
    logger.info("Pipeline run finished; new model loaded.")


@app.post("/pipeline/run", status_code=202)
def run_pipeline(background_tasks: BackgroundTasks):
    """DOOR 4: trigger a full retrain over HTTP.

    WHY BackgroundTasks: training can take minutes. If we trained inside the
    request, the caller would sit there waiting and eventually time out. Instead
    we say "accepted, I have started" straight away and do the work afterwards.

    That is what status code 202 means: "Accepted, but not finished yet."
    (200 would wrongly promise the work is already done.)

    SECURITY NOTE: this endpoint is expensive and changes state, so it is
    exactly the kind of door you protect with APIM + ADFS in Part 6. Do not
    expose it to the open internet unprotected.
    """
    background_tasks.add_task(_run_pipeline)
    return {"status": "accepted", "detail": "Pipeline retraining started."}
