# RestoBot Sprint Execution Plan

Дата: 2026-04-29
Горизонт: 14 дней
Режим: fast MVP / pilot-first

## 1. Цель спринта

Собрать минимально продаваемый и технически работоспособный MVP `RestoBot`, одновременно:

- готовый к первому пилоту;
- готовый к публичной презентации на `chatbot24.su`;
- не перегруженный функциями;
- не откатывающий уже сделанный cloud/security фундамент.

## 2. Роли

### Codex

Отвечает за:

- MVP scope;
- backlog;
- интеграцию изменений в `restobot`;
- технические решения;
- приёмку материалов от внешних сервисов;
- финальную сборку спринта.

### Deep Research

Отвечает за:

- внешний рынок;
- прямых и смежных конкурентов;
- JTBD и buyer analysis;
- pricing/offer/CTA guidance;
- market framing around `152-ФЗ`.

### Swarm

Отвечает за:

- landing drafts;
- sales collateral drafts;
- onboarding/checklist drafts;
- extraction полезного из menu-module.

## 3. Календарный план

### Days 1-2

Codex:

- зафиксировать MVP scope;
- собрать backlog;
- подготовить execution plan;
- продолжить технический baseline в `restobot`.

Deep Research:

- выполнить restaurant-specific competitor/JTBD/GTM research.

Swarm:

- подготовить варианты лендинга;
- подготовить sales/FAQ/demoscript drafts.

### Days 3-5

Codex:

- принять и отфильтровать выводы Deep Research;
- принять и отфильтровать материалы Swarm;
- собрать final positioning baseline;
- продолжить backend/product path для demo tenant.

Swarm:

- доработать drafts по замечаниям;
- подготовить onboarding/checklist/menu template materials.

### Days 6-9

Codex:

- довести pilot path в `restobot`;
- подготовить demo tenant;
- синхронизировать product обещания и реальные функции;
- сформировать landing brief final.

### Days 10-12

Codex:

- подготовить финальную структуру страницы;
- собрать operator flow;
- проверить demo path;
- подготовить pilot launch package.

### Days 13-14

Codex:

- провести финальную сверку:
  - сайт
  - оффер
  - deploy
  - smoke
  - demo tenant
- принять решение: pilot ready / not ready.

## 4. Входные и выходные артефакты

### Ожидается от Deep Research

- `RESTOBOT_COMPETITOR_MAP.md`
- `RESTOBOT_JTBD_AND_BUYER.md`
- `RESTOBOT_GTM_RECOMMENDATION.md`

### Ожидается от Swarm

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

### Формируется у Codex

- `MVP_SCOPE.md`
- `SPRINT_BACKLOG.md`
- `SPRINT_EXECUTION_PLAN.md`
- далее:
  - `POSITIONING_FINAL.md`
  - `LANDING_BRIEF_FINAL.md`
  - repo changes in `restobot`

## 5. Правила принятия внешних артефактов

### Deep Research

Принимать только:

- подтверждённые данные или явно маркированные assumptions;
- restaurant-specific выводы;
- конкретные рекомендации по pricing/CTA/offer.

Не принимать как final:

- слишком общий chatbot-market analysis;
- абстрактные AI positioning statements без restaurant fit.

### Swarm

Принимать только:

- тексты, не обещающие лишнего;
- drafts, работающие для Telegram-first restaurant offer;
- материалы, пригодные для жёсткой редакции.

Не принимать как final:

- enterprise-heavy messaging;
- feature creep;
- product claims без backend support.

## 6. Решения, которые принимает только Codex

- финальный MVP scope;
- что реально входит в первый пилот;
- что переносить из внешнего menu-module;
- какие backend-изменения делать в `restobot`;
- что можно обещать на сайте;
- готов ли проект к публичному pilot launch.

## 7. Критерии завершения спринта

Спринт считается успешным, если:

- есть финальный оффер `RestoBot`;
- есть готовая структура/контент страницы для `chatbot24.su`;
- есть работающий demo tenant;
- deploy path в YC воспроизводим;
- smoke path проходит;
- Telegram lead flow понятен;
- pilot launch может быть выполнен без импровизации.

## 8. Следующий immediate step

После получения внешних артефактов:

1. собрать `POSITIONING_FINAL.md`;
2. собрать `LANDING_BRIEF_FINAL.md`;
3. принять решение по menu-domain adaptation backlog;
4. довести pilot package до готовности.

