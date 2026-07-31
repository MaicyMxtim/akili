# Incident 1: Docker VM out of memory, two control-plane nodes killed

Date: 2026-07-31. Duration: about 10 minutes of degraded control plane. No data lost.

## What happened

During the Phase 3 rollout (MinIO, Argo Workflows and the pipelines app syncing at the same time), the Docker Desktop VM hit its 7.75GB default memory allocation. The kernel killed the k3s processes in two of the three server containers. Docker restarted them, but while they were coming back the API server intermittently returned ServiceUnavailable, and in-cluster DNS lookups timed out, which made Argo CD sync retries fail with DNS errors against its own repo-server.

## How it showed up

- Argo CD app status: ComparisonError, "dns: A record lookup error ... i/o timeout".
- kubectl returning "the server is currently unable to handle the request".
- docker stats showing two server containers at around 230MiB when they had been at 1.4GiB and 2GiB, meaning their processes had restarted.
- docker ps showing server-0 up 8 minutes and server-2 up 1 minute while everything else was up 47 minutes.

## Root cause

The VM allocation was the default 7.75GB. Steady state before Phase 3 was already about 5.9GB, and the simultaneous arrival of MinIO, the Argo Workflows CRD install job and new image pulls pushed it over. Kernel OOM killed the biggest targets, which were k3s server processes.

This is the same failure mode as Tamani incidents 1 and 2: the platform grows, memory headroom quietly disappears, and the next rollout tips it over.

## Fix

Docker Desktop memory raised from the 7.75GB default to an explicit 10GB (MemoryMiB 10240 in settings-store.json) and Docker restarted. The cluster containers restart automatically and the HA control plane recovers on its own.

## Lessons

- The etcd HA design worked: with three servers, losing two to OOM kills degraded the API but the cluster state survived and everything self-recovered. On the single-node Tamani setup the equivalent incident needed a manual reboot.
- Check memory headroom before rolling out a batch of new platform components, not after. docker stats is one command.
- Deploying three new apps at once made diagnosis noisier than deploying them one at a time would have.
- k3d containers do not restart on their own after Docker Desktop quits, even with an unless-stopped restart policy. After any Docker restart, run `k3d cluster start akili`.
