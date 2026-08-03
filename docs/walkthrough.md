# Akili Platform Walkthrough

A guided tour of what the Akili Platform is, how it is built, and where each part lives. For the underlying concepts and a phase-by-phase rebuild, see `complete-guide.md`. For decisions, incidents and cost, see `runbooks/`, `runbooks/postmortems/` and `docs/unit-economics.md` in the repository.

---

## Overview

The Akili Platform runs a machine learning workload as a production-grade internal platform. It takes a real dataset — around 780,000 UK residential property sales published by HM Land Registry — and builds the infrastructure that an ML platform or MLOps team would run around it: a Kubernetes platform delivered by GitOps, validated data pipelines, experiment tracking and a model registry, an automated promotion gate, progressive delivery with automatic rollback, a feature store, drift monitoring, an enforced secure supply chain covering both containers and model artifacts, reliability evidence, and published unit economics.

It is the counterpart to the Tamani Platform. Tamani covers consuming AI through a gateway and agents; Akili covers producing and operating models. The two together span both halves of AI infrastructure work.

Everything runs on a three-node virtual cluster on a laptop, at no cost.

## Local endpoints

Nothing is exposed publicly. Each interface is reached by port-forward.

- **Prediction API:** `kubectl -n akili-prod port-forward svc/serve 8000:80` → http://localhost:8000/docs
- **Argo CD:** `kubectl -n argocd port-forward svc/argocd-server 8080:80`
- **MLflow:** `kubectl -n mlflow port-forward svc/mlflow 5000:80`
- **Argo Workflows:** `kubectl -n argo port-forward svc/argo-workflows-server 2746:2746`
- **Grafana:** `kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80`
- **MinIO console:** `kubectl -n minio port-forward svc/minio-console 9001:9001`

The cluster runs on eight shared CPU cores. Under a heavy rollout it can saturate, which is documented behaviour rather than a fault (see `runbooks/postmortems/`).

## Architecture

The system is organised in tiers.

- **Platform** — k3s in Docker (k3d), one server and two agents, reconciled from Git by Argo CD, observed by Prometheus, Grafana and Loki, with admission policy enforced by Kyverno.
- **Data** — MinIO provides S3-compatible object storage for raw sales data, computed features, model artifacts and signatures; DVC versions local datasets against the same store; a bundled Postgres backs the tracking server.
- **Pipeline** — Argo Workflows runs ingest, feature refresh, training, promotion and drift checks, both on schedule and on demand.
- **Modelling** — LightGBM trains against versioned parquet; MLflow records every run and owns the registry, where a `champion` alias names the model in production.
- **Feature** — Feast defines the features once, serving history from parquet for training and current values from Redis for inference.
- **Serving** — a FastAPI service loads the champion at startup, verifies its signature, and answers predictions; Argo Rollouts fronts it with a canary gated on live error rate.
- **Supply chain** — GitHub Actions builds, signs, scans and attests every image; Kyverno refuses unsigned images at admission; models are signed at promotion and verified before a pod will serve them.

## Repository layout

- **`ml/`** — the Phase 0 baseline script, the simplest path from raw CSV to a scored model.
- **`pipelines/`** — the containerised job code: `ingest` (download and validate), `features` (compute and materialise), `train` (fit, log, and the promotion gate), `drift` (compare distributions).
- **`services/serve/`** — the prediction API.
- **`platform/argocd/`** — the GitOps content: the root application and one Application per platform component.
- **`platform/k8s/`** — the manifests those Applications point at: `tenancy` (namespaces, RBAC, network policy, quotas), `pipelines` (workflow templates and crons), `serving` (rollout, service, policies, SLOs, dashboard), `feast`, `policy`.
- **`runbooks/`** — one file per alert, plus the postmortem and chaos archives.
- **`docs/`** — unit economics.

## Request paths

**A prediction.** A client posts property attributes to the serving API. The service derives the postcode outward code and area, builds a single-row frame, projects it onto exactly the feature list the loaded model declares, and returns the exponentiated prediction. If the champion was trained with area features, it first reads them from Redis; if not, that lookup is skipped entirely.

