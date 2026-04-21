# compliance/documents.py
"""Auto-generation of compliance documents (152-FZ)."""

import hashlib
from datetime import datetime
from string import Template
from typing import Optional

from shared.config import get_settings

settings = get_settings()


PRIVACY_POLICY_TEMPLATE = Template("""
ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ

1. Оператор персональных данных:
   Название: $company_name
   ИНН: $inn
   ОГРН/ОГРНИП: $ogrn
   Адрес: $legal_address
   Email: $email
   Телефон: $phone

2. Цели обработки ПДн:
   - Обработка заказов и доставки
   - Бонусная программа лояльности
   - Уведомления о статусе заказа
   - Маркетинговые рассылки (только с согласия)

3. Категории ПДн:
   - ФИО
   - Телефон
   - Адрес доставки
   - Email
   - История заказов
   - Бонусные баллы

4. Правовые основания:
   - Согласие субъекта ПДн (ст. 9 152-ФЗ)
   - Договор (ст. 6 152-ФЗ)
   - Законодательство РФ (ст. 6)

5. Сроки хранения:
   - Заказы: 5 лет
   - ПДн клиентов: до отзыва согласия + 30 дней
   - Аудит-логи: 3 года

6. Права субъекта ПДн:
   - Право на доступ (ст. 14)
   - Право на исправление (ст. 14)
   - Право на удаление (ст. 14) — заявка через бота
   - Право на отзыв согласия (ст. 9)

7. Передача третьим лицам:
   - ЮKassa — обработка платежей
   - Yandex Cloud — хостинг (серверы в РФ)
   - Telegram/Max — только ID пользователя

8. Контакты: $contact_info

Дата: $generated_at
Версия: $version
""")


def generate_privacy_policy(tenant: dict) -> str:
    """Auto-generate privacy policy for tenant."""
    return PRIVACY_POLICY_TEMPLATE.substitute(
        company_name=tenant.get("name", "[НАЗВАНИЕ]"),
        inn=tenant.get("inn", "[УКАЖИТЕ ИНН]"),
        ogrn=tenant.get("ogrn", "[УКАЖИТЕ ОГРН/ОГРНИП]"),
        legal_address=tenant.get("legal_address", "[УКАЖИТЕ АДРЕС]"),
        email=tenant.get("email", "[УКАЖИТЕ EMAIL]"),
        phone=tenant.get("phone", "[УКАЖИТЕ ТЕЛЕФОН]"),
        contact_info=f"Email: {tenant.get('email', '[УКАЖИТЕ]')}",
        generated_at=datetime.now().isoformat(),
        version="1.0"
    )


def generate_consent_text(version: int = 1) -> str:
    """Generate consent text for personal data processing."""
    text = f"""
СОГЛАСИЕ НА ОБРАБОТКУ ПЕРСОНАЛЬНЫХ ДАННЫХ (версия {version})

Я даю согласие на обработку моих персональных данных:
- ФИО
- Телефон
- Адрес доставки
- Email

Цели обработки:
1. Оформление и доставка заказов
2. Участие в бонусной программе
3. Уведомления о статусе заказа

Я ознакомлен(а) с Политикой конфиденциальности и понимаю,
что могу отозвать согласие в любой момент через бота.

Дата: {datetime.now().isoformat()}
"""
    return text.strip()


def hash_consent(text: str) -> str:
    """Generate SHA256 hash of consent text for integrity proof."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def generate_rkn_notification_json(tenant: dict) -> dict:
    """Generate JSON for RKN notification (rkn.gov.ru)."""
    return {
        "operator": {
            "name": tenant.get("name", ""),
            "inn": tenant.get("inn", ""),
            "ogrn": tenant.get("ogrn", ""),
            "address": tenant.get("legal_address", ""),
            "email": tenant.get("email", ""),
            "phone": tenant.get("phone", "")
        },
        "dpo": {
            "name": tenant.get("dpo_name", "[УКАЖИТЕ]"),
            "email": tenant.get("dpo_email", "[УКАЖИТЕ]")
        },
        "processing": {
            "purposes": ["order_processing", "delivery", "loyalty"],
            "data_categories": ["full_name", "phone", "address", "email"],
            "cross_border": False,
            "servers_location": "Russian Federation"
        },
        "generated_at": datetime.now().isoformat()
    }
