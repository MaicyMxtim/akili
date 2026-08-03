# Akili Platform

An end-to-end MLOps platform on a virtual multi-node Kubernetes cluster, delivered entirely by GitOps, with validated data pipelines, experiment tracking and a model registry, an automated promotion gate, progressive delivery with automatic rollback, a feature store, drift monitoring, a signed supply chain covering both containers and model artifacts, reliability evidence, and published unit economics.

It is the counterpart to the [Tamani Platform](https://maicymxtim.github.io/tamani-platform/): Tamani covers consuming AI through a gateway and agents, Akili covers producing and operating models.

## Source

- **Repository:** [github.com/MaicyMxtim/akili](https://github.com/MaicyMxtim/akili)

The platform runs on a laptop rather than a public cloud, so there is no live endpoint. Everything is reproducible from the repository: `make cluster`, a handful of bootstrap secrets, and Argo CD installs the rest.

## Read

- **[Walkthrough](walkthrough.html)** — a tour of the finished platform: architecture, components, request paths and measured results.
- **[Unit economics](unit-economics.html)** — what the same capabilities cost as managed services, and when buying is the right call.
- **[Chaos experiments](https://github.com/MaicyMxtim/akili/blob/main/runbooks/chaos/experiments.md)** — five deliberate failures, each with a hypothesis and a measured result.
- **[Postmortems](https://github.com/MaicyMxtim/akili/tree/main/runbooks/postmortems)** — four real incidents and what they changed.

## Measured results

- **Model.** £93,229 mean absolute error, 18.07% median absolute percentage error on a held-out month, against 780,000 sales.
- **Reliability.** Killing a serving pod: 90 requests, no failures. Draining a node: 89 of 90. Losing the feature store, tracking server or database: no failures.
- **Supply chain.** An unverifiable image is refused at admission; a tampered model signature stops a pod serving while its sibling continues.
- **Cost.** Nothing to run; the managed equivalent prices at roughly £650–700 per month.

## What is proven, not just built

Every phase ended with a demonstration rather than a claim: a corrupted data file rejected with a per-row report; identical metrics across reruns; a deliberately weak model refused promotion; an unloadable model version canaried, aborted and rolled back with no interruption to traffic; point-in-time correct features; drift alerts firing on synthetic drift and staying quiet on real data; and the full retrain-to-deploy loop running with no human involvement.

## An honest note

The rolling area-price features from the feature store made the model slightly worse (£95,602 against £93,229) and are recorded as a negative result rather than quietly dropped. Four incidents during the build are written up in full, including one where every prediction failed for ninety minutes while the platform reported itself healthy.
