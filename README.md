<div align="center">

# E-Commerce Backend

**Production-grade e-commerce backend API built with real-world engineering practices, designed under real constraints and trade-offs.**

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.121-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white)](https://redis.io)
[![Celery](https://img.shields.io/badge/Celery-5.5-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?logo=sqlalchemy&logoColor=white)](https://sqlalchemy.org)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![CI](https://github.com/anasmohamed05221/E-Commerce/actions/workflows/ci.yml/badge.svg)](https://github.com/anasmohamed05221/E-Commerce/actions)

</div>

---

## Live Demo

| | |
|---|---|
| **API** | https://ecommerce-api-25zx.onrender.com |
| **Docs (Swagger UI)** | https://ecommerce-api-25zx.onrender.com/docs |
| **Health** | https://ecommerce-api-25zx.onrender.com/health |

> Free tier instances spin down after inactivity, first request may take ~50 seconds to wake up.

---

Built as a deliberate learning exercise to practice backend engineering the way it works in real teams, not to follow a tutorial. The system was shaped iteratively as complexity grew, converging into a clean, layered architecture that keeps it maintainable, flexible, and scalable. It deals with real challenges such as race conditions, atomic transactions, token security, cache invalidation, and production deployment.

---

## Features

**👤 Auth & Identity**
- Email registration with 6-digit verification code (10-minute expiry)
- Login with short-lived JWT access tokens + long-lived refresh tokens
- Token rotation on every refresh: old token revoked, reuse rejected
- Two-step password change via email confirmation (confirm or deny)
- Time-limited, single-use password reset tokens
- Logout: single session or all devices at once
- Profile update (name, phone number) and self-deactivation

**🛍️ Shopping**
- Browse products with `category`, `min_price`, `max_price` filters and pagination
- View individual product details
- Manage cart: add, update quantity, remove items, or clear all
- Manage multiple delivery addresses with a default flag
- Place orders with COD payment and a selected address
- View paginated order history and individual order details
- Cancel eligible orders (PENDING status only)

**🔧 Admin**
- Full product and category CRUD
- View all orders across the platform with pagination
- Drive orders through the status lifecycle (PENDING → CONFIRMED → SHIPPED → COMPLETED)
- List all users and view individual profiles
- Deactivate and reactivate accounts
- Change user roles (promote to admin or demote back to customer)

---

## Engineering Highlights

> Decisions that shaped the system, and why they were made.

| | |
|---|---|
| ⚛️ **Atomic checkout** | Stock decrement, order creation, cart clear, and inventory log commit in one transaction. Any failure rolls everything back. No partial orders, no phantom stock. |
| 🔒 **Race conditions prevented at the DB level** | Checkout uses `SELECT FOR UPDATE` to lock the product row before reading stock. Two concurrent checkouts for the last unit cannot both succeed. |
| 🔄 **Token rotation with reuse detection** | On every refresh, the old token is revoked and a new pair issued. Presenting a revoked token is treated as a security event. |
| 🔀 **Full async data layer** | Entire stack runs on one event loop: async routes, async SQLAlchemy 2.0 (asyncpg), async Redis. Migrated as a dedicated refactor story before adding Stripe and Celery. |
| 🧪 **Test suite engineered for speed** | 413 tests in ~11s. Savepoint-based isolation, parallel execution via `pytest-xdist`, passwords pre-hashed once at module load. Was 194 tests in ~70s before optimization. |
| ⚙️ **Order status FSM** | `PENDING → CONFIRMED → SHIPPED → COMPLETED`. Skipping or reversing states raises a 409. Cancellation is a separate path with different rules per role. |
| 💰 **Price snapshots at purchase time** | `order_items.price_at_time` captures the price at checkout. Changing a product price never affects existing orders. |
| ⚡ **Redis for caching and rate limiting** | Cache-aside pattern with explicit invalidation on writes. Rate limiting counters shared across Gunicorn workers so limits cannot be bypassed. |
| 🖥️ **Structured logging with request tracing** | Every request logged as JSON with a unique request ID, status code, duration, and client IP. Stdout-only in production (12-Factor App). |
| 📋 **Inventory fully audited** | Every stock change logged in `inventory_changes` with a typed reason (`SALE`, `CANCELLATION`, `RESTOCK`, `ADJUSTMENT`, `RETURN`). Stock is never mutated silently. |
| 📬 **Async task queue** | Celery + Redis implements producer/broker/consumer separation. Slow jobs run off the request path with at-least-once delivery and JSON serialization. |

---

## System Design

```mermaid
flowchart TD
    Client([Client])

    subgraph Render App Container
        MW[Middleware\nlogging · rate limiting · CORS · request ID]
        Router[Router\nHTTP contract · status codes · DI]
        Schema[Schema\nPydantic validation · request parsing]
        Service[Service\nbusiness logic · auth · DB transactions]
        Model[Model\nasync SQLAlchemy 2.0 + asyncpg]
        Worker[Celery Worker]
    end

    subgraph Render Managed
        PG[(PostgreSQL)]
    end

    subgraph Upstash
        Redis[(Redis\ncache · rate limiter · broker)]
    end

    Client --> MW
    MW --> Redis
    MW --> Router --> Schema --> Service --> Model --> PG
    Service --> Redis
    Redis -->|broker| Worker
```

Hard rules enforced throughout:
- **Routers** never touch the database directly
- **Services** own all business logic and authorization checks, ownership is verified here, not in the router
- **Schemas** validate all input at the boundary: password strength, phone normalization (E.164 via libphonenumber), email format
- **Redis** is accessed from middleware (rate limiting) and services (caching), never from routers directly

---

## Auth System

Not a tutorial JWT setup. Every edge case is handled.

| Capability | Detail |
|---|---|
| Registration | Email + password, validated via Pydantic + phonenumbers |
| Email Verification | 6-digit code with 10-minute expiry |
| Login | Short-lived access token (15 min) + long-lived refresh token (7 days) |
| Token Rotation | Old refresh token revoked on every refresh, reuse is rejected |
| Token Storage | All tokens hashed with SHA-256 before DB write, plaintext never persists |
| Password Change | Two-step: pending hash stored, confirmation email sent, applied on confirm |
| Password Reset | Time-limited token (15 min), hashed in DB, single-use |
| Logout | Single device (revoke one token) or all devices (revoke all) |
| Account Deactivation | Soft delete, account disabled, all sessions revoked |
| RBAC | `CUSTOMER` and `ADMIN` roles enforced via FastAPI dependency injection |

---

## Data Model

```mermaid
erDiagram
    users {
        int id PK
        string email UK
        string role "CUSTOMER · ADMIN"
        bool is_active
        bool is_verified
    }

    refresh_tokens {
        int id PK
        int user_id FK
        string token_hash UK "SHA-256, never plaintext"
        bool revoked
        timestamp expires_at
    }

    addresses {
        int id PK
        int user_id FK
        bool is_default
    }

    categories {
        int id PK
        string name UK
    }

    products {
        int id PK
        int category_id FK
        decimal price
        int stock
    }

    cart_items {
        int id PK
        int user_id FK
        int product_id FK
        int quantity
    }

    orders {
        int id PK
        int user_id FK
        int address_id FK
        string status "FSM: PENDING → CONFIRMED → SHIPPED → COMPLETED"
        decimal total_amount
    }

    order_items {
        int id PK
        int order_id FK
        int product_id FK
        int quantity
        decimal price_at_time "snapshot at checkout"
    }

    inventory_changes {
        int id PK
        int product_id FK
        int change_amount
        string reason "SALE · CANCELLATION · RESTOCK · ADJUSTMENT · RETURN"
    }

    users ||--o{ refresh_tokens : "sessions"
    users ||--o{ addresses : "ships to"
    users ||--o{ cart_items : "has in cart"
    users ||--o{ orders : "places"
    addresses ||--o{ orders : "used in"
    categories ||--o{ products : "contains"
    products ||--o{ cart_items : "added to"
    products ||--o{ order_items : "purchased as"
    products ||--o{ inventory_changes : "tracked by"
    orders ||--o{ order_items : "contains"
```

**9 tables · 22 Alembic migrations**

---

## Test Suite

**413 tests**: unit, integration, API, and middleware layers, running against a real PostgreSQL database for Dev/Prod parity.

```
tests/
├── unit/           → FSM correctness, hashing, token generation, validation
├── integration/    → every service method tested directly against the DB
│                     auth · users · tokens · products · categories · cart
│                     checkout · orders · addresses · admin services
├── api/            → full HTTP layer: status codes, response schemas,
│                     auth enforcement, RBAC, ownership, edge cases
└── middleware/     → rate limiting, request ID propagation
```

The setup is engineered, not just functional:

- **Transactional isolation** : schema created once per session, each test runs in a savepoint that rolls back on completion. No DDL overhead per test.
- **Parallel execution** : `pytest-xdist` with filelock-guarded DDL. One worker creates the schema; all others reuse it concurrently.
- **Fully async fixtures** : all fixtures use `AsyncSession` with `pytest-asyncio`, matching the production data layer.
- **Connection isolation** : each test gets its own connection from the pool via the `connection` fixture; a `ROLLBACK` after each test returns it clean. No connection contamination between tests.
- **No bcrypt in fixtures** : passwords pre-hashed once at module load. JWT tokens generated directly without HTTP round-trips. Bcrypt cost is not paid on every test.
- **Worker-scoped emails** : fixture emails include the xdist worker ID, preventing unique-constraint collisions under parallel execution.

> Before optimization: 194 tests in ~70s, After: 413 tests in ~11s

---

## API Reference

**45 endpoints across 11 domains.** Full contracts documented in [`docs/API_Contracts/`](docs/API_Contracts/) as Markdown files, one file per domain, covering request/response schemas, status codes, auth requirements, and edge cases.

Domains: `auth` · `users` · `addresses` · `products` · `categories` · `cart` · `orders` · `admin/products` · `admin/categories` · `admin/orders` · `admin/users`

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI + Uvicorn |
| Database | PostgreSQL + async SQLAlchemy 2.0 (asyncpg) + Alembic |
| Cache & Broker | Upstash Redis (async, cache-aside pattern, write-through invalidation; also Celery broker + result backend) |
| Task Queue | Celery 5.5 + Upstash Redis (broker + result backend), JSON serializer, at-least-once delivery |
| Auth | python-jose (JWT) + passlib (bcrypt) + SHA-256 token hashing |
| Validation | Pydantic v2 + email-validator + phonenumbers (E.164) |
| Rate Limiting | SlowAPI is Redis-backed, multi-worker safe |
| Email | SMTP via Celery task (3-retry, 60s countdown) |
| Logging | Structured JSON · rotating file handlers · request ID tracing |
| Containerization | Docker · docker-compose (local multi-service parity) |
| Testing | pytest + pytest-asyncio + httpx + pytest-xdist |
| CI/CD | GitHub Actions CI · Render (web + Celery worker in same container, auto-deploy from main) |
| Linting | Ruff |

---

## Quick Start

**Option 1: Docker (recommended, no local Postgres/Redis needed)**

```bash
git clone https://github.com/anasmohamed05221/E-Commerce.git
cd E-Commerce
docker-compose up --build
```

App runs at `http://localhost:8000`. Migrations run automatically on startup. The `worker` service starts automatically alongside the app.

**Running the Celery worker locally (without Docker)**

```bash
celery -A core.celery_app worker --loglevel=info
```

> Tests do not require a running worker. `CELERY_TASK_ALWAYS_EAGER=True` is set in the test environment, so tasks execute inline without touching the broker.

**Option 2: Local**

> **Prerequisites:** PostgreSQL and Redis must be running locally.

```bash
git clone https://github.com/anasmohamed05221/E-Commerce.git
cd E-Commerce
cp .env.example .env        # fill in DATABASE_URL, SECRET_KEY, REDIS_URL, MAIL_*
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload
```

**Seeding an admin user (both options)**

Linux / macOS:

```bash
SEED_ADMIN_EMAIL=admin@example.com \
SEED_ADMIN_PASSWORD=yourpassword \
SEED_ADMIN_FIRST_NAME=Admin \
SEED_ADMIN_LAST_NAME=User \
python -m scripts.seed_admin
```

Windows PowerShell:

```powershell
$env:SEED_ADMIN_EMAIL="admin@example.com"
$env:SEED_ADMIN_PASSWORD="yourpassword"
$env:SEED_ADMIN_FIRST_NAME="Admin"
$env:SEED_ADMIN_LAST_NAME="User"
python -m scripts.seed_admin
```

---

## Roadmap

**Epic 1: MVP** ✅ shipped · ✅ deployed
- [x] Full auth pipeline with token rotation and two-step password change
- [x] Product catalog with category filtering, price filters, and Redis caching
- [x] Paginated responses on all list endpoints
- [x] Cart, checkout (atomic + SELECT FOR UPDATE), order lifecycle
- [x] Address management with ownership enforcement
- [x] Admin: product CRUD, order status FSM, user management
- [x] RBAC, rate limiting, structured logging, health checks
- [x] 413 tests · GitHub Actions CI
- [x] Dockerized: Dockerfile, docker-compose, entrypoint.sh
- [x] Deployed to Render (web + managed PostgreSQL + Celery worker co-located) + Upstash Redis, HTTPS, auto-deploy from main

**Async SQLAlchemy Migration** ✅ shipped
- [x] Full data access layer migrated to async SQLAlchemy 2.0 (`create_async_engine`, `AsyncSession`, `select()` API)
- [x] All service methods async, all routes back to `async def`, explicit `selectinload`/`joinedload`
- [x] Alembic env.py, all test fixtures and conftest converted to async equivalents

**Planned**
- Stripe payments + webhooks, Celery task queue, order confirmation emails, coupons
- OAuth login, reviews and ratings, wishlist, shipment tracking, in-app notifications
- Typesense product search with filters and typo tolerance
- AWS deployment (EC2 + RDS + Upstash Redis) as a cloud learning exercise
- Monitoring, admin dashboard, reports

<details>
<summary>Full roadmap breakdown</summary>

**Epic 2: Payments & Background Jobs**
- [ ] Stripe integration (checkout session + webhooks)
- [x] Celery + Upstash Redis task queue infrastructure (worker co-located in Render container)
- [x] Move emails to Celery (verification, password reset, password change)
- [ ] Order confirmation email on payment
- [ ] Coupons and promo codes (fixed + percentage discounts, expiry, min order value)
- [ ] Coupon management (admin: create, disable, list)
- [ ] Smart Cart Insight Engine: rule-based backend service that analyzes the cart in real time and returns max 3 prioritized insights (free shipping nudge, bundle suggestion, cheaper alternative, coupon hint) alongside the cart response. All four rules are backed by real data via a `product_relationships` table (`BUNDLE` / `ALTERNATIVE`). Capstone story for Epic 2.

**Epic 3: Engagement & Fulfillment**
- [ ] OAuth login (Google / Apple / Facebook)
- [ ] Shipment & delivery simulation with order tracking
- [ ] Wishlist (add / remove / move to cart)
- [ ] Reviews and ratings (purchased-only constraint, auto-updated product avg)
- [ ] Review moderation (admin: approve, hide, delete)
- [ ] In-app notifications (order status changes)

**Epic 4: Search**
- [ ] Typesense product search with filters, typo tolerance, and ranking

**Epic 5: DevOps & Platform Improvements**
- [ ] AWS deployment (EC2 + RDS + Upstash Redis). Real cloud skills, 12-month free tier
- [ ] Monitoring and observability (log aggregation, error tracking)
- [ ] Admin dashboard: revenue, orders, top products, new users (charts)
- [ ] Reports: sales by period, revenue by category, return rates
- [ ] Hierarchical categories
- [ ] SEO slugs for product/category pages
- [ ] CSRF protection

</details>

---

<div align="center">

**Built by [Anas Mohamed](https://github.com/anasmohamed05221)**

*Learning backend engineering by building, not by watching.*

</div>
