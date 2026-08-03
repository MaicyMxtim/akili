# Walkthrough

How the Akili platform is put together, and what happens when it runs.

## The workload

The model predicts the sale price of a UK residential property. It is trained on HM Land Registry Price Paid Data, roughly 780,000 sales, using LightGBM. The inputs are property type, tenure, location and month.

It reaches £93,229 mean absolute error. That is close to the limit of what this data supports, because the public records contain no floor area and no condition. The model is kept simple on purpose so that the platform is the interesting part.

## The cluster

Three Kubernetes nodes run as containers on a laptop, using k3d. One node runs the control plane and two run workloads. Nothing is installed by hand. Argo CD reads the repository and makes the cluster match it, so anything deleted by accident is put back within seconds.

The whole platform was rebuilt from the repository three times during development.

## Storage and data

MinIO provides object storage inside the cluster and behaves like S3. It holds the raw sales files as parquet, the computed features, the trained model files, and the signatures for those models.

Incoming data is checked before it is stored. A schema describes what a valid file looks like: column types, allowed categories, sensible bounds, and a minimum row count. A file that fails is rejected with a report naming every row and column at fault, and nothing downstream ever sees it.

The bounds describe corruption rather than business rules. Real Land Registry data contains £1 transfers and a £793 million portfolio sale. Both were rejected by earlier bounds that were too opinionated.

## Pipelines

Argo Workflows runs the jobs. Each job is a container and each pipeline is a sequence of them. There are five: ingest, feature refresh, training, promotion and drift checking. A sixth chains them into a single run for month end.

Every job is parameterised, so the same training definition runs one model or a sweep of three in parallel across the nodes.

## Training and tracking

MLflow records every training run: the parameters, the data it read, the scores, and the model file. Two runs of the same configuration on the same data produce identical numbers, which is how reproducibility is verified rather than assumed.

MLflow also holds the registry. One name, `champion`, points at whichever version is live. Training moves that pointer and serving reads it. Neither needs to know anything else about the other.

## The promotion gate

A newly trained model does not go live because it exists. It goes live because it is better.

The gate reads the new model's score and the champion's score on the same held out data. If the new one wins, it is registered, signed, and the `champion` name is moved. If it does not win, the gate stops, tags the run as refused, and leaves production alone.

This was tested with a deliberately bad model of 20 trees, which was refused. It was tested again with an identical retrain that tied rather than beat the champion, which was also refused.

## Features

Feast defines the features once and serves them to both training and inference. Training reads history from parquet. Inference reads current values from Redis.

The important property is that training only sees what was knowable at the time. Asking for a postcode's area statistics at three different sale dates returns three different historical values, not today's value repeated. Without that, a model learns from the future and looks excellent in testing before failing in production.

## Serving

A FastAPI service loads the champion model when it starts. Before loading, it verifies the model's signature against a public key. If the signature is missing or wrong, the pod refuses to start.

The health check makes a real prediction rather than only checking that a model object exists. That change came from an incident where every prediction failed for ninety minutes while the platform reported itself healthy.

## Deployment

New versions are not swapped in all at once. Argo Rollouts replaces half the pods, pauses, and queries live error rates before continuing. If the numbers are bad, or if progress stalls past a deadline, it destroys the new pods and leaves the old ones serving.

This was proven by deploying a model version that cannot load. The new pod crashed, the rollout reversed itself, and a stream of prediction requests ran throughout without a single failure.

## Monitoring

Prometheus collects metrics every fifteen seconds, Grafana draws them, and Loki makes every pod's logs searchable in one place. Alerts are based on error budgets, so a fast burn pages someone and a slow burn opens a ticket. Each alert has a runbook written before the incident rather than during it.

Evidently watches the data rather than the service. Each month it compares the newest records against the data the model trained on, and reports how far the distributions have moved.

## Signatures

GitHub Actions builds every container image, signs it, scans it for vulnerabilities and publishes a list of its contents. Kyverno checks those signatures when a pod is created, and refuses anything that does not carry one from this repository.

Models get the same treatment. The promotion step signs the model files, and the serving pod verifies that signature before loading. This was tested by tampering with a stored signature. The pod refused to serve while its sibling carried on answering requests.

## A month end run

New data is published. The ingest job downloads and validates it, then writes parquet to storage. The drift job compares it against the training reference. The feature job recomputes area statistics and pushes current values to Redis. Training fits a new model and logs it. The gate compares it to the champion and either promotes it or stops. If it promoted, the last step restarts the service, which brings the new model in gradually behind the rollout checks.

Nobody touches any of it.

## Reliability

Five failures were caused on purpose while traffic ran.

Killing a serving pod cost nothing, 90 requests and no failures, because a second replica and a disruption budget cover it. Draining an entire node cost one request out of 90, in the moment between the pod stopping and the load balancer noticing. Removing the feature store cost nothing, because the current model does not use it and the code checks before calling. Removing MLflow cost nothing while everything was running, but no new pod could start, because startup needs the registry. Killing the tracking database cost nothing, and the registry came back intact.

The MLflow result is the most useful one. That outage is invisible until something restarts, and then it is total.

## Repository layout

`ml/` holds the starting point, a script that goes from raw file to scored model.

`pipelines/` holds the job code: ingest, features, train and drift, each in its own container.

`services/serve/` holds the prediction API.

`platform/argocd/` holds one file per platform component, plus a root file pointing at the rest.

`platform/k8s/` holds the manifests those components install: namespaces and permissions, pipeline definitions, the serving deployment, policies and alerts.

`runbooks/` holds one file per alert, plus the postmortems and the chaos results.

## Relevance to roles

The whole project is MLOps and ML platform work.

The GitOps setup, tenancy, rollouts, admission policy and supply chain are platform and DevOps work.

The error budgets, alerts, runbooks, postmortems and chaos results are site reliability work.

The validated ingestion, partitioned storage and scheduled pipelines are data engineering.

The experiment tracking, evaluation gate, point in time correctness, drift detection and the recorded negative result are data science.
