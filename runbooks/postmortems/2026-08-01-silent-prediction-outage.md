# Incident 3: every prediction failed while the platform reported healthy

Date: 2026-08-01. Duration: roughly 90 minutes between the Phase 10 serving cutover and detection during Phase 11 load testing. No users affected (pre-production platform), no data lost.

## What happened

The Phase 10 cutover deployed a serving image that reads area features from the online store and passes them to the model. The champion it loaded (v3) was trained without those features, because Phase 9 measured them as unhelpful and put them behind a flag. LightGBM refuses input whose feature list does not match the model, so every call to /predict returned 500.

Nothing noticed. The rollout completed, the canary analysis passed, Prometheus targets stayed up, and /healthz returned 200 throughout.

## Why nothing noticed

- **/healthz only checked that the model object existed.** It never made a prediction, so a model that could load but not serve looked identical to a working one.
- **The canary analysis measured error rate, and there was no traffic.** Zero requests means zero errors, so the analysis passed a service that would have failed every real request. An analysis with no traffic is not evidence.
- **Prometheus target health tracks the /metrics endpoint**, which kept working. Scrape health is not service health.

Detection came from the first load test, which reported 100% request failure at real latencies (a connection problem gives near-zero latencies, so the timings were the clue that requests were arriving and being rejected).

## Fix

- Serving now projects each request onto `model.feature_name()`, so it sends exactly the features the loaded champion declares. This makes the service tolerant of champions trained with or without the area features.
- /healthz now performs a real prediction and returns 503 if it raises. A model that cannot predict can no longer report ready, so a bad version fails its readiness probe and the canary aborts on its own.

## Lessons

- A health check that does not exercise the real path is a liar. Cheap to write, and it converts a silent outage into an automatic rollback.
- Canary analysis needs traffic to mean anything. Either generate synthetic traffic during the analysis window or gate on a probe that exercises the path.
- When two artifacts must agree (model and serving code), one of them should adapt at runtime rather than both assuming. The model already declares its feature list; the service should read it instead of hardcoding.
- Latency shape distinguishes failure modes: connection refused gives ~0ms and huge request rates; application errors give normal latencies with non-2xx codes.
