"""Ingest one Price Paid file: download, validate, write parquet to MinIO.

Usage: python ingest.py <http-url-or-s3-path>

Env: MINIO_ENDPOINT, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
"""

import json
import os
import sys

import pandas as pd
import pandera.errors

from schema import schema

COLUMNS = [
    "transaction_id", "price", "date", "postcode", "property_type",
    "new_build", "duration", "paon", "saon", "street", "locality",
    "town", "district", "county", "ppd_category", "record_status",
]

BUCKET = "akili-data"


def storage_options() -> dict:
    return {
        "key": os.environ["AWS_ACCESS_KEY_ID"],
        "secret": os.environ["AWS_SECRET_ACCESS_KEY"],
        "client_kwargs": {"endpoint_url": os.environ["MINIO_ENDPOINT"]},
    }


def main() -> None:
    source = sys.argv[1]
    opts = storage_options() if source.startswith("s3://") else None
    df = pd.read_csv(source, names=COLUMNS, parse_dates=["date"], storage_options=opts)
    print(f"read {len(df)} rows from {source}")

    try:
        schema.validate(df, lazy=True)
    except pandera.errors.SchemaErrors as err:
        report = err.failure_cases.head(50).to_dict(orient="records")
        print("VALIDATION FAILED")
        print(json.dumps(report, indent=2, default=str))
        pd.DataFrame(err.failure_cases).to_csv(
            f"s3://{BUCKET}/rejected/failure_report.csv",
            index=False, storage_options=storage_options(),
        )
        sys.exit(1)

    month = df["date"].max().strftime("%Y-%m")
    dest = f"s3://{BUCKET}/raw/pp/{month}/pp.parquet"
    df.to_parquet(dest, index=False, storage_options=storage_options())
    print(f"validated and wrote {len(df)} rows to {dest}")


if __name__ == "__main__":
    main()
