# RestoBot Handoff Packet

Дата: 2026-04-29
Назначение: стартовый контекст для нового чата / нового исполнителя без потери текущего состояния

## 1. Проект

- Проект: `RestoBot`
- Репозиторий: `restobot`
- Рабочая ветка: `codex/yc-mvp-deploy`
- Основной сайт: `chatbot24.su`
- Новое направление: Telegram-first SaaS для ресторанов / кафе / доставки
- Канал заявок: Telegram
- Цель: быстро собрать коммерческий MVP и подготовить пилот

## 2. Общая рамка

Текущий приоритет:

1. вывести `RestoBot` на пилотный MVP;
2. подготовить вторую страницу/оффер на `chatbot24.su`;
3. не раздувать scope;
4. не откатывать уже сделанный cloud/security фундамент.

Подход:

- pilot-first;
- минимально достаточный продуктовый контур;
- Telegram-first lead flow;
- российский cloud-контур;
- первый месяц бесплатно как входной offer.

## 3. Что уже сделано в репозитории

### 3.1 Cloud / Infra / Deploy

Уже добавлены или изменены:

- Terraform stack для Yandex Cloud:
  - Serverless Containers
  - API Gateway
  - Lockbox
  - Managed PostgreSQL
  - Managed Redis
  - Object Storage backend
- русские `README.md` и `DEPLOYMENT.md`
- bootstrap backend под Terraform state
- GitHub Actions deploy workflow
- migration runner
- smoke test script

### 3.2 Cloud app layer

Добавлены cloud entrypoint'ы:

- `apps/admin_api/main.py`
- `apps/public_api/main.py`

Legacy surface сохранён:

- `api/main.py`

### 3.3 Security / runtime hardening

Уже внесён пакет критичных правок:

- onboarding защищён;
- widget order endpoints требуют auth;
- публичное создание tenant schema из widget-flow убрано;
- webhook route добавлен;
- `.dockerignore` добавлен;
- Docker runtime переведён на non-root + no shell launch;
- request_id добавлен в 500 responses;
- Redis TLS / deploy hardening частично проведены.

### 3.4 Tests

Добавлены cloud-facing тесты:

- `tests/test_cloud_apps.py`

Локально проходили:

- cloud app tests;
- часть targeted pytest suites;
- compileall по изменённым Python-модулям.

## 4. Что сейчас в рабочем дереве

Важно: не всё ещё оформлено в коммит.

В рабочем дереве есть:

- незакоммиченные технические изменения по:
  - cloud/security/runtime/deploy
  - Redis TLS
  - immutable image flow
  - plan/apply hardening
  - bootstrap token flow
- незакоммиченные продуктовые документы спринта

Перед любым новым коммитом нужно:

1. осознанно разделить product docs и technical changes;
2. не потерять текущее состояние ветки;
3. не перетирать существующие правки без просмотра diff.

## 5. Продуктовые артефакты, уже подготовленные в текущем чате

Созданы:

- `MVP_SCOPE.md`
- `SPRINT_BACKLOG.md`
- `SPRINT_EXECUTION_PLAN.md`
- `POSITIONING_FINAL.md`
- `LANDING_BRIEF_FINAL.md`
- `HANDOFF.md`

### 5.1 Назначение файлов

`MVP_SCOPE.md`

- фиксирует продуктовую рамку пилота;
- определяет, что входит и не входит в MVP;
- задаёт definition of done.

`SPRINT_BACKLOG.md`

- backlog на 2 недели;
- приоритеты `must / should / later`;
- владельцы по потокам.

`SPRINT_EXECUTION_PLAN.md`

- execution plan на 14 дней;
- роли Codex / Deep Research / Swarm;
- ожидаемые артефакты;
- правила принятия внешних результатов.

`POSITIONING_FINAL.md`

- заготовка для финального позиционирования;
- будет заполнена после приёмки Deep Research.

`LANDING_BRIEF_FINAL.md`

- заготовка для финального брифа второй страницы;
- будет заполнена после приёмки Swarm и Deep Research.

## 6. Внешние сервисы и их роль

### 6.1 Kimi Deep Research

Уже запущен.

От него ожидаются:

- `RESTOBOT_COMPETITOR_MAP.md`
- `RESTOBOT_JTBD_AND_BUYER.md`
- `RESTOBOT_GTM_RECOMMENDATION.md`

Назначение:

- restaurant competitor map;
- JTBD / buyer analysis;
- offer / pricing / CTA guidance;
- `152-ФЗ` positioning guidance.

### 6.2 Kimi Swarm

Уже запущен.

От него ожидаются:

