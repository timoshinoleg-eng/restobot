# restobot-deploy
version: 1.2.0
stack: Python,FastAPI,React,Docker,Caddy,Telegram,YC Serverless

## ARCHITECTURE
- VM: 51.250.91.143, ubuntu, ssh -i C:\Users\Имярек\.ssh\openclaw_key
- Paths: /opt/restobot (prod runtime), /opt/restobot-build (temp build context, created on demand)
- Services: admin:8000, public:8001, caddy:80/443, bot (no exposed port), db (external YC Managed)
- Images: ADMIN_IMAGE=restobot-local:latest, PUBLIC_IMAGE=restobot-local:latest (from .env.prod)
- Domain: app.chatbot24.su
- SSH template: & 'C:\Windows\System32\OpenSSH\ssh.exe' -i 'KEY' ubuntu@IP 'bash -c "COMMAND"'
- Node.js: must be installed on VM for `npm ci && npm run build`. If missing, build frontend locally and `scp -r dist/` to `/opt/restobot/frontend/webapp/`.

## HARD CONSTRAINTS (любая сессия с этим skill)
- Max 3 Shell tool calls per session.
- All remote ops: ONE ssh with && / ; .
- NEVER use sed/cat/tee to "fix" files on VM. Use scp or ssh+tee <<'EOF'.
- NEVER do intermediate validations. Batch validate at the end.
- NEVER rebuild image unless explicitly asked.
- NEVER modify .env.prod unless explicitly asked.
- ALL files written to VM MUST be LF-only (no CRLF). Use `dos2unix /path` or `sed -i 's/\r$//' /path` or write via `tee` directly on VM.
- ALL `docker compose` commands MUST include `-f docker-compose.prod.yml --env-file .env.prod`. Short `docker compose restart` is FORBIDDEN — it ignores prod env.

## CADDYFILE (production on VM)
```
{
}

http://:80 {
	log {
		output stdout
		format json
	}

	handle /admin/health {
		rewrite * /health
		reverse_proxy admin:8000
	}

	handle /widget/health {
		rewrite * /health
		reverse_proxy public:8001
	}

	handle /admin/* {
		reverse_proxy admin:8000
	}

	handle /widget/* {
		reverse_proxy public:8001
	}

	handle /api/* {
		reverse_proxy public:8001
	}

	header {
		X-Content-Type-Options "nosniff"
		X-Frame-Options "DENY"
		Strict-Transport-Security "max-age=31536000; includeSubDomains"
		Referrer-Policy "strict-origin-when-cross-origin"
	}

	handle {
		respond "Not Found" 404
	}
}

app.chatbot24.su {
	log {
		output stdout
		format json
	}

	route {
		handle /admin/* {
			reverse_proxy admin:8000
		}

		handle /widget/* {
			reverse_proxy public:8001
		}

		handle /api/* {
			reverse_proxy public:8001
		}

		handle {
			root * /srv/webapp
			try_files {path} /index.html
			file_server
		}
	}

	header {
		X-Content-Type-Options "nosniff"
		X-Frame-Options "DENY"
		Strict-Transport-Security "max-age=31536000; includeSubDomains"
		Referrer-Policy "strict-origin-when-cross-origin"
	}
}
```

## HTTP-ONLY CADDYFILE TEMPLATE (domain verification before HTTPS)
Use this ONLY for initial domain/A-record verification. Replace the full file, then switch back to production Caddyfile after confirming DNS.
```
{
	auto_https off
}

:80 {
	log {
		output stdout
		format json
	}

	handle /admin/health {
		rewrite * /health
		reverse_proxy admin:8000
	}

	handle /widget/health {
		rewrite * /health
		reverse_proxy public:8001
	}

	handle /admin/* {
		reverse_proxy admin:8000
	}

	handle /widget/* {
		reverse_proxy public:8001
	}

	handle /api/* {
		reverse_proxy public:8001
	}

	header {
		X-Content-Type-Options "nosniff"
		X-Frame-Options "DENY"
		Referrer-Policy "strict-origin-when-cross-origin"
	}

	handle {
		respond "Not Found" 404
	}
}
```
After DNS is verified, restore the production Caddyfile (with `app.chatbot24.su` block and without `auto_https off`).

