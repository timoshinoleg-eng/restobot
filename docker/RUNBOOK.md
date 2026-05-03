# RestoBot VM Runtime — Runbook

## Архитектура

- **Caddy** — reverse proxy (порт 80/443), терминация TLS, маршрутизация по префиксам.
- **admin** (`apps.admin_api`) — порт 8000, префикс `/admin`.
- **public** (`apps.public_api`) — порт 8001, префиксы `/widget`, `/api`.
- **bot** (`bot.main`) — Telegram bot runtime. Для MVP на VM работает в polling mode, если `TELEGRAM_WEBHOOK_URL` пустой.
- **docker-compose.prod.yml** управляет `caddy`, `admin`, `public`, `bot`.
- Managed PostgreSQL и Redis находятся за пределами VM и не трогаются.

### Redis connection contract

В `.env.prod` **не используем** `REDIS_URL`. Вместо этого передаём компоненты:

```bash
REDIS_HOST=<managed-redis-host>
REDIS_PORT=6379
REDIS_PASSWORD=<password-with-special-chars-ok>
REDIS_DB=0
# YC Managed Redis требует TLS
REDIS_TLS_ENABLED=true
```

Приложение (`shared/config.py`) само соберёт URL с `urllib.parse.quote` для пароля. Это исключает баг с парсингом `/` и других спецсимволов внутри Redis-URL.

## Tenant provisioning (CLI)

Production-операции **должны использовать CLI**, а не HTTP bootstrap endpoint.

```bash
cd /opt/restobot
# Копируем скрипт в контейнер
docker cp ./scripts/provision_tenant.py restobot-admin-1:/tmp/provision_tenant.py

# Создаём tenant
docker exec restobot-admin-1 python3 /tmp/provision_tenant.py \
  --tenant-id bistro_01 \
  --restaurant-name "Bistro 01" \
  --admin-name "Owner Name" \
  --admin-email "owner@bistro.ru" \
  --admin-phone "+79990000000"
```

Результат — JSON с `admin_token`, который выдаётся в stdout. Сохраните его для оператора.

### Залить меню и цены для нового ресторана

Используйте JSON-файл той же формы, что и [MENU_UPLOAD_TEMPLATE.json](<C:/Users/Имярек/Downloads/restobot-main/MENU_UPLOAD_TEMPLATE.json>).

```bash
cd /opt/restobot
docker cp ./scripts/upload_menu.py restobot-admin-1:/tmp/upload_menu.py
docker cp ./MENU_UPLOAD_TEMPLATE.json restobot-admin-1:/tmp/menu.json
docker exec restobot-admin-1 python3 /tmp/upload_menu.py \
  --tenant-id bistro_01 \
  --menu-file /tmp/menu.json
```

CLI-импорт предпочтительнее ручных SQL-правок и не требует отдельной admin UI.

**HTTP bootstrap API (`POST /admin/onboarding`) — deprecated fallback.**
- Оставлен для совместимости со старыми smoke-тестами.
- В production должен быть выключен: `ENABLE_BOOTSTRAP_API=false`.
- Если временно включён, обязательно задать `BOOTSTRAP_API_TOKEN` и сразу выключить после использования.

## Demo tenant

### Создать или обновить demo tenant

```bash
cd /opt/restobot
docker cp ./scripts/seed_demo_tenant.py restobot-admin-1:/tmp/seed_demo_tenant.py
docker exec restobot-admin-1 python3 /tmp/seed_demo_tenant.py --tenant-id demo
```

Команда идемпотентна:
- Если tenant не существует — создаёт его.
- Если существует — обновляет menu и выдаёт свежий `admin_token`.

### Deep link для Telegram бота

Бот определяет ресторан через deep link при старте:

```
https://t.me/<bot_username>?start=demo
```

При открытии диалога бот получает `/start demo`, извлекает `tenant_id=demo`, сохраняет его в FSM-состоянии пользователя и формирует кнопку меню с правильным URL (`https://app.chatbot24.su/demo/menu`).

**Пример для demo tenant:**
```
https://t.me/SwimEasy_bot?start=demo
```

**Безопасность:**
- `--reset` на `seed_demo_tenant.py` по умолчанию работает только для `tenant_id=demo`.
- Для других tenant'ов требуется `--force-reset`.

**Fallback (dev/demo только через env):**
- Если пользователь заходит без deep link (`/start` без payload), бот **сначала проверяет persisted mapping** в таблице `telegram_user_tenants`.
- Если mapping есть — бот восстанавливает tenant и продолжает диалог.
- Если mapping отсутствует — бот проверяет `TELEGRAM_BOT_DEFAULT_TENANT_ID` в `.env.prod`.
- Если и она не задана — бот показывает инструкцию с предложением обратиться в поддержку.
- В production `TELEGRAM_BOT_DEFAULT_TENANT_ID` должна быть не задана, чтобы избежать случайного смешения tenant'ов.

