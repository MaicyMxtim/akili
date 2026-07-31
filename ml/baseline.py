"""Phase 0 baseline: raw Price Paid CSV in, scored LightGBM model out.

Usage: python ml/baseline.py data/pp-2025.csv
"""

import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error

COLUMNS = [
    "transaction_id", "price", "date", "postcode", "property_type",
    "new_build", "duration", "paon", "saon", "street", "locality",
    "town", "district", "county", "ppd_category", "record_status",
]

CATEGORICAL = [
    "property_type", "new_build", "duration",
    "postcode_area", "postcode_outward", "town", "district", "county",
]

# last 3 months of the file are the holdout
TEST_MONTHS = 3


def load(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, names=COLUMNS, parse_dates=["date"])
    # category A = standard price paid sales; B is repossessions, buy-to-let
    # portfolios and other odd sales that would skew the target
    df = df[df["ppd_category"] == "A"]
    df = df[df["price"].between(10_000, 5_000_000)]
    df = df.dropna(subset=["postcode"])
    return df


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    outward = df["postcode"].str.split(" ").str[0]
    df["postcode_outward"] = outward
    df["postcode_area"] = outward.str.extract(r"^([A-Z]+)")
    df["month"] = df["date"].dt.month
    for col in CATEGORICAL:
        df[col] = df[col].astype("category")
    return df


def split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cutoff = df["date"].max().to_period("M") - TEST_MONTHS + 1
    test_start = cutoff.to_timestamp()
    train = df[df["date"] < test_start]
    test = df[df["date"] >= test_start]
    return train, test


def main() -> None:
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/pp-2025.csv"
    df = add_features(load(csv_path))
    train, test = split(df)
    features = CATEGORICAL + ["month"]

    model = lgb.LGBMRegressor(
        n_estimators=500,
        learning_rate=0.05,
        num_leaves=63,
        random_state=42,
        verbose=-1,
    )
    # train on log price: the target spans 10k to 5M and errors on cheap
    # houses matter as much as errors on expensive ones
    model.fit(train[features], np.log(train["price"]))

    pred = np.exp(model.predict(test[features]))
    actual = test["price"]
    ape = (pred - actual).abs() / actual

    metrics = {
        "train_rows": len(train),
        "test_rows": len(test),
        "train_period": f"{train['date'].min():%Y-%m} to {train['date'].max():%Y-%m}",
        "test_period": f"{test['date'].min():%Y-%m} to {test['date'].max():%Y-%m}",
        "mae": round(float(mean_absolute_error(actual, pred)), 2),
        "median_ape_pct": round(float(ape.median() * 100), 2),
        "within_20pct": round(float((ape <= 0.20).mean() * 100), 2),
    }

    out = Path("models")
    out.mkdir(exist_ok=True)
    model.booster_.save_model(out / "baseline.txt")
    (out / "baseline_metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
