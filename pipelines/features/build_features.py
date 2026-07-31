"""Compute rolling area price features from raw Price Paid parquet.

For each postcode outward code, monthly snapshots of the trailing 90-day
median sale price and sale count. Output parquet becomes the Feast offline
source; each row carries the snapshot date as event_timestamp so training
joins are point-in-time correct.

Usage: python build_features.py s3://akili-data/raw/pp/2025-12/pp.parquet [more...]
"""

import os
import sys

import pandas as pd


def storage_options() -> dict:
    return {
        "key": os.environ["AWS_ACCESS_KEY_ID"],
        "secret": os.environ["AWS_SECRET_ACCESS_KEY"],
        "client_kwargs": {"endpoint_url": os.environ["MINIO_ENDPOINT"]},
    }


def main() -> None:
    sources = sys.argv[1:]
    frames = []
    for src in sources:
        df = pd.read_parquet(
            src, columns=["price", "date", "postcode", "ppd_category"],
            storage_options=storage_options(),
        )
        df = df[df["ppd_category"] == "A"].dropna(subset=["postcode"])
        df["outward"] = df["postcode"].str.split(" ").str[0]
        frames.append(df[["date", "outward", "price"]])
    sales = pd.concat(frames).sort_values("date")
    print(f"{len(sales)} sales across {sales['outward'].nunique()} outward codes")

    # monthly snapshot dates over the span of the data
    start = sales["date"].min() + pd.offsets.MonthEnd(3)
    snapshots = pd.date_range(start, sales["date"].max(), freq="ME")

    rows = []
    for snap in snapshots:
        window = sales[(sales["date"] > snap - pd.Timedelta(days=90)) & (sales["date"] <= snap)]
        g = window.groupby("outward")["price"]
        stats = pd.DataFrame({
            "median_price_90d": g.median(),
            "sales_count_90d": g.count(),
        }).reset_index()
        stats["event_timestamp"] = snap
        rows.append(stats)
    features = pd.concat(rows)
    features["sales_count_90d"] = features["sales_count_90d"].astype("int64")
    dest = "s3://akili-data/features/area_price_stats.parquet"
    features.to_parquet(dest, index=False, storage_options=storage_options())
    print(f"wrote {len(features)} feature rows ({len(snapshots)} snapshots) to {dest}")


if __name__ == "__main__":
    main()
