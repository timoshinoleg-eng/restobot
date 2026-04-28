# RestoBot Local MVP

This guide bootstraps a completely fresh local environment and walks through the Private Beta MVP flow:

1. start infrastructure
2. seed shared data
3. run admin/public APIs
4. execute the automated smoke test
5. manually verify onboarding, widget ordering, and admin order management via `curl` or Postman

## Prerequisites

- Python 3.11+
- Poetry
- Docker / Docker Compose

## 1. Environment

Copy `.env.example` to `.env` and set local-safe values.

Example minimal `.env`:

```env
DEBUG=true
ENV=development
LOG_LEVEL=INFO

DATABASE_URL=postgresql+asyncpg://restobot:password@localhost:5432/restobot
REDIS_URL=redis://localhost:6379/0

TELEGRAM_BOT_TOKEN=test
TELEGRAM_WEBHOOK_URL=
TELEGRAM_WEBHOOK_SECRET=test-secret

YC_FOLDER_ID=test
YC_IAM_TOKEN=

YOOKASSA_SHOP_ID=test
YOOKASSA_SECRET_KEY=test
YOOKASSA_RETURN_URL=http://localhost

JWT_SECRET=test_secret_key_min_32_chars_here

YC_OBJECT_STORAGE_BUCKET=restobot-local
YC_OBJECT_STORAGE_ENDPOINT=https://storage.yandexcloud.net
```

## 2. Start infrastructure

```powershell
docker-compose up -d postgres redis
```

Optional health checks:

```powershell
docker-compose ps
```

## 3. Bootstrap a fresh local database

This creates shared tables and seeds default plans.

```powershell
poetry run restobot-bootstrap-local
```

Expected output:

```text
Local bootstrap completed.
Seeded plans: Start, Pro, Enterprise
```

## 4. Run the APIs

Start the admin API in one terminal:

```powershell
poetry run restobot-admin-api
```

Start the public API in a second terminal:

```powershell
poetry run restobot-public-api
```

Health checks:

```powershell
curl http://127.0.0.1:8010/health
curl http://127.0.0.1:8011/health
```

Expected response:

```json
{"status":"ok"}
```

## 5. Automated smoke test

This runs the end-to-end path:

- signup
- onboarding restaurant info
- menu upload
- widget session
- widget order
- admin status update
- DB verification

```powershell
poetry run restobot-smoke-local-mvp
```

Expected output:

```text
Smoke test completed successfully.
Tenant slug: ...
Tenant id: ...
Order id: ...
```

## 6. Manual API verification with curl

### 6.1 Signup / onboarding start

```powershell
curl -X POST http://127.0.0.1:8010/admin/v1/onboarding/start ^
  -H "Content-Type: application/json" ^
  -d "{\"restaurant_name\":\"Roma Pizza\",\"owner_email\":\"owner@roma.local\",\"owner_password\":\"StrongPass123!\",\"owner_name\":\"Ivan Owner\",\"phone\":\"+79990000000\"}"
```

Response contains:

- `tenant_slug`
- `token.access_token`
- `token.refresh_token`

Save the `access_token`.

### 6.2 Restaurant info

```powershell
curl -X POST http://127.0.0.1:8010/admin/v1/onboarding/restaurant-info ^
  -H "Authorization: Bearer <ACCESS_TOKEN>" ^
  -H "Content-Type: application/json" ^
  -d "{\"restaurant_display_name\":\"Roma Pizza\",\"legal_name\":\"Roma Pizza LLC\",\"phone\":\"+79990000000\",\"support_email\":\"owner@roma.local\",\"address_json\":{\"city\":\"Moscow\",\"line1\":\"Pushkina 1\"},\"working_hours_json\":{\"mon-sun\":\"10:00-22:00\"}}"
```

### 6.3 Menu upload

```powershell
curl -X POST http://127.0.0.1:8010/admin/v1/onboarding/menu-upload ^
  -H "Authorization: Bearer <ACCESS_TOKEN>" ^
  -H "Content-Type: application/json" ^
  -d "{\"categories\":[{\"name\":\"Pizza\",\"items\":[{\"name\":\"Margarita\",\"description\":\"Classic pizza\",\"price\":590},{\"name\":\"Pepperoni\",\"description\":\"Spicy pizza\",\"price\":690}]}]}"
```

### 6.4 Read settings

```powershell
curl http://127.0.0.1:8010/admin/v1/settings ^
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### 6.5 Update settings

```powershell
curl -X PATCH http://127.0.0.1:8010/admin/v1/settings ^
  -H "Authorization: Bearer <ACCESS_TOKEN>" ^
  -H "Content-Type: application/json" ^
  -d "{\"bot_name\":\"Roma Bot\",\"greeting_text\":\"Welcome to Roma Pizza\",\"ai_enabled\":true}"
