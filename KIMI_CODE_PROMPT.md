# Kimi Code Prompt — RestoBot Code Review & Improvement

## Project Overview

**RestoBot** — SaaS Telegram/Max messenger bot for restaurants with AI recommendations, payments, and 152-ФЗ compliance.

**Stack:** Python 3.11+, FastAPI, aiogram 3.x, SQLAlchemy 2.0, asyncpg, YandexGPT, pgvector, Redis, YooKassa, Docker

**Architecture:** 5 microservices (WebApp, Bot API, Admin API, AI Service, Payment Worker), schema-per-tenant PostgreSQL with RLS

**Repository:** https://github.com/[YOUR_USERNAME]/restobot

---

## Your Task

Perform comprehensive code review and improvement of the RestoBot codebase. Focus on production readiness.

### 1. Type Safety (HIGH PRIORITY)
- Run `mypy --strict` on all Python files
- Fix all type errors
- Add missing type hints (return types, Optional, Union, generics)
- Ensure Pydantic models have proper types
- Check async function signatures

### 2. Error Handling (HIGH PRIORITY)
- Add try/except blocks where missing
- Implement circuit breaker for YandexGPT API calls
- Add retry logic with exponential backoff for external APIs
- Handle database connection failures gracefully
- Add proper HTTP exception handling in FastAPI routes
- Implement graceful shutdown for all services

### 3. Security (CRITICAL)
- **SQL Injection:** Verify all SQL queries use parameterized queries (NOT string formatting)
- **JWT:** Check JWT secret strength, expiration handling, algorithm security
- **Input Validation:** Add stricter Pydantic validators (phone format, email, price > 0)
- **Secrets:** Ensure no hardcoded secrets in code
- **Headers:** Add security headers (CORS, CSP, HSTS)
- **Rate Limiting:** Add rate limiting for API endpoints

### 4. Performance (MEDIUM)
- Optimize SQL queries (add indexes, reduce N+1)
- Add Redis caching for frequently accessed data
- Implement connection pooling optimization
- Add query result caching for AI recommendations
- Profile slow endpoints

### 5. Testing (HIGH PRIORITY)
- Expand test coverage to > 80%
- Add tests for:
  - AI recommendation engine (mock YandexGPT)
  - Payment webhook handling
  - Order validation rules
  - Compliance document generation
  - Database RLS isolation
- Add integration tests for API endpoints
- Add async test fixtures

### 6. Best Practices (MEDIUM)
- Run `black --check` and `isort --check`
- Fix PEP 8 violations
- Add docstrings to all public functions
- Add logging (structured with structlog)
- Add metrics (Prometheus counters for orders, payments, AI calls)
- Implement health checks for all services

### 7. Specific Files to Review

#### `bot/main.py`
- [ ] Add error handling for webhook setup
- [ ] Implement user session management
- [ ] Add rate limiting for bot commands
- [ ] Handle Telegram API errors gracefully

#### `api/routes/orders.py`
- [ ] Fix SQL injection risk (check f-string queries)
- [ ] Add transaction wrapping for order creation
- [ ] Implement idempotency keys for payments
- [ ] Add order status state machine validation

#### `ai/rag_engine.py`
- [ ] Add circuit breaker for YandexGPT
- [ ] Implement embedding cache
- [ ] Add query timeout handling
- [ ] Improve fallback engine with more categories

#### `payments/worker.py`
- [ ] Add idempotency for payment creation
- [ ] Implement payment status polling fallback
- [ ] Add retry for failed webhooks
- [ ] Handle ЮKassa API errors

#### `shared/database.py`
- [ ] Add connection retry logic
- [ ] Implement connection health checks
- [ ] Add query timeout

### 8. Deliverables

1. **Report:** List all found issues with severity (HIGH/MEDIUM/LOW)
2. **Fixed Code:** Provide improved versions of files
3. **Test Results:** Show `pytest` output with coverage
4. **Lint Results:** Show `mypy`, `black`, `isort` output
5. **Security Check:** Confirm no SQL injection, secure JWT

### 9. Constraints
- Do NOT change architecture (keep 5 microservices)
- Do NOT add new dependencies without justification
- Do NOT break existing API contracts
- Keep Python 3.11+ compatibility
- Maintain async/await patterns

### 10. Success Criteria
```
[ ] mypy --strict passes with 0 errors
[ ] black --check passes
[ ] pytest passes with > 80% coverage
[ ] No SQL injection vulnerabilities (bandit scan)
[ ] JWT handling is secure (jwt.io verification)
[ ] All external APIs have timeout + retry
[ ] Graceful shutdown implemented
[ ] Structured logging added
```

---

## Running the Project Locally

```bash
# Setup
cd restobot
cp .env.example .env
# Edit .env with test values

# Install dependencies
poetry install

# Run tests
poetry run pytest --cov=restobot --cov-report=html

# Run linting
poetry run mypy --strict restobot
poetry run black --check restobot
poetry run isort --check restobot
poetry run bandit -r restobot
```

---

## Questions?

If blocked on any issue, document it and move on. Return a detailed report of what was found, what was fixed, and what remains TODO.

**Expected output format:**
1. Executive Summary (3-5 bullet points)
2. Critical Issues Found (with file:line references)
3. What Was Fixed (file + description)
4. Test Results (coverage %, pass/fail)
5. Remaining TODOs (prioritized)
6. Recommendations for Next Steps
