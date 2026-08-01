"""
STEP 3a of our ML project: Make "new" house data that arrived LATER.

WHAT this file does:
    It invents a second batch of fake houses and saves it to house_data_new.csv.

WHY we do this:
    Imagine our model was trained last year. Since then the world CHANGED:
    people are buying bigger, newer houses, and prices went up.
    The model has not been retrained, so it may now be guessing badly.

    This change in the incoming data is called DRIFT.
    To *see* drift we need two datasets:
        - the OLD data the model learned from  -> house_data.csv   ("reference")
        - the NEW data arriving today          -> house_data_new.csv ("current")

    Then in step 3b (check_drift.py) we let Evidently compare the two.
"""

import numpy as np
import pandas as pd

# Different seed = different random houses (this is a genuinely new batch).
rng = np.random.default_rng(seed=99)

n_houses = 200

# --- The DRIFT is right here ---
# Compare these numbers with generate_data.py and you can see what changed:
#
#   column        | old data (train) | new data (today)  | what happened
#   --------------|------------------|-------------------|-----------------------
#   size_sqft     | 500 .. 3500      | 1800 .. 4500      | houses got BIGGER
#   num_bedrooms  | 1 .. 5           | 3 .. 6            | more bedrooms
#   age_years     | 0 .. 40          | 0 .. 12           | houses are much NEWER
#
size_sqft = rng.integers(low=1800, high=4500, size=n_houses)
num_bedrooms = rng.integers(low=3, high=7, size=n_houses)
age_years = rng.integers(low=0, high=12, size=n_houses)

noise = rng.normal(loc=0, scale=15000, size=n_houses)

# The market also got more expensive: $260 per sqft instead of $200.
# So the PRICE drifted too, not just the inputs.
price = (
    50000
    + 260 * size_sqft          # <-- was 200 in the old data
    + 10000 * num_bedrooms
    - 1500 * age_years
    + noise
)

data = pd.DataFrame(
    {
        "size_sqft": size_sqft,
        "num_bedrooms": num_bedrooms,
        "age_years": age_years,
        "price": price.round(0),
    }
)

output_file = "house_data_new.csv"
data.to_csv(output_file, index=False)

print(f"Created {output_file} with {len(data)} rows (this is the 'new/today' data).")
print("\nFirst 5 new houses:")
print(data.head())
print("\nQuick comparison of the average house:")
old = pd.read_csv("house_data.csv")
comparison = pd.DataFrame(
    {"old data (training)": old.mean().round(0), "new data (today)": data.mean().round(0)}
)
print(comparison)