## РАСХОЖДЕНИЯ РЕПО ↔ VM

### docker-compose.prod.yml
- **Статус: ИДЕНТИЧНЫ** (проверено 2026-05-04)
- Локальный `docker/docker-compose.prod.yml` и `/opt/restobot/docker-compose.prod.yml` на VM совпадают побайтно.
- **Важно:** compose УЖЕ содержит `command: ["python", "scripts/run_admin.py"]` для admin и `command: ["python", "scripts/run_public.py"]` для public. Можно копировать compose с VM на репо и обратно без правки `command`.

### Caddyfile
- **Расхождение: exact-match routes**
- Локальный `docker/Caddyfile` содержит exact-match `handle /admin` и `handle /widget` (без wildcard) для редиректа на backend.
- На VM `/opt/restobot/Caddyfile` НЕ содержит exact-match `/admin` и `/widget` — только `/admin/*`, `/widget/*`, `/api/*`.
- Exact-match `/admin/health` и `/widget/health` присутствуют и локально, и на VM.
- **Рекомендация:** exact-match `handle /admin` (without wildcard) exists in local repo but is INTENTIONALLY ABSENT on VM. `handle /admin/*` (with wildcard) covers `/admin` and `/admin/...` correctly. DO NOT add exact-match to VM Caddyfile — this is NOT a bug.

### Dockerfile
- **На VM:** файла `/opt/restobot/Dockerfile` НЕТ. Образ `restobot-local:latest` собран из `docker/Dockerfile.admin` и `docker/Dockerfile.public`.
- **В локальном репо:** в корне есть `Dockerfile` (legacy), который использует `CMD ["python", "-m", "api.main"]` (port 8001, подходит для public, НЕ подходит для admin). 
- `docker/Dockerfile.admin` и `docker/Dockerfile.public` — правильные production-образы с корректными CMD.

### Порты
- **На VM:** порт 80 слушает (`ss -tlnp` подтверждает). Порт 443 НЕ слушает.
- **Причина:** Caddyfile на VM не имеет `auto_https off`, но блок `app.chatbot24.su` активен. Если домен не резолвится или нет A-записи, Caddy не открывает 443.
- **Действие:** проверить A-запись домена и YC Security Group для 443.

## DOCKER-COMPOSE FIXES
- admin service already has correct command: `["python","scripts/run_admin.py"]`
- public service already has correct command: `["python","scripts/run_public.py"]`
- bot service uses command: `["python","-m","bot.main"]`
- Default CMD in legacy root Dockerfile is `python -m api.main` (port 8001) — correct for public, WRONG for admin; admin MUST use `docker/Dockerfile.admin` which sets correct CMD.
- Healthchecks in compose AND Dockerfile use `python3 -c "import urllib.request; urllib.request.urlopen(...)"` — they do NOT use curl. Containers on VM show `healthy` status.
- Dockerfile EXPOSE 8000 8001, but only internal ports matter; Caddy proxies to admin:8000 and public:8001.

## ОБЯЗАТЕЛЬНЫЕ ENV-ПЕРЕМЕННЫЕ (из .env.prod)
- ADMIN_IMAGE
- PUBLIC_IMAGE
- DATABASE_URL
- REDIS_HOST
- REDIS_PORT
- REDIS_PASSWORD
- REDIS_DB
- REDIS_TLS_ENABLED
- JWT_SECRET
- TELEGRAM_BOT_TOKEN
- TELEGRAM_WEBHOOK_URL
- TELEGRAM_WEBHOOK_SECRET
- TELEGRAM_BOT_DEFAULT_TENANT_ID
- YOOKASSA_SHOP_ID
- YOOKASSA_SECRET_KEY
- YOOKASSA_RETURN_URL
- YC_FOLDER_ID
- YC_IAM_TOKEN
- YC_OBJECT_STORAGE_BUCKET
- YC_OBJECT_STORAGE_ENDPOINT
- ENABLE_BOOTSTRAP_API
- BOOTSTRAP_API_TOKEN

