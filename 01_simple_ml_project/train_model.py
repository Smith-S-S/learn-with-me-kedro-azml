"""
STEP 2 of our ML project: Train a Linear Regression model.

WHAT this file does:
    1. Reads the house data we created.
    2. Splits it into a "training" part and a "testing" part.
    3. Teaches a Linear Regression model to predict price from the features.
    4. Checks how good the model is on data it has NEVER seen.
    5. Saves the trained model to a file so we can reuse it later.

WHY Linear Regression:
    It is the simplest useful ML model. It just draws the best straight-line
    relationship between the inputs (size, bedrooms, age) and the output (price).
    It literally tries to relearn the hidden rule we wrote in generate_data.py.
"""

import joblib               # used to save/load the trained model to a file
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

# --- 1. Load the data ---
data = pd.read_csv("house_data.csv")

# X = the inputs (what we know).  y = the answer we want to predict (price).
# Why separate them: the model needs to know which columns are questions
# and which column is the answer.
X = data[["size_sqft", "num_bedrooms", "age_years"]]
y = data["price"]

# --- 2. Split into training and testing sets ---
# WHY: If we test the model on the same data it learned from, it can "cheat"
# by memorising. We hold back 20% of houses so we can test on FRESH examples,
# which tells us how it will do on real, unseen houses.
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# --- 3. Train (a.k.a. "fit") the model ---
# .fit() is the actual learning step: it finds the best numbers (coefficients).
model = LinearRegression()
model.fit(X_train, y_train)

# --- 4. Evaluate the model on the unseen test houses ---
predictions = model.predict(X_test)

mae = mean_absolute_error(y_test, predictions)   # average dollars we are "off" by
r2 = r2_score(y_test, predictions)               # 1.0 = perfect, 0.0 = useless

print("=== Model results ===")
print(f"Mean Absolute Error: ${mae:,.0f}  (average prediction miss)")
print(f"R^2 score:           {r2:.3f}       (closer to 1.0 is better)")

# --- Show what the model LEARNED ---
# Remember our hidden rule: +200 per sqft, +10000 per bedroom, -1500 per year.
# The model should discover numbers close to these on its own!
print("\n=== What the model learned (compare to our hidden rule) ===")
for feature, coefficient in zip(X.columns, model.coef_):
    print(f"  {feature:15s}: {coefficient:>12,.1f}")
print(f"  {'base value':15s}: {model.intercept_:>12,.1f}")

# --- 5. Save the trained model to a file ---
# WHY: training can be slow/expensive. We save the finished model so later steps
# (or a website, or Azure) can just LOAD it and make predictions instantly.
joblib.dump(model, "house_price_model.joblib")
print("\nSaved trained model to house_price_model.joblib")

# --- Bonus: use the model to predict a brand-new house ---
new_house = pd.DataFrame(
    {"size_sqft": [2000], "num_bedrooms": [3], "age_years": [10]}
)
predicted_price = model.predict(new_house)[0]
print(f"\nPredicted price for a 2000 sqft, 3-bed, 10-year-old house: ${predicted_price:,.0f}")
