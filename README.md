# Akili Platform

An end-to-end MLOps platform running on a virtual multi-node Kubernetes cluster (k3d). The workload is a UK house price model trained on Land Registry Price Paid Data, retrained automatically when new monthly data lands.

Full plan and phase list: [PROJECT-PLAN.md](PROJECT-PLAN.md).

## Status

| Phase | What | Status |
|---|---|---|
| 0 | Baseline model on the laptop | done |
| 1 | k3d cluster bring-up | done |
| 2 | GitOps and platform baseline | done |
| 3 | Data pipeline | done |
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

Needs: docker, k3d, uv, helm, make.

```
make baseline   # download 2025 data and train the baseline model
make cluster    # create the 5-node k3d cluster
```

## Rebuilding the platform from git

The cluster contents are managed by Argo CD from this repo. After `make cluster`, two manual steps bootstrap it: the repo deploy key secret, then `make platform-up`. Everything else self-installs from git.

```
kubectl -n argocd create secret generic repo-akili \
  --from-literal=type=git \
  --from-literal=url=git@github.com:MaicyMxtim/akili.git \
  --from-file=sshPrivateKey=$HOME/.ssh/akili_deploy
kubectl -n argocd label secret repo-akili argocd.argoproj.io/secret-type=repository
make platform-up
```

The deploy key is read-only and lives at `~/.ssh/akili_deploy` (not in git). The Argo CD UI is available with `kubectl -n argocd port-forward svc/argocd-server 8080:80`; Grafana with `kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80` (admin / REDACTED-ROTATED-CREDENTIAL).
