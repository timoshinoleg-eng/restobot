# Деплой RestoBot в Yandex Cloud

Этот документ описывает реальный сценарий деплоя для текущего состояния репозитория.

## Целевая схема

- Yandex Managed PostgreSQL 15
- Yandex Managed Redis 7
- Yandex Lockbox для секретов
- Yandex Container Registry для образов
- Serverless Container `admin-api`
- Serverless Container `public-api`
- Serverless Container `migration-runner` в режиме `task`
- Yandex API Gateway с маршрутами `/admin/*`, `/widget/*`, `/api/v1/*`, `/health`

## Предварительные требования

- Python 3.11
- Poetry 1.7.1
- Docker
- Terraform 1.6+
- YC CLI
- доступ в целевой cloud/folder в `ru-central1`

## 1. Установка YC CLI и Terraform

Windows PowerShell:

```powershell
Invoke-WebRequest https://storage.yandexcloud.net/yandexcloud-yc/install.ps1 -OutFile install-yc.ps1
powershell -ExecutionPolicy Bypass -File .\install-yc.ps1
```

Terraform:

```powershell
choco install terraform
```

## 2. Создание bootstrap service account

Для MVP достаточно одного service account с ролью `editor` на папку.

```powershell
yc iam service-account create --name restobot-bootstrap
yc resource-manager folder add-access-binding <folder-id> `
  --role editor `
  --subject serviceAccount:<service-account-id>
yc iam key create `
  --service-account-id <service-account-id> `
  --output key.json
```

Далее активируйте профиль:

```powershell
yc init
yc config set service-account-key .\key.json
yc config set cloud-id <cloud-id>
yc config set folder-id <folder-id>
```

## 3. Подготовка переменных Terraform

Основной стек:

```powershell
Copy-Item infra\yc\terraform.tfvars.example infra\yc\terraform.tfvars
```

Bootstrap remote state:

```powershell
Copy-Item infra\state_backend\terraform.tfvars.example infra\state_backend\terraform.tfvars
```

Заполните реальные значения:

- `yc_cloud_id`
- `yc_folder_id`
- секреты БД/Redis/JWT/Telegram/YooKassa
- `bootstrap_api_token` для защищённого onboarding/smoke-flow
- уникальное имя bucket для remote state

## 4. Поднятие remote backend в Yandex Object Storage

Для хранения Terraform state добавлен отдельный bootstrap-стек `infra/state_backend`.

Он создаёт:

- приватный bucket в Object Storage
- отдельный service account
- static access key для S3 backend

Ручной запуск:

```powershell
terraform -chdir=infra/state_backend init
terraform -chdir=infra/state_backend apply -auto-approve
```

Получение outputs:

```powershell
$bucket = terraform -chdir=infra/state_backend output -raw tfstate_bucket_name
$accessKey = terraform -chdir=infra/state_backend output -raw tfstate_access_key
$secretKey = terraform -chdir=infra/state_backend output -raw tfstate_secret_key
```

Подготовка backend-конфига:

```powershell
Copy-Item infra\yc\backend.hcl.example infra\yc\backend.hcl
```

В `infra/yc/backend.hcl` укажите имя bucket, затем экспортируйте ключи:

```powershell
$env:ACCESS_KEY = $accessKey
$env:SECRET_KEY = $secretKey
terraform -chdir=infra/yc init -reconfigure -backend-config=backend.hcl
```

## 5. Автоматический bootstrap backend + init main stack

### Вариант A. PowerShell

