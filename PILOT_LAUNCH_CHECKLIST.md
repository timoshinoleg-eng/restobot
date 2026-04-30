# Pilot Launch Checklist

Дата: 2026-04-30
Статус: MVP draft

## 1. Инфраструктура

- Terraform применён для `infra/yc` без ручных правок в консоли.
- Контейнеры `admin` и `public` опубликованы с актуальными image refs.
- Выполнен `python scripts/migrate_cloud.py`.
- `/health` на gateway отвечает успешно.
- Redis и PostgreSQL доступны из контейнеров.

## 2. Безопасность запуска

- `ENABLE_BOOTSTRAP_API=true` включён только на время bootstrap/smoke.
- `BOOTSTRAP_API_TOKEN` задан и хранится вне репозитория.
- После seed/smoke bootstrap API выключен и конфигурация применена повторно.
- В логах нет 500 на pilot path.

## 3. Demo / pilot data

- Создан tenant для пилота или demo: `python scripts/seed_demo_tenant.py --tenant-id <slug>`.
- Меню загружено по шаблону [MENU_UPLOAD_TEMPLATE.json](<C:/Users/Имярек/Downloads/restobot-main/MENU_UPLOAD_TEMPLATE.json>).
- Есть хотя бы один тестовый пользователь через widget session.
- Есть хотя бы один тестовый заказ со сменой статуса.

## 4. Операционный прогон

- Выполнен smoke:
  `python scripts/smoke_cloud.py --gateway-url <gateway-url> --tenant-id <slug> --bootstrap-token <token>`
- Проверены шаги `onboarding -> menu -> session -> order -> status update`.
- Проверено, что админ видит список заказов.
- Проверено, что клиент видит актуальный статус заказа.

## 5. Коммерческая готовность

- CTA ведёт в Telegram.
- Оффер ограничен пилотным сценарием и первым бесплатным месяцем.
- Клиенту не обещаны POS, booking, loyalty или full automation в текущем пилоте.
