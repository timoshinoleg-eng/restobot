# RestoBot Pilot Go-Live Package
**Ветка:** `codex/yc-mvp-deploy`  
**Среда:** VM (`51.250.91.143`) + YC Managed Postgres/Redis  
**Цель:** минимальный риск, запуск пилота за 1 день

---

## 1. P0 Go-Live Checklist (30–90 мин)

Выполнять строго по порядку. Любой FAIL → остановка, разбор, фикс.

| # | Шаг | Команда / Действие | Ожидаемый результат | Если FAIL |
|---|-----|-------------------|---------------------|-----------|
| 1 | **Локальная валидация** | `pytest -m "not cloud"` (в CI или локально) | `163 passed`, фронтенд билд OK | Фиксить баги, не деплоить |
| 2 | **Checkout ветки** | `git log --oneline origin/main..HEAD` | Убедиться, что коммиты осознанные | Лишние коммиты → `git rebase -i` или `git reset` |
| 3 | **Билд образов** | CI собирает `admin`/`public` images, тег `pilot-YYYYMMDD-N` | Образы в Container Registry | Локально проверить `docker build` |
| 4 | **SSH на VM** | `ssh -i ~/.ssh/openclaw_key ubuntu@51.250.91.143` | Сессия открыта | Проверить VPN/YC SG |
| 5 | **Сохранить rollback-точку** | `cd /opt/restobot && cat .rollback.env` | Два ключа `ADMIN_IMAGE=` / `PUBLIC_IMAGE=` | Скопировать вручную в `.rollback.env` |
| 6 | **Проверить `.env.prod`** | `grep -E "^(DATABASE_URL|REDIS_HOST|REDIS_TLS_ENABLED|JWT_SECRET|YOOKASSA|TELEGRAM_BOT_TOKEN|ENABLE_BOOTSTRAP_API)" .env.prod` | Все ключи заданы, `ENABLE_BOOTSTRAP_API=false` | Не деплоить с включённым bootstrap |
| 7 | **Деплой** | `./deploy.sh cr.yandex/xxx/restobot-admin:pilot-YYYYMMDD-N cr.yandex/xxx/restobot-public:pilot-YYYYMMDD-N` | `Deploy successful` | Автооткат сработает через 90 сек; если нет — `./rollback.sh` |
| 8 | **Ingress smoke** | `bash ingress_smoke.sh http://localhost` | `INGRESS SMOKE PASSED` | Проверить Caddyfile, перезапустить `caddy` |
| 9 | **Health gates** | `curl -s -o /dev/null -w "%{http_code}" http://localhost/admin/health && curl ... /widget/health` | `200` + `200` | Логи `docker logs restobot-admin-1` — коннект к БД/Redis |
| 10 | **Demo tenant reset** | `docker cp ./scripts/seed_demo_tenant.py restobot-admin-1:/tmp/seed_demo_tenant.py && docker exec restobot-admin-1 python3 /tmp/seed_demo_tenant.py --tenant-id demo --reset` | JSON с `admin_token` != null, `categories_written=2` | Проверить schema `tenant_demo` в Postgres, права доступа |
| 11 | **CLI smoke E2E** | `poetry run python scripts/smoke_cli_tenant.py --gateway-url http://51.250.91.143 --tenant-id demo --admin-token <token>` | `SUCCESS` + `order_id=<id>` | Логи admin/public, повторить с `demo --reset` |
| 12 | **YooKassa callback readiness** | Убедиться, что в YooKassa dashboard webhook URL ведёт на `https://app.chatbot24.su/api/v1/{tenant}/webhook/yookassa` | URL доступен извне, TLS OK | Проверить Caddy + firewall + DNS A-запись |
| 13 | **Bot sanity** | `docker compose logs -f bot` → написать боту `/start demo` | Бот отвечает, выдаёт кнопку меню | Проверить `TELEGRAM_BOT_TOKEN`, polling mode, `TELEGRAM_BOT_DEFAULT_TENANT_ID` пустой |
| 14 | **Frontend build sanity** | `python scripts/smoke_webapp.py --gateway-url http://51.250.91.143 --tenant-id demo` | `PASSED` (SPA routes, widget session) | Пересобрать `frontend/webapp`, перезапустить `caddy` |
| 15 | **Backup checkpoint** | Скопировать `.rollback.env` и свежий `admin_token` в pass-менеджер | Артефакты сохранены | — |

