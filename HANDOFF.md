# RestoBot Handoff

Дата: 2026-05-04
Репозиторий: `C:\Users\Имярек\Downloads\restobot-main`
Ветка: `codex/yc-mvp-deploy`
Состояние: `ahead 25`, working tree clean (единственное локальное изменение — этот `HANDOFF.md`)

## 1. Что это за срез

Это актуальный handoff для продолжения работы без повторной раскопки проекта.
Ниже только текущее инженерное состояние, подтверждённые точки и ближайший pragmatic next step.

## 2. Текущий статус продукта и платформы

Подтверждено:

- production и demo/pilot контуры поднимались и проверялись;
- tenant provisioning идёт через CLI, не через HTTP bootstrap;
- Telegram WebApp обновлён;
- online payment flow через YooKassa доведён до рабочего backend/frontend контракта;
- admin backoffice MVP добавлен и заведён в репозиторий;
- setup token lifecycle стабилизирован;
- unit и integration CI разделены;
- integration suite под real Postgres/Redis добавлен.

## 3. Что уже есть в коде

### CLI provisioning

Основные скрипты:

- `scripts/provision_tenant.py`
- `scripts/upload_menu.py`
- `scripts/seed_demo_tenant.py`
- `scripts/set_admin_password.py`
- `scripts/smoke_webapp.py`

### Admin Backoffice MVP

Подтверждённые возможности:

- cookie-based auth;
- first-login через `setup_token`;
- JWT revocation on logout;
- audit log;
- onboarding / settings / users / menu / orders / bookings / inventory / loyalty pages;
- static admin panel;
- graceful startup admin app без `static/admin`.

Ключевые admin роуты:

- `api/routes/auth.py`
- `api/routes/audit.py`
- `api/routes/onboarding.py`
- `api/routes/settings.py`
- `api/routes/users.py`

Admin app entrypoint:

- `apps/admin_api/main.py`

### WebApp / Public contour

Подтверждено:

- улучшен дизайн;
- добавлена маска телефона;
- frontend/backend flow оплаты синхронизирован;
- exact-match routing для `/widget` и `/admin` в Caddy исправлен.

### Infra / deploy

Подтверждено:

- `.github/workflows/ci.yml` оставлен для unit/in-memory;
- `.github/workflows/integration-staging.yml` запускает migrations + integration tests на postgres/redis service containers;
- `docker/Caddyfile` исправлен для `/admin`, `/widget`, `/admin/health`, `/widget/health`;
- `.dockerignore` исключает `frontend/webapp/node_modules` и `frontend/webapp/dist`.

## 4. Последние значимые коммиты

Последние подтверждённые коммиты:

- `0a11d14` `fix(admin): graceful startup when static/admin is missing; add regression test`
- `336b68b` `fix(deploy): add /admin /widget exact-match routes to Caddy; ignore frontend build artifacts in Docker`
- `64a93cc` `test: cover admin users CRUD, settings, onboarding, audit, auth rate limiter`
- `ee9b0f6` `test: add admin auth, e2e, integration smoke, bot tenant routing tests`
- `7afd5ce` `feat(ci,deploy): split unit/integration CI, docker updates, runbook docs`
- `ce5651b` `feat(api,bot,payments): extend routes, bot tenant routing, payments flow`
- `475906b` `feat(frontend): add Telegram webapp source and deployment scripts`
- `ac5b2a8` `feat(admin): add admin backoffice MVP — auth, audit, settings, onboarding, static panel`

## 5. Последняя подтверждённая проверка

Фактически проверено в этом чате:

- `git status` clean;
- ветка `ahead 25`;
- `tests/test_users.py` и `tests/test_admin_routes.py` на месте;
- `tests/test_auth.py` расширен regression coverage;
- `apps/admin_api/main.py` не падает без `static/admin`;
- `docker/Caddyfile` содержит exact-match handlers для `/admin` и `/widget`;
- `.dockerignore` режет frontend build artifacts.

Целевые локальные прогоны, подтверждённые здесь:

- `pytest tests/ -o addopts="" -m "not integration" -q --tb=short`
  - результат: **`163 passed, 8 skipped, 28 deselected`** (полный unit suite)
- `pytest tests/test_auth.py tests/test_users.py tests/test_admin_routes.py -q`
  - результат: `23 passed, 25 skipped`