- `LANDING_VARIANT_A.md`
- `LANDING_VARIANT_B.md`
- `LANDING_VARIANT_C.md`
- `SALES_FAQ.md`
- `OBJECTION_HANDLING.md`
- `DEMO_SCRIPT.md`
- `CUSTOMER_ONBOARDING_CHECKLIST.md`
- `MENU_UPLOAD_TEMPLATE.json`
- `PILOT_LAUNCH_CHECKLIST.md`
- `MENU_MODULE_MVP_EXTRACTION.md`

Назначение:

- landing drafts;
- sales materials;
- onboarding drafts;
- extraction полезного из внешнего menu-module.

## 7. Внешний menu-module от Swarm

Был отдельно изучен пакет файлов из каталога:

- `C:\Users\Имярек\Downloads\Kimi_Agent_Создание модуля Рестобот\...`

Ключевой вывод:

- это не готовый merge-ready модуль;
- это хорошо проработанный доменный проект `menu` под другую архитектурную раскладку;
- полезен как reference/backlog source;
- не должен интегрироваться целиком в `restobot` без адаптации.

Главные замечания:

- `router.py` — скелет с `...`, не рабочая реализация;
- `menu_handlers.py` вызывает методы, которых нет в `service.py`;
- тесты частично демонстрационные и не доказывают production readiness;
- архитектура ориентирована на `app/modules/menu/*`, которой в реальном `restobot` нет.

Практический вывод:

- брать только MVP-полезные сущности и business rules;
- не тащить весь модуль как есть.

## 8. Текущее MVP-решение

Рабочий MVP scope уже зафиксирован.

В MVP входят:

- onboarding ресторана;
- загрузка меню;
- просмотр меню;
- создание заказа;
- обновление статуса заказа;
- demo tenant;
- smoke after deploy;
- Telegram CTA.

В MVP не входят:

- variants/modifiers как развитый продуктовый слой;
- AI-описания;
- booking;
- waiter call;
- склад;
- сложная аналитика;
- полный aiogram catalog UX.

## 9. Текущее состояние исследований

Было отдельно изучено исследование:

- `OPERATION_ MARKET BREACH — Board-Level Intelligence Brief.docx`

Вывод:

- как общий chatbot SaaS market baseline — полезно;
- для `RestoBot` как restaurant-specific GTM — недостаточно;
- нужен не полный перезапуск, а узкий дополнительный deep research round по ресторанной вертикали.

Предварительно признанные ближайшие конкуренты:

- `ChatFood`
- `CafeBotum`
- `Smartbot Pro`

На дополнительной проверке:

- `Nyambot`
- `BorisBot` как adjacent competitor

## 10. Что нужно делать дальше

Следующий шаг после открытия нового чата:

1. восстановить рабочую картину по `HANDOFF.md`;
2. принять артефакты `Deep Research`;
3. принять артефакты `Swarm`;
4. заполнить:
   - `POSITIONING_FINAL.md`
   - `LANDING_BRIEF_FINAL.md`
5. после этого продолжить:
   - продуктовую сборку второй страницы;
   - технический фронт `restobot`;
   - при необходимости подготовку коммита/пуша.

## 11. Приоритетный порядок продолжения

### Шаг 1

Принять и отфильтровать `Deep Research`.

Нужен результат:

- финальное позиционирование;
- direct competitors;
- buyer/JTBD clarity;
- pricing/offer/CTA guidance.

### Шаг 2

Принять и отфильтровать `Swarm`.

Нужен результат:

- usable landing drafts;
- FAQ / objections;
- onboarding materials;
- extraction по menu-module.

### Шаг 3

Заполнить `POSITIONING_FINAL.md`.

### Шаг 4

Заполнить `LANDING_BRIEF_FINAL.md`.

### Шаг 5

Только после этого принимать решения:

- по финальному контенту страницы;
- по интеграции menu-domain;
- по следующему пакету product/engineering tasks.

## 12. Что нельзя потерять

- не раздувать scope;
- не обещать на лендинге то, чего нет в demo tenant;
- не перетаскивать внешний menu-module целиком;
- не ломать уже сделанный cloud/security hardening;
- не забыть, что в рабочем дереве уже есть незакоммиченные технические правки.

## 13. Готовый стартовый текст для нового чата

Ниже текст, который можно вставить в новый чат вместе с этим файлом:

```text
Используй HANDOFF.md как основной стартовый контекст.

Работаем над RestoBot в репозитории `restobot`, ветка `codex/yc-mvp-deploy`.
Нужно продолжить без повторного общего анализа.

Сначала:
1. восстанови рабочую картину по HANDOFF.md,
2. зафиксируй, что уже сделано,
3. затем переходи к следующему активному шагу:
   приёмка артефактов Deep Research и Swarm,
   сборка final positioning и landing brief.
```

