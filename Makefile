DATA_URL := http://prod.publicdata.landregistry.gov.uk.s3-website-eu-west-1.amazonaws.com/pp-2025.csv

data/pp-2025.csv:
	mkdir -p data
	curl -fL -o $@ $(DATA_URL)

.PHONY: baseline
baseline: data/pp-2025.csv
	uv run python ml/baseline.py $<

# 1 server + 4 agents: a 3-server etcd quorum on one laptop VM flapped the
# API under load (proven and written up); HA was demonstrated in Phase 1.
# Multi-node scheduling, drains and PDBs only need multiple agents.
.PHONY: cluster
cluster:
	k3d cluster create akili --servers 1 --agents 2 \
		--k3s-arg "--disable=traefik@server:*" \
		--wait

.PHONY: cluster-down
cluster-down:
	k3d cluster delete akili

# installs Argo CD and the root app; needs the repo deploy key secret in
# place first (see README). Everything else comes from git after this.
.PHONY: platform-up
platform-up:
	helm upgrade --install argocd argo/argo-cd --version 10.2.1 \
		-n argocd --create-namespace -f platform/argocd/values.yaml --wait
	kubectl apply -f platform/argocd/root.yaml
