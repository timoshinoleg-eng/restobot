# RestoBot VM Runtime — Runbook

## Архитектура

- **Caddy** — reverse proxy (порт 80/443), терминация TLS, маршрутизация по префиксам.
- **admin** (`apps.admin_api`) — порт 8000, префикс `/admin`.
- **public** (`apps.public_api`) — порт 8001, префиксы `/widget`, `/api`.
- **docker-compose.prod.yml** управляет только этими тремя сервисами.
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

## Deploy

```bash
cd /opt/restobot
# Пример с конкретными тегами
./deploy.sh cr.yandex/<registry>/restobot-admin:v1.2.3 cr.yandex/<registry>/restobot-public:v1.2.3
```

Скрипт:
1. Сохраняет текущие теги в `.rollback.env`.
2. Обновляет `ADMIN_IMAGE` / `PUBLIC_IMAGE` в `.env.prod` (создаёт ключ, если отсутствует).
3. Делает `docker compose pull admin public && up -d`.
4. **Поллит health каждые 5 секунд до 90 секунд**.
5. **После healthy admin/public проверяет proxy ingress** (`curl` через Caddy на `/admin/health` и `/widget/health`).
6. При любой неудаче — автоматически вызывает `rollback.sh`.

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
| Деплой откатился сразу | Проверить `docker inspect restobot-admin-1 --format='{{.State.Health.Status}}'` — возможно, старт длится дольше 90 секунд (увеличить `MAX_WAIT` в `deploy.sh`). |
| VM перезагрузилась | `systemctl status restobot-compose@ubuntu` должен показывать `active (exited)`. Если нет — `sudo systemctl enable --now restobot-compose@ubuntu`. |
| Caddy не стартует из-за unhealthy backend | Caddy больше не ждёт healthy admin/public (`depends_on` без condition). Если Caddy не поднялся — смотреть `docker logs restobot-caddy-1`. |
