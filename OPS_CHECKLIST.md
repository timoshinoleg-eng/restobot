# Операторский checklist — RestoBot

## 1. Создать / подготовить tenant

### Через bootstrap API (serverless)
```bash
# Убедиться, что ENABLE_BOOTSTRAP_API=true и BOOTSTRAP_API_TOKEN задан
curl -X POST https://d5dql99olrs7m7lascpm.628pfjdx.apigw.yandexcloud.net/admin/onboarding \
  -H "Content-Type: application/json" \
  -H "X-Bootstrap-Token: <BOOTSTRAP_API_TOKEN>" \
  -d '{
    "tenant_id": "new_bistro",
    "restaurant_name": "New Bistro",
    "admin_name": "Owner",
    "admin_email": "owner@example.com",
    "admin_phone": "+79990000001",
    "min_order_amount": 0
  }'
```

### Через CLI на VM (рекомендуется для production)
```bash
cd /opt/restobot
docker cp ./scripts/provision_tenant.py restobot-admin-1:/tmp/provision_tenant.py
docker exec restobot-admin-1 python3 /tmp/provision_tenant.py \
  --tenant-id new_bistro \
  --restaurant-name "New Bistro" \
  --admin-name "Owner" \
  --admin-email "owner@example.com" \
  --admin-phone "+79990000001"
```
Результат: JSON с `admin_token`. Сохранить для оператора.

---

## 2. Выдать admin доступ

### Для нового tenant (после provision)
- Первый login админа требует `setup_token`.
- `setup_token` генерируется автоматически при provision и возвращается в ответе (или выдаётся отдельно).
- Админ заходит в `/admin/{tenant}/`, вводит phone + password + setup_token.
- При первом успешном входе `setup_token` сбрасывается, `password_hash` сохраняется.

### Для legacy tenant (до 005, например `demo`)
- Если `password_hash=null` и `setup_token=null`, admin login заблокирован.
- Ручная активация через БД:
```sql
-- Сгенерировать setup_token (bcrypt hash)
-- Или напрямую задать password_hash
UPDATE tenant_demo.restaurant_settings SET setup_token = 'plaintext-token';
-- Или
UPDATE tenant_demo.users SET password_hash = '<bcrypt-hash>' WHERE id = 1;
```

---

## 3. Проверить /health

### Gateway (рекомендуется)
```bash
curl -s https://d5dql99olrs7m7lascpm.628pfjdx.apigw.yandexcloud.net/health | python -m json.tool
```
Ожидаемо:
```json
{
  "status": "ok",
  "database": { "session": { "status": "healthy" }, "pool": { "status": "healthy" } },
  "redis": { "status": "healthy" },
  "version": "1.0.0",
  "environment": "production"
}
```

### Напрямую к контейнеру (диагностика)
```bash
# Требуется IAM token
curl -s -H "Authorization: Bearer $(yc iam create-token)" \
  https://bbat13jql8mciiac5g21.containers.yandexcloud.net/health
```

---

## 4. Проверить widget / session / order

### Menu
```bash
curl -s https://d5dql99olrs7m7lascpm.628pfjdx.apigw.yandexcloud.net/widget/demo/menu | python -m json.tool
```

### Session (получить JWT)
```bash
curl -X POST https://d5dql99olrs7m7lascpm.628pfjdx.apigw.yandexcloud.net/widget/demo/session \
  -H "Content-Type: application/json" \
  -d '{"external_id":"test-001","name":"Test User","phone":"+79990000001"}'
```
Сохранить `access_token` из ответа.

### Order (с JWT)
```bash
curl -X POST https://d5dql99olrs7m7lascpm.628pfjdx.apigw.yandexcloud.net/widget/demo/orders \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "user_id": 31,
    "items": [{"menu_item_id": 70, "quantity": 2}],
    "delivery_type": "pickup"
  }'
```

---

## 5. Откатиться на предыдущий image tag

### Serverless (Terraform)
1. Отредактировать `infra/yc/terraform.tfvars.pilot` — вернуть старые теги в `admin_image`, `public_image`, `migration_image`.
2. Выполнить на VM:
```bash
cd /opt/restobot/infra/yc
export YC_TOKEN=$(yc iam create-token)
terraform plan -var-file=terraform.tfvars.pilot -out=deploy.tfplan
terraform apply deploy.tfplan
```

### VM (docker-compose)
1. Отредактировать `.env.prod` — вернуть старые `ADMIN_IMAGE` / `PUBLIC_IMAGE`.
2. Пересоздать контейнеры:
```bash
cd /opt/restobot
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --force-recreate
```
3. Проверить статус:
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
```

### Быстрый откат только сервиса (VM)
```bash
cd /opt/restobot
docker compose -f docker-compose.prod.yml --env-file .env.prod restart admin public
```

Важно:

- для **VM docker-compose** сервисы называются именно `admin` и `public`;
- имена `admin_api` и `public_api` относятся к **YC Serverless Containers / Terraform**, а не к compose-файлу на VM.
