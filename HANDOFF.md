# RestoBot Handoff

Дата: 2026-05-05  
Репозиторий: `C:\Users\Имярек\Downloads\restobot-main`  
Ветка: `codex/yc-mvp-deploy`

## 1. Что это за срез

Это актуальный handoff после завершения critical YC Serverless/VPC debugging.

На этом срезе:

- Terraform pilot attach flow уже стабилизирован;
- root cause `502/503/504` на `/health` найден;
- production-like `/health` сейчас подтвержденно работает;
- Redis reconnect issue после выкатки новых образов уже подтвержденно исправлен;
- static admin UI теперь реально отдается из контейнера;
- следующий фокус уже не на infra-debug, а на smoke/e2e и дальнейшей операционке.

## 2. Текущее состояние дерева

Working tree **не clean**.

Основные подтвержденные infra-файлы с изменениями:

- [infra/yc/api-gateway.tf](C:/Users/Имярек/Downloads/restobot-main/infra/yc/api-gateway.tf)
- [infra/yc/containers.tf](C:/Users/Имярек/Downloads/restobot-main/infra/yc/containers.tf)
- [infra/yc/db.tf](C:/Users/Имярек/Downloads/restobot-main/infra/yc/db.tf)
- [infra/yc/lockbox.tf](C:/Users/Имярек/Downloads/restobot-main/infra/yc/lockbox.tf)
- [infra/yc/network.tf](C:/Users/Имярек/Downloads/restobot-main/infra/yc/network.tf)
- [infra/yc/outputs.tf](C:/Users/Имярек/Downloads/restobot-main/infra/yc/outputs.tf)
- [infra/yc/providers.tf](C:/Users/Имярек/Downloads/restobot-main/infra/yc/providers.tf)
- [infra/yc/redis.tf](C:/Users/Имярек/Downloads/restobot-main/infra/yc/redis.tf)
- [infra/yc/security-group-rules.tf](C:/Users/Имярек/Downloads/restobot-main/infra/yc/security-group-rules.tf)
- [infra/yc/service-account.tf](C:/Users/Имярек/Downloads/restobot-main/infra/yc/service-account.tf)
- [infra/yc/terraform.tfvars.example](C:/Users/Имярек/Downloads/restobot-main/infra/yc/terraform.tfvars.example)
- [infra/yc/variables.tf](C:/Users/Имярек/Downloads/restobot-main/infra/yc/variables.tf)

Есть также много временных/диагностических локальных файлов в корне repo и сервисных папках. Они не являются source of truth для infra. Источник истины по YC deploy — `infra/yc/*.tf` в репозитории.

Опорный коммит для текущего рабочего состояния:

- `d19d694` `fix(deploy): restore yc serverless connectivity and stabilize redis health`

## 3. Что уже сделано по YC infra

### 3.1 Pilot attach flow

Стек переведен в безопасный режим для пилота:

- Managed PostgreSQL вынесен из активного Terraform-управления;
- Managed Redis/Valkey вынесен из активного Terraform-управления;
- `yandex_lockbox_secret_version.*` больше не создаются Terraform-ом в этом стеке;
- subnet/security group data plane не пересоздаются текущим стеком;
- serverless containers получают существующие:
  - `db_host`
  - `redis_host`
  - `Lockbox version ids`

Это было сделано, чтобы убрать destructive plan по Redis/Lockbox/VPC.

### 3.2 Важные Terraform-изменения

#### [infra/yc/containers.tf](C:/Users/Имярек/Downloads/restobot-main/infra/yc/containers.tf)

- контейнеры используют:
  - `existing_db_host`
  - `existing_redis_host`
  - `existing_common_secret_version_id`
  - `existing_db_secret_version_id`
  - `existing_redis_secret_version_id`
- `bootstrap_api_token` dynamic block переписан в безопасную форму;
- runtime entrypoint fix:
  - `admin_api`: `python -m apps.admin_api.main`
  - `public_api`: `python -m apps.public_api.main`
- `connectivity` для `admin_api` и `public_api` должна быть включена и не должна теряться при следующих правках

Причина: старый registry image не умел корректно стартовать через `python scripts/run_admin.py` / `python scripts/run_public.py`.

#### [infra/yc/providers.tf](C:/Users/Имярек/Downloads/restobot-main/infra/yc/providers.tf)

Старые cross-variable `validation` убраны и заменены на `check`-блоки, совместимые с реально используемым Terraform runtime.

#### [infra/yc/service-account.tf](C:/Users/Имярек/Downloads/restobot-main/infra/yc/service-account.tf)

Для runtime service account добавлена роль:

- `vpc.user`

Это обязательная часть serverless VPC-path.

#### [infra/yc/api-gateway.tf](C:/Users/Имярек/Downloads/restobot-main/infra/yc/api-gateway.tf)

