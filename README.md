# FastAPI E-Commerce API

A production-oriented e-commerce backend built with FastAPI: full catalog and checkout, real Stripe payments and subscriptions, multi-currency pricing, loyalty points and gift cards, guest checkout, and a full observability stack (metrics, tracing, logs).

## Features

-   **Accounts & Auth**: JWT access/refresh tokens, Argon2 password hashing, email verification, password reset, TOTP-based MFA, and OAuth social login (Google, Facebook).
-   **Catalog**: products with variants, images, and brands; hierarchical categories; tax rates and shipping zones/methods; product Q&A; back-in-stock and price-drop email alerts; CSV bulk product import/export.
-   **Cart & Checkout**: persistent and guest carts, coupons, promotions, multi-currency display and checkout (base-currency accounting with live conversion), loyalty points, and gift cards / store credit — all stackable as checkout discounts.
-   **Orders**: full lifecycle (pending → paid → shipped → delivered), guest checkout with order tracking and later account-claiming, returns and admin-approved refunds, PDF invoices.
-   **Subscriptions**: recurring orders on a fixed interval, billed automatically off-session against a saved payment method, with pause/resume/skip and dunning on failed renewals.
-   **Payments**: Stripe PaymentIntents and webhooks, saved payment methods, idempotency keys on payment-creating requests.
-   **Admin**: sales/inventory analytics, audit log, order and return management, coupon/promotion/currency/gift-card administration.
-   **Search**: Elasticsearch-backed product search.
-   **Background jobs**: an ARQ worker handles subscription renewals, abandoned-cart recovery emails, back-in-stock/price-drop notifications, and inventory-reservation cleanup.
-   **Reliability**: the outbox pattern for reliably publishing domain events, row-level locking on stock reservations, rate limiting, and security-header middleware.
-   **Observability**: structured JSON request logging (Loguru), OpenTelemetry tracing, and Prometheus metrics — see [Docker Support](#docker-support) for the full stack.
-   **Testing**: the suite runs against a real, ephemeral PostgreSQL container (via testcontainers) rather than SQLite, so it exercises the same database engine as production.

## Tech Stack

-   **Framework**: [FastAPI](https://fastapi.tiangolo.com/)
-   **Language**: Python 3.10+
-   **Database**: PostgreSQL, via [SQLAlchemy](https://www.sqlalchemy.org/) 2.x and [Alembic](https://alembic.sqlalchemy.org/) migrations
-   **Cache / Background jobs**: Redis, [ARQ](https://arq-docs.helpmanual.io/)
-   **Search**: Elasticsearch
-   **Payments**: [Stripe](https://stripe.com/)
-   **Validation**: [Pydantic](https://docs.pydantic.dev/) v2
-   **Auth**: PyJWT, Argon2 (pwdlib), PyOTP (MFA), OAuth (Google, Facebook)
-   **Observability**: OpenTelemetry, Prometheus, Loguru
-   **Testing**: pytest, testcontainers
-   **Dependency management**: [Poetry](https://python-poetry.org/) (a `requirements.txt` is also kept in sync for Docker)

## Prerequisites

-   Python 3.10 or higher
-   Docker and Docker Compose (recommended — the app needs PostgreSQL, Redis, and Elasticsearch to fully start; Compose runs all of them together)
-   A Stripe account (test-mode keys) if you want to exercise the payment/subscription flows
-   Git

## 🚀 Quick Start (Docker Compose)

This is the fastest way to get every dependency (PostgreSQL, Redis, Elasticsearch) running alongside the app.

1.  **Clone the repository**

    ```bash
    git clone https://github.com/Sanoy24/fastapi-ecommerce.git
    cd fastapi-ecommerce
    ```

2.  **Create your `.env`**

    ```bash
    cp .env.example .env
    ```

    At minimum, set `JWT_SECRET_KEY` to a random string of 32+ characters. See [Environment Configuration](#environment-configuration) for everything else.

3.  **Start the stack**

    ```bash
    docker compose up --build
    ```

    This starts the API (`:8000`), the ARQ background worker, PostgreSQL, Redis, and Elasticsearch (plus Kibana/Prometheus/Grafana/Loki/Tempo — see [Docker Support](#docker-support)).

4.  **Apply migrations**

    ```bash
    docker compose exec fastapi-app alembic upgrade head
    ```

5.  Visit **http://localhost:8000/docs**.

## 🔧 Manual Setup

Use this if you'd rather run the app directly and point it at your own PostgreSQL/Redis/Elasticsearch instances.

1.  **Create a virtual environment**

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

2.  **Install dependencies**

    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure the environment** — see [Environment Configuration](#environment-configuration).

4.  **Apply migrations**

    ```bash
    alembic upgrade head
    ```

5.  **Run it**

    ```bash
    uvicorn app.main:app --reload
    ```

### Using Poetry

CI uses Poetry, so it's kept as the source of truth for dependencies:

```bash
poetry install --with dev
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload
```

## Environment Configuration

Settings are defined in `app/core/config.py` (case-insensitive env var names) and loaded from a `.env` file. `JWT_SECRET_KEY` is the only variable with no default — everything else falls back to a sensible local-dev value.

```env
# Required
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ecommerce
JWT_SECRET_KEY=replace-with-a-random-secret-at-least-32-characters-long

# Infra (defaults assume Docker Compose / localhost)
REDIS_URL=redis://localhost:6379/0
ELASTIC_URL=http://localhost:9200

# Stripe (test-mode keys — required for payment/subscription flows)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# OAuth social login (optional — leave blank to disable a provider)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
FACEBOOK_CLIENT_ID=
FACEBOOK_CLIENT_SECRET=
OAUTH_REDIRECT_URI=http://localhost:3000/auth/callback

# Outbound email (optional — password reset / order emails)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
EMAILS_FROM_ADDRESS=

# Storefront behavior
BASE_CURRENCY_CODE=USD
FRONTEND_URL=http://localhost:3000
```

`app/core/config.py` also covers JWT token lifetimes, CORS origins, loyalty-points earn/redemption rates, and S3-backed file storage — all optional with working defaults.

## Database Setup

```bash
alembic upgrade head
```

The migration chain bootstraps a full schema from empty — no separate seed step required. To create a new migration after changing a model:

```bash
alembic revision --autogenerate -m "describe the change"
```

## Running the Application

```bash
uvicorn app.main:app --reload
```

The app also runs with `root_path=/api/v1` configured for deployment behind a reverse proxy — locally it answers on both `http://127.0.0.1:8000/...` and `http://127.0.0.1:8000/api/v1/...`.

## Running the Background Worker

Subscription renewals, abandoned-cart recovery, and back-in-stock/price-drop notification emails all run through an ARQ worker, not the API process:

```bash
arq app.workers.arq_worker.WorkerSettings
```

It needs the same `.env` (particularly `DATABASE_URL` and `REDIS_URL`) as the API.

## Testing

```bash
pytest
```

The suite spins up its own disposable PostgreSQL container via testcontainers (Docker must be running) rather than mocking the database, so it needs no `DATABASE_URL` of its own. Lint and type-check the same way CI does:

```bash
ruff check app/
mypy app/
```

## API Documentation

Once running:

-   **Swagger UI**: http://127.0.0.1:8000/docs
-   **ReDoc**: http://127.0.0.1:8000/redoc

## Docker Support

`docker-compose.yml` brings up the full stack:

| Service | Purpose | Port |
|---|---|---|
| `fastapi-app` | the API | 8000 |
| `worker` | ARQ background jobs | — |
| `postgres` | primary database | 5432 |
| `redis` | cache, rate limiting, ARQ queue | 6379 |
| `elasticsearch` | product search | 9200 |
| `kibana` | Elasticsearch UI | 5601 |
| `prometheus` | metrics | 9090 |
| `grafana` | dashboards (`admin`/`admin`) | 3000 |
| `loki` | log aggregation | 3100 |
| `tempo` | trace storage (OTLP on 4317/4318) | 3200 |

```bash
docker compose up --build        # everything
docker compose up fastapi-app worker postgres redis elasticsearch  # just what the API needs
```

## Project Structure

```
fastapi-ecommerce/
├── alembic/              # Database migrations
├── app/
│   ├── api/              # API route handlers
│   ├── core/             # Core configuration (config, security, limiter)
│   ├── crud/             # Database access layer
│   ├── db/               # Database connection and session
│   ├── middleware/       # Request logging, security headers
│   ├── models/           # SQLAlchemy database models
│   ├── schema/           # Pydantic schemas (request/response)
│   ├── services/         # Business logic
│   ├── workers/          # ARQ background jobs
│   ├── utils/            # Utility functions
│   └── main.py           # Application entry point
├── tests/                # Test suite (real Postgres via testcontainers)
├── .env.example          # Environment variable template
├── alembic.ini           # Alembic configuration
├── docker-compose.yml    # Full local stack (API, worker, Postgres, Redis, ES, observability)
├── Dockerfile
├── pyproject.toml        # Poetry project (source of truth for dependencies)
├── requirements.txt      # Exported for Docker/pip installs
└── README.md
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1.  Fork the project
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

Yonas Mekonnen - [Portfolio](https://yonas-mekonnen-portfolio.vercel.app/) - myonas886@gmail.com