## HEALTHCHECK
- **Механизм:** `python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:PORT/health')"`
- **curl в образе ОТСУТСТВУЕТ.** Не паниковать, если healthcheck не использует curl — python urllib работает.
- **Статус на VM:** admin и public контейнеры имеют статус `(healthy)`. bot имеет `healthcheck: disable: true`.
- **Если статус `unhealthy`:** сначала `docker logs --tail 30 restobot-admin-1` (или public), затем проверь `docker exec restobot-admin-1 python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"`. НЕ перезапускай весь стек без чтения логов.

## YC FIREWALL CHECK
- Порты 80 и 443 должны быть открыты в Yandex Cloud Security Group для ingress.
- **Проверка на VM:** `ss -tlnp | grep -E ':80|:443'`
- Если 443 не слушает — сначала проверить A-запись домена, затем Security Group, затем Caddy logs.
- **Команда для проверки Caddy listener:** `docker exec restobot-caddy-1 ss -tlnp | grep -E ':80|:443'`

## ONE-LINERS (copy-paste ready)

### Frontend build
```bash
cd /opt/restobot/frontend/webapp && npm ci && npm run build
```

### Full stack restart
```bash
cd /opt/restobot && docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --force-recreate
```

### Caddy only restart
```bash
cd /opt/restobot && docker compose -f docker-compose.prod.yml --env-file .env.prod restart caddy
```

### Batch verification (HTTP + validate)
```bash
curl -s -o /dev/null -w "demo_menu:%{http_code}\n" http://app.chatbot24.su/demo/menu && \
curl -s -o /dev/null -w "widget:%{http_code}\n" http://app.chatbot24.su/widget/demo/menu && \
curl -s -o /dev/null -w "admin_health:%{http_code}\n" http://app.chatbot24.su/admin/health && \
docker exec restobot-caddy-1 caddy validate --config /etc/caddy/Caddyfile
```

### Batch verification (HTTPS)
```bash
curl -s -o /dev/null -w "https_demo:%{http_code}\n" --insecure https://app.chatbot24.su/demo/menu && \
curl -s -o /dev/null -w "https_widget:%{http_code}\n" --insecure https://app.chatbot24.su/widget/demo/menu
```

## TYPICAL TASKS (prompt patterns)

### Переключить домен на DOMAIN
1. Backup Caddyfile: `cp /opt/restobot/Caddyfile /opt/restobot/Caddyfile.bak.$(date +%s)`
2. Replace `app.chatbot24.su` with new domain in `/opt/restobot/Caddyfile` on VM (production template from skill). Use `scp` or `ssh + tee <<'EOF'` per HARD CONSTRAINTS.
3. Update `YOOKASSA_RETURN_URL` and any frontend references in `.env.prod` (only if explicitly asked).
4. Restart Caddy: `cd /opt/restobot && docker compose -f docker-compose.prod.yml --env-file .env.prod restart caddy`
5. Verify HTTP first: `curl -s -o /dev/null -w "%{http_code}" http://DOMAIN/demo/menu`
6. Verify HTTPS after DNS propagation: `curl -s -o /dev/null -w "%{http_code}" --insecure https://DOMAIN/demo/menu`

### Добавить новый API endpoint /api/v2/...
1. Add route in `apps/public_api/main.py` or `apps/admin_api/main.py`.
2. Add Caddy `handle /api/v2/* { reverse_proxy public:8001 }` if needed (usually `/api/*` already covers it).
3. Restart affected service only: `cd /opt/restobot && docker compose -f docker-compose.prod.yml --env-file .env.prod restart admin` (или `public`).

Important:
- for **VM docker-compose**, service names are `admin` and `public`;
- names `admin_api` and `public_api` refer to **YC Serverless Containers / Terraform** resources, not compose services.

### Переключиться с HTTP-only на HTTPS (новый домен)
1. Ensure A-record points to VM IP.
2. Replace HTTP-only Caddyfile with production template (remove `auto_https off`, add `DOMAIN` block).
3. Open port 443 in YC Security Group.
4. Restart Caddy: `cd /opt/restobot && docker compose -f docker-compose.prod.yml --env-file .env.prod restart caddy`
5. Wait 30-60s for Let's Encrypt.
6. Verify: `curl -s -o /dev/null -w "%{http_code}" --insecure https://DOMAIN/demo/menu`
7. If `connection refused` on 443 — check YC firewall FIRST, do NOT edit Caddyfile.