Исправлен `execution_timeout`:

- было: `"30s"`
- стало: `"30"`

#### [infra/yc/security-group-rules.tf](C:/Users/Имярек/Downloads/restobot-main/infra/yc/security-group-rules.tf)

Добавлены отдельные ingress-правила для documented YC Serverless service subnet range:

- `198.19.0.0/16` → PostgreSQL `6432`
- `198.19.0.0/16` → Redis `6379`
- `198.19.0.0/16` → Redis TLS `6380`

Это финальный fix, который реально починил `/health`.

### 3.3 Изменения в приложении после infra-fix

#### [shared/redis_client.py](C:/Users/Имярек/Downloads/restobot-main/shared/redis_client.py)

Подтвержденный fix против intermittent Redis unhealthy:

- добавлены pool health settings:
  - `health_check_interval=30`
  - `retry_on_timeout=True`
  - `socket_keepalive=True`
- при `redis.ConnectionError` singleton клиент сбрасывается;
- `check_redis_health()` делает одну попытку пересоздания клиента перед возвратом `unhealthy`;
- cache helpers (`get_cache`, `set_cache` и т.п.) тоже сбрасывают singleton при connection-level ошибке

#### [shared/app_factory.py](C:/Users/Имярек/Downloads/restobot-main/shared/app_factory.py)

В `lifespan` добавлена eager Redis initialization при старте контейнера.

Причина:

- без этого serverless instance мог просыпаться с уже умершим соединением из старого пула;
- после фикса `/health x10` прошел без Redis flaps.

## 4. Root cause и как он был закрыт

### 4.1 Первый root cause: сломанный entrypoint в старом image

Подтверждено:

- старый image `manual-20260502000125-12fea33`
- `python scripts/run_admin.py` / `python scripts/run_public.py`
- ошибка:
  - `ModuleNotFoundError: No module named 'apps'`

Это было исправлено через `python -m apps.admin_api.main` и `python -m apps.public_api.main`.

### 4.2 Второй root cause: Serverless connectivity + Security Group mismatch

После починки entrypoint получили:

- `connectivity OFF` → быстрый `503`, body показывает DNS failure по DB и Redis
- `connectivity ON` → долгий `504 execution timeout exceeded`

Потом отдельный диагностический serverless container доказал:

- DNS resolve работает
- private IP Postgres и Redis резолвятся корректно
- TCP к PostgreSQL и Redis зависает на timeout
- source IP serverless runtime приходит не из `10.0.x.x`, а из диапазона `198.19.x.x`

Дополнительно собраны 5 cold starts. Наблюдаемые source IP:

- `198.19.36.229`
- `198.19.35.242`
- `198.19.35.215`
- `198.19.35.253`
- `198.19.36.76`

Из этого стало ясно:

- SG на Postgres/Redis разрешала ingress только с `10.0.1.0/24`, `10.0.2.0/24`, `10.0.3.0/24`
- Serverless Containers with connectivity используют documented YC service subnet range `198.19.0.0/16`
- SYN packets к DB/Redis дропались SG, из-за чего app доходил до timeout и gateway отдавал `504`

После добавления SG-правил под `198.19.0.0/16` проблема полностью ушла.

### 4.3 Третий root cause: Redis stale connection reuse

После того как infra-path был починен, осталось intermittent поведение:

- быстрый `503`
- `database healthy`
- `redis unhealthy`
- ошибка вида `the handler is closed`

Это уже было не infra и не DNS, а проблема reuse мертвого Redis connection в singleton/pool.

После изменений в:

- [shared/redis_client.py](C:/Users/Имярек/Downloads/restobot-main/shared/redis_client.py)
- [shared/app_factory.py](C:/Users/Имярек/Downloads/restobot-main/shared/app_factory.py)

и после сборки/выкатки новых образов проблема ушла.

## 5. Финальное подтвержденное рабочее состояние

Текущее рабочее состояние:

- `admin_api`: `python -m apps.admin_api.main`
- `public_api`: `python -m apps.public_api.main`
- `connectivity ON` для `admin_api` и `public_api`
- runtime SA имеет `vpc.user`
- PostgreSQL `serverless=true`
- SG пропускает `198.19.0.0/16` на `6432/6379/6380`

Проверка `/health` после финального fix:

### Request 1

```json
{
  "status": "ok",
  "database": {
    "session": {
      "status": "healthy"
    },
    "pool": {
      "status": "healthy",
      "pool": {
        "size": 1,
        "idle": 1
      }
    }
  },
  "redis": {
    "status": "healthy"
  },
  "version": "1.0.0",
  "environment": "production"
}
```

- `HTTP 200`
- `~2.8s` cold start

### Request 2

- `HTTP 200`
- `~1.66s`

### Request 3

- `HTTP 200`
- `~1.01s`

