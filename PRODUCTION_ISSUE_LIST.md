# Production Issue List

Ниже заготовки GitHub issues для production-hardening текущего репозитория.

## 1. Harden bootstrap and onboarding admin endpoints before production

### Problem
The new admin bootstrap flow currently exposes `POST /admin/onboarding` as a production-capable endpoint without a dedicated bootstrap guard.

### Why this matters
Before production, tenant/bootstrap operations must not be callable by any regular runtime client.

### Scope
- Add a dedicated bootstrap protection mechanism.
- Prefer one of:
  - bootstrap token
  - IP allowlist
  - environment flag such as `ENABLE_BOOTSTRAP_API=false` by default
- Ensure the endpoint is disabled by default in production.
- Add tests for the disabled/forbidden path.

### Acceptance criteria
- Production deployment does not expose unrestricted onboarding.
- Tests cover success and rejection paths.
- Operator docs explain how bootstrap is enabled temporarily when needed.

## 2. Remove schema drift between Alembic and runtime tenant bootstrap DDL

### Problem
`shared/mvp_bootstrap.py` currently creates tenant schemas and tables at runtime, while Alembic also owns part of the schema lifecycle.

### Why this matters
This creates two sources of truth for DDL and makes production upgrades fragile.

### Scope
- Define one canonical ownership model for schema creation.
- Prefer moving tenant DDL into migrations or a dedicated provisioning workflow.
- Reduce or remove runtime table creation from application code.
- Document the provisioning sequence for a new tenant.

### Acceptance criteria
- Tenant schema/table creation is managed from one source of truth.
- Runtime code does not silently create production DDL that Alembic does not own.
- Deployment and tenant provisioning docs are updated.

## 3. Run and fix a full staging deployment in Yandex Cloud

### Problem
The repository now contains Terraform, Docker and migration tooling for Yandex Cloud, but the full cloud deployment path still needs a real staging validation.

### Scope
- Run the complete flow in YC:
  1. `infra/state_backend`
  2. `infra/yc` backend init
  3. bootstrap apply
  4. image build and push
  5. full apply
  6. migration runner invoke
  7. smoke test through API Gateway
- Fix any provider/runtime/gateway issues found during the run.
- Capture the final exact operator commands in docs.

### Acceptance criteria
- Staging deployment completes successfully end-to-end.
- Migration runner exits with code 0.
- `scripts/smoke_cloud.py` returns `SUCCESS` against the deployed gateway.
- Final docs match the real working sequence.

## 4. Harden YooKassa payment integration for production failure modes

### Problem
The payment flow is still MVP-grade. Config, worker behavior and webhook handling need explicit production validation.

### Scope
- Validate payment init behavior with real/realistic settings.
- Cover duplicate webhooks and webhook idempotency.
- Cover cancel/failure/refund paths.
- Cover timeout/retry behavior when YooKassa is unavailable.
- Add targeted tests around `payments/worker.py` and payment webhooks.

### Acceptance criteria
- Payment lifecycle is documented and tested.
- Duplicate webhook delivery is safe.
- Failure and cancel paths are deterministic.
- Production config expectations for `YOOKASSA_*` are explicit.

## 5. Secure Terraform remote state bootstrap and backend credentials

### Problem
The main stack now supports remote state in Yandex Object Storage, but the bootstrap stack still creates local state containing backend credentials.

### Scope
- Define the safe operational flow for `infra/state_backend`.
- Prevent accidental leakage of backend credentials.
- Consider migrating the bootstrap stack into a separate secured backend after initial creation.
- Review `.gitignore`, local artifacts and operator instructions.

### Acceptance criteria
- Backend credentials are not committed or casually persisted.
- The bootstrap flow is documented with clear handling guidance for local state.
- The team has an agreed path for key rotation and backend recovery.

## 6. Add production-grade observability: readiness, audit logs and key dimensions

### Problem
The project now has structured logging and a `/health` endpoint, but production operations need a stronger observability baseline.

### Scope
- Split liveness and readiness checks where appropriate.
- Extend logs with stable dimensions such as:
  - `request_id`
  - `tenant_id`
  - `user_id`
  - `order_id`
  - operation name
- Identify critical alerts/metrics for DB, Redis, gateway and containers.
- Update docs with log/metric lookup instructions.

### Acceptance criteria
- Operators can distinguish startup/aliveness/readiness failures.
- Core business actions emit structured audit-friendly log fields.
- Monitoring guidance exists for the deployed YC stack.

## 7. Document rollback, redeploy and recovery procedures

### Problem
A production rollout is not complete without tested rollback and recovery instructions.

### Scope
- Document how to roll back to a previous image tag.
- Document how to rerun migrations safely.
- Document how to redeploy only containers without recreating the full stack.
- Document how to recover after a failed `terraform apply`.

### Acceptance criteria
- A concise operator runbook exists for rollback and recovery.
- Image rollback commands are explicit.
- Migration rerun behavior is explained.
- Recovery steps are actionable during incidents.

## 8. Extend cloud API test coverage beyond baseline admin/public entrypoint tests

### Context
Baseline tests for `apps/admin_api` and `apps/public_api` were added in the `codex/yc-mvp-deploy` branch.

### Problem
The new cloud entrypoints now have route-level coverage, but they still need deeper end-to-end and authorization-focused scenarios before production.

### Scope
- Add deeper integration coverage for:
  - `/admin/onboarding`
  - `/admin/{tenant}/menu/upload`
  - `/admin/{tenant}/orders/*`
  - `/widget/{tenant}/session`
  - `/widget/{tenant}/orders/*`
- Add tenant isolation checks for the new app surfaces.
- Add negative tests for admin auth, token/header mismatch and malformed payloads.

### Acceptance criteria
- New admin/public entrypoints have dedicated integration coverage.
- Tenant mismatch and auth failures are explicitly tested.
- The cloud-facing API surface has meaningful confidence before staging deploy.
