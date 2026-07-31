"""Pandera schema for a raw Price Paid file. A file that fails here never
reaches the dataset."""

import pandera.pandas as pa

# monthly updates are usually 40k-100k rows; anything tiny means a truncated
# or wrong file
MIN_ROWS = 1_000

schema = pa.DataFrameSchema(
    columns={
        "transaction_id": pa.Column(str, nullable=False),
        "price": pa.Column(int, pa.Check.in_range(100, 500_000_000)),
        "date": pa.Column("datetime64[ns]", nullable=False),
        "postcode": pa.Column(str, nullable=True),
        "property_type": pa.Column(str, pa.Check.isin(["D", "S", "T", "F", "O"])),
        "new_build": pa.Column(str, pa.Check.isin(["Y", "N"])),
        "duration": pa.Column(str, pa.Check.isin(["F", "L", "U"])),
        "ppd_category": pa.Column(str, pa.Check.isin(["A", "B"])),
        "record_status": pa.Column(str, pa.Check.isin(["A", "C", "D"])),
    },
    checks=pa.Check(lambda df: len(df) >= MIN_ROWS, error=f"fewer than {MIN_ROWS} rows"),
    strict=False,
)
