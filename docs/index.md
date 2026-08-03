# Akili Platform

An MLOps platform running on Kubernetes. It trains a machine learning model, decides whether the new model is good enough to replace the old one, deploys it without downtime, and watches for the data changing underneath it.

The model predicts UK house prices from Land Registry records. The model is simple on purpose. The engineering around it is the project.

**Source:** [github.com/MaicyMxtim/akili](https://github.com/MaicyMxtim/akili)

The platform runs on a laptop, so there is no public endpoint. It rebuilds from the repository with two commands.

## Contents

1. [Walkthrough](walkthrough.html). How the platform is built and what happens when it runs.
2. [Costs](unit-economics.html). What the same platform costs as managed services.
3. [Chaos experiments](https://github.com/MaicyMxtim/akili/blob/main/runbooks/chaos/experiments.md). Five deliberate failures and their results.
4. [Postmortems](https://github.com/MaicyMxtim/akili/tree/main/runbooks/postmortems). Four real incidents from the build.

## Stack

| Layer | Tool |
|---|---|
| Cluster | k3d, 3 nodes |
| Deployment | Argo CD |
| Pipelines | Argo Workflows |
| Storage | MinIO, DVC |
| Validation | pandera |
| Training | LightGBM |
| Tracking and registry | MLflow |
| Features | Feast, Redis |
| Serving | FastAPI |
| Releases | Argo Rollouts |
| Monitoring | Prometheus, Grafana, Loki |
| Drift | Evidently |
| Supply chain | cosign, trivy, syft, Kyverno |

## Model results

| Metric | Value |
|---|---|
| Mean absolute error | £93,229 |
| Median error | 18.07% |
| Training rows | 780,000 |
| Test set | held out month |

## Reliability results

Measured by breaking things while traffic was running.

| Failure | Requests | Failed |
|---|---|---|
| Serving pod killed | 90 | 0 |
| Node drained | 90 | 1 |
| Feature store stopped | 90 | 0 |
| Tracking server stopped | 90 | 0 |
| Tracking database killed | 90 | 0 |

Stopping the tracking server caused no failures, but no new pod could start while it was down. That is the most useful result of the five.

## Demonstrations

| Claim | How it was proven |
|---|---|
| Bad data is rejected | A corrupted file was refused with a row and column report |
| Training is repeatable | Two identical runs produced identical scores |
| Weak models do not ship | A 20 tree model was trained and refused promotion |
| Bad releases roll back | A broken model was deployed, detected and reversed with no dropped requests |
| Features match | Training and serving returned identical values |
| Drift is detected | Alerts stayed quiet on real data and fired on synthetic drift |
| Unsigned images are blocked | The cluster refused an image without a valid signature |
| Tampered models do not load | A pod refused to serve a model whose signature had been altered |
| The cycle runs alone | Retrain to deploy ran twice with nobody involved |

## Costs

| Option | Monthly |
|---|---|
| This platform, on a laptop | £0 |
| Self hosted on one cloud server | £25 to £30 |
| Bought as managed services | £650 to £700 |

Orchestration and monitoring are most of the managed bill. Training the model is a few pence of compute.

## Findings

The area price features from the feature store made the model slightly worse, £95,602 against £93,229. Recorded as a negative result rather than dropped.

Every prediction failed for ninety minutes during the build while the platform reported itself healthy. The health check only confirmed a model object existed, and the release check saw no errors because there was no traffic. Both are fixed and the incident is written up.