### Tenant-aware команды

После успешного `/start <tenant_id>` все основные команды используют сохранённый tenant:

| Команда | Что делает |
|---------|-----------|
| `/menu` | Показывает кнопку «🍽️ Открыть меню» → `https://app.chatbot24.su/{tenant}/menu` |
| `/cart` | Показывает корзину с указанием ресторана |
| `/order` | Показывает типы заказа + кнопку «📱 Оформить в приложении» → `https://app.chatbot24.su/{tenant}/order` |
| `/my_data` | Показывает персональные данные пользователя из `{tenant}.users` (имя, телефон, email, баллы) и агрегаты заказов в рамках текущего tenant |
| `/delete_account` | Запрашивает подтверждение и анонимизирует PII пользователя только в текущем tenant (профиль + поля заказов/броней) |

Если пользователь вызывает команду **без предварительного `/start`** (нет tenant в FSM), бот отвечает:

> ⚠️ *Не удалось определить ресторан*  
> Для использования бота перейдите по ссылке, предоставленной рестораном, или отсканируйте QR-код.

### Сбросить demo-данные (reset)

Команда идемпотентна и безопасна для повторных демо-показов:

```bash
docker exec restobot-admin-1 python3 /tmp/seed_demo_tenant.py --tenant-id demo --reset
```

**Reset contract** (что очищается vs сохраняется):

- **Очищается:**
  - `orders` — все заказы
  - `loyalty_transactions` — все транзакции лояльности
  - `reservations` — все бронирования
  - `stock_movements` — все складские движения
  - `payment_dlq` — dead letter queue
  - `users` с `role = 'user'` — widget-пользователи
  - `loyalty_points` сбрасывается в `0` у оставшихся admin-аккаунтов

- **Сохраняется:**
  - `users` с `role = 'admin'` — admin и его credentials/token
  - `restaurant_settings` — настройки ресторана
  - `ingredients`, `recipes`, `tables`, `menu_item_modifiers`, `modifier_options` — справочники

- **Пересоздаётся:**
  - `menu_categories` / `menu_items` — через `replace_menu`

- **Безопасность:**
  - `--reset` по умолчанию работает только для `tenant_id = "demo"`
  - Для сброса других tenant'ов требуется явный флаг `--force-reset`

### Проверить demo tenant

```bash
# Admin health через Caddy
curl http://localhost/admin/health

# Widget session
curl -X POST http://localhost/widget/demo/session \
  -H "Content-Type: application/json" \
  -d '{"external_id":"demo-user-1","name":"Demo","phone":"+79991112233"}'

# Menu
curl http://localhost/widget/demo/menu -H "Authorization: Bearer <user_token>"
```

### Demo данные

- **Ресторан:** RestoBot Demo
- **Админ:** demo@restobot.ru / +79990000000
- **Меню:** 2 категории (Хиты, Напитки), 3 блюда
  - Фирменный бургер — 490 ₽
  - Картофель по-деревенски — 210 ₽
  - Лимонад цитрус — 190 ₽

## Pilot Demo Flow

Canonical pilot tenant: `demo`

### 1. Подготовить demo tenant

Команда ниже была проверена live на production runtime. Она пересоздаёт demo menu, очищает транзакционные данные и печатает свежий `admin_token`.

```bash
scp -i ~/.ssh/openclaw_key ./scripts/seed_demo_tenant.py ubuntu@51.250.91.143:/home/ubuntu/seed_demo_tenant.py
ssh -i ~/.ssh/openclaw_key ubuntu@51.250.91.143 \
  "docker cp /home/ubuntu/seed_demo_tenant.py restobot-admin-1:/tmp/seed_demo_tenant.py && \
   docker exec restobot-admin-1 python3 /tmp/seed_demo_tenant.py --tenant-id demo --reset"
```

Успешный результат:
- строка `RESET: ... tenant_demo`
- JSON с `tenant_id = "demo"`
- JSON с ненулевым `admin_token`
- JSON с `categories_written = 2` и `items_written = 3`

### 2. Deep link для оператора

Canonical deep link для pilot demo:

```text
https://t.me/SwimEasy_bot?start=demo
```

Что должно происходить:
- бот получает `/start demo`
- сохраняет mapping `telegram_user_id -> demo` в `telegram_user_tenants`
- строит tenant-aware widget URL `https://app.chatbot24.su/demo/menu`
- при следующем `/start` без payload может восстановить tenant из БД