**Время выполнения:** 30 мин (если CI уже собрал образы) — 90 мин (если сборка локально + отладка).

---

## 2. E2E Smoke Script для 1 tenant (production-like)

Целевой tenant: `pilot_<client>` (не `demo` — `demo` это песочница).  
Предполагается, что `ENABLE_BOOTSTRAP_API=false`, поэтому provisioning только через CLI.

### Шаг A. Provision tenant
| | |
|---|---|
| **Входные данные** | `tenant_id` (slug, `[a-z0-9_]+`), restaurant name, admin email/phone |
| **Команда** | ```docker exec restobot-admin-1 python3 /tmp/provision_tenant.py --tenant-id pilot_bistro --restaurant-name "Bistro Pilot" --admin-name "Owner" --admin-email "owner@bistro.ru" --admin-phone "+79991112233" --min-order-amount 500.0``` |
| **Точка проверки** | JSON stdout содержит `tenant_id`, `tenant_schema=tenant_pilot_bistro`, `admin_user_id`, `setup_token` (raw) |
| **Типовой сбой** | `tenant_id` уже существует → скрипт идемпотентен, обновит настройки и вернёт существующего admin. **Mitigation:** проверить `admin_token` в выводе; если пароль уже задан — использовать `set_admin_password.py` |

### Шаг B. Menu upload / seed
| | |
|---|---|
| **Входные данные** | `MENU_UPLOAD_TEMPLATE.json` или `demo_seed.py` |
| **Команда** | ```docker exec restobot-admin-1 python3 /tmp/upload_menu.py --tenant-id pilot_bistro --menu-file /tmp/menu.json --min-order-amount 500.0``` |
| **Точка проверки** | `categories_written >= 1`, `items_written >= 1` |
| **Типовой сбой** | JSON parse error → проверить кодировку UTF-8, BOM, валидность schema (поля `name`, `price`, `is_available`). **Rollback:** скрипт делает `DELETE` внутри транзакции; при ошибке данные не меняются. Повторить с исправленным файлом |

### Шаг C. Admin first-login (setup_token → password)
| | |
|---|---|
| **Входные данные** | `setup_token` из шага A, новый пароль admin |
| **Команда** | ```docker exec restobot-admin-1 python3 /tmp/set_admin_password.py --tenant-id pilot_bistro --password "StrongP@ssw0rd"``` |
| **Точка проверка** | JSON stdout содержит `setup_token` (новый raw token, если first-login) или `password_updated=true` |
| **Типовой сбой** | `setup_token` уже использован → login endpoint вернёт `401`. **Mitigation:** `set_admin_password.py` всегда обновляет пароль; admin заходит по email + новый пароль |
| **Ручная проверка login** | ```curl -X POST http://51.250.91.143/admin/pilot_bistro/auth/login -H "Content-Type: application/json" -d '{"email":"owner@bistro.ru","password":"StrongP@ssw0rd"}' -c cookies.txt``` | `200` + cookie `access_token` |

### Шаг D. WebApp order (widget session → menu → order)
| | |
|---|---|
| **Входные данные** | `tenant_id=pilot_bistro`, `gateway_url=https://app.chatbot24.su` |
| **1. Session** | `POST /widget/pilot_bistro/session` `{external_id:"usr-1",name:"Иван",phone:"+79991112233"}` → `201`, извлечь `access_token` |
| **2. Menu** | `GET /widget/pilot_bistro/menu` + Bearer token → `200`, `length > 0` |
| **3. Order** | `POST /widget/pilot_bistro/orders` `{user_id, type:"delivery", items:[{menu_item_id,quantity:1,price}], address:"...", phone:"...", payment_method:"cash", loyalty_points_to_use:0}` → `201`, извлечь `order_id` |
| **Точка проверки** | `order_id` числовой, `status=new` или `pending` |
| **Типовой сбой** | `403` на `/widget/*/orders` → нет Bearer токена или token expired. **Mitigation:** повторить `/session`, убедиться что `Authorization: Bearer <token>` передан |

