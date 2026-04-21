# RestoBot 🤖🍽️

**AI-powered restaurant bot for Telegram and Max messenger.**
Built on Yandex Cloud, compliant with 152-ФЗ, ready for SMB restaurants.

## Features

- 🤖 **AI Recommendations** — YandexGPT-powered menu suggestions
- 📋 **Order Management** — Delivery, pickup, dine-in, pre-order
- 💳 **Payments** — ЮKassa integration with fiscal receipts (54-ФЗ)
- 🎁 **Loyalty Program** — Bonus points, referrals, promotions
- 📅 **Table Booking** — Restaurant reservation system
- 🔒 **152-ФЗ Compliance** — Auto-generated privacy policy, RLS, audit trails
- 🏢 **Multi-tenant** — Schema-per-tenant architecture
- 🇷🇺 **Russian Infrastructure** — All data stays in Yandex Cloud (ru-central1)

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/restobot/restobot.git
cd restobot
cp .env.example .env
# Edit .env with your credentials

# 2. Start infrastructure
docker-compose up -d postgres redis

# 3. Run migrations
poetry run alembic upgrade head

# 4. Start services
docker-compose up -d
```

## Architecture

```
┌─ Telegram / Max ──┐    ┌─ Yandex API Gateway ─┐    ┌─ YC MK8s ───┐
│                   │───▶│                      │───▶│  Bot API     │
│  User             │    │  Rate limiting       │    │  Admin API   │
│                   │    │  JWT validation      │    │  AI Service  │
└───────────────────┘    └──────────────────────┘    │  Payment     │
                                                     └──────┬───────┘
                                                            │
┌─ Data Layer ──────────────────────────────────────────────┘
│  PostgreSQL 15 + pgvector (Managed)
│  Redis 7 (Managed)
│  Object Storage (S3)
│  Message Queue (YMQ)
└───────────────────────────────────────────────────────────
```

## API Documentation

OpenAPI 3.1 spec available at `/api/v1/docs` when running.

Key endpoints:
- `POST /api/v1/{tenant}/menu/ai-recommend` — AI recommendation
- `POST /api/v1/{tenant}/orders` — Create order
- `POST /api/v1/{tenant}/payments/yookassa` — Initialize payment
- `POST /api/v1/{tenant}/loyalty/apply` — Apply loyalty points

## Compliance

- ✅ 152-ФЗ — all 15 requirements automated
- ✅ 54-ФЗ — fiscal receipts via ЮKassa
- ✅ Privacy policy — auto-generated per tenant
- ✅ RKN notification — auto-filled JSON/XML
- ✅ Right to be forgotten — 1-click deletion
- ✅ Audit trails — all PDN changes logged

## Pricing

| Plan | Price | Features |
|------|-------|----------|
| Start | 2 990 ₽/мес | 100 menu items, 5 staff, basic loyalty |
| Pro | 4 990 ₽/мес | 500 items, AI recommendations, delivery |
| Enterprise | 9 990 ₽/мес | 2000 items, full features, priority support |

## Tech Stack

- **Python 3.11+**
- **FastAPI** — API framework
- **aiogram 3.x** — Telegram bot
- **SQLAlchemy 2.0 + asyncpg** — Database
- **YandexGPT** — AI/LLM
- **pgvector** — Vector search
- **Redis** — Cache & sessions
- **ЮKassa** — Payments
- **Docker + Docker Compose**

## License

MIT © RestoBot Team
