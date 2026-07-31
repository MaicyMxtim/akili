"""Drift check: compare a current window of sales against the training
reference and write a drift report.

Compares the distribution of price, property type and geography between the
reference dataset (what the champion trained on) and the comparison window.
Writes a JSON summary to MinIO and exits 1 if drift crosses the threshold,
so the workflow surfaces it (and Phase 9 wires that into retraining).

Usage: python drift_check.py <reference-parquet> <current-parquet>
"""

import json
import os
import sys

import pandas as pd
from evidently import Report
from evidently.presets import DataDriftPreset

COLUMNS = ["price", "property_type", "new_build", "duration", "county"]
DRIFT_SHARE_THRESHOLD = 0.5


def storage_options() -> dict:
    return {
        "key": os.environ["AWS_ACCESS_KEY_ID"],
        "secret": os.environ["AWS_SECRET_ACCESS_KEY"],
        "client_kwargs": {"endpoint_url": os.environ["MINIO_ENDPOINT"]},
    }


def load(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path, columns=COLUMNS + ["ppd_category"], storage_options=storage_options())
    df = df[df["ppd_category"] == "A"]
    return df[COLUMNS]


def main() -> None:
    reference_path, current_path = sys.argv[1], sys.argv[2]
    reference, current = load(reference_path), load(current_path)
    print(f"reference {len(reference)} rows vs current {len(current)} rows")

    report = Report([DataDriftPreset(drift_share=DRIFT_SHARE_THRESHOLD)])
    result = report.run(reference_data=reference, current_data=current)
    summary = result.dict()

    drifted = {}
    for metric in summary.get("metrics", []):
        mid = metric.get("metric_id", "")
        if mid.startswith("ValueDrift"):
            col = mid.split("column=")[-1].rstrip(")")
            drifted[col] = round(float(metric["value"]), 4)

    out = {
        "reference": reference_path,
        "current": current_path,
        "per_column_drift_score": drifted,
        "share_threshold": DRIFT_SHARE_THRESHOLD,
    }
    dest = "s3://akili-data/drift/latest_report.json"
    import s3fs
    fs = s3fs.S3FileSystem(
        key=os.environ["AWS_ACCESS_KEY_ID"], secret=os.environ["AWS_SECRET_ACCESS_KEY"],
        client_kwargs={"endpoint_url": os.environ["MINIO_ENDPOINT"]},
    )
    with fs.open(dest, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))

    drift_metric = next(
        (m for m in summary.get("metrics", []) if m.get("metric_id", "").startswith("DriftedColumnsCount")),
        None,
    )
    share = float(drift_metric["value"]["share"]) if drift_metric else 0.0
    print(f"drifted column share: {share}")
    if share >= DRIFT_SHARE_THRESHOLD:
        print("DRIFT DETECTED beyond threshold")
        sys.exit(1)
    print("no significant drift")


if __name__ == "__main__":
    main()
