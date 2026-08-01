"""Champion/challenger promotion gate.

Takes a challenger run (default: the most recent finished run), compares it
against the current champion on MAE, and promotes it only if it is better.
First model through becomes champion unopposed. Exit code 1 on refusal so
workflows surface the gate closing.

Usage: python promote.py [--run-id ID] [--min-improvement 0]
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from mlflow import MlflowClient, register_model


def dir_digest(path: str) -> str:
    """Deterministic digest of a model directory: sha256 over the sorted
    list of relative-path:file-sha256 lines."""
    lines = []
    for f in sorted(Path(path).rglob("*")):
        if f.is_file():
            lines.append(f"{f.relative_to(path)}:{hashlib.sha256(f.read_bytes()).hexdigest()}")
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def sign_model(version: str) -> None:
    """Sign the registered model's digest; serving verifies before load."""
    import mlflow.artifacts
    import s3fs
    from cryptography.hazmat.primitives import serialization

    local = mlflow.artifacts.download_artifacts(f"models:/{MODEL}/{version}")
    digest = dir_digest(local)
    key = serialization.load_pem_private_key(
        Path(os.environ["MODEL_SIGNING_KEY_PATH"]).read_bytes(), password=None
    )
    sig = key.sign(digest.encode()).hex()
    fs = s3fs.S3FileSystem(
        key=os.environ["AWS_ACCESS_KEY_ID"], secret=os.environ["AWS_SECRET_ACCESS_KEY"],
        client_kwargs={"endpoint_url": os.environ["MLFLOW_S3_ENDPOINT_URL"]},
    )
    with fs.open(f"akili-mlflow/signatures/{MODEL}-v{version}.json", "w") as f:
        json.dump({"digest": digest, "signature": sig}, f)
    print(f"model v{version} signed ({digest[:12]}...)")

EXPERIMENT = "price-model"
MODEL = "price-model"
METRIC = "mae"  # lower is better


def model_card(run, version: str, champ_mae, challenger_mae: float) -> str:
    p, m = run.data.params, run.data.metrics
    beat = (
        f"beat champion MAE £{champ_mae:,.0f}" if champ_mae is not None
        else "first model, promoted unopposed"
    )
    return f"""# price-model v{version}

Promoted {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC ({beat}).

## Training
- train data: {p.get('train_data')} ({p.get('train_rows')} rows)
- test data: {p.get('test_data')} ({p.get('test_rows')} rows)
- params: n_estimators={p.get('n_estimators')}, learning_rate={p.get('learning_rate')}, num_leaves={p.get('num_leaves')}

## Holdout metrics
- MAE: £{challenger_mae:,.0f}
- median APE: {m.get('median_ape_pct'):.2f}%
- within 20%: {m.get('within_20pct'):.1f}%

## Known limitations
Price Paid data has no property size or condition; errors reflect that
ceiling. Source run: {run.info.run_id}.
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default="")
    ap.add_argument("--min-improvement", type=float, default=0.0)
    args = ap.parse_args()

    client = MlflowClient()
    if args.run_id:
        run = client.get_run(args.run_id)
    else:
        exp = client.get_experiment_by_name(EXPERIMENT)
        run = client.search_runs(
            [exp.experiment_id], "attributes.status = 'FINISHED'",
            order_by=["attributes.start_time DESC"], max_results=1,
        )[0]
    challenger_mae = run.data.metrics[METRIC]

    champ_mae = None
    try:
        champ_version = client.get_model_version_by_alias(MODEL, "champion")
        champ_mae = client.get_run(champ_version.run_id).data.metrics[METRIC]
    except Exception:
        pass

    if champ_mae is not None and challenger_mae >= champ_mae - args.min_improvement:
        client.set_tag(run.info.run_id, "promotion", "refused")
        print(
            f"REFUSED: challenger MAE £{challenger_mae:,.0f} does not beat "
            f"champion £{champ_mae:,.0f} (min improvement £{args.min_improvement:,.0f})"
        )
        sys.exit(1)

    version = register_model(f"runs:/{run.info.run_id}/model", MODEL)
    sign_model(version.version)
    client.set_registered_model_alias(MODEL, "champion", version.version)
    client.update_model_version(
        MODEL, version.version,
        description=model_card(run, version.version, champ_mae, challenger_mae),
    )
    client.set_tag(run.info.run_id, "promotion", f"champion-v{version.version}")
    print(f"PROMOTED: run {run.info.run_id} is champion v{version.version} (MAE £{challenger_mae:,.0f})")


if __name__ == "__main__":
    main()