### Откатить Caddyfile
1. List backups: `ls -lt /opt/restobot/Caddyfile.bak*`
2. Restore: `cp /opt/restobot/Caddyfile.bak.XXXXXX /opt/restobot/Caddyfile`
3. Restart Caddy: `cd /opt/restobot && docker compose -f docker-compose.prod.yml --env-file .env.prod restart caddy`

## TELEGRAM CHECKS
- getMe: `curl -s https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe`
- getWebhookInfo: `curl -s https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo` — must return empty `webhook_url` (polling mode). VM `.env.prod` has `TELEGRAM_WEBHOOK_URL=` (empty)
- WebApp URLs: `https://app.chatbot24.su/{tenant}/menu` and `https://app.chatbot24.su/{tenant}/order`
- Bot command: `python -m bot.main` (compose `command` already set)

## GOTCHAS
- PowerShell heredoc through ssh breaks on quotes. Always use: `ssh ... 'bash -c "..."'` or scp file then ssh to run.
- Windows CRLF → Linux LF: always write configs via `tee` on VM, never scp raw text from Windows editor.
- Tenant `demo` may not exist in DB → `/widget/demo/menu` returns `{"detail":"Not Found"}`, this is EXPECTED. Any `/{tenant}/menu` path is handled by SPA `try_files` (serves `index.html`), NOT by Caddy 404. Only API calls to `/widget/{tenant}/menu` hit backend and may 404 if tenant missing.
- Bot logs may appear empty in `docker logs` because structlog writes to stdout only on events; process running = OK.
- `localhost:8000/8001` are NOT exposed externally; check only via Caddy proxy or `docker exec`.
- YooKassa return URL in prod: `https://app.chatbot24.su/demo/menu`
- Caddyfile on VM has a backup at `/opt/restobot/Caddyfile.bak` (created manually). Compose backup: `.env.prod.before_manual_deploy_20260502` and `.env.prod.codex-pre-smoke.bak`.
- Frontend dist exists at `/opt/restobot/frontend/webapp/dist/index.html` + assets.
- Database is external (YC Managed PostgreSQL at `rc1a-skqer2ssphs8dhib.mdb.yandexcloud.net:6432`).
- Redis is external (YC Managed Redis at `rc1a-9qjbbk3fmsdjlb6h.mdb.yandexcloud.net:6379`, TLS disabled).
- Exact-match `/admin` and `/widget` routes are present in local repo `docker/Caddyfile` but INTENTIONALLY ABSENT on VM. DO NOT add them.
- If `curl https://DOMAIN` fails with `connection refused` — FIRST check `ss -tlnp | grep :443` on VM. If 443 is not listening, the problem is YC Security Group or DNS A-record, NOT Caddyfile. DO NOT touch Caddyfile. Fix firewall first.

## YC SERVERLESS CONTAINERS (Terraform: infra/yc)
- **Terraform dir:** `infra/yc` (локально и на VM `/opt/restobot/infra/yc`)
- **Backend:** S3 `restobot-tfstate-bucket-unique-20260430`
- **Images:** `cr.yandex/crp3m1quoo95obppic6e/restobot-{admin,public,migrate}:TAG`
- **Gateway:** `https://d5dql99olrs7m7lascpm.628pfjdx.apigw.yandexcloud.net`
- **DB:** `restobot-mvp-postgres` (`rc1a-skqer2ssphs8dhib.mdb.yandexcloud.net:6432`)
- **Redis:** `restobot-mvp-redis` (`rc1a-9qjbbk3fmsdjlb6h.mdb.yandexcloud.net:6379`, TLS disabled)
- **VPC:** `enp9gvbk39vipha0ib4o`, subnets `10.0.1.0/24` (a), `10.0.2.0/24` (b), `10.0.3.0/24` (d)
- **Runtime SA:** `ajeekhvh9qclb84dmce2` (roles: `serverless.containers.invoker`, `container-registry.images.puller`, `monitoring.editor`, `vpc.user` **required for connectivity**)
- **Connectivity status:** SOLVED — `GET /health` returns **200** consistently. Root cause был двойной: отсутствие `connectivity` + missing SG ingress для YC Serverless service subnet (`198.19.0.0/16`).