### Шаг E. Payment callback (YooKassa flow)
| | |
|---|---|
| **Входные данные** | `order_id`, YooKassa shop credentials |
| **Сценарий пилота** | Для пилота допустим `payment_method: cash` (шаг D). Если нужен YooKassa:  |
| **1. Создание платежа** | Admin UI или API вызывает `POST /api/v1/pilot_bistro/payments` → возвращает `confirmation_url` |
| **2. Webhook** | YooKassa шлёт `POST /api/v1/pilot_bistro/payments/webhook` → `payments/worker.py:handle_webhook` обновляет `payment_status=paid`, `status=confirmed`, начисляет loyalty |
| **Точка проверки** | `GET /widget/pilot_bistro/orders/{order_id}` → `status=confirmed`, `payment_status=paid` |
| **Типовой сбой** | Webhook не доходит → проверить URL в dashboard, TLS, Caddy route `/api/*`. **Mitigation:** ручной `PATCH /admin/pilot_bistro/orders/{id}/status` `{status:confirmed, payment_status:paid}` |
| **Idempotency guard** | `handle_webhook` игнорирует дубликаты `payment.succeeded` если уже `paid`. DLQ: проверить таблицу `payment_dlq` в `tenant_pilot_bistro` |

### Шаг F. Logout / login retry
| | |
|---|---|
| **Logout** | `POST /admin/pilot_bistro/auth/logout` с cookie `access_token` → `200` |
| **Проверка revocation** | `GET /admin/pilot_bistro/auth/me` с тем же cookie → `401` |
| **Login retry** | Повторить login (шаг C) → новый cookie, `/me` → `200` |
| **Типовой сбой** | `401` после logout не срабатывает → Redis недоступен (fail-open). **Mitigation:** перезапустить Redis, проверить `REDIS_TLS_ENABLED` / `REDIS_PASSWORD` |

### Полная CLI-автоматизация E2E
```bash
# 1. Provision
ssh ubuntu@51.250.91.143 "docker exec restobot-admin-1 python3 /tmp/provision_tenant.py \
  --tenant-id pilot_bistro --restaurant-name 'Bistro Pilot' \
  --admin-name 'Owner' --admin-email 'owner@bistro.ru' --admin-phone '+79991112233'" > provision.json

ADMIN_TOKEN=$(jq -r '.admin_token' provision.json)
SETUP_TOKEN=$(jq -r '.setup_token' provision.json)

# 2. Menu (загрузить JSON на VM и запустить upload_menu.py)
# 3. Smoke (адаптировать smoke_cli_tenant.py под новый tenant)
poetry run python scripts/smoke_cli_tenant.py \
  --gateway-url https://app.chatbot24.su \
  --tenant-id pilot_bistro \
  --admin-token "$ADMIN_TOKEN"
```

---

## 3. Риск-матрица TOP-10 для пилота

| # | Риск | Вероят-ность | Влияние | Как обнаружить | Превентивное действие | План реакции |
|---|------|-------------|---------|----------------|----------------------|--------------|
| 1 | **Redis fail-open на revocation** | Средняя | Высокое | `test_revoked_token.py` проходит, но при `redis-down` logout не работает | Проверить `REDIS_TLS_ENABLED=true`, мониторить Redis availability | При падении Redis → рестарт контейнера/сервиса; если недоступен >2 мин → режим read-only для admin, уведомить клиента |
| 2 | **Tenant isolation breach** | Низкая | Критическое | `test_tenant_isolation.py` skipped; legacy `api/main.py` без глобального auth | Не экспонировать `api/main.py` в проде; использовать только `apps/admin_api` + `apps/public_api` | Немедленно проверить `X-Tenant-ID` mismatch в логах; отключить legacy routes в Caddy |
| 3 | **YooKassa callback lost / DLQ** | Средняя | Высокое | `payment_dlq` растёт; заказы висят в `pending` | Проверить webhook URL в YooKassa dashboard до пилота; включить `poll_payment_status` fallback | Ручное подтверждение заказа через admin UI + разбор DLQ; связываться с YooKassa support |
| 4 | **Migration провал на schema-per-tenant** | Средняя | Критическое | `migrate.sh` падает при создании `tenant_*` schema; Alembic revision не применяется к новым tenant'ам | `deploy.sh` всегда запускает `migrate.sh` перед `up -d`; тестировать на staging | `./rollback.sh` → откат image; ручной `alembic downgrade` если данные не затронуты; иначе restore из YC backup |
| 5 | **Caddy route regression** | Низкая | Высокое | `/admin/health` или `/widget/health` возвращает `404` из SPA | `ingress_smoke.sh` в `deploy.sh` + отдельный шаг в чеклисте | Перезапустить `caddy`; проверить `Caddyfile` (rewrite `/admin/health` → `/health`) |
| 6 | **Postgres connection pool exhaustion** | Средняя | Высокое | Логи admin/public: `FATAL: sorry, too many clients already`; latency >2s | Мониторить `pg_stat_activity`; `pool_pre_ping=true`; max_connections=100 на YC | Перезапуск admin/public контейнеров; уменьшить `DATABASE_POOL_MAX`; увеличить YC instance class |
| 7 | **JWT secret compromise / rotation** | Низкая | Критическое | Нет механизма rotation без downtime | Хранить `JWT_SECRET` в YC Lockbox; ограничить доступ к `.env.prod` | Срочная смена secret → все активные сессии слетят → users re-login; коммуникация с клиентом |
| 8 | **Bot tenant fallback смешение** | Средняя | Среднее | Пользователь без `/start` попадает в чужой ресторан | `TELEGRAM_BOT_DEFAULT_TENANT_ID` должен быть **пустым** в `.env.prod` | Проверить env, перезапустить bot; очистить таблицу `telegram_user_tenants` для затронутых user_id |
| 9 | **Frontend build / Caddy SPA cache** | Низкая | Среднее | Новый билд не отдаётся; `index.html` старый | Версионировать `dist` (`dist-vN`), рестарт caddy после билда | Ручной `docker compose restart caddy`; проверить `file_server` root |
| 10 | **XSS / JSON.parse guard regression** | Низкая | Среднее | Ручной тест вставки `<script>` в поле имени заказа | Уже hardened (createElement, JSON.parse guard); проверить в пилоте | Быстрый фикс в `frontend/webapp` → rebuild → restart caddy; нет затронутых данных |

