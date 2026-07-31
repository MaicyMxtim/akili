# Incident 2: MLflow 3.14 process leak, then a migration race

Date: 2026-07-31. Duration: about 90 minutes of MLflow being down during Phase 4 bring-up. No experiment data lost (none existed yet). The rest of the platform stayed up, apart from a control-plane wobble covered below.

## What happened

Three problems chained together.

First, MLflow 3.14 (chart 1.11.2) leaks server processes. The pod OOMed at 512Mi, then at 1Gi, then at 1.5Gi, with one worker configured. The kernel log showed eight or more python processes of about 150MB each inside one pod. Reproduced outside Kubernetes: a plain docker container running the same image grew from 3 processes and 400MiB to 13 processes and 762MiB within a couple of minutes while idle. The version was the problem, not the platform.

Second, the crashloop churn (two replicasets of a big pod restarting for an hour, alongside everything else) put enough memory and I/O pressure on the Docker VM that the k3s servers were OOM killed again, and after a cluster restart etcd spent a while in leader-election loops with the API flapping. A full `k3d cluster stop && start` settled it.

Third, the fix (pin chart 1.8.1, MLflow 3.7) hit a migration race. The 3.14 pods had already stamped the database with a newer alembic revision than 3.7 knows, so 3.7's migration failed with "Can't locate revision". Wiping the schema did not help at first, and the reason was subtle: the deployment still had the old 3.14 replicaset alive mid-rollout, and after each wipe the OLD pod's migration init container re-applied the 3.14 schema before the new pod could migrate. The database kept getting re-poisoned by a pod that was supposed to be on its way out.

The fix that worked, in order: delete the old replicasets first, wipe the schema once, and let the single remaining 3.7 pod run its migration alone.

## Lessons

- When a pod OOMs at a limit that should be generous, stop raising the limit and go read the kernel OOM log on the node. Process count times per-process RSS tells you in one line whether it is a leak or a real requirement.
- Reproducing an in-cluster failure with plain `docker run` is fast and removes every Kubernetes variable at once. It settled in two minutes what an hour of limit-tweaking did not.
- A stuck rollout keeps the old replicaset alive, and old pods keep executing their init containers on every restart. Any init container with side effects (migrations especially) can race the replacement version. Kill the old replicaset before repairing shared state.
- Downgrading a service whose migrations already ran means restoring or resetting the database to match. Alembic will not walk backwards past an unknown revision.
- Pinning chart versions is not enough on its own; the pin has to be to a version you have reason to trust. The newest chart shipped a bad app release.
