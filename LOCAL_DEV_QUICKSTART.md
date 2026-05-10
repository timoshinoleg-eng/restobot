# RestoBot — Локальный запуск для тестирования

## Требования

- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation)
- Docker + Docker Compose
- Node.js 20+ (если нужен фронтенд)

## Вариант A. Быстрый старт (Poetry + Uvicorn)

Лучше всего для разработки и отладки.

```bash
# Клон / переход в ветку
git checkout codex/yc-mvp-deploy

# Зависимости Python
poetry install

# Переменные окружения
cp .env.example .env
# Отредактируй .env при необходимости (токен бота, JWT_SECRET)

# Инфраструктура: PostgreSQL + Redis
docker-compose up -d postgres redis

# Миграции
poetry run python scripts/migrate_cloud.py
# или напрямую: poetry run alembic upgrade head

# Legacy API (все роуты на одном порту, удобно для тестов)
poetry run uvicorn api.main:app --reload --port 8001
```

**API доступно на:** `http://localhost:8001`  
**Документация:** `http://localhost:8001/docs`

### Раздельный запуск (admin + public + frontend)

Если нужно тестировать именно разделённые cloud API и фронтенд:

```bash
# Терминал 1 — Admin API
poetry run uvicorn apps.admin_api.main:app --reload --port 8000

# Терминал 2 — Public / Widget API
poetry run uvicorn apps.public_api.main:app --reload --port 8001

# Терминал 3 — Frontend
cd frontend/webapp
npm install
npm run dev
```

**URL:**
- Admin API: `http://localhost:8000`
- Public API: `http://localhost:8001`
- WebApp: `http://localhost:5173/demo/menu`

---

## Вариант B. Полный стек в Docker Compose

Если нужно поднять всё сразу в контейнерах без Poetry на хосте.

```bash
cp .env.example .env
# Отредактируй .env (токен бота, JWT_SECRET, YC_FOLDER_ID и т.д.)

# Собрать образ и поднять всё
docker-compose up --build -d

# Миграции (в отдельном одноразовом контейнере)
docker-compose run --rm api poetry run alembic upgrade head
```

**Что поднимается:**
- PostgreSQL `localhost:5432`
- Redis `localhost:6379`
- Legacy API `http://localhost:8001`
- Telegram Bot
- AI Service
- Payment Worker

> В `docker-compose.yml` используется **legacy API** (`api.main`) на порту 8001.  
> Если нужны раздельные admin/public API — используй Вариант A (запуск двух uvicorn-процессов) или докеризуй `apps/admin_api` + `apps/public_api` вручную.

---

## Demo-данные

```bash
# Создать demo tenant + меню + admin
poetry run python scripts/seed_demo_tenant.py --tenant-id demo
```

Выведет JSON с `admin_token`. Скопируй его для smoke-тестов.

```bash
# Smoke-тест (через legacy API)
poetry run python scripts/smoke_cli_tenant.py \
  --gateway-url http://localhost:8001 \
  --tenant-id demo \
  --admin-token <admin_token из вывода выше>
```

---

## Тесты

```bash
# Все тесты (исключая cloud-интеграции)
poetry run pytest -m "not cloud" -q

# Только авторизация и админка
poetry run pytest tests/test_auth.py tests/test_admin_routes.py -q
```

---

## Полезные команды

| Действие | Команда |
|----------|---------|
| Проверить БД | `docker-compose ps postgres redis` |
| Логи БД | `docker-compose logs -f postgres` |
| Пересоздать БД | `docker-compose down -v && docker-compose up -d postgres redis` |
| Проверить миграции | `poetry run alembic current` |
| Новый tenant (CLI) | `poetry run python scripts/provision_tenant.py --tenant-id my_test --restaurant-name "Test" --admin-name "Admin" --admin-email "a@test.ru" --admin-phone "+79990000000"` |
| Загрузить меню | `poetry run python scripts/upload_menu.py --tenant-id my_test --menu-file MENU_UPLOAD_TEMPLATE.json` |
| Линтер | `poetry run ruff check .` |

---

## Переменные окружения (`.env`)

Минимальный набор для локального запуска:

```env
DATABASE_URL=postgresql+asyncpg://restobot:password@localhost:5432/restobot
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_TLS_ENABLED=false
JWT_SECRET=local_dev_secret_min_32_chars_here
TELEGRAM_BOT_TOKEN=your_bot_token_or_dummy_for_tests
YOOKASSA_SHOP_ID=test
YOOKASSA_SECRET_KEY=test
YC_FOLDER_ID=test-folder
```

> Для тестов `TELEGRAM_BOT_TOKEN` может быть любой строкой. Для реального бота — получи у [@BotFather](https://t.me/botfather).

---

## Что запускать для чего

| Задача | Что запускать |
|--------|---------------|
| Юнит-тесты, отладка роутов | `uvicorn api.main:app --reload --port 8001` |
| Проверить разделение admin/public | `uvicorn apps.admin_api.main:app --port 8000` + `apps.public_api.main:app --port 8001` |
| Пилотный UI-флоу | `frontend/webapp` + `api.main:app` |
| Проверить Telegram-бота | `docker-compose up bot` (нужен реальный токен) |
