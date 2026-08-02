# Kyverno wedged: every pod creation fails

Symptoms: `kubectl` operations time out or return "context deadline exceeded"; pod creation in akili-prod or argo fails with a webhook error; the API server feels slow for everything.

## Confirm

```
kubectl -n kyverno get pods
kubectl -n kyverno get pod <admission-controller-pod> -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}'
```

Restarts climbing, or `OOMKilled`, means the policy engine is down. Because its webhooks are fail-closed, every guarded admission is being refused.

## Break glass

Deleting the webhook configurations restores the API immediately. Kyverno recreates them when it is healthy again, so this is a temporary loss of enforcement, not a permanent one.

```
kubectl delete validatingwebhookconfiguration -l webhook.kyverno.io/managed-by=kyverno
kubectl delete mutatingwebhookconfiguration -l webhook.kyverno.io/managed-by=kyverno
```

If the label selector matches nothing, list them and delete by name (they are prefixed `kyverno-`).

## Then fix the cause

Usually memory. Raise the admission controller limit in `platform/argocd/apps/kyverno.yaml` and let Argo CD apply it. Verification load scales with pod admission rate, so a crashlooping workload multiplies it.

Check afterwards that enforcement is back:

```
kubectl get validatingwebhookconfigurations | grep kyverno
kubectl -n akili-prod run test --image=ghcr.io/maicymxtim/akili-ingest@sha256:<bad-digest> --restart=Never
```

The second command must be refused.

## Prevention

- Keep the admission controller's memory generous relative to admission rate.
- Alert on kyverno pod restarts; it is on the critical path for every workload.
- Avoid crashloop storms in guarded namespaces: they multiply verification work.
