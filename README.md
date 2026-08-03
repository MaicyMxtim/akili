# Akili Platform

An end-to-end MLOps platform running on a virtual multi-node Kubernetes cluster (k3d) on a laptop, at zero cost.

When new data arrives, the platform ingests and validates it, retrains a model, compares it against the one currently serving, promotes it only if it scores better, and rolls it out gradually with automatic rollback. Drift monitoring watches for the world changing and can trigger the same cycle between scheduled runs. Every image and every model is cryptographically signed, and the cluster refuses to run anything unsigned.

The workload is a UK house price model (LightGBM on HM Land Registry Price Paid Data, about 780,000 sales). The model is deliberately simple: the platform around it is the project.

Full plan and phase list: [PROJECT-PLAN.md](PROJECT-PLAN.md). Cost analysis: [docs/unit-economics.md](docs/unit-economics.md).

## Status

| Phase | What | Status |
|---|---|---|
| 0 | Baseline model on the laptop | done |
| 1 | k3d cluster bring-up | done |
| 2 | GitOps and platform baseline | done |
| 3 | Data pipeline | done |
| 4 | Experiment tracking and training pipeline | done |
| 5 | Registry and promotion gate | done |
| 6 | Serving with canary rollout | done |
| 7 | Feature store | done |
| 8 | Drift and model monitoring | done |
| 9 | The closed loop | done |
| 10 | Supply chain for models | done |
| 11 | Reliability and chaos | done |
| 12 | Economics and write-up | done |

## What is proven, not just built

Each phase ended with a demonstration rather than a claim:

- **Self-healing GitOps** — a resource deleted by hand is restored from git within seconds; the entire platform has been rebuilt from the repository three times.
- **Data validation** — a corrupted file is rejected with a per-row failure report and never reaches the dataset.
- **Reproducibility** — the same data version and hyperparameters produce metrics identical to the decimal across separate runs.
- **Promotion gate** — a deliberately weak model is trained, registered, and automatically refused promotion; the champion is untouched.
- **Canary rollback** — an unloadable model version is deployed on purpose; the canary fails, the rollout aborts itself, and prediction traffic never stops flowing from the stable pods.
- **Feature consistency** — identical values offline and online for the same entity, and point-in-time joins returning different historically correct values for the same postcode at different dates.
- **Drift detection** — real month-on-month data passes; a synthetic set with tripled prices trips the alert.
- **The closed loop** — the full chain run twice with no human involvement: once ending in a correct refusal, once in a promotion that deployed a new champion through the canary.
- **Supply chain** — an unverifiable image is denied at admission; a tampered model signature stops the serving pod from starting while its sibling keeps answering requests.

## What went wrong, and what it taught

Four incidents, each with a postmortem in [runbooks/postmortems](runbooks/postmortems):

1. **Docker VM out of memory** — the kernel killed two control-plane nodes during a rollout. HA etcd survived it.
2. **MLflow process leak and a migration race** — an upstream release leaked workers until any memory limit was exhausted; downgrading then hit a database migration race caused by a stuck rollout's old pods.
3. **Silent prediction outage** — every prediction failed for ninety minutes while the platform reported healthy, because the health check only verified the model object existed and the canary analysis saw no errors on zero traffic. Health checks now perform a real prediction.
4. **Admission controller deadlock** — a fail-closed policy engine ran out of memory and blocked every pod creation in the cluster, including the ones needed to fix it. The policy is now fail-open by deliberate choice.

A measured negative result worth recording: the rolling area-price features from the feature store made the model slightly worse (£95,602 against £93,229 MAE), because at this data volume the postcode categorical already encodes area price level. The feature path remains behind a flag.

## Quick start

Needs: docker, k3d, uv, helm, make.

```
make baseline   # download 2025 data and train the baseline model
make cluster    # create the k3d cluster (1 server, 2 agents)
```

## Rebuilding the platform from git

After `make cluster`, a handful of secrets bootstrap the cluster; everything else installs itself from this repository. No credential is committed.

```
# object storage credentials (in minio, argo, mlflow, akili-prod)
kubectl -n <ns> create secret generic minio-creds \
  --from-literal=rootUser=$MINIO_ROOT_USER --from-literal=rootPassword=$MINIO_ROOT_PASSWORD

# private registry pull (in akili-prod, argo, kyverno)
kubectl -n <ns> create secret docker-registry ghcr-pull \
  --docker-server=ghcr.io --docker-username=MaicyMxtim --docker-password="$(gh auth token)"

# database and dashboard credentials (never committed)
kubectl -n mlflow create secret generic mlflow-postgres-auth \
  --from-literal=password="$(openssl rand -hex 12)"
kubectl -n monitoring create secret generic grafana-admin \
  --from-literal=admin-user=admin --from-literal=admin-password="$(openssl rand -hex 12)"

# model signing key (in argo)
kubectl -n argo create secret generic model-signing-key --from-file=key.pem=$HOME/.akili-model-signing.pem

# repo deploy key, then hand over to Argo CD
kubectl -n argocd create secret generic repo-akili --from-literal=type=git \
  --from-literal=url=git@github.com:MaicyMxtim/akili.git --from-file=sshPrivateKey=$HOME/.ssh/akili_deploy
kubectl -n argocd label secret repo-akili argocd.argoproj.io/secret-type=repository
make platform-up
```

Note that this restores the platform, not its data. Recreating the cluster destroys the MinIO and Postgres volumes, so datasets and models must be regenerated by rerunning the pipelines. See the durability section in the economics document.

## Interfaces

All by port-forward; nothing is exposed publicly.

| UI | Command | Login |
|---|---|---|
| Argo CD | `kubectl -n argocd port-forward svc/argocd-server 8080:80` | admin / initial admin secret |
| MLflow | `kubectl -n mlflow port-forward svc/mlflow 5000:80` | none |
| Argo Workflows | `kubectl -n argo port-forward svc/argo-workflows-server 2746:2746` | none |
| Grafana | `kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80` | admin / from the `grafana-admin` secret |
| MinIO console | `kubectl -n minio port-forward svc/minio-console 9001:9001` | root credentials |
| Prediction API | `kubectl -n akili-prod port-forward svc/serve 8000:80` | none, docs at /docs |
