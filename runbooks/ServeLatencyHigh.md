# ServeLatencyHigh

p95 latency on the prediction API is above 400ms for 15 minutes.

## First checks

1. `kubectl top pods -n akili-prod` — CPU throttling? The pods have small CPU requests; heavy load queues requests.
2. Is a training or feature-refresh workflow saturating the cluster? `kubectl -n argo get workflows` — LightGBM jobs are thread-capped but still heavy. Latency during a sweep is expected on this single-VM cluster.
3. `kubectl -n akili-prod get pods -l app=serve` — one pod down means the survivor takes double traffic.

## Mitigations

- If load is genuine: scale replicas in platform/k8s/serving/rollout.yaml via git.
- If a batch job is the cause: accept the blip (documented behaviour on this hardware) or move the job to off-peak in its CronWorkflow schedule.