Используйте [bootstrap_backend.ps1](<C:/Users/Имярек/Downloads/restobot-main/scripts/bootstrap_backend.ps1>):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_backend.ps1
```

Скрипт:

1. инициализирует `infra/state_backend`
2. выполняет `apply`
3. читает outputs
4. генерирует `infra/yc/backend.hcl`
5. выставляет `ACCESS_KEY` и `SECRET_KEY`
6. выполняет `terraform init -reconfigure` для `infra/yc`

### Вариант B. Makefile

Для Git Bash / Linux / WSL добавлен [Makefile](<C:/Users/Имярек/Downloads/restobot-main/Makefile>):

```bash
make backend-bootstrap
make yc-backend-init
```

Или одним шагом:

```bash
make bootstrap-all
```

## 6. Bootstrap инфраструктуры без контейнеров

Реестр, БД, Redis и Lockbox должны существовать до первой сборки/публикации образов.

```powershell
terraform -chdir=infra/yc apply -auto-approve `
  -target=yandex_container_repository.admin `
  -target=yandex_container_repository.public `
  -target=yandex_container_repository.migration `
  -target=yandex_mdb_postgresql_database.restobot `
  -target=yandex_mdb_redis_cluster.restobot `
  -target=yandex_lockbox_secret_version.common `
  -target=yandex_lockbox_secret_version.db `
  -target=yandex_lockbox_secret_version.redis
```

Получите `registry_id`:

```powershell
$registryId = terraform -chdir=infra/yc output -raw registry_id
```

## 7. Сборка и push Docker-образов

Настройка Docker для Yandex Container Registry:

```powershell
yc container registry configure-docker
```

Сборка и push:

```powershell
$sha = "manual-" + (Get-Date -Format "yyyyMMddHHmmss")
$adminImage = "cr.yandex/$registryId/restobot-admin:$sha"
$publicImage = "cr.yandex/$registryId/restobot-public:$sha"
$migrationImage = "cr.yandex/$registryId/restobot-migrate:$sha"

docker build -f docker/Dockerfile.admin -t $adminImage .
docker build -f docker/Dockerfile.public -t $publicImage .
docker tag $adminImage $migrationImage

docker push $adminImage
docker push $publicImage
docker push $migrationImage
```

## 8. Полный Terraform apply

После публикации образов:

```powershell
terraform -chdir=infra/yc plan `
  -out deploy.tfplan `
  -var "enable_bootstrap_api=true" `
  -var "admin_image=$adminImage" `
  -var "public_image=$publicImage" `
  -var "migration_image=$migrationImage"
terraform -chdir=infra/yc apply deploy.tfplan
```

Получите gateway URL:

```powershell
$gatewayUrl = terraform -chdir=infra/yc output -raw gateway_url
```

## 9. Применение миграций

Миграции выполняются через отдельный `migration-runner` container в режиме `task`.

Ручной invoke:

```powershell
$migrationUrl = terraform -chdir=infra/yc output -raw migration_container_url
$iamToken = yc iam create-token
curl.exe -sS -D migration-headers.txt -o migration-body.txt `
  -H "Authorization: Bearer $iamToken" `
  $migrationUrl
```

Что проверять:

- успех: заголовок `X-Task-Exit-Code: 0`
- ошибка: открыть `migration-body.txt` и логи контейнера

Локальная проверка доступности БД без применения миграций:

```powershell
poetry run python scripts/migrate_cloud.py --check-only
```

## 10. Smoke test после деплоя

Запуск:

```powershell
poetry run python scripts/smoke_cloud.py --gateway-url $gatewayUrl --bootstrap-token "<bootstrap-api-token>"
```

Сразу после smoke-test закройте bootstrap endpoint:

```powershell
terraform -chdir=infra/yc plan `
  -out close-bootstrap.tfplan `
  -var "enable_bootstrap_api=false" `
  -var "admin_image=$adminImage" `
  -var "public_image=$publicImage" `
  -var "migration_image=$migrationImage"
