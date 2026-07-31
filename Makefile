DATA_URL := http://prod.publicdata.landregistry.gov.uk.s3-website-eu-west-1.amazonaws.com/pp-2025.csv

data/pp-2025.csv:
	mkdir -p data
	curl -fL -o $@ $(DATA_URL)

.PHONY: baseline
baseline: data/pp-2025.csv
	uv run python ml/baseline.py $<

.PHONY: cluster
cluster:
	k3d cluster create akili --servers 3 --agents 2 \
		--k3s-arg "--disable=traefik@server:*" \
		--wait

.PHONY: cluster-down
cluster-down:
	k3d cluster delete akili
