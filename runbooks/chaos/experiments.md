# Chaos experiments

Run 2026-08-03 against the three-node k3d cluster (1 server, 2 agents) with the platform fully converged and champion v1 serving.

Traffic is generated from a long-lived pod inside the cluster, sending 90 prediction requests over about 40 seconds and counting non-200 responses.

**A measurement lesson first.** Two earlier attempts produced meaningless numbers. Driving traffic through `kubectl port-forward` reports 100% failure when the pod it is bound to is deleted, because the tunnel dies with that pod rather than the service failing. And one-shot probe pods that curl immediately on startup fail with connection timeouts, because the CNI has not finished programming their network rules yet; a pod that has been alive for twenty seconds works fine. Both look exactly like platform failures and are not. Generate load from inside the cluster, from a pod that already exists.

## C1 — serving survives losing a pod

**Hypothesis.** Killing one serving pod does not interrupt predictions, because two replicas run behind a PodDisruptionBudget requiring one available.

**Method.** Steady prediction traffic; delete one ready pod twelve seconds in.

**Result. Confirmed. 90 requests, 0 failures.** The surviving replica absorbed the traffic and the deleted pod was replaced without a visible gap.

## C2 — serving survives a node drain

**Hypothesis.** Draining an agent reschedules the serving pod onto another node without dropping requests. This is the experiment a single-node cluster cannot run at all.

**Method.** Steady traffic; `kubectl drain --ignore-daemonsets --delete-emptydir-data` on the node hosting a serving pod; uncordon afterwards.

**Result. Confirmed with one caveat. 89 of 90 requests succeeded (98.9%).** A single request failed at the instant of eviction. The pod rescheduled onto another node and the drain completed cleanly.

The single failure is worth keeping rather than tuning away: it is the window between the pod being killed and the endpoint being removed from the service. Eliminating it needs a preStop hook that delays shutdown for a few seconds while the endpoint drains, which is the standard fix and a fair improvement to note.

## C3 — serving degrades gracefully without the feature store

**Hypothesis.** Killing Redis does not stop predictions, because the current champion does not use the online features, and the serving code checks the model's declared feature list before attempting a lookup.

**Method.** Scale Redis to zero, run the probe, restore.

**Result. Confirmed. 90 requests, 0 failures.** The dependency is genuinely optional for this champion. Note that a champion trained *with* the area features would behave differently, and the graceful path there is the exception handler that returns null features rather than failing the request.

## C4 — the platform survives losing MLflow, until something restarts

**Hypothesis.** Predictions continue when MLflow is down, because the model is loaded into memory at startup and never re-fetched. New pods, however, cannot start, so this is a latent failure that only surfaces at the next restart.

**Method.** Scale MLflow to zero, run the probe, then delete a serving pod to force a replacement while the registry is still unavailable.

**Result. Confirmed, both halves. 90 requests, 0 failures** while MLflow was down. The replacement pod then could not become ready, because startup resolves the champion alias against the registry and verifies the model signature, both of which need MLflow.

This is the most operationally interesting finding in the set. A registry outage is invisible while everything is running and becomes an outage the moment anything restarts — a node drain, an eviction, a scale-up. The mitigation is to cache the verified model on disk and fall back to it when the registry is unreachable, so a restart during a registry outage is survivable.

## C5 — the tracking database

**Hypothesis.** Deleting the MLflow Postgres pod causes a brief tracking outage and then recovery, since the data sits on a persistent volume rather than in the pod.

**Method.** Delete the Postgres pod, run the probe throughout, then query the registry once it returns.

**Result. Confirmed. 90 requests, 0 failures**, and after the pod came back the registry still resolved the champion alias to v1. Serving was unaffected because it holds its model in memory, and the registry state survived because the volume outlived the pod.

The caveat from C4 applies here too: this looked harmless only because nothing needed to start during the outage.

## What these experiments changed

- The single dropped request during a drain justifies adding a preStop delay to the serving pods.
- C4 justifies treating the model registry as a startup-critical dependency and documenting it as such, rather than assuming serving is independent once running.
- Neither C1 nor C3 needed any change, which is its own result: the disruption budget and the optional-feature path both behave as designed under real failure.