---

## 4. Go/No-Go критерии

### Обязательные «зелёные» условия (все должны быть YES)

| # | Критерий | Артефакт проверки |
|---|----------|-------------------|
| 1 | CI зелёный: `pytest -m "not cloud"` = 163 passed | CI badge / консоль |
| 2 | Образы собраны и протегированы `pilot-*` | Container Registry |
| 3 | `deploy.sh` отработал успешно, `ingress_smoke.sh` PASSED | Логи на VM |
| 4 | `/admin/health` + `/widget/health` = `200` | `curl` |
| 5 | `ENABLE_BOOTSTRAP_API=false` в `.env.prod` | `grep` |
| 6 | Demo tenant smoke (`smoke_cli_tenant.py`) = SUCCESS | Консоль |
| 7 | `TELEGRAM_BOT_DEFAULT_TENANT_ID` пустой | `grep` |
| 8 | YooKassa webhook URL настроен и доступен | Dashboard YooKassa + `curl` |
| 9 | `.rollback.env` сохранён, содержит рабочие предыдущие теги | Файл на VM |
| 10 | Пилотный клиент согласован, deep link/QR-код готовы | Чат/письмо с клиентом |

### Допустимые отклонения для пилота (ограниченный scope)

| Отклонение | Условие допустимости |
|------------|---------------------|
| `test_tenant_isolation.py` skipped | OK, если **legacy `api/main.py` не проксируется через Caddy** (проверить `ingress_smoke.sh` — `POST /admin/onboarding` должен возвращать `403`, а не `404` от Caddy, что означает маршрутизацию на backend) |
| Нет автотеста для YooKassa webhook | OK, если ручной smoke (шаг E) пройден на demo tenant |
| Bot работает в polling mode | OK для пилота (до 1000 юзеров); webhook — post-pilot |
| Frontend без service worker / PWA | OK для MVP; только WebApp в Telegram |
| Нет мониторинга APM (Datadog/ Grafana) | OK, если есть `docker logs` + ручные health checks первые 72ч |

### Кто принимает решение

- **Go/No-Go владелец:** Senior QA Lead / DevOps Release Manager (вы).
- **На основании:**
  1. Подписанный чеклист п.1 (все 15 шагов).
  2. Артефакт `SUCCESS` от `smoke_cli_tenant.py`.
  3. Скриншот/лог `INGRESS SMOKE PASSED`.
  4. Подтверждение клиента о готовности deep link.
- **Hard No-Go:** любой FAIL на шагах 1, 4, 5, 6, 7, 8.

---

## 5. План первых 72 часов после запуска

### 5.1 Мониторинг

