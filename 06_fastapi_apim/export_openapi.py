"""
Export the FastAPI OpenAPI spec to a file that Azure APIM can import.

WHY THIS FILE EXISTS
    APIM can configure itself from your API's OpenAPI spec, so you don't have to
    type every endpoint into the portal by hand.

    Two problems get in the way, and this script solves both:

    PROBLEM 1: `az apim api import --specification-url` needs a URL APIM can
    REACH. If your API is only on localhost, APIM cannot fetch it. But you do
    not actually need a running server -- FastAPI can produce the spec straight
    from your Python code. We write it to a file and import with
    `--specification-path` instead.

    PROBLEM 2: FastAPI 0.140+ emits **OpenAPI 3.1.0**, and APIM's importer has
    historically only accepted 3.0.x. Worse, simply editing the version string
    is not enough: 3.1 writes `exclusiveMinimum` as a NUMBER, while 3.0 expects
    a BOOLEAN alongside `minimum`. That mismatch comes from perfectly ordinary
    validation like `Field(..., gt=0)` in main.py.

    This script downgrades those constructs properly.

HOW TO RUN
    cd house-price
    python ../06_fastapi_apim/export_openapi.py

    -> writes openapi-3.0.json next to this script
"""

import json
import sys
from pathlib import Path

# Make `house_price` importable without installing anything.
PROJECT_ROOT = Path(__file__).resolve().parents[1] / "house-price"
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from house_price.main import app  # noqa: E402


def downgrade_3_1_to_3_0(node):
    """Walk the spec and rewrite the 3.1-only bits that APIM rejects.

    We only fix the constructs FastAPI actually produces:

      1. exclusiveMinimum/Maximum as a NUMBER  (3.1)
         -> minimum/maximum + exclusiveMinimum: true   (3.0)

      2. type: ["string", "null"]              (3.1)
         -> type: "string" + nullable: true             (3.0)
    """
    if isinstance(node, dict):
        # --- fix 1: exclusive bounds ---
        for bound, pair in (("exclusiveMinimum", "minimum"),
                            ("exclusiveMaximum", "maximum")):
            if isinstance(node.get(bound), (int, float)):
                node[pair] = node.pop(bound)
                node[bound] = True

        # --- fix 2: nullable unions ---
        t = node.get("type")
        if isinstance(t, list):
            non_null = [x for x in t if x != "null"]
            if len(non_null) == 1:
                node["type"] = non_null[0]
                if "null" in t:
                    node["nullable"] = True

        for value in node.values():
            downgrade_3_1_to_3_0(value)

    elif isinstance(node, list):
        for item in node:
            downgrade_3_1_to_3_0(item)

    return node


spec = app.openapi()
print(f"FastAPI produced OpenAPI {spec['openapi']}")

spec["openapi"] = "3.0.3"
spec = downgrade_3_1_to_3_0(spec)

out = Path(__file__).resolve().parent / "openapi-3.0.json"
out.write_text(json.dumps(spec, indent=2), encoding="utf-8")

print(f"Wrote {out.name} as OpenAPI {spec['openapi']}")
print("Endpoints included:")
for path in spec["paths"]:
    print(f"  {path}")
print("\nImport it with:")
print("  az apim api import --specification-path 06_fastapi_apim/openapi-3.0.json \\")
print("    --specification-format OpenApiJson --path houseprice \\")
print("    --api-id house-price-api -g <rg> --service-name <apim>")
