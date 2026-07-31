# Akili Platform — Project Plan

Akili (Swahili for "intelligence") is an end-to-end MLOps platform. It runs on a virtual multi-node Kubernetes cluster on the laptop, so it costs nothing.

It is the second portfolio project after Tamani. Tamani covered using AI through an API gateway and agents. Akili covers the other side: training, tracking, registering, serving and monitoring your own models. This is what ML Platform Engineer job specs ask for.

The name is a placeholder. Rename the folder and this doc if you want something else.

## What it does, in one paragraph

Every month the UK Land Registry publishes new house sale data. When that lands, the platform ingests it, validates it, retrains a price prediction model, compares the new model against the current one, promotes it only if it scores better, and rolls it out gradually with automatic rollback if it misbehaves. Drift monitoring can also trigger the same pipeline between monthly drops. The whole loop runs without anyone touching it, and that end-to-end run is the main demo.

## The ML problem

Predict UK residential property sale prices from HM Land Registry Price Paid Data.

Why this dataset:

- Real, large (about 30M rows since 1995), free, openly licensed.
- Updates monthly, so the retraining pipeline has a real job. Every month there is a real reason for the platform to run.
- Prices genuinely drift with the market, so drift monitoring measures something real.
- Tabular data, so training runs fine on CPU. No GPU needed.
- The model itself is deliberately simple (LightGBM regression). The platform is the project, the model is just the workload it manages.

Data source: https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads (monthly CSVs plus a full history file). Possible later additions: ONS postcode lookup for geography, EPC data for property features, Bank of England rates.

## Stack

All open source, all CPU-friendly, all recognisable on a CV.

| Concern | Tool | Notes |
|---|---|---|
| Cluster | k3d (k3s in Docker), 5 nodes | Multi-node for real: drains, rescheduling, HA etcd |
| GitOps | Argo CD | Same pattern as Tamani, reinforces the re-learn |
| Storage | local-path provisioner + MinIO | local-path comes with k3s; MinIO for S3-style object storage |
| Orchestration | Argo Workflows | Kubernetes-native pipelines, pairs with Argo CD. Airflow is the bigger interview keyword; write an ADR on this choice |
| Data versioning | DVC (remote on MinIO) | Reproducible datasets per training run |
| Data validation | pandera or Great Expectations | Catch bad monthly files before they reach training |
| Experiment tracking | MLflow (Postgres backend, MinIO artifacts) | Tracking server plus model registry |
| Training | LightGBM + scikit-learn, Optuna for sweeps | CPU only |
| Feature store | Feast (offline parquet, online Redis) | Same features at training time and serving time |
| Serving | FastAPI first, then KServe (RawDeployment mode) | Raw mode avoids installing Istio and Knative |
| Progressive delivery | Argo Rollouts canary | Deferred in Tamani, done properly here |
| Drift monitoring | Evidently, run as a scheduled workflow | Feeds the retraining trigger |
| Observability | kube-prometheus-stack + Loki + Grafana | Known territory from Tamani |
| Supply chain | cosign, trivy, syft, gitleaks, Kyverno | Reuse the Tamani CI patterns, extend signing to model files |
| Load testing | k6 | Safe to run properly now there is more than one node |

## The virtual cluster

No hardware and no cloud spend. The cluster is k3d: each k3s node is a Docker container on the Mac (16GB RAM, 8 cores). A five-node cluster starts in under a minute and costs nothing.

Layout: 3 server nodes (an odd number is needed for an HA control plane with embedded etcd) plus 2 agent nodes for workloads. Cap Docker Desktop at around 10GB RAM and 6 CPUs so the Mac stays usable. Because nodes are containers, chaos testing is one command: `docker stop` a node to kill it, `kubectl drain` to empty it, delete a server and watch etcd elect a new leader.

What this keeps from a physical setup: multi-node scheduling, drains and rescheduling, PodDisruptionBudgets that actually do something, an HA control plane, and the full platform stack. What it gives up: distributed block storage (Longhorn needs real disks, local-path fills in), real hardware failure, and memory beyond what the laptop has. Memory was the recurring problem on Tamani and it will be the thing to watch here too, so the same habits apply: trimmed Helm values, realistic resource limits, one replica where two is not needed.

If a physical homelab happens some day, everything moves across unchanged because it is all declared in git. Also worth knowing: Oracle Cloud has a permanent free tier with 4 ARM cores and 24GB RAM, which could host the same cluster with more headroom. Not needed to start.

## Phases

Each phase ends with something you can demonstrate, same as Tamani.

**Phase 0 — Baseline model on the laptop.** Set up the repo and Python tooling, download a slice of Price Paid data, train a LightGBM baseline, pick the evaluation metrics (MAE and median absolute percentage error on a time-based holdout). Proof: one command takes raw CSV to a scored model.