```

### 6.6 Create widget session

```powershell
curl -X POST http://127.0.0.1:8011/public/v1/widget/session ^
  -H "Content-Type: application/json" ^
  -d "{\"tenant_slug\":\"roma-pizza\",\"source_url\":\"http://localhost/test\",\"consent_personal_data\":true,\"consent_marketing\":false}"
```

Save `session_token`.

### 6.7 Read widget menu

```powershell
curl http://127.0.0.1:8011/public/v1/widget/menu ^
  -H "X-Session-Token: <SESSION_TOKEN>"
```

Use one returned `id` as `menu_item_id`.

### 6.8 Create widget order

```powershell
curl -X POST http://127.0.0.1:8011/public/v1/widget/orders ^
  -H "X-Session-Token: <SESSION_TOKEN>" ^
  -H "Content-Type: application/json" ^
  -d "{\"customer_name\":\"Anna\",\"phone\":\"+79990000001\",\"order_type\":\"pickup\",\"payment_method\":\"cash\",\"items\":[{\"menu_item_id\":1,\"quantity\":1,\"modifier_option_ids\":[]}]}"
```

Save the returned `order.id`.

### 6.9 List admin orders

```powershell
curl http://127.0.0.1:8010/admin/v1/orders ^
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### 6.10 Get one order

```powershell
curl http://127.0.0.1:8010/admin/v1/orders/<ORDER_ID> ^
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### 6.11 Update order status

```powershell
curl -X PATCH http://127.0.0.1:8010/admin/v1/orders/<ORDER_ID>/status ^
  -H "Authorization: Bearer <ACCESS_TOKEN>" ^
  -H "Content-Type: application/json" ^
  -d "{\"status\":\"accepted\",\"comment\":\"Confirmed by manager\"}"
```

Then:

```powershell
curl -X PATCH http://127.0.0.1:8010/admin/v1/orders/<ORDER_ID>/status ^
  -H "Authorization: Bearer <ACCESS_TOKEN>" ^
  -H "Content-Type: application/json" ^
  -d "{\"status\":\"preparing\",\"comment\":\"Sent to kitchen\"}"
```

### 6.12 Read audit log

```powershell
curl http://127.0.0.1:8010/admin/v1/audit ^
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

## 7. Postman checklist

Suggested collection order:

1. `POST /admin/v1/onboarding/start`
2. `POST /admin/v1/onboarding/restaurant-info`
3. `POST /admin/v1/onboarding/menu-upload`
4. `GET /admin/v1/settings`
5. `PATCH /admin/v1/settings`
6. `POST /public/v1/widget/session`
7. `GET /public/v1/widget/menu`
8. `POST /public/v1/widget/orders`
9. `GET /admin/v1/orders`
10. `PATCH /admin/v1/orders/{id}/status`
11. `GET /admin/v1/audit`

Variables to store in Postman:

- `access_token`
- `tenant_slug`
- `session_token`
- `menu_item_id`
- `order_id`

## 8. Troubleshooting

### Migration / shared tables missing

Run:

```powershell
poetry run restobot-bootstrap-local
```

### `401 Authorization required` on admin endpoints

- ensure you are using the `access_token` from onboarding start or login
- send header exactly as:

```text
Authorization: Bearer <ACCESS_TOKEN>
```

### `401 Session token required` on widget endpoints

Send:

```text
X-Session-Token: <SESSION_TOKEN>
```

### `402 Trial expired`

Your tenant billing status is not `trial` or `active`. For local testing, create a fresh tenant through onboarding start.

### `Invalid tenant schema`

Tenant schemas are based on numeric tenant id, not slug. If you changed onboarding logic manually, recreate the tenant using the official onboarding endpoint.

### Widget order fails because menu is empty

Ensure `menu-upload` completed successfully before creating a widget session and order.

## 9. Useful local test commands

Targeted regression suite:

```powershell
$env:DATABASE_URL='postgresql://restobot:password@localhost:5432/restobot'
$env:TELEGRAM_BOT_TOKEN='test'
$env:YC_FOLDER_ID='test'
$env:YOOKASSA_SHOP_ID='test'
$env:YOOKASSA_SECRET_KEY='test'
$env:JWT_SECRET='test_secret_key_min_32_chars_here'
$env:YC_OBJECT_STORAGE_BUCKET='test'
poetry run pytest tests/test_tenant_isolation.py tests/test_auth.py tests/test_menu.py tests/test_orders.py tests/test_settings.py tests/test_onboarding.py tests/test_widget.py -q
```

Full app health:

```powershell
curl http://127.0.0.1:8010/health
curl http://127.0.0.1:8011/health
```
