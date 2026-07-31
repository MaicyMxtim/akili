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
FEATURES = CATEGORICAL + ["month"]


def storage_options() -> dict:
    return {
        "key": os.environ["AWS_ACCESS_KEY_ID"],
        "secret": os.environ["AWS_SECRET_ACCESS_KEY"],
        "client_kwargs": {"endpoint_url": os.environ["MLFLOW_S3_ENDPOINT_URL"]},
    }


def load(path: str) -> pd.DataFrame:
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
    return df


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--train-data", required=True)
    p.add_argument("--test-data", required=True)
    p.add_argument("--n-estimators", type=int, default=500)
    p.add_argument("--learning-rate", type=float, default=0.05)
    p.add_argument("--num-leaves", type=int, default=63)
    args = p.parse_args()

    train, test = load(args.train_data), load(args.test_data)
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
