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

The single failed request during a node drain happened in the gap between the pod being told to stop and the load balancer removing it from rotation. The standard fix is a short delay before shutdown.

Stopping the tracking server produced the most useful finding. Predictions carried on because each pod holds its model in memory, but a pod deleted during that window could not start again, because startup reads the live model pointer from the tracking server and verifies the signature. So the outage is invisible until something restarts, and then it is total.

## Demonstrations

Each claim below was tested by causing the failure on purpose and recording what happened.

**Bad data is rejected.** A copy of a real monthly file was corrupted by setting 200 prices negative and 50 property types to an invalid code. The ingest job refused the whole file and wrote a report listing each failing row, column and rule, for example a price of -472,696 at row 3,693. The workflow exited with an error and nothing was written to storage. The same job accepts the genuine file of 90,287 rows.

**Training is repeatable.** The same configuration on the same data was trained twice and produced £93,229 mean absolute error both times, identical to the pound. This is enforced by a fixed random seed and by logging the exact data path as a run parameter.

**Weak models do not ship.** A model was trained deliberately badly, with 20 trees, a learning rate of 0.5 and 4 leaves. It scored £102,737 against the champion's £93,229. The promotion gate refused it, tagged the run as refused, and exited with an error so the pipeline stopped. The champion was untouched.

**Bad releases roll back on their own.** The serving deployment was pointed at a model version that does not exist. The new pod started, failed to load a model, and crashlooped. The rollout controller waited, saw no progress by its deadline, destroyed the new pod and left the old ones running. Throughout this a script sent prediction requests every 0.4 seconds and received a valid price every time.

**Features match between training and serving.** For postcode area BS3, the training store and the serving store both returned a median price of £408,750 over 44 sales. Asking the training store for the same area at three different dates returned £372,500, £406,750 and £392,500, A model trained on this sees only what was known at the time, not today's figure.

**Drift is detected.** Comparing December 2025 against June 2026 found no significant drift, with a price distribution score of 0.02 against a threshold of 0.5, and the check passed. A synthetic copy of the same file with every price tripled and every tenure changed to leasehold moved every monitored column, and the check failed and wrote a report.

**Unsigned images are blocked.** A pod was created referencing an image digest that carries no signature. The cluster refused to create it, naming the policy that rejected it. The same pod definition with a properly signed image is admitted normally.

**Tampered models do not load.** The stored signature for the live model was edited so its recorded digest no longer matched the files. The next pod to start recomputed the digest, found the mismatch, and refused to become ready with the message "model v3 digest mismatch: artifact was modified after signing". Its sibling pod, already running, kept answering requests, so the service stayed up. Restoring the signature let the pod start.

**The cycle runs without anyone.** The month end workflow chains seven steps: download, validate, drift check, feature build, feature publish, train, promote, restart. It was run twice. The first run trained a model that tied the champion exactly and the gate refused it, which is correct. The second run was given a lower bar, promoted the new model, signed it, moved the live pointer and restarted the service, which brought the new model in gradually. Neither run needed a person.

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