- `pytest tests/test_auth.py -q`
  - результат: `7 passed, 9 skipped`

Из пользовательского статуса:

- **unit suite:** `163 passed, 8 skipped, 28 deselected` (актуальный прогон; deselected = integration tests)
- **integration:** локально недоступен (нет Postgres/Redis)

Важно: полный integration suite локально зависит от доступных Postgres/Redis. В текущем окружении они не запущены — integration path не прогонялся.

## 6. Миграции и данные

Новые миграции:

- `migrations/versions/004_add_telegram_user_tenants.py`
- `migrations/versions/005_add_admin_tables.py`

С setup token lifecycle есть важные инварианты:

- `bootstrap_tenant()` не должен перегенерировать token, если у админа уже есть `password_hash`;
- `scripts/set_admin_password.py` не должен трогать `setup_token`, если пароль уже существовал.

## 7. Что уже покрыто тестами

### Auth

Покрыто:

- first-login через `setup_token`;
- отказ без token;
- отказ с неверным token;
- subsequent login по паролю;
- `/auth/me`;
- logout + cookie clearing;
- `401` после logout;
- login rate limiter;
- startup admin app без static directory.

### Users

Покрыто:

- Pydantic validation `UserCreate/UserUpdate`;
- phone normalization;
- role validation;
- list/create/update/soft-delete;
- `404` / `422` scenarios.

### Admin routes

Покрыто:

- settings get/update;
- working hours;
- onboarding status;
- onboarding complete;
- audit log;
- audit filters.

### Integration / infra

Покрыто:

- bootstrap / Redis smoke;
- revoked-token post-logout;
- bot tenant routing;
- staging integration workflow.

## 8. На что смотреть первым делом, если продолжаем

Если работа идёт по admin/auth/integration/deploy, сначала читать актуальные файлы:

- `apps/admin_api/main.py`
- `api/routes/auth.py`
- `api/routes/users.py`
- `api/routes/settings.py`
- `api/routes/onboarding.py`
- `api/routes/audit.py`
- `shared/mvp_bootstrap.py`
- `shared/jwt_utils.py`
- `shared/auth_dependencies.py`
- `.github/workflows/ci.yml`
- `.github/workflows/integration-staging.yml`
- `docker/Caddyfile`

Не опираться на старые handoff-заметки или раннее состояние дерева.

## 9. Открытые практические темы

На текущий момент не выглядит как авария, но это нормальные следующие зоны работы:

1. ✅ Прогнать полный локальный unit suite — **выполнено**, `163 passed, 8 skipped, 28 deselected`.
2. ✅ Добавить `pytest.mark.integration` к integration-тестам (`test_auth.py`, `test_users.py`, `test_admin_routes.py`) — **выполнено**.
3. ⏳ Прогнать integration path на доступных Postgres/Redis или через staging workflow.
4. ⏳ Сделать end-to-end pilot walkthrough:
   - `provision_tenant.py`
   - `upload_menu.py` / `seed_demo_tenant.py`
   - first admin login
   - webapp order flow
   - payment flow
   - logout/login retry
5. ⏳ Дочистить и структурировать runbook/ops шаги, если пойдут новые деплойные изменения.

## 10. Что не делать

- не откатывать ничего вслепую;
- не исходить из старого состояния admin/auth/deploy;
- не смешивать новый функциональный diff с unrelated cleanup;
- не ломать CLI provisioning возвратом к HTTP bootstrap;
- не тащить frontend build artifacts в базовый Python image.

## 11. Готовый стартовый текст для нового чата

```text
Используй HANDOFF.md как основной контекст.

Работаем в `C:\Users\Имярек\Downloads\restobot-main`, ветка `codex/yc-mvp-deploy`.
Working tree должен быть clean, ветка ahead of origin.

Сначала:
1. проверь `git status`,
2. подтверди текущее состояние по HANDOFF.md,
3. только потом переходи к следующей инженерной задаче.

Если задача касается admin/auth/integration/deploy, сначала прочитай актуальные:
- apps/admin_api/main.py
- api/routes/auth.py
- api/routes/users.py
- api/routes/settings.py
- api/routes/onboarding.py
- api/routes/audit.py
- shared/mvp_bootstrap.py
- docker/Caddyfile
- .github/workflows/integration-staging.yml
```
