# Akili Platform

An MLOps platform that runs on Kubernetes. It takes a machine learning model and builds the infrastructure a team needs to operate it: pipelines that prepare data, training that is tracked and repeatable, a gate that decides which model goes live, deployment that can undo itself, monitoring that watches for the data changing, and signatures on everything that runs.

The model predicts UK house prices from Land Registry records. It is intentionally simple. The engineering around it is the project.

Source code: [github.com/MaicyMxtim/akili](https://github.com/MaicyMxtim/akili)

The platform runs on a laptop rather than a cloud account, so there is no public endpoint. It rebuilds from the repository with two commands.

## Contents

[Walkthrough](walkthrough.html). How the platform is put together and how a request moves through it.

[Costs](unit-economics.html). What the same capabilities cost as managed services, and when paying for them makes sense.

[Chaos experiments](https://github.com/MaicyMxtim/akili/blob/main/runbooks/chaos/experiments.md). Five deliberate failures with measured results.

[Postmortems](https://github.com/MaicyMxtim/akili/tree/main/runbooks/postmortems). Four real incidents from the build.

## Results

The model reaches £93,229 mean absolute error and 18.07% median error on a held out month, trained on 780,000 sales.

Reliability was measured by breaking things while traffic ran. Killing a serving pod cost nothing: 90 requests, no failures. Draining a whole node cost one request in 90. Losing the feature store, the tracking server or its database caused no failures at all.

Security was tested the same way. An image without a valid signature is refused by the cluster. A model whose signature has been tampered with will not load, and the pod refuses to start rather than serve it.

Running cost is nothing. The same platform bought as managed services would cost roughly £650 to £700 a month.

## Demonstrations

Every stage of the build finished with something demonstrable rather than a claim.

A deliberately corrupted data file was rejected, with a report naming the row and column at fault. Two identical training runs produced identical metrics. A deliberately weak model was trained and the gate refused to promote it. A broken model version was deployed on purpose, and the rollout detected it, reversed itself, and never dropped a request. Features read from the training store and the serving store matched exactly. Drift alerts stayed quiet on real data and fired on synthetic drift. The full retrain and deploy cycle ran twice with nobody touching it.

## Two findings worth stating

The area price features from the feature store made the model slightly worse, £95,602 against £93,229. They are recorded as a negative result rather than dropped quietly.

During the build, every prediction failed for ninety minutes while the platform reported itself healthy. The health check only confirmed that a model object existed, and the deployment check saw no errors because there was no traffic. Both are fixed, and the incident is written up in full.