Ограничение текущей сессии:
- production bot identity live подтверждена через Bot API `getMe`: `username = "SwimEasy_bot"`
- этот Telegram round-trip не прогонялся live через реальный клиент Telegram
- runtime proof подтверждён кодом в image и наличием таблицы `telegram_user_tenants`

### 3. Widget -> order -> admin -> verify

Canonical live smoke для pilot flow выполняется из source-of-truth repo:

```bash
poetry run python scripts/smoke_cli_tenant.py \
  --gateway-url http://51.250.91.143 \
  --tenant-id demo \
  --admin-token <admin_token_from_seed_output>
```

Что делает smoke:
- загружает demo menu в `/admin/demo/menu/upload`
- создаёт widget session через `/widget/demo/session`
- читает menu через `/widget/demo/menu`
- создаёт order через `/widget/demo/orders`
- обновляет status через `/admin/demo/orders/{order_id}/status`
- проверяет финальный status через `/widget/demo/orders/{order_id}`

Успешный результат:

```text
SUCCESS
order_id=<id>
```

### 4. Expected status transition

Canonical pilot status update:
- admin устанавливает `status = confirmed`
- admin устанавливает `payment_status = paid`
- widget final verification должен вернуть `status = confirmed`

### 5. Health gates перед показом

Перед любым pilot demo убедиться:

```bash
ssh -i ~/.ssh/openclaw_key ubuntu@51.250.91.143 \
  "cd /opt/restobot && bash ingress_smoke.sh http://localhost"

curl -s -o /dev/null -w "%{http_code}" http://51.250.91.143/admin/health
curl -s -o /dev/null -w "%{http_code}" http://51.250.91.143/widget/health
```

Успешный результат:
- `ingress_smoke.sh` -> `INGRESS SMOKE PASSED`
- `/admin/health` -> `200`
- `/widget/health` -> `200`

### 6. Что подтверждено live

Подтверждено live в production runtime:
- demo tenant reset/reseed
- fresh `admin_token` issuance
- widget session
- menu fetch
- order creation
- admin status update
- widget final order verification
- ingress and health checks

Подтверждено runtime-level proof only:
- Telegram deep link `/start demo`
- persistence в `telegram_user_tenants`
- recovery path для `/start` без payload

## Deploy

```bash
cd /opt/restobot
# Пример с конкретными тегами
./deploy.sh cr.yandex/<registry>/restobot-admin:v1.2.3 cr.yandex/<registry>/restobot-public:v1.2.3
```

Скрипт:
1. Сохраняет текущие теги в `.rollback.env`.
2. Обновляет `ADMIN_IMAGE` / `PUBLIC_IMAGE` в `.env.prod` (создаёт ключ, если отсутствует).
3. Делает `docker compose pull admin public`.
4. **Запускает `migrate.sh` — Alembic `upgrade head` в одноразовом контейнере**.
5. Делает `docker compose up -d`.
6. **Поллит health каждые 5 секунд до 90 секунд**.
7. **После healthy admin/public проверяет proxy ingress** (`curl` через Caddy на `/admin/health` и `/widget/health`).
8. При любой неудаче — автоматически вызывает `rollback.sh`.

### Миграции вручную (вне deploy)

```bash
cd /opt/restobot
bash migrate.sh
```

Использует текущий `ADMIN_IMAGE` из `.env.prod`. Безопасно запускать отдельно — Alembic применит только недостающие ревизии.

## Restart

Перезапуск всего стека:
```bash
sudo systemctl restart restobot-compose@ubuntu
```

Или вручную:
```bash
cd /opt/restobot
docker compose -f docker-compose.prod.yml --env-file .env.prod restart
```

Перезапуск отдельного сервиса:
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod restart admin
docker compose -f docker-compose.prod.yml --env-file .env.prod restart bot
```

## Rollback

```bash
cd /opt/restobot
./rollback.sh
```

Откатывает image-теги к последнему успешному деплою из `.rollback.env`, делает `pull` (если образ отсутствует локально) и перезапускает сервисы.

Если `.rollback.env` потерян — откатить вручную, отредактировав `ADMIN_IMAGE` / `PUBLIC_IMAGE` в `.env.prod` и выполнив:
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

## Logs

Все сервисы:
```bash
cd /opt/restobot
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f --tail=100
```

Конкретный сервис:
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f admin
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f public
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f caddy
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f bot
```

Внутри контейнера (FastAPI JSON-логи):
```bash
docker logs -f restobot-admin-1 --tail=100
docker logs -f restobot-public-1 --tail=100
```

## Ingress verification

Быстрый regression-check для Caddy-маршрутизации (проверяет, что catch-all не перехватывает backend-пути):

