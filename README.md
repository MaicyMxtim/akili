# Akili Platform

An end-to-end MLOps platform running on a virtual multi-node Kubernetes cluster (k3d). The workload is a UK house price model trained on Land Registry Price Paid Data, retrained automatically when new monthly data lands.

Full plan and phase list: [PROJECT-PLAN.md](PROJECT-PLAN.md).

## Status

| Phase | What | Status |
|---|---|---|
| 0 | Baseline model on the laptop | done |
| 1 | k3d cluster bring-up | done |
| 2 | GitOps and platform baseline | not started |
| 3 | Data pipeline | not started |
| 4 | Experiment tracking and training pipeline | not started |
| 5 | Registry and promotion gate | not started |
| 6 | Serving | not started |
| 7 | Feature store | not started |
| 8 | Drift and model monitoring | not started |
| 9 | The closed loop | not started |
| 10 | Supply chain for models | not started |
| 11 | Reliability and chaos | not started |
| 12 | Economics and write-up | not started |

## Quick start

Needs: docker, k3d, uv, make.

```
make baseline   # download 2025 data and train the baseline model
make cluster    # create the 5-node k3d cluster
```
