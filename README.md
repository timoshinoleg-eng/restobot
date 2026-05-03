# RestoBot

RestoBot - backend/API для ресторанного MVP на FastAPI, PostgreSQL, Redis и Yandex Cloud.

В текущем состоянии репозиторий содержит:

- совместимый локальный API в `api/main.py`
- облачный admin API в `apps/admin_api/main.py`
- облачный public/widget API в `apps/public_api/main.py`
- Terraform для Yandex Cloud в `infra/yc`
- отдельный bootstrap для remote state в `infra/state_backend`
- одноразовый migration runner в `scripts/migrate_cloud.py`
- smoke-тест после деплоя в `scripts/smoke_cloud.py`
- seed-скрипт для demo tenant в `scripts/seed_demo_tenant.py`
- CLI-импорт меню для нового tenant в `scripts/upload_menu.py`

## Локальный запуск

```bash
cp .env.example .env
docker-compose up -d postgres redis
poetry install
poetry run python scripts/migrate_cloud.py
poetry run uvicorn api.main:app --reload --port 8001
```

Локально основной совместимый HTTP API доступен на `http://localhost:8001`.

## Demo tenant для пилота

Для воспроизводимого demo/pilot-контура добавлен seed-скрипт:

```bash
poetry run python scripts/seed_demo_tenant.py --tenant-id demo
```

Скрипт:

1. создаёт или обновляет tenant;
2. создаёт admin-пользователя;
3. записывает demo menu;
4. возвращает `admin_token` для последующих admin-вызовов.

Если нужен только JSON-шаблон меню без записи в БД:

```bash
poetry run python scripts/seed_demo_tenant.py --print-menu-template
```

Шаблон также сохранён в [MENU_UPLOAD_TEMPLATE.json](<C:/Users/Имярек/Downloads/restobot-main/MENU_UPLOAD_TEMPLATE.json>).

## Новый магазин: provisioning и загрузка меню

Production-контур рассчитан на CLI, а не на постоянный HTTP bootstrap:

```bash
poetry run python scripts/provision_tenant.py \
  --tenant-id bistro_01 \
  --restaurant-name "Bistro 01" \
  --admin-name "Owner Name" \
  --admin-email "owner@bistro.ru" \
  --admin-phone "+79990000000"
```

После этого меню и цены можно залить из JSON-шаблона:

```bash
poetry run python scripts/upload_menu.py \
  --tenant-id bistro_01 \
  --menu-file MENU_UPLOAD_TEMPLATE.json
```

## Деплой в Yandex Cloud

Короткий сценарий:

1. Поднять backend для Terraform state в `infra/state_backend`.
2. Инициализировать основной стек `infra/yc` на Yandex Object Storage backend.
3. Заполнить `infra/yc/terraform.tfvars`.
4. Выполнить bootstrap инфраструктуры без контейнеров.
5. Собрать и запушить Docker-образы в Yandex Container Registry.
6. Выполнить `terraform plan` и затем `terraform apply` с реальными image URL, временно включив `enable_bootstrap_api=true`.
7. Запустить migration runner.
8. Выполнить `poetry run python scripts/smoke_cloud.py --gateway-url <gateway-url> --bootstrap-token <bootstrap-token>`.
9. После smoke вернуть `enable_bootstrap_api=false` и применить Terraform повторно.

Подробная инструкция находится в [DEPLOYMENT.md](<C:/Users/Имярек/Downloads/restobot-main/DEPLOYMENT.md>).

Для операторского запуска пилота дополнительно подготовлены:

- [PILOT_LAUNCH_CHECKLIST.md](<C:/Users/Имярек/Downloads/restobot-main/PILOT_LAUNCH_CHECKLIST.md>)
- [CUSTOMER_ONBOARDING_CHECKLIST.md](<C:/Users/Имярек/Downloads/restobot-main/CUSTOMER_ONBOARDING_CHECKLIST.md>)

## Автоматизация bootstrap

Добавлены два варианта автоматизации:

- [Makefile](<C:/Users/Имярек/Downloads/restobot-main/Makefile>) для Unix-like окружений и Git Bash
- [bootstrap_backend.ps1](<C:/Users/Имярек/Downloads/restobot-main/scripts/bootstrap_backend.ps1>) для Windows PowerShell

PowerShell-скрипт выполняет:

1. `terraform init/apply` в `infra/state_backend`
2. чтение bucket/access key/secret key из outputs
3. генерацию `infra/yc/backend.hcl`
4. `terraform init -reconfigure` в `infra/yc`

## Ключевые файлы

- [apps/admin_api/main.py](<C:/Users/Имярек/Downloads/restobot-main/apps/admin_api/main.py>)
- [apps/public_api/main.py](<C:/Users/Имярек/Downloads/restobot-main/apps/public_api/main.py>)
- [shared/app_factory.py](<C:/Users/Имярек/Downloads/restobot-main/shared/app_factory.py>)
- [shared/mvp_bootstrap.py](<C:/Users/Имярек/Downloads/restobot-main/shared/mvp_bootstrap.py>)
- [infra/yc](<C:/Users/Имярек/Downloads/restobot-main/infra/yc>)
- [.github/workflows/deploy.yml](<C:/Users/Имярек/Downloads/restobot-main/.github/workflows/deploy.yml>)

## Локальная валидация

Изменения были локально проверены:

```bash
poetry run pytest -q
```

Текущий результат: `80 passed, 4 skipped`.