**A month of new data.** The ingest workflow downloads the published file, validates it against a schema, and writes partitioned parquet to object storage. A drift check compares the new window against the training reference. The feature job recomputes area statistics and materialises them to Redis. Training fits a new model and logs it. The promotion gate compares it against the champion and either moves the alias or refuses. If it promoted, the final step restarts the rollout, which brings the new champion in through a canary.

**A deployment.** A commit lands on `main`. GitHub Actions builds the affected images, signs them keylessly with the workflow's own identity, scans them, and publishes SBOMs. Argo CD notices the repository has changed and applies the new manifests. Kyverno verifies the image signature before admitting any pod.

## Component tour

**Argo CD** holds the cluster to the repository. Every component is an Application; a root Application defines the others, so adding a component means adding one file. Deleting a resource by hand gets it recreated within seconds.

**Argo Workflows** runs the pipelines. Templates are parameterised and reference each other, so the month-end loop is a short file that chains templates rather than duplicating them.

**MinIO** stores everything that is too big for Git: raw and processed data, model artifacts, feature parquet, drift reports, model signatures.

**MLflow** records runs and owns the registry. The `champion` alias is the contract between training and serving: training moves it, serving resolves it, and neither knows anything else about the other.

**Feast** defines the features once. Training reads history with a point-in-time join so no example sees information from after its own date; serving reads the current value from Redis.

**The serving API** loads the champion at startup, verifies the model signature against a public key, and refuses to become ready if verification fails or if a test prediction raises.

**Argo Rollouts** replaces pods in stages rather than all at once, pausing to let an analysis query the live error rate before continuing, and aborting on failure or on a stalled deadline.

**Kyverno** verifies at admission that any image from the project registry carries a signature from this repository's CI on `main`.

**Prometheus, Grafana and Loki** collect metrics, draw them, and make every pod's logs searchable in one place.

## Delivery

Nothing is deployed by hand. A change to a manifest is a commit; Argo CD applies it. A change to service code is a commit; CI builds and signs an image, and the rollout picks it up.

Promotion of a *model* is deliberately separate from deployment of *code*. A new champion changes nothing about the running image; it changes an alias in the registry, and the serving pods pick it up when they next restart. That separation is what lets the platform retrain on a schedule without touching the deployment pipeline.

## Operations

Alerts are defined as Prometheus rules with runbooks committed beside them: an availability burn-rate alert that pages on fast burn and tickets on slow burn, and a latency alert on the 95th percentile. Four incidents have their own postmortems, covering memory exhaustion, an upstream release with a process leak, a silent outage hidden by a shallow health check, and a fail-closed admission controller that deadlocked the cluster.

The chaos archive records five deliberate failure experiments with measured results.

## Measured results

- **Model.** £93,229 mean absolute error, 18.07% median absolute percentage error, tested on a held-out month. A classical baseline and a larger-capacity variant were both measured; the area features from the feature store made the model slightly worse and are recorded as a negative result.
- **Reliability.** Killing a serving pod: 90 requests, no failures. Draining a node: 89 of 90. Losing the feature store, the tracking server or the tracking database: no failures, though no pod can start while the registry is down.
- **Supply chain.** An unverifiable image is refused at admission; a tampered model signature prevents a pod from serving while its sibling continues.
- **Cost.** Nothing to run. The managed equivalent prices at roughly £650 to £700 per month, dominated by orchestration and observability rather than compute.

## How it maps to roles

- **MLOps or ML Platform Engineer** — the whole project.
- **Platform or DevOps Engineer** — GitOps, tenancy, progressive delivery, admission policy, supply chain.
- **SRE** — SLOs, burn-rate alerting, runbooks, postmortems, chaos evidence.
- **Data Engineer** — schema-validated ingestion, partitioned storage, dataset versioning, scheduled pipelines.
- **Data Scientist** — experiment tracking, an evaluation gate with a holdout, point-in-time correctness, drift detection, and an honest negative result.
