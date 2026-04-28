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

## Локальный запуск

```bash
cp .env.example .env
docker-compose up -d postgres redis
poetry install
poetry run python scripts/migrate_cloud.py
poetry run uvicorn api.main:app --reload --port 8001
```

Локально основной совместимый HTTP API доступен на `http://localhost:8001`.

## Деплой в Yandex Cloud

Короткий сценарий:

1. Поднять backend для Terraform state в `infra/state_backend`.
2. Инициализировать основной стек `infra/yc` на Yandex Object Storage backend.
3. Заполнить `infra/yc/terraform.tfvars`.
4. Выполнить bootstrap инфраструктуры без контейнеров.
5. Собрать и запушить Docker-образы в Yandex Container Registry.
6. Выполнить полный `terraform apply` с реальными image URL.
7. Запустить migration runner.
8. Выполнить `poetry run python scripts/smoke_cloud.py --gateway-url <gateway-url>`.

Подробная инструкция находится в [DEPLOYMENT.md](<C:/Users/Имярек/Downloads/restobot-main/DEPLOYMENT.md>).

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