| Время | Что смотреть | Как | Порог тревоги |
|-------|-------------|-----|---------------|
| **Час 0–6** (каждые 15 мин) | Health endpoints, ingress smoke | `watch -n 300 'curl -s http://app.chatbot24.su/admin/health && curl -s http://app.chatbot24.su/widget/health'` | Не `200` >1 мин |
| **Час 6–24** (каждый час) | Логи admin/public на ошибки DB/Redis | `docker logs --tail=200 restobot-admin-1 2>&1 \| grep -iE "error|exception|timeout"` | >10 ошибок в час |
| **День 2–3** (каждые 3 часа) | `payment_dlq`, `orders` в `pending` >30 мин | SQL: `SELECT tenant_schema, COUNT(*) FROM payment_dlq GROUP BY tenant_schema` | `payment_dlq` >0 |
| **День 2–3** (каждые 3 часа) | Bot response time, polling errors | `docker logs --tail=100 restobot-bot-1 \| grep -iE "error|polling"` | Bot silent >5 мин |
| **Ежедневно** | Disk/CPU на VM | `df -h`, `htop` | Disk >80%, CPU >80% >10 мин |

### 5.2 Incident playbook «первые 15 минут»

```
T+0   Alert (health != 200 или клиент пишет о сбое)
T+1   SSH на VM: проверить статус контейнеров
      docker compose -f docker-compose.prod.yml --env-file .env.prod ps
T+2   Если контейнер unhealthy/restarting:
      docker logs --tail=100 restobot-admin-1
      docker logs --tail=100 restobot-public-1
T+3   Если ошибка DB/Redis connectivity:
      - Проверить .env.prod (DATABASE_URL, REDIS_HOST/PASSWORD/TLS)
      - Проверить YC Managed DB status в консоли Yandex Cloud
T+4   Если не ясно, что сломалось, или фикс >10 мин:
      ./rollback.sh
T+5   Проверить rollback: ingress_smoke.sh + smoke_cli_tenant.py
T+8   Если rollback не помог:
      sudo systemctl restart restobot-compose@ubuntu
T+10  Повторить чеклист п.1 (шаги 8–14)
T+15  Либо сервис стабилен → информировать клиента, 
      либо продолжаем инцидент с эскалацией на CTO.
```

**Команды one-liner для копирования:**
```bash
# Быстрый статус
ssh ubuntu@51.250.91.143 "cd /opt/restobot && docker compose ps && echo '---' && bash ingress_smoke.sh http://localhost"

# Быстрый rollback
ssh ubuntu@51.250.91.143 "cd /opt/restobot && ./rollback.sh && bash ingress_smoke.sh http://localhost"

# Быстрый перезапуск
ssh ubuntu@51.250.91.143 "sudo systemctl restart restobot-compose@ubuntu"
```

### 5.3 Коммуникация с пилотным клиентом при сбое

| Сценарий | Шаблон сообщения (Telegram/email) | Действие |
|----------|-----------------------------------|----------|
| **Деградация <5 мин** | *«Ведутся технические работы, сервис восстановится в течение 5 минут. Заказы можно оставить через официанта.»* | Не звонить; фиксим молча |
| **Даунтайм 5–30 мин** | *«Обнаружена неполадка, команда работает над исправлением. ETA: 30 мин. В качестве альтернативы — звоните нам по телефону: +7…»* | Предложить компенсацию (скидка 10% на следующий заказ) |
| **Критический сбой >30 мин** | *«Сервис временно недоступен. Мы уже откатились на стабильную версию. ETA восстановления полного функционала: X мин. Личный менеджер свяжется с вами.»* | Звонок от account manager; фиксация в Jira/Notion; post-mortem в течение 24ч |
| **Потеря заказа/платежа** | *«По техническим причинам заказ #{id} не дошёл. Мы восстановим его вручную в течение 1 часа. Деньги не списаны / будут возвращены.»* | Ручное восстановление через admin UI; проверка `payment_dlq`; связываться с YooKassa при необходимости |

**Правило:** Клиент узнаёт о проблеме от нас первым, а не от своих гостей.

---

## Приложение. Быстрые ссылки

- **VM:** `ubuntu@51.250.91.143` → `/opt/restobot`
- **Health:** `https://app.chatbot24.su/admin/health`, `/widget/health`
- **Runbook:** `docker/RUNBOOK.md`
- **Deploy:** `docker/deploy.sh`, `docker/rollback.sh`, `docker/ingress_smoke.sh`
- **Smoke:** `scripts/smoke_cli_tenant.py`, `scripts/smoke_webapp.py`
- **Provision:** `scripts/provision_tenant.py`, `scripts/upload_menu.py`, `scripts/seed_demo_tenant.py`
- **Password:** `scripts/set_admin_password.py`