**Phase 1 — Cluster bring-up.** k3d cluster with 3 servers (embedded etcd) and 2 agents, Docker Desktop resource caps, ingress-nginx, cert-manager, MinIO. Proof: `docker stop` one server node and the cluster keeps serving while etcd elects a new leader.

**Phase 2 — GitOps and platform baseline.** Argo CD app-of-apps, namespaces with PSA, RBAC, default-deny network policies, quotas, kube-prometheus-stack, Loki. This overlaps the August re-learn material on purpose: doing it here is re-learn practice on fresh infrastructure. Proof: the full platform can be rebuilt from the git repo alone.

**Phase 3 — Data pipeline.** Install Argo Workflows. Monthly ingest workflow: download the Price Paid update, validate it with pandera (schema, value ranges, row counts, duplicate checks), write partitioned parquet to MinIO, version it with DVC. Proof: a deliberately corrupted file gets rejected with a clear failure report and never reaches the dataset.

**Phase 4 — Experiment tracking and training pipeline.** MLflow server on the cluster. Training as an Argo Workflow: pull a versioned dataset, train, log params, metrics and artifacts. Optuna sweeps fan out as workflow steps across nodes. Proof: two sweep runs compared in the MLflow UI, and any past run reproducible from its logged dataset version and params.

**Phase 5 — Registry and promotion gate.** MLflow model registry with a champion/challenger setup. An eval gate in CI, like Tamani's: a challenger gets registered but only promoted if it beats the champion on the holdout by more than a set tolerance. Generate a model card for each promoted version. Proof: train a deliberately worse model and watch it get refused promotion automatically.

**Phase 6 — Serving.** A FastAPI inference service that loads the champion model from the registry, with request logging, Prometheus metrics, and the hardened deployment patterns from Tamani (probes, limits, netpol, PDB). Then move to KServe RawDeployment. Put Argo Rollouts canary in front: a new model version takes 10% of traffic, and rolls back automatically if error rate or latency regresses. Proof: a bad model version gets canaried, fails the analysis, and rolls back with no human involved.

**Phase 7 — Feature store.** Feast with parquet as the offline store and Redis as the online store. Training reads point-in-time-correct features offline; serving reads the same features online. Proof: a test showing identical feature values for the same entity on both paths.

**Phase 8 — Drift and model monitoring.** A scheduled Evidently workflow compares recent inputs and predictions against the training reference: data drift, prediction drift, and (once the next monthly file arrives) real error against actual sale prices. Grafana dashboard for model health next to service health, with SLOs and burn-rate alerts on the serving path. Proof: feed old reference data against current inputs and watch drift alerts fire.

**Phase 9 — The closed loop.** Wire it all together: monthly data drop triggers ingest, validation, retrain, eval gate, promotion, canary rollout. A drift alert can trigger the same pipeline between drops. Proof: simulate a month-end run end to end with no human touches, then show the audit trail (data version, run, model version, deployment) for the model now serving.

**Phase 10 — Supply chain for models.** Port the Tamani CI security stack, then extend it: sign model artifacts with cosign, verify the signature before the serving pod loads a model, SBOM and scan the training and serving images, secrets via sealed-secrets or ESO pointing at a local Vault. Proof: an unsigned model file is refused at load time.

**Phase 11 — Reliability and chaos, multi-node edition.** Everything the single Tamani node could not do: drain a node under load, kill the MLflow Postgres and check recovery, kill Redis and check serving degrades sensibly, run proper k6 load tests to find the real saturation point. Write the experiments up in runbooks like the Tamani chaos log. Proof: documented experiments with measured numbers.

**Phase 12 — Economics and write-up.** A unit economics doc: what this platform would cost on managed services (a SageMaker or Vertex endpoint, managed MLflow, managed Airflow) against the £0 it actually costs, and at what scale each managed piece becomes worth paying for. README with an architecture diagram and a status table. A learning doc in the style of the-story-so-far.md, written as you go.

## Running it alongside the August re-learn

You have about 40 hours a week from August. Suggested split: mornings on the Tamani re-learn with complete-guide.md, afternoons on Akili. The overlap helps rather than competes: re-learn GitOps in the morning, then set up Argo CD on your own cluster in the afternoon. Same material twice, once guided and once for real.

Phases 0 and 1 can happen before August, since the cluster takes minutes to set up. Phases 2 onward line up with the re-learn weeks.

Rough effort guess: 100 to 140 hours, so about 5 to 7 weeks at half-time alongside the re-learn, finishing mid-to-late September.

## What this adds to the portfolio

Tamani shows platform engineering for AI consumption: gateway, agents, GitOps, observability, supply chain, cost control. Akili adds the ML lifecycle: pipelines, experiment tracking, registries, gradual model rollout, feature stores, drift, automated retraining, all on a multi-node cluster you operate yourself at zero cost. Together they cover both halves of the AI infrastructure job market.