terraform -chdir=infra/yc apply close-bootstrap.tfplan
```

Smoke-сценарий проходит:

1. onboarding tenant
2. загрузку меню
3. создание widget session
4. чтение меню
5. создание заказа
6. обновление статуса через admin API
7. финальную проверку заказа

Ожидаемый результат:

```text
SUCCESS
```

Если нужен фиксированный tenant для ручной demo-проверки:

```powershell
poetry run python scripts/seed_demo_tenant.py --tenant-id demo
```

Скрипт создаёт или обновляет demo tenant и записывает каноническое demo menu. Для ручной подготовки клиентского меню можно использовать [MENU_UPLOAD_TEMPLATE.json](<C:/Users/Имярек/Downloads/restobot-main/MENU_UPLOAD_TEMPLATE.json>).

## 11. Краткий операторский прогон

Минимальный порядок действий для пилота:

1. включить bootstrap API на время начального seed/smoke;
2. выполнить миграции;
3. создать demo/pilot tenant через `seed_demo_tenant.py` или `admin/onboarding`;
4. прогнать `smoke_cloud.py`;
5. выключить bootstrap API и повторно применить Terraform;
6. пройтись по [PILOT_LAUNCH_CHECKLIST.md](<C:/Users/Имярек/Downloads/restobot-main/PILOT_LAUNCH_CHECKLIST.md>).

## 12. GitHub Actions

Workflow расположен в [deploy.yml](<C:/Users/Имярек/Downloads/restobot-main/.github/workflows/deploy.yml>).

Необходимые GitHub Secrets:

- `YC_SA_JSON_KEY`
- `YC_CLOUD_ID`
- `YC_FOLDER_ID`
- `TF_VAR_DB_PASSWORD`
- `TF_VAR_REDIS_PASSWORD`
- `TF_VAR_JWT_SECRET`
- `TF_VAR_TELEGRAM_TOKEN`
- `TF_VAR_YOKASSA_SHOP_ID`
- `TF_VAR_YOKASSA_SECRET_KEY`
- `TF_VAR_BOOTSTRAP_API_TOKEN`

Workflow выполняет:

1. lint
2. unit tests
3. bootstrap apply
4. build/push образов
5. полный `terraform apply`
6. invoke migration runner
7. smoke test

## 13. Мониторинг и логи

Основные точки наблюдения:

- Serverless Containers -> контейнер -> Revisions -> Logs
- Managed PostgreSQL -> Monitoring
- Managed Redis -> Monitoring
- API Gateway -> метрики и access logs

Полезные Terraform outputs:

- `gateway_url`
- `admin_container_id`
- `public_container_id`
- `db_host`
- `redis_host`
- `migration_container_url`

## 13. Типовые проблемы

### Placeholder images

Нельзя рассчитывать, что контейнеры создадутся на первом `terraform apply` с placeholder image URL. Для этого и нужен двухфазный bootstrap.

### Ограничение max scale

У текущего Terraform provider для Serverless Containers есть управление warm instances (`min_instances`), но нет полноценного hard-поля для верхнего лимита инстансов.

Чтобы не выбить PostgreSQL по connection budget, в стек добавлены консервативные лимиты:

- `database_pool_min = 1`
- `database_pool_max = 2`

Если вы поднимаете большую нагрузку, сначала пересчитайте бюджет соединений, а уже потом увеличивайте pool size.

### Redis TLS

Managed Redis теперь разворачивается с `tls_enabled = true`, а `REDIS_URL` формируется как `rediss://...`.
Убедитесь, что ваши ручные клиенты и отладочные скрипты тоже используют TLS.

### Redis preset

Исходное требование про `2 GB RAM` не всегда напрямую совпадает с текущими доступными preset'ами YC. В Terraform выбран ближайший практический минимальный вариант.

### Безопасность Terraform state

Основной стек уже можно хранить в Object Storage backend, но bootstrap-стек `infra/state_backend` сначала использует локальный state. Этот state содержит static secret key backend service account, поэтому:

- не коммитьте его
- храните его в защищённом месте
- при необходимости после bootstrap удалите локальный state или мигрируйте и этот стек в отдельный backend

### Ошибка migration runner

Чаще всего причина одна из следующих:

- PostgreSQL недоступен из serverless connectivity
- Lockbox secrets ещё не записаны
- в образе нет последних migration files

Проверяйте image tag, логи migration runner и повторяйте invoke только после исправления причины.
