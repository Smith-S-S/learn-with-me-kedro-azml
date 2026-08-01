"""
STEP 3b of our ML project: Check for DRIFT with Evidently.

WHAT this file does:
    Compares the OLD data (what the model learned from) with the NEW data
    (what is arriving today), and writes a colourful HTML report you open
    in your browser: drift_report.html

WHY this matters:
    A model is only good while the world looks like its training data.
    If today's houses are much bigger and newer than last year's houses,
    the model is answering a question it was never taught. Accuracy quietly
    rots. Nobody gets an error message -- that is what makes it dangerous.

    Drift detection is the smoke alarm. It tells you "retrain me".

JARGON TABLE
    Reference data : the OLD data. The baseline. Usually your training data.
    Current data   : the NEW data arriving now, that we want to judge.
    Data drift     : the INPUT columns changed shape (houses got bigger).
    Target drift   : the ANSWER column changed shape (prices went up).
    p-value        : a statistics score from 0 to 1 telling us how likely the
                     difference is just random luck. SMALL p-value (< 0.05)
                     = "this is a real change, not luck" = DRIFT DETECTED.
"""

import warnings

import pandas as pd
from evidently import Report
from evidently.presets import DataDriftPreset

# Hide a harmless maths warning from scipy. It happens because our new data has
# a bedroom count (6) that never appeared in the old data, so one bucket is
# empty and a division hits zero. It does not affect the result.
warnings.filterwarnings("ignore", message="divide by zero encountered")

# --- 1. Load both datasets ---
# reference = the past (what the model was trained on)
# current   = the present (what the model is being asked about now)
reference_data = pd.read_csv("house_data.csv")
current_data = pd.read_csv("house_data_new.csv")

print(f"Reference (old) data: {len(reference_data)} rows")
print(f"Current   (new) data: {len(current_data)} rows")

# --- 2. Build the report ---
# A "Preset" is a ready-made bundle of checks, so beginners don't have to pick
# statistical tests by hand. DataDriftPreset runs a suitable test on every column.
report = Report([DataDriftPreset()])

# .run() does the actual comparing.
result = report.run(reference_data=reference_data, current_data=current_data)

# --- 3. Save the visual report ---
output_file = "drift_report.html"
result.save_html(output_file)
print(f"\nSaved report to {output_file} -- open it in your browser.")

# --- 4. Also print a plain-text summary so you don't have to open the browser ---
# result.dict() turns the report into a normal Python dictionary of numbers.
summary = result.dict()

print("\n=== Drift summary ===")
for metric in summary["metrics"]:
    # "config" holds what this metric was measuring, e.g. which column.
    config = metric["config"]
    kind = config["type"]          # e.g. "evidently:metric_v2:ValueDrift"
    value = metric["value"]

    # Metric 1: how many columns drifted in total.
    if kind.endswith("DriftedColumnsCount"):
        print(f"Columns that drifted: {value['count']:.0f} out of {len(reference_data.columns)}")
        print(f"That is {value['share']:.0%} of all columns.\n")

    # Metric 2..N: one verdict per column, where value IS the p-value.
    elif kind.endswith("ValueDrift"):
        column = config["column"]
        method = config["method"]  # K-S for numbers, chi-square for categories
        verdict = "DRIFT!" if value < 0.05 else "no drift"
        print(f"  {column:15s} p-value={value:<12.2e} ({method:22s}) -> {verdict}")

print(
    "\nHow to read this: p-value below 0.05 means the column really changed.\n"
    "(2.00e-20 is scientific notation for 0.00000...2 -- basically zero.)\n"
    "If important columns drifted, the honest next step is to RETRAIN the model\n"
    "on fresh data -- which is exactly what a scheduled Kedro job does in Part 4."
)
