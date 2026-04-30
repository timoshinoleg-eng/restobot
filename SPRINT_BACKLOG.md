# RestoBot Sprint Backlog

Дата: 2026-04-29
Спринт: 2 недели
Владелец сборки: Codex

## 1. Must

### Product / GTM

- [ ] Подготовить и утвердить вторую страницу `RestoBot` на `chatbot24.su`
- [ ] Зафиксировать Telegram как единственный канал входящих заявок
- [ ] Подготовить offer: `первый месяц бесплатно`
- [ ] Подготовить короткий demo pitch для первых пилотных клиентов

### Backend / Platform

- [ ] Довести flow `onboarding -> menu upload -> widget session -> order -> status update`
- [ ] Подготовить один demo tenant с demo menu
- [ ] Подтвердить deploy path в Yandex Cloud
- [ ] Подтвердить smoke path после deploy
- [ ] Закрыть pilot-level blockers по security/runtime, не откатывая уже сделанный hardening

### Operations

- [ ] Описать минимальный manual operator flow
- [ ] Подготовить pilot launch checklist
- [ ] Подготовить customer onboarding checklist

## 2. Should

### Product

- [ ] Упростить и нормализовать menu-model под MVP
- [ ] Подготовить JSON template для загрузки меню
- [ ] Подготовить FAQ и objection handling для сайта и диалогов

### Engineering

- [ ] Выделить из внешнего menu-module только MVP-полезные сущности и правила
- [ ] Подготовить adaptation backlog для menu-domain в текущую архитектуру `restobot`
- [ ] Добавить дополнительные negative checks для pilot path

### GTM

- [ ] Подготовить финальный messaging по `152-ФЗ`
- [ ] Подготовить Telegram CTA flow
- [ ] Подготовить demo script для созвона/переписки

## 3. Later

- [ ] Полная интеграция внешнего menu-module
- [ ] Полноценный aiogram menu-FSM
- [ ] Variants / modifiers / dietary tags как развитый продуктовый слой
- [ ] YandexGPT описания блюд
- [ ] Booking / waiter call / inventory / analytics
- [ ] Full production hardening beyond pilot scope

## 4. Владельцы

### Codex

- MVP scope and execution
- real `restobot` repo changes
- deploy/smoke path
- integration decisions
- final acceptance of external artifacts

### Deep Research

- restaurant competitor map
- JTBD / buyer analysis
- pricing / offer / CTA validation
- 152-ФЗ positioning guidance

### Swarm

- landing drafts
- sales materials
- onboarding checklists drafts
- menu-module MVP extraction

## 5. Blockers to watch

- результаты Deep Research могут изменить messaging, но не должны ломать MVP scope;
- результаты Swarm могут раздувать функциональность — использовать только после фильтрации;
- menu-domain интеграция не должна затормозить deployable pilot;
- сайт и продукт должны обещать только то, что можно показать в demo tenant.

