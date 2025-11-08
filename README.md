# fastapi-ecommerce

A scalable and modular eCommerce REST API built with FastAPI, SQLAlchemy, and JWT authentication.

This repository provides a starting backend for an online store. It includes models for users, products, categories, carts, orders, payments and reviews, plus basic user registration/login and address management.

## Quick overview

-   Framework: FastAPI
-   ORM: SQLAlchemy (declarative)
-   Auth: JWT (helpers in `app/utils/security.py`)
-   Migrations: Alembic (folder: `alembic/`)

API docs are available when the app is running at: `/api/v1/docs` (the app sets `root_path=/api/v1`).

## Requirements

-   Python 3.10+ is recommended
-   A virtual environment (venv, virtualenv, conda)
-   Install requirements (if `requirements.txt` exists) or install the packages below:

Recommended packages (examples):

```bash
python -m venv .venv
source .venv/bin/activate   # on Windows (bash): .venv\Scripts\activate
pip install fastapi uvicorn sqlalchemy pydantic alembic pyjwt passlib
```

Note: The project currently imports `pwdlib.PasswordHash` in `app/utils/security.py` — that looks non-standard (commonly `passlib` is used). Check and align dependencies.

## Configuration

The project uses pydantic settings (see `app/core/config.py`). Create a `.env` file in the project root with at least the following variables set (example):

```
Database_url=sqlite:///./dev.db
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_DEFAULT_EXP_MINUTES=60
```

Notes:

-   `Database_url` is the name used in code (case-insensitive when reading .env). You may prefer standard `DATABASE_URL`.
-   Alembic is present for migrations — prefer using migrations over `Base.metadata.create_all()` in production.

## How to run (development)

Start the server with uvicorn from the repository root:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open docs at: http://127.0.0.1:8000/api/v1/docs

## Key API endpoints (implemented / visible in code)

-   GET /api/v1/ — root message
-   GET /api/v1/healthcheck — health check (database connectivity)
-   POST /api/v1/users/register — register user
-   POST /api/v1/users/login — user login (returns JWT)
-   GET /api/v1/users/me — get current user (requires Bearer token)
-   PUT /api/v1/users/me — update current user
-   DELETE /api/v1/users/me — delete current user (admin required)
-   POST /api/v1/users/me/address — add address for current user
-   PUT /api/v1/users/me/address/{address_id} — update address

Many other models exist (products, categories, carts, orders, payments, reviews), but corresponding routes/crud/service implementations are incomplete or missing in this repo snapshot.

## Models (quick summary)

-   User: id, email, password_hash, first_name, last_name, phone, role, created_at, updated_at
-   Address: id, user_id, type, street, city, state, postal_code, country, is_default
-   Product: id, name, slug, description, price, stock_quantity, sku, image_url, category_id, is_active
-   Category: id, name, slug, parent_id, description, image_url
-   Cart / CartItem: cart with items and quantities
-   Order / OrderItem: order with items, totals, status, addresses
-   Payment: order payment records
-   Review: product reviews (rating, comment, approval)

See the `app/models/` folder for full field definitions.

## Known issues & incomplete areas (observations from code scan)

I scanned the codebase and found multiple issues and incomplete parts you should address before production use:

1. Schema duplication: `app/schema/user_schema.py` contains two `UserPublic` class definitions (duplicate). This will cause confusion and should be deduplicated.
2. Empty files: `app/schema/category_schema.py`, `app/crud/category.py`, and `app/services/category_service.py` are empty — category endpoints and logic are not implemented.
3. AddressService bug: `app/services/address_service.py` raises `HTTPException(status_code=s, ...)` where `s` is undefined. Also exception handling calls `e.errors()` which may not exist for arbitrary Exceptions.
4. Auth/crypto: `app/utils/security.py` imports `pwdlib.PasswordHash` — this is unusual. Consider switching to `passlib` (e.g., `from passlib.context import CryptContext`) and using a well-known scheme. Verify installed dependencies.
5. Dependency wiring / annotation issues: In `app/api/v1/routes/user.py` the `delete_user` endpoint uses `current_user: Annotated[require_admin, Depends()]` which is incorrect — `Annotated` should reference the return type (e.g., `Annotated[UserPublic, Depends(require_admin)]`). This will raise runtime errors.
6. Config naming: `app/core/config.py` defines `Database_url` (capitalized). It's functional but unconventional; prefer `DATABASE_URL` or `database_url` for clarity and compatibility.
7. DB initialization: `app/db/database.py` calls `Base.metadata.create_all(engine)` at import time. This is convenient for quick testing but migrations (Alembic) should be the canonical approach in development/production.
8. Missing or inconsistent validation: Several places rely on `.model_dump()` / `.model_validate()` (Pydantic v2). Confirm the project uses Pydantic v2. Also some endpoints trust schema->model conversions without validation of critical fields (e.g., order totals, payment processing).
9. Some files are empty or missing routes for products, carts, orders, payments, and many CRUD/service implementations are not present.

## Suggested next steps (priority)

1. Fix critical bugs in current code:

    - Fix `AddressService.update_address` (undefined `s` and exception handling).
    - Remove duplicate `UserPublic` declarations and ensure schemas match models.
    - Fix DI/annotation issues in routes (e.g., `require_admin` usage).
    - Replace `pwdlib` usage with `passlib` or ensure `pwdlib` is intentionally used and added to requirements.

2. Implement missing CRUD/services for categories, products, carts, orders, and payments.

3. Add `requirements.txt` or `pyproject.toml` with pinned dependencies.

4. Add tests (unit tests for services and integration tests for endpoints). Start with user registration/login and address flows.

5. Use Alembic migrations for schema changes; avoid `create_all()` in production.

6. Add CI (GitHub Actions) to run linting and tests.

## Contributing

If you're continuing development on this project, work in feature branches and open PRs against `develop`.

Please run linters and tests before opening a PR.

## Contact / author

Project author contact is present in `app/main.py` contact metadata.

---

If you'd like, I can:

-   create a corrected `app/schema/category_schema.py` skeleton,
-   fix the `AddressService.update_address` bug,
-   remove duplicate `UserPublic` and clean up schemas, and
-   add a `requirements.txt` file.

Tell me which of these you'd like me to do next and I'll implement the changes and run quick checks.