### Container entrypoint
- Образы собираются из `docker/Dockerfile.admin` и `docker/Dockerfile.public`.
- В Dockerfile CMD: `python scripts/run_admin.py` / `python scripts/run_public.py` (скрипты корректно настраивают `sys.path`).
- **Terraform `containers.tf` ПЕРЕОПРЕДЕЛЯЕТ** entrypoint на `command = ["python"]`, `args = ["-m", "apps.admin_api.main"]` с `work_dir = "/app"`.
- Оба подхода работают в актуальных образах. Старые образы в registry (`manual-20260502000125-12fea33` и ранее) имели проблему с `ModuleNotFoundError`, которая решена в текущем коде.

### Connectivity & DNS
- **Without `connectivity`:** serverless runtime cannot resolve YC Managed DB/Redis FQDNs → `/health` returns **503** with `Name or service not known` for BOTH DB and Redis.
- **With `connectivity` ON but SG blocks the serverless source range:** DNS resolves, but TCP SYN is dropped by the DB/Redis security group → TCP hangs → container execution timeout → **504** from gateway.
- **With connectivity + SG OK, но singleton Redis stale:** DB healthy, Redis unhealthy с ошибкой `TCPTransport closed=True` → fast **503** (~1-2s). Решение в `shared/redis_client.py` (см. раздел Redis stability).
- **Required fix order:**
  1. Enable `serverless=true` on PostgreSQL cluster (`configSpec.access.serverless` via API or Terraform).
  2. Add `connectivity { network_id = yandex_vpc_network.restobot.id }` to admin/public/migration containers.
  3. Ensure runtime SA has `vpc.user` role on folder BEFORE creating the revision with connectivity.
  4. **Add SG ingress rules for YC Serverless service subnet `198.19.0.0/16`** on DB (6432) and Redis (6379, 6380) ports.  
     This is the documented YC Serverless runtime NAT/service CIDR — not empirical magic.  
     Without it the managed services drop packets from serverless revisions even though DNS and `serverless=true` are correct.  
     See `infra/yc/security-group-rules.tf`.
  5. **Fix Redis singleton reconnect** (см. ниже).

### PostgreSQL serverless access (API)
```bash
# GET current access
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://mdb.api.cloud.yandex.net/managed-postgresql/v1/clusters/$CLUSTER_ID"

# PATCH (correct field is configSpec, not config)
curl -s -X PATCH \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"configSpec": {"access": {"serverless": true}}, "updateMask": "configSpec.access.serverless"}' \
  "https://mdb.api.cloud.yandex.net/managed-postgresql/v1/clusters/$CLUSTER_ID"
```
- Operation takes ~60s; verify with `GET /operations/{opId}`.
- **Do NOT confuse** with `serverless_access` Terraform variable — that is a different concept (previously misleading).

### Cloud Logging (read via SDK, NOT yc CLI)
- `yc logging read` requires **OAuth token**; IAM token fails with "OAuth token is invalid".
- **Working approach:** Python `yandexcloud` SDK with IAM token over gRPC.
- Default log group: `e23g5h28u4b6je0hgvmc` (folder `b1g447hnv7s5o74n4qcr`).
- Resource type for serverless container logs: `serverless-container` (with hyphen).
- Example: see `/tmp/get_logs7.py` pattern on VM.

### Gateway vs Direct Invoke
- **Gateway:** `https://d5dql99olrs7m7lascpm.628pfjdx.apigw.yandexcloud.net/health`
  - Hard timeout ~30s. If container takes >30s, returns **504** (`JobExecutionTimeoutExceeded`).
- **Direct invoke:** `https://bbat13jql8mciiac5g21.containers.yandexcloud.net/health`
  - Requires `Authorization: Bearer <IAM-token>` with `serverless.containers.invoker` role on the container (or `allUsers` binding for unauthenticated).
  - Useful for diagnostics when gateway returns 504 but you need the actual body.

