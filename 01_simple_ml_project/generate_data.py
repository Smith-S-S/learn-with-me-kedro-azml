"""
STEP 1 of our ML project: Make a dummy dataset.

WHAT this file does:
    It invents some fake "house" data and saves it to a CSV file.

WHY we do this:
    A machine learning model learns from examples (data). We don't have a real
    dataset yet, so we create a pretend one. Because WE invent the hidden rule
    that connects house size to price, we can later check whether the model
    managed to "rediscover" that rule. That is a great way to learn.
"""

import numpy as np
import pandas as pd

# A "seed" makes the random numbers come out the SAME every time we run this.
# Why: so your results match mine and are repeatable (important in real projects).
rng = np.random.default_rng(seed=42)

# How many pretend houses to create.
n_houses = 200

# --- Invent the input features (the things we know about a house) ---
size_sqft = rng.integers(low=500, high=3500, size=n_houses)      # floor area
num_bedrooms = rng.integers(low=1, high=6, size=n_houses)        # 1 to 5 bedrooms
age_years = rng.integers(low=0, high=40, size=n_houses)          # how old the house is

# --- Invent the HIDDEN rule that decides the price ---
# price = base + (price per sqft) + (bonus per bedroom) - (penalty per year of age)
# We also add a little random "noise" so it looks like messy real-world data.
noise = rng.normal(loc=0, scale=15000, size=n_houses)

price = (
    50000                      # a base price every house starts with
    + 200 * size_sqft          # each square foot adds $200
    + 10000 * num_bedrooms     # each bedroom adds $10,000
    - 1500 * age_years         # each year of age removes $1,500
    + noise                    # random wobble
)

# Put everything into a table (a DataFrame is just a spreadsheet in Python).
data = pd.DataFrame(
    {
        "size_sqft": size_sqft,
        "num_bedrooms": num_bedrooms,
        "age_years": age_years,
        "price": price.round(0),   # round to whole dollars
    }
)

# Save the table to a file so the next step can read it.
output_file = "house_data.csv"
data.to_csv(output_file, index=False)

print(f"Created {output_file} with {len(data)} rows.")
print("\nHere are the first 5 houses:")
print(data.head())
