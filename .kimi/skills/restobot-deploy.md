# restobot-deploy
version: 1.0.2
stack: Python,FastAPI,React,Docker,Caddy,Telegram

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

## ROLLBACK
- Caddyfile: ALWAYS backup before change: `cp /opt/restobot/Caddyfile /opt/restobot/Caddyfile.bak.$(date +%s)`
- Compose: previous `.env.prod` state is source of truth; `cd /opt/restobot && docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --force-recreate` to revert to last known image tags.
- Image rollback: if new image is broken, revert `ADMIN_IMAGE` / `PUBLIC_IMAGE` in `.env.prod`, then `cd /opt/restobot && docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --force-recreate`.
- Service-only rollback: `cd /opt/restobot && docker compose -f docker-compose.prod.yml --env-file .env.prod restart [admin|public|caddy|bot]`