```bash
cd /opt/restobot
bash ingress_smoke.sh
```

Покрываемые кейсы:
- `/admin/health` → `200` (проксировано на admin backend)
- `/widget/health` → `200` (проксировано на public backend)
- неизвестный путь (`/unknown-path-xyz`) → `404` от Caddy (тело содержит `Not Found`)
- `POST /admin/onboarding` → `403` от backend (тело содержит `Bootstrap API is disabled`), а не `404` от Caddy

Можно передать произвольный base URL:
```bash
bash ingress_smoke.sh http://51.250.91.143
```

## Healthcheck

Внешние endpoint-ы через Caddy (proxy rewrite → internal `/health` backend'ов):
```bash
curl http://51.250.91.143/admin/health    # → admin:8000/health
curl http://51.250.91.143/widget/health   # → public:8001/health
```

Внутренние (напрямую на VM):
```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
```

## TLS / Домен

1. Настроить A-запись домена на IP VM (`51.250.91.143`).
2. В `Caddyfile` закомментировать блок `:80 { ... }` и раскомментировать блок `your-domain.example.com { ... }`.
3. Убрать строку `auto_https off`.
4. Перезапустить:
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.prod restart caddy
   ```
Caddy сам запросит и обновит сертификат Let's Encrypt.

## Troubleshooting

| Симптом | Действие |
|---------|----------|
| `502 Bad Gateway` | Проверить `docker compose -f docker-compose.prod.yml --env-file .env.prod ps` — healthy ли admin/public. Смотреть логи приложения. |
| `Connection refused` | Убедиться, что Caddy поднят. Проверить `ufw` / YC Security Group на порты 80/443. |
| Контейнер `unhealthy` | `docker logs restobot-admin-1` — скорее всего нет коннекта к БД или Redis. Проверить `DATABASE_URL`, `REDIS_HOST`/`REDIS_PASSWORD`/`REDIS_TLS_ENABLED` в `.env.prod`. |
| Бот не отвечает на `/start` | Проверить, что сервис `bot` поднят: `docker compose -f docker-compose.prod.yml --env-file .env.prod ps`. Проверить реальный `TELEGRAM_BOT_TOKEN` в `.env.prod` и логи `docker compose ... logs -f bot`. Если `TELEGRAM_WEBHOOK_URL` пустой — бот должен логировать polling mode. |
| Деплой откатился сразу | Проверить `docker inspect restobot-admin-1 --format='{{.State.Health.Status}}'` — возможно, старт длится дольше 90 секунд (увеличить `MAX_WAIT` в `deploy.sh`). |
| VM перезагрузилась | `systemctl status restobot-compose@ubuntu` должен показывать `active (exited)`. Если нет — `sudo systemctl enable --now restobot-compose@ubuntu`. |
| Caddy не стартует из-за unhealthy backend | Caddy больше не ждёт healthy admin/public (`depends_on` без condition). Если Caddy не поднялся — смотреть `docker logs restobot-caddy-1`. |

## Frontend WebApp

### Стек

- React 18 + TypeScript + Vite
- Билд в `frontend/webapp/dist` — статические файлы
- Caddy раздаёт SPA через `app.chatbot24.su` (reverse proxy API + file_server для остальных путей)
- Telegram WebApp JS SDK подключён в `index.html`

### Локальная разработка

```bash
cd frontend/webapp
npm install
npm run dev
```

Vite dev server (port 5173) проксирует `/widget` и `/admin` на `localhost:8001/8000`.

Откройте: `http://localhost:5173/demo/menu`

### Сборка production

```bash
cd frontend/webapp
npm ci
npm run build
```

Результат: `frontend/webapp/dist/` — готовый для деплоя набор статики.

### Деплой на VM

1. Собрать статику на хосте (или в CI):
   ```bash
   cd /opt/restobot/frontend/webapp
   npm ci
   npm run build
   ```

2. Перезапустить Caddy чтобы подхватить новый `dist`:
   ```bash
   cd /opt/restobot
   docker compose -f docker-compose.prod.yml --env-file .env.prod restart caddy
   ```

Caddyfile уже содержит блок `app.chatbot24.su`:
- `/admin/*`, `/widget/*`, `/api/*` → reverse proxy на backend
- остальные пути → `file_server` с `try_files {path} /index.html` (SPA routing)

### Docker image (опционально)

```bash
docker build -t restobot-webapp -f frontend/webapp/Dockerfile frontend/webapp
```

Можно использовать отдельный nginx-контейнер вместо volume mount.

### Проверка

```bash
# Проверить что фронтенд билд есть и SPA routes отдают index.html
python scripts/smoke_webapp.py --gateway-url http://51.250.91.143 --tenant-id demo
```
