# Chaos experiments

Each experiment states a hypothesis, the method, and what actually happened. Run against the three-node k3d cluster with the platform fully converged.

## C1 — serving survives losing a pod

**Hypothesis.** Killing one serving pod does not interrupt predictions, because two replicas run behind a PodDisruptionBudget requiring one available.

**Method.** Send a steady stream of prediction requests, delete one pod mid-stream, count failures.

**Result.** _pending_

## C2 — serving survives a node drain

**Hypothesis.** Draining an agent node reschedules the serving pod onto the other agent without dropping requests. This is the experiment the single-node Tamani cluster could never run.

**Method.** `kubectl drain` one agent with `--ignore-daemonsets --delete-emptydir-data` while requests flow, then uncordon.

**Result.** _pending_

## C3 — serving degrades gracefully without the feature store

**Hypothesis.** Killing Redis does not stop predictions, because the current champion does not use the online features and the serving code skips the lookup entirely when the model does not declare them.

**Method.** Scale Redis to zero, send predictions, restore.

**Result.** _pending_

## C4 — the platform survives losing MLflow

**Hypothesis.** Predictions continue when MLflow is down, because the model is loaded into memory at startup and never re-fetched. New pods, however, cannot start, so this is a latent failure that only appears at the next restart.

**Method.** Scale the MLflow deployment to zero, verify serving continues, then force a pod restart to demonstrate the latent dependency, then restore.

**Result.** _pending_

## C5 — the tracking database

**Hypothesis.** Killing the MLflow Postgres pod causes a brief MLflow outage and then recovery, since the data lives on a persistent volume.

**Method.** Delete the Postgres pod, watch it come back, confirm the registry still resolves the champion alias.

**Result.** _pending_