### Execution timeout
- Default: `30s`. Increase to `60s` temporarily for diagnostics if container hangs on DB retries.
- `check_database_health` retries 5 times with exponential backoff (delay 1.5s → ~22s total sleep), so 30s is tight.

### Redis stability in serverless (singleton fix)
- **Проблема:** `redis.asyncio` singleton (`_redis`) переживает idle/pause циклы Serverless Containers. TCP-соединение закрывается платформой, но Python-объект остаётся. При повторном `get_redis()` возвращается мёртвый клиент → `TCPTransport closed=True`.
- **Решение (уже в `shared/redis_client.py`):**
  - `health_check_interval=30` — пул сам проверяет соединения.
  - `retry_on_timeout=True`, `socket_keepalive=True`.
  - `check_redis_health()` ловит `ConnectionError`, сбрасывает `_redis = None` и пробует один раз пересоздать клиент.
  - Cache-helpers (`get_cache`, `set_cache`, `delete_cache`) отдельно ловят `ConnectionError` и сбрасывают `_redis`.
  - `shared/app_factory.py` инициализирует Redis **eagerly** в lifespan (`await get_redis()` на старте), а не lazy при первом запросе.

### Admin static files
- `static/admin/` (index.html, menu.html, orders.html) должен попадать в образ через `COPY` в Dockerfile.
- Если `GET /admin/` возвращает 404 — образ собран без `static/admin/` (либо старый образ в registry).
- FastAPI монтирует `StaticFiles` в `apps/admin_api/main.py` при наличии директории.

### Build & deploy from Windows
- **Docker Desktop должен быть запущен.** Если `docker version` показывает `failed to connect to the docker API` — запустить Docker Desktop.
- **Build:** `docker build --platform linux/amd64 -f docker/Dockerfile.{admin,public} -t cr.yandex/.../restobot-{admin,public}:TAG .`
- **Push:** `yc container registry configure-docker`, затем `docker push cr.yandex/.../restobot-{admin,public}:TAG`
- **Migration image:** `docker tag admin-image migrate-image && docker push migrate-image`
- **Terraform:**
  - `terraform.tfvars.pilot` — реальные значения с секретами. **НЕ КОММИТИТЬ.**
  - `terraform.tfvars.example` — шаблон без секретов, можно в repo.
  - `terraform init -backend-config=.tmpdeploy/backend.hcl`
  - `terraform plan -var-file=terraform.tfvars.pilot -out=deploy.tfplan`
  - `terraform apply deploy.tfplan`
- **YC auth для Terraform:** `export YC_TOKEN=$(yc iam create-token)` или `TF_VAR_yc_token=...`.

### Typical Terraform apply flow
```bash
cd /opt/restobot/infra/yc
export YC_TOKEN=$(yc iam create-token)
terraform plan -var-file=terraform.tfvars.pilot -out=deploy.tfplan
terraform apply deploy.tfplan
```

## ROLLBACK
- Caddyfile: ALWAYS backup before change: `cp /opt/restobot/Caddyfile /opt/restobot/Caddyfile.bak.$(date +%s)`
- Compose: previous `.env.prod` state is source of truth; `cd /opt/restobot && docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --force-recreate` to revert to last known image tags.
- Image rollback: if new image is broken, revert `ADMIN_IMAGE` / `PUBLIC_IMAGE` in `.env.prod`, then `cd /opt/restobot && docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --force-recreate`.
- Service-only rollback: `cd /opt/restobot && docker compose -f docker-compose.prod.yml --env-file .env.prod restart [admin|public|caddy|bot]`

## CURRENT DEPLOY STATE (as of 2026-05-05)
- **Schema:** `005` (head)
- **Active image tag:** `manual-20260505141001-3f3f6ea`
- **Status:** GO — all infra baseline + migration 005 confirmed stable
- **Terraform last apply:** 0 added, 3 changed, 0 destroyed (admin/public/migrate image tags only)
- **Known operational item:** legacy `demo` tenant has `password_hash=null` and `setup_token=null` in DB. Admin login for this tenant requires manual activation (set `setup_token` or `password_hash` via DB or onboarding flow).
