SHELL := /bin/sh

STATE_BACKEND_DIR := infra/state_backend
YC_DIR := infra/yc
BACKEND_FILE := $(YC_DIR)/backend.hcl

.PHONY: backend-bootstrap yc-backend-init bootstrap-all

backend-bootstrap:
	terraform -chdir=$(STATE_BACKEND_DIR) init
	terraform -chdir=$(STATE_BACKEND_DIR) apply -auto-approve

yc-backend-init:
	@test -f $(BACKEND_FILE) || cp $(YC_DIR)/backend.hcl.example $(BACKEND_FILE)
	@bucket="$$(terraform -chdir=$(STATE_BACKEND_DIR) output -raw tfstate_bucket_name)"; \
	access_key="$$(terraform -chdir=$(STATE_BACKEND_DIR) output -raw tfstate_access_key)"; \
	secret_key="$$(terraform -chdir=$(STATE_BACKEND_DIR) output -raw tfstate_secret_key)"; \
	sed "s/replace-with-tfstate-bucket-name/$$bucket/" $(YC_DIR)/backend.hcl.example > $(BACKEND_FILE); \
	ACCESS_KEY="$$access_key" SECRET_KEY="$$secret_key" terraform -chdir=$(YC_DIR) init -reconfigure -backend-config=backend.hcl

bootstrap-all: backend-bootstrap yc-backend-init
