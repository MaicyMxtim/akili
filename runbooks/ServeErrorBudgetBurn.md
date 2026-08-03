# ServeErrorBudgetBurn

The prediction API is returning 5xx at a rate that eats the 99.5% availability budget. Fast burn pages; slow burn is a ticket.

## First checks

1. `kubectl -n akili-prod get pods -l app=serve`. Crashlooping or OOMKilled pods?
2. `kubectl -n akili-prod logs -l app=serve --tail 50`. Model load failures usually mean MLflow or MinIO is unreachable, or the champion alias points at a broken version.
3. `kubectl -n akili-prod get rollout serve`. Is a canary mid-rollout? An aborted rollout with a failing canary can leave error spikes in the window.
4. Check MLflow and MinIO health: `kubectl -n mlflow get pods`, `kubectl -n minio get pods`.

## Common causes seen on this platform

- Champion model version unloadable (registry alias points at a deleted or broken run). Roll the alias back to the previous version in MLflow, or `git revert` the change that promoted it.
- MinIO or MLflow down: serving pods fail readiness after restart because the model cannot load. Fix the dependency, pods recover on their own.
- Memory pressure on the node killing pods: check `kubectl top nodes`.

## If the cause is a bad model version

The canary analysis should have caught it. If it reached stable anyway: `kubectl argo rollouts undo serve -n akili-prod`. Then investigate why analysis passed.
