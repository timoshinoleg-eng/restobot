# RestoBot Environment Contract (Production)

## 1. Philosophy

- **Explicit over implicit**: каждая переменная окружения должна быть задана явно. Defaults допустимы только для не-критичных параметров (TTL, timeouts).
- **Component-first для connection strings**: пароли со спецсимволами (`/`, `+`, `@`) ломают URL-парсинг. Поэтому Redis подключается через компоненты, а не монолитный URL.
- **Backward compat without baggage**: `REDIS_URL` и `DATABASE_URL` пока поддерживаются, но помечены как deprecated и не рекомендуются для новых сред.

## 2. Required Variables

| Variable | Source | Purpose |
|----------|--------|---------|
| `DATABASE_URL` | Lockbox / env | Managed PostgreSQL. Для VM-runtime используется готовый URL от YC (обычно без проблемных спецсимволов в пароле). Компонентный fallback (`DATABASE_HOST`/`DATABASE_USER`/`DATABASE_PASSWORD`) зарезервирован для edge-case. |
| `REDIS_HOST` | Lockbox / env | Managed Redis hostname. |
| `REDIS_PASSWORD` | Lockbox | Managed Redis password (может содержать `/`). |
| `REDIS_PORT` | env (default `6379`) | Redis port. |
| `REDIS_DB` | env (default `0`) | Redis logical database. |
| `REDIS_TLS_ENABLED` | env (default `false`) | **Обязательно `true` для YC Managed Redis** (требует `rediss://`). Для локального dev-Redis — `false`. |
| `JWT_SECRET` | Lockbox | HS256 key, min 32 chars. |
| `YOOKASSA_SHOP_ID` | Lockbox | ЮKassa shop identifier. |
| `YOOKASSA_SECRET_KEY` | Lockbox | ЮKassa secret key. |
| `TELEGRAM_BOT_TOKEN` | Lockbox | Telegram Bot API token. |
| `YC_FOLDER_ID` | env | Yandex Cloud folder ID. |
| `YC_OBJECT_STORAGE_BUCKET` | env | S3-compatible bucket name. |
| `YC_OBJECT_STORAGE_ENDPOINT` | env (default `https://storage.yandexcloud.net`) | Object Storage endpoint. |

## 3. Bootstrap & Security

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENABLE_BOOTSTRAP_API` | `false` | Включает `POST /admin/onboarding`. **В production должен быть `false` после первоначального onboarding'а.** |
| `BOOTSTRAP_API_TOKEN` | `None` | Токен для защиты bootstrap endpoint. Обязателен, если `ENABLE_BOOTSTRAP_API=true`. |

**Правило**: bootstrap endpoint отключён по умолчанию. Включать только на время создания первого tenant'а, затем сразу отключать.

## 4. Deprecated / Legacy

| Variable | Status | Action |
|----------|--------|--------|
| `REDIS_URL` | Deprecated | При использовании выбрасывает `DeprecationWarning`. Перейти на `REDIS_HOST`/`REDIS_PASSWORD`/`REDIS_TLS_ENABLED`. |
| `ENV` | Alias | `ENVIRONMENT` имеет приоритет. Оставлен для совместимости со старыми модулями. |

## 5. Secret Management (YC Lockbox)

Для serverless- и VM-runtime единый источник truth — **Yandex Lockbox**.

### Lockbox Secret Structure

**`common`** (non-sensitive + shared secrets):
- `jwt_secret` → `JWT_SECRET`
- `telegram_token` → `TELEGRAM_BOT_TOKEN`
- `yokassa_shop_id` → `YOOKASSA_SHOP_ID`
- `yokassa_secret_key` → `YOOKASSA_SECRET_KEY`
- `bootstrap_api_token` → `BOOTSTRAP_API_TOKEN` (optional)

**`db`** (database credentials):
- `database_url` → `DATABASE_URL` (legacy, лучше `db_user` + `db_password` + `db_host`)
- `db_user` / `db_password` → компоненты для сборки `DATABASE_URL`

**`redis`** (redis credentials):
- `redis_password` → `REDIS_PASSWORD`
- ~~`redis_url`~~ → **удалён из контракта**, хост передаётся через `environment` в Terraform (`local.redis_host`), TLS явно `true`.

### VM Runtime (production-consistent)

На VM секреты подаются через `.env.prod` (файл на диске, `chmod 600`). Он не коммитится. Пример: `docker/.env.prod.example`.

## 6. Migration & Database

- **Managed PostgreSQL (YC) не поддерживает `pgvector`**. Миграция `000_base_mvp_schema.py` проверяет `pg_available_extensions` перед `CREATE EXTENSION`.
- Alembic entrypoint (`migrations/env.py`) использует `shared.config.get_settings()`, поэтому миграции видят те же переменные, что и runtime.
- `alembic.ini` содержит `prepend_sys_path = .`, что корректно работает при `WORKDIR /app` в контейнере.

## 7. Entrypoints & CWD Independence

- `scripts/run_admin.py` и `scripts/run_public.py` определяют `PROJECT_ROOT` через `pathlib.Path(__file__).resolve().parents[1]` и вставляют его в `sys.path[0]`.
- Это гарантирует корректный импорт `apps.*` и `shared.*` независимо от `cwd`.
- Dockerfile устанавливает `WORKDIR /app`, поэтому `python scripts/run_admin.py` работает из корня проекта.

## 8. Temporary Workarounds to Remove

| Workaround | Location | When to Remove |
|------------|----------|----------------|
| `REDIS_URL` backward compat | `shared/config.py` | Когда все среды (serverless + VM + dev) перешли на компоненты. После перехода — удалить поле `REDIS_URL` и валидатор. |
| `pgvector` conditional create | `migrations/versions/000_base_mvp_schema.py` | Когда мигрируем на self-hosted Postgres с pgvector или если YC добавит поддержку. Тогда убрать `IF EXISTS` проверку. |
| `ENABLE_BOOTSTRAP_API` | `shared/auth_dependencies.py` | После того как tenant provisioning вынесен в отдельный сервис/CLI (см. `PRODUCTION_ISSUE_LIST.md` #2). |

## 9. Validation Checklist

Перед выкаткой в production:

- [ ] `.env.prod` не содержит `REDIS_URL`.
- [ ] `.env.prod` содержит `REDIS_HOST`, `REDIS_PASSWORD`, `REDIS_TLS_ENABLED=true` (для YC).
- [ ] `ENABLE_BOOTSTRAP_API=false` (или отсутствует).
- [ ] `BOOTSTRAP_API_TOKEN` задан, если bootstrap временно включён.
- [ ] `JWT_SECRET` ≥ 32 символов.
- [ ] `DATABASE_URL` не содержит неэкранированных спецсимволов (или используются компоненты `DATABASE_HOST`/`DATABASE_USER`/`DATABASE_PASSWORD`).
- [ ] `docker compose -f docker-compose.prod.yml config` отрабатывает без ошибок.
- [ ] `alembic upgrade head` проходит на целевой managed PostgreSQL.
