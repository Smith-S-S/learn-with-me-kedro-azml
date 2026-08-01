"""
NODES = the individual "worker functions" of our pipeline.

Think of a node as one station on an assembly line. Each function below does
ONE small job and hands its result to the next station. Notice these are just
plain Python functions -- Kedro does NOT force you to learn a weird new language.
This is the SAME house-price logic from Part 1, just split into tidy stations.
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score


def create_house_data(n_houses: int, seed: int, message: dict) -> pd.DataFrame:
    """STATION 1: invent the dummy house dataset (same hidden rule as Part 1)."""
    rng = np.random.default_rng(seed=seed)

    size_sqft = rng.integers(low=500, high=3500, size=n_houses)
    num_bedrooms = rng.integers(low=1, high=6, size=n_houses)
    age_years = rng.integers(low=0, high=40, size=n_houses)
    noise = rng.normal(loc=0, scale=15000, size=n_houses)

    price = (
        50000
        + 200 * size_sqft
        + 10000 * num_bedrooms
        - 1500 * age_years
        + noise
    )

    return pd.DataFrame(
        {
            "size_sqft": size_sqft,
            "num_bedrooms": num_bedrooms,
            "age_years": age_years,
            "price": price.round(0),
        }
    )


def split_data(data: pd.DataFrame, parameters: dict) -> tuple:
    """STATION 2: split the table into training inputs/answers and test inputs/answers."""
    from sklearn.model_selection import train_test_split

    features = parameters["features"]   # e.g. ["size_sqft", "num_bedrooms", "age_years"]
    target = parameters["target"]       # e.g. "price"

    X = data[features]
    y = data[target]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=parameters["test_size"],
        random_state=parameters["random_state"],
    )
    return X_train, X_test, y_train, y_test


def train_model(X_train: pd.DataFrame, y_train: pd.Series) -> LinearRegression:
    """STATION 3: teach the Linear Regression model (the actual learning step)."""
    model = LinearRegression()
    model.fit(X_train, y_train)
    return model


def evaluate_model(
    model: LinearRegression, X_test: pd.DataFrame, y_test: pd.Series
) -> dict:
    """STATION 4: score the model on houses it never saw, and return the metrics."""
    predictions = model.predict(X_test)
    mae = float(mean_absolute_error(y_test, predictions))
    r2 = float(r2_score(y_test, predictions))

    # Kedro shows anything we `logger.info` in the run output.
    import logging

    logger = logging.getLogger(__name__)
    logger.info("Mean Absolute Error: $%s", f"{mae:,.0f}")
    logger.info("R^2 score: %.3f (closer to 1.0 is better)", r2)

    return {"mae": mae, "r2": r2}

def say_hi_at_start(message: str, metrics: dict = None)-> str:
    """STATION 0: Say hello at the start or end of the pipeline."""
    import logging
    logger = logging.getLogger(__name__)
    if message == "start":
        logger.info("===============> pipeline is starting <=====================")
        return "Jio hotstar"
    else:
        logger.info("===============> pipeline is ended <=====================")
        return "Happy Ending"

