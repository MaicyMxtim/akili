"""Train a price model from parquet in MinIO, log everything to MLflow.

Usage: python train.py --train-data s3://... --test-data s3://... [params]
"""

import argparse
import os

import lightgbm as lgb
import mlflow
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error

CATEGORICAL = [
    "property_type", "new_build", "duration",
    "postcode_area", "postcode_outward", "town", "district", "county",
]
AREA_FEATURES = ["median_price_90d", "sales_count_90d"]
FEATURES = CATEGORICAL + ["month"] + AREA_FEATURES


def storage_options() -> dict:
    return {
        "key": os.environ["AWS_ACCESS_KEY_ID"],
        "secret": os.environ["AWS_SECRET_ACCESS_KEY"],
        "client_kwargs": {"endpoint_url": os.environ["MLFLOW_S3_ENDPOINT_URL"]},
    }


def load(path: str, use_area: bool = False) -> pd.DataFrame:
    df = pd.read_parquet(path, storage_options=storage_options())
    df = df[df["ppd_category"] == "A"]
    df = df[df["price"].between(10_000, 5_000_000)]
    df = df.dropna(subset=["postcode"])
    outward = df["postcode"].str.split(" ").str[0]
    df["postcode_outward"] = outward
    df["postcode_area"] = outward.str.extract(r"^([A-Z]+)")
    df["month"] = df["date"].dt.month
    for col in CATEGORICAL:
        df[col] = df[col].astype("category")
    return add_area_features(df) if use_area else df


def add_area_features(df: pd.DataFrame) -> pd.DataFrame:
    """Point-in-time join of area price features.

    Same semantics as feast get_historical_features (most recent snapshot at
    or before each sale date, within ttl), done with merge_asof because the
    feast file offline store is minutes-per-run at this row count. Feast
    remains the definition registry and the online store; equivalence of the
    join was verified against feast on samples in Phase 7.
    """
    features = pd.read_parquet(
        os.environ.get("FEATURES_PATH", "s3://akili-data/features/area_price_stats.parquet"),
        storage_options=storage_options(),
    ).sort_values("event_timestamp")
    out = df.sort_values("date").reset_index(drop=True)
    # merge_asof needs matching key dtypes; join on plain strings
    out["postcode_outward"] = out["postcode_outward"].astype(str)
    joined = pd.merge_asof(
        out,
        features.rename(columns={"outward": "postcode_outward"}),
        left_on="date", right_on="event_timestamp",
        by="postcode_outward",
        tolerance=pd.Timedelta(days=62),
    )
    joined["postcode_outward"] = joined["postcode_outward"].astype("category")
    covered = joined[AREA_FEATURES[0]].notna().mean()
    print(f"area features joined, coverage {covered:.1%}")
    return joined.drop(columns=["event_timestamp"])


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--train-data", required=True)
    p.add_argument("--test-data", required=True)
    p.add_argument("--n-estimators", type=int, default=500)
    p.add_argument("--learning-rate", type=float, default=0.05)
    p.add_argument("--num-leaves", type=int, default=63)
    # measured 2026-07-31: area features WORSEN MAE (95.6k vs 93.2k), the
    # outward-code categorical already carries area price level at this data
    # volume. Kept available for future data regimes.
    p.add_argument("--use-area-features", default="false")
    args = p.parse_args()

    global FEATURES
    use_area = args.use_area_features.lower() == "true"
    if not use_area:
        FEATURES = CATEGORICAL + ["month"]

    train, test = load(args.train_data, use_area), load(args.test_data, use_area)
    # align category levels so the model sees consistent encodings
    for col in CATEGORICAL:
        cats = train[col].cat.categories
        test[col] = pd.Categorical(test[col], categories=cats)

    mlflow.set_experiment("price-model")
    with mlflow.start_run():
        mlflow.log_params({
            "n_estimators": args.n_estimators,
            "learning_rate": args.learning_rate,
            "num_leaves": args.num_leaves,
            "train_data": args.train_data,
            "test_data": args.test_data,
            "train_rows": len(train),
            "test_rows": len(test),
        })
        model = lgb.LGBMRegressor(
            n_estimators=args.n_estimators,
            learning_rate=args.learning_rate,
            num_leaves=args.num_leaves,
            random_state=42,
            verbose=-1,
        )
        model.fit(train[FEATURES], np.log(train["price"]))

        pred = np.exp(model.predict(test[FEATURES]))
        ape = (pred - test["price"]).abs() / test["price"]
        metrics = {
            "mae": float(mean_absolute_error(test["price"], pred)),
            "median_ape_pct": float(ape.median() * 100),
            "within_20pct": float((ape <= 0.20).mean() * 100),
        }
        mlflow.log_metrics(metrics)
        mlflow.lightgbm.log_model(model, name="model")
        print({k: round(v, 2) for k, v in metrics.items()})


if __name__ == "__main__":
    main()
