"""Price prediction API. Loads the champion model from the MLflow registry
at startup and serves predictions.

LightGBM stores the training-time category mappings inside the model, so
inputs only need the same columns as category dtype; the model re-applies
its own encodings. Real train/serve feature consistency arrives with the
feature store in Phase 7.
"""

import logging
import os

import mlflow.lightgbm
import pandas as pd
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field

MODEL_URI = os.environ.get("MODEL_URI", "models:/price-model@champion")

logging.basicConfig(level=logging.INFO, format='{"level":"%(levelname)s","msg":"%(message)s"}')
log = logging.getLogger("serve")

app = FastAPI(title="akili price API")
Instrumentator().instrument(app).expose(app)
model = None
feature_store = None

CATEGORICAL = [
    "property_type", "new_build", "duration",
    "postcode_area", "postcode_outward", "town", "district", "county",
]
AREA_FEATURES = ["median_price_90d", "sales_count_90d"]


class PredictRequest(BaseModel):
    postcode: str = Field(examples=["SW1A 1AA"])
    property_type: str = Field(examples=["T"], description="D/S/T/F/O")
    new_build: str = Field(default="N", description="Y/N")
    duration: str = Field(default="F", description="F freehold, L leasehold")
    town: str = Field(examples=["LONDON"])
    district: str = Field(examples=["WESTMINSTER"])
    county: str = Field(examples=["GREATER LONDON"])
    month: int = Field(default=6, ge=1, le=12)


def dir_digest(path: str) -> str:
    import hashlib
    from pathlib import Path
    lines = []
    for f in sorted(Path(path).rglob("*")):
        if f.is_file():
            lines.append(f"{f.relative_to(path)}:{hashlib.sha256(f.read_bytes()).hexdigest()}")
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def verify_and_load():
    """Refuse to serve any model whose signature is missing or wrong."""
    import json
    from pathlib import Path

    import mlflow.artifacts
    import s3fs
    from cryptography.hazmat.primitives import serialization
    from mlflow import MlflowClient

    version = MlflowClient().get_model_version_by_alias("price-model", "champion").version
    local = mlflow.artifacts.download_artifacts(f"models:/price-model/{version}")
    fs = s3fs.S3FileSystem(
        key=os.environ["AWS_ACCESS_KEY_ID"], secret=os.environ["AWS_SECRET_ACCESS_KEY"],
        client_kwargs={"endpoint_url": os.environ["MLFLOW_S3_ENDPOINT_URL"]},
    )
    with fs.open(f"akili-mlflow/signatures/price-model-v{version}.json") as f:
        sig = json.load(f)
    digest = dir_digest(local)
    if digest != sig["digest"]:
        raise RuntimeError(f"model v{version} digest mismatch: artifact was modified after signing")
    pub = serialization.load_pem_public_key(
        Path(os.environ["MODEL_SIGNING_PUB_PATH"]).read_bytes()
    )
    pub.verify(bytes.fromhex(sig["signature"]), digest.encode())
    log.info(f"model v{version} signature verified ({digest[:12]}...)")
    return mlflow.lightgbm.load_model(local)


@app.on_event("startup")
def load_model() -> None:
    global model, feature_store
    if os.environ.get("MODEL_SIGNING_PUB_PATH"):
        model = verify_and_load()
    else:
        model = mlflow.lightgbm.load_model(MODEL_URI)
    log.info(f"loaded model {MODEL_URI}")
    import sys
    from feast import FeatureStore
    sys.path.insert(0, "feature_repo")
    from features import area_price_stats, outward as outward_entity
    feature_store = FeatureStore(repo_path="feature_repo")
    feature_store.apply([outward_entity, area_price_stats])
    log.info("feature store connected")


def area_features(outward: str) -> dict:
    """Latest area stats from the online store; missing areas predict
    without them (LightGBM handles NaN)."""
    try:
        vals = feature_store.get_online_features(
            features=[f"area_price_stats:{f}" for f in AREA_FEATURES],
            entity_rows=[{"outward": outward}],
        ).to_dict()
        return {f: vals[f][0] for f in AREA_FEATURES}
    except Exception as err:
        log.warning(f"online features unavailable: {err}")
        return {f: None for f in AREA_FEATURES}


@app.get("/healthz")
def healthz() -> dict:
    if model is None:
        raise HTTPException(status_code=503, detail="model not loaded")
    return {"status": "ok", "model": MODEL_URI}


@app.post("/predict")
def predict(req: PredictRequest) -> dict:
    if model is None:
        raise HTTPException(status_code=503, detail="model not loaded")
    outward = req.postcode.strip().upper().split(" ")[0]
    area = "".join(c for c in outward if c.isalpha())
    row = pd.DataFrame([{
        "property_type": req.property_type.upper(),
        "new_build": req.new_build.upper(),
        "duration": req.duration.upper(),
        "postcode_area": area,
        "postcode_outward": outward,
        "town": req.town.upper(),
        "district": req.district.upper(),
        "county": req.county.upper(),
        "month": req.month,
        **area_features(outward),
    }])
    for col in CATEGORICAL:
        row[col] = row[col].astype("category")
    import numpy as np
    price = float(np.exp(model.predict(row)[0]))
    return {"predicted_price": round(price, -2)}
