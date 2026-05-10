# Backup & Recovery Runbook

## Цель
Обеспечить ежедневное резервное копирование БД и проверенную процедуру восстановления.

## RPO / RTO
- **RPO:** 24 часа (ежедневный бэкап в 03:00 UTC)
- **RTO:** 4 часа (восстановление на чистый инстанс + smoke-тест)

## Предварительные требования
- `pg_dump` и `pg_restore` установлены на хосте
- Доступ к Yandex Object Storage (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)
- `aws-cli` или `boto3` для загрузки в S3

## Ежедневный бэкап

### Через хостовый cron (рекомендуется)
```bash
# /etc/cron.d/restobot-backup
0 3 * * * root cd /opt/restobot && docker compose -f docker/docker-compose.prod.yml run --rm backup >> /var/log/restobot-backup.log 2>&1
```

### Через Docker Compose (ручной запуск)
```bash
docker compose -f docker/docker-compose.prod.yml run --rm backup
```

### Локальный запуск скрипта
```bash
export DATABASE_URL="postgresql://user:pass@host:6432/restobot"
export YC_OBJECT_STORAGE_BUCKET="restobot-backups"
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
python scripts/backup_db.py
```

## Ротация
В бакете хранятся последние **30** резервных копий. Старые автоматически удаляются при создании новой.

## Восстановление (drill)

### Шаг 1: Подготовить чистую БД
```bash
export DATABASE_URL="postgresql://user:pass@staging-host:6432/restobot_staging"
```

### Шаг 2: Скачать и восстановить
```bash
python scripts/restore_db.py s3://restobot-backups/backups/restobot/restobot_20260115_030000.dump
```

### Шаг 3: Проверить целостность
```bash
python scripts/smoke_production.py --base-url https://staging.chatbot24.su --tenant smoke_drill
```

### Шаг 4: Проверить ключевые таблицы
```sql
SELECT COUNT(*) FROM shared.tenants;
SELECT COUNT(*) FROM tenant_demo.orders;
SELECT MAX(created_at) FROM tenant_demo.orders;
```

## Проверка бэкапа
Каждое воскресенье запускать `restore_db.py` на staging и прогонять smoke-тест.

## Контакты при инциденте
- On-call SRE: +7...
- Yandex Cloud support: https://cloud.yandex.ru/support
