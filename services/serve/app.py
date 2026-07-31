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

CATEGORICAL = [
    "property_type", "new_build", "duration",
    "postcode_area", "postcode_outward", "town", "district", "county",
]


class PredictRequest(BaseModel):
    postcode: str = Field(examples=["SW1A 1AA"])
    property_type: str = Field(examples=["T"], description="D/S/T/F/O")
    new_build: str = Field(default="N", description="Y/N")
    duration: str = Field(default="F", description="F freehold, L leasehold")
    town: str = Field(examples=["LONDON"])
    district: str = Field(examples=["WESTMINSTER"])
    county: str = Field(examples=["GREATER LONDON"])
    month: int = Field(default=6, ge=1, le=12)


@app.on_event("startup")
def load_model() -> None:
    global model
    model = mlflow.lightgbm.load_model(MODEL_URI)
    log.info(f"loaded model {MODEL_URI}")


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
    }])
    for col in CATEGORICAL:
        row[col] = row[col].astype("category")
    import numpy as np
    price = float(np.exp(model.predict(row)[0]))
    return {"predicted_price": round(price, -2)}
