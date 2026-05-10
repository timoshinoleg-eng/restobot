# Operational Runbook — RestoBot

## Health Endpoints
| Сервис | Endpoint | Проверяет |
|--------|----------|-----------|
| Admin API | `GET /health` | DB session, DB pool, Redis |
| Public API | `GET /health` | DB session, DB pool, Redis |
| Bot | `GET /health` | DB pool, Redis, bot session |
| Metrics | `GET /metrics` | Prometheus exposition |

## Критические алерты

### 1. service_down
**Условие:** `up{job="restobot"} == 0` в течение 2 минут  
**Действие:**
1. Проверить `docker ps` — сервис running?
2. Посмотреть логи: `docker logs --tail 200 restobot-admin-1`
3. Если OOM — увеличить memory limit в compose
4. Если DB connection error — проверить `yc managed-postgresql health`

### 2. error_rate_high
**Условие:** rate(http_requests_total{status=~"5.."}[5m]) > 1%  
**Действие:**
1. Открыть логи: grep `"status_code": 5` в JSON-логах
2. Найти `request_id` последнего 500
3. Проверить `/metrics` на спikes `restobot_ai_latency_seconds` или DB pool

### 3. db_pool_exhausted
**Условие:** `database_pool_idle / database_pool_size < 0.2`  
**Действие:**
1. Проверить long-running queries: `SELECT * FROM pg_stat_activity WHERE state = 'active'`
2. Увеличить `DATABASE_POOL_MAX` (перезапуск контейнера)
3. Если постоянно — добавить read-replica

### 4. latency_p99_high
**Условие:** histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 2s  
**Действие:**
1. Проверить pg_stat_statements на медленные запросы
2. Проверить Redis latency
3. Проверить YandexGPT latency в `/metrics`

### 5. backup_failed
**Условие:** Отсутствие нового объекта в S3 за последние 25 часов  
**Действие:**
1. Проверить `/var/log/restobot-backup.log`
2. Запустить бэкап вручную: `docker compose run --rm backup`

## Rollback Procedure
1. Остановить сервисы: `docker compose down`
2. Откатить image tag в `.env.prod` на предыдущий SHA
3. Перезапустить: `docker compose up -d`
4. Проверить `/health` и запустить `scripts/smoke_production.py`

## Bootstrap в production
1. Включить временно: `ENABLE_BOOTSTRAP_API=true` + `BOOTSTRAP_API_TOKEN=<random>`
2. Создать tenant через `POST /admin/onboarding`
3. Выключить: `ENABLE_BOOTSTRAP_API=false`
4. Проверить, что endpoint возвращает 403

## Контакты
- Primary on-call: ...
- Secondary: ...
