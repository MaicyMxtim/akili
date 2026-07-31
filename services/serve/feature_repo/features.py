"""Feast definitions: area price statistics keyed by postcode outward code."""

import os
from datetime import timedelta

from feast import Entity, FeatureView, Field, FileSource, ValueType
from feast.types import Float64, Int64

outward = Entity(
    name="outward",
    join_keys=["outward"],
    value_type=ValueType.STRING,
    description="postcode outward code, e.g. SW1A",
)

area_price_source = FileSource(
    name="area_price_stats_source",
    path=os.environ.get(
        "FEATURES_PATH", "s3://akili-data/features/area_price_stats.parquet"
    ),
    timestamp_field="event_timestamp",
    s3_endpoint_override=os.environ.get("MINIO_ENDPOINT"),
)

area_price_stats = FeatureView(
    name="area_price_stats",
    entities=[outward],
    # snapshots are monthly; 62 days tolerates a late month without serving
    # features older than two snapshots
    ttl=timedelta(days=62),
    schema=[
        Field(name="median_price_90d", dtype=Float64),
        Field(name="sales_count_90d", dtype=Int64),
    ],
    online=True,
    source=area_price_source,
)