Вывод:

- root cause закрыт;
- обе зависимости healthy;
- `/health` стабильно возвращает `200`.

Дополнительно подтверждено после пересборки/выкатки новых образов:

- `/health x10` подряд:
  - все 10 ответов `200`
  - Redis healthy во всех 10 случаях
- `GET /widget/demo/menu` → `200`
- `POST /widget/demo/session` → `201`
- `GET /admin/` → `200`
- `GET /admin/demo/orders` без токена → `401`

Это означает:

- Redis reconnect fix реально применился;
- static admin files реально попали в новый образ;
- admin/public контуры в рабочем состоянии.

## 6. Что теперь считать baseline

Считать эталонным только это состояние:

- entrypoint через `python -m ...`
- `connectivity ON`
- `vpc.user` присутствует
- SG с `198.19.0.0/16` правилами присутствует
- `/health = 200`

Не откатываться к старому baseline `connectivity OFF`, кроме случаев отдельной controlled диагностики.

## 7. Следующий practical focus

Critical infra-debug завершен. Дальше логичный порядок:

1. Проверка tenant provisioning flow
2. Проверка order/payment flow
3. Проверка admin UI в браузере, если нужен визуальный smoke
4. Отдельно, если нужно, проверить `migration_runner`
5. Отдельно решить, когда выкатывать migration `005_add_admin_tables.py`

То есть следующий фокус уже не на сетевом path, а на functional verification.

## 8. Что не делать

- не откатывать SG rules для `198.19.0.0/16`, пока не найден другой документированный и проверенный механизм;
- не возвращать старые entrypoints `python scripts/run_admin.py` / `python scripts/run_public.py` для этого image;
- не тащить обратно Terraform к управлению MDB/Redis/Lockbox versions ради “чистоты”;
- не делать ручные `.tf` правки на VM как source of truth;
- не добавлять временные `allUsers`, forced labels, forced revision env;
- не трогать image tags без отдельной необходимости;
- не трогать `migration_runner`, если задача не про миграции.
- не терять `connectivity` блоки в `infra/yc/containers.tf` при следующих правках;
- не откатывать Redis reconnect fix в `shared/redis_client.py` / `shared/app_factory.py`.

## 9. Безопасность

В ходе deploy/debug цикла секреты и ключи уже засвечивались в операционном процессе. Их по-прежнему нужно считать скомпрометированными и ротировать отдельно.

Минимум под ротацию:

- DB password
- Redis password
- JWT secret
- Telegram token
- YooKassa secret
- SA/backend access keys, если они попадали в логи, временные файлы или shell history

## 10. Важные файлы для продолжения

- [shared/app_factory.py](C:/Users/Имярек/Downloads/restobot-main/shared/app_factory.py)
- [shared/database.py](C:/Users/Имярек/Downloads/restobot-main/shared/database.py)
- [shared/config.py](C:/Users/Имярек/Downloads/restobot-main/shared/config.py)
- [shared/redis_client.py](C:/Users/Имярек/Downloads/restobot-main/shared/redis_client.py)
- [scripts/run_admin.py](C:/Users/Имярек/Downloads/restobot-main/scripts/run_admin.py)
- [scripts/run_public.py](C:/Users/Имярек/Downloads/restobot-main/scripts/run_public.py)
- [infra/yc/containers.tf](C:/Users/Имярек/Downloads/restobot-main/infra/yc/containers.tf)
- [infra/yc/security-group-rules.tf](C:/Users/Имярек/Downloads/restobot-main/infra/yc/security-group-rules.tf)
- [infra/yc/service-account.tf](C:/Users/Имярек/Downloads/restobot-main/infra/yc/service-account.tf)
- [static/admin/index.html](C:/Users/Имярек/Downloads/restobot-main/static/admin/index.html)

## 11. Готовый стартовый текст для нового чата

```text
Используй HANDOFF.md как основной контекст.

Работаем в `C:\Users\Имярек\Downloads\restobot-main`, ветка `codex/yc-mvp-deploy`.
Working tree не clean. Не откатывай infra-изменения вслепую.

Главное:
- YC critical infra-debug уже завершен
- root cause /health 504 закрыт
- текущее рабочее состояние: connectivity ON + vpc.user + SG rules для 198.19.0.0/16 + entrypoint через python -m
- /health уже подтвержден как 200 и Redis fix после пересборки образов тоже подтвержден
- опорный коммит: d19d694

Сначала:
1. прочитай HANDOFF.md,
2. проверь `git status`,
3. подтверди наличие infra/yc/security-group-rules.tf, runtime_vpc_user и Redis reconnect fix,
4. только потом переходи к следующей functional/ops задаче.

Не делай:
- ручные .tf правки на VM
- allUsers invoker
- forced revision labels/env
- откат SG rules для 198.19.0.0/16
```
