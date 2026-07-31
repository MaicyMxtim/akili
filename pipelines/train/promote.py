"""Champion/challenger promotion gate.

Takes a challenger run (default: the most recent finished run), compares it
against the current champion on MAE, and promotes it only if it is better.
First model through becomes champion unopposed. Exit code 1 on refusal so
workflows surface the gate closing.

Usage: python promote.py [--run-id ID] [--min-improvement 0]
"""

import argparse
import sys
from datetime import datetime, timezone

from mlflow import MlflowClient, register_model

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
    client.set_registered_model_alias(MODEL, "champion", version.version)
    client.update_model_version(
        MODEL, version.version,
        description=model_card(run, version.version, champ_mae, challenger_mae),
    )
    client.set_tag(run.info.run_id, "promotion", f"champion-v{version.version}")
    print(f"PROMOTED: run {run.info.run_id} is champion v{version.version} (MAE £{challenger_mae:,.0f})")


if __name__ == "__main__":
    main()
