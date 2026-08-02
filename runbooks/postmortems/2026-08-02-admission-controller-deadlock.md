# Incident 4: a fail-closed admission controller took the cluster down

Date: 2026-08-02. Duration: about 40 minutes of cluster-wide admission failure during Phase 11. No production users; the platform could not create any pod in the guarded namespaces.

## What happened

While repeatedly redeploying the serving component to fix a prediction bug, pods crashlooped. Every pod creation triggers Kyverno's image-signature verification, which fetches signatures from the registry and consults the public transparency log. A crashloop storm therefore became a verification storm.

Kyverno's admission controller, limited to 384Mi, was OOMKilled repeatedly. Its webhooks are configured `failurePolicy: Fail`, meaning "if the policy engine cannot answer, refuse the request". With the engine dead, that rule applied to every pod creation in the guarded namespaces, and API requests hung for the webhook's 30 second timeout before failing.

The deadlock: fixing Kyverno required API calls, and the API was being blocked by Kyverno's own broken webhooks.

## Recovery

Delete the Kyverno webhook configurations. The API immediately became responsive, the deployment could be patched to 768Mi, and Kyverno recreates its own webhook configurations once healthy. Enforcement is restored automatically; the window in between is unguarded, which is the price of the recovery.

## Contributing causes

- **Memory sized for idle, not for load.** Signature verification is network and memory heavy, and nothing had ever exercised it at rate before.
- **A rollout whose stable version was also broken.** Every aborted canary fell back to a previous version that had the same defect, so each attempt recreated pods and fed the storm. The fix was to delete the Rollout and let GitOps recreate it with no bad predecessor.
- **Digest pinning hid the fix.** Kyverno's verification mutates the pod spec to the digest it verified. Pods therefore stay pinned to the digest present when first admitted, so `:main` with `imagePullPolicy: Always` never picks up a newer build on restart. Only freshly admitted pods get the current image, which explained several "the fix didn't apply" cycles.

## Lessons

- Fail-closed is the right default for a security control and the wrong default for the control's own availability. Either give the webhook generous resources and multiple replicas, or scope `failurePolicy: Fail` to the namespaces that truly need it and leave the rest fail-open.
- Know the break-glass procedure before you need it: deleting the webhook configurations is the standard escape from a wedged admission controller, and it belongs in a runbook rather than being discovered mid-incident.
- Anything that fires on every pod admission is on the critical path of the whole cluster. Size it accordingly and alert on its restarts.
- Mutating admission and mutable tags interact badly. The correct fix is for CI to write the immutable digest into the manifest so git states exactly what runs, instead of relying on a moving tag.
