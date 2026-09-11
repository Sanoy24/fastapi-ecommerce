"""
Tests for GET /admin/analytics/sales/trends.

This endpoint previously grouped by `func.strftime(...)`, a SQLite-only
function, so it raised ProgrammingError on every call against the PostgreSQL
database the app actually runs on. It had no test coverage at all, and the
suite runs on SQLite, so nothing caught it.

`test_statement_compiles_for_postgresql` is the guard for that specific class
of bug: it compiles the real statement under a PostgreSQL dialect, so it fails
on a SQLite-only function even though the suite itself is still on SQLite.
"""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.user import User
from app.utils.security import hash_password


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return resp.json()["access_token"]


@pytest.fixture
def shop(client: TestClient, db_session: Session):
    """An admin, a customer, a purchasable product and a shipping address."""
    db_session.add_all(
        [
            User(
                email="admin_trends@test.com",
                password_hash=hash_password("AdminTrend1"),
                first_name="Admin",
                last_name="Trends",
                phone="0900000090",
                is_verified=True,
                role="admin",
            ),
            User(
                email="buyer_trends@test.com",
                password_hash=hash_password("BuyerTrend1"),
                first_name="Buyer",
                last_name="Trends",
                phone="0900000091",
                is_verified=True,
                role="customer",
            ),
        ]
    )
    db_session.commit()

    admin_token = _login(client, "admin_trends@test.com", "AdminTrend1")
    buyer_token = _login(client, "buyer_trends@test.com", "BuyerTrend1")
    admin_auth = {"Authorization": f"Bearer {admin_token}"}
    buyer_auth = {"Authorization": f"Bearer {buyer_token}"}

    resp = client.post(
        "/category",
        json={"name": "TrendCat", "description": "For trend tests"},
        headers=admin_auth,
    )
    category_id = resp.json()["id"]

    resp = client.post(
        "/product",
        json={
            "name": "Trend Widget",
            "description": "A widget",
            "price": 50.0,
            "stock_quantity": 500,
            "is_active": True,
            "category_id": category_id,
            "image_url": "http://test.com/widget.jpg",
        },
        headers=admin_auth,
    )
    product_id = resp.json()["id"]

    resp = client.post(
        "/users/me/address",
        json={
            "type": "shipping",
            "street": "1 Trend St",
            "city": "Town",
            "state": "State",
            "zip_code": "12345",
            "country": "Country",
        },
        headers=buyer_auth,
    )
    address_id = resp.json()["id"]

    return {
        "admin_auth": admin_auth,
        "buyer_auth": buyer_auth,
        "product_id": product_id,
        "address_id": address_id,
    }


def _place_order(client: TestClient, shop, quantity: int = 1) -> int:
    """Place a real order through the API and return its id."""
    resp = client.post(
        "/cart/items",
        json={"product_id": shop["product_id"], "quantity": quantity},
        headers=shop["buyer_auth"],
    )
    assert resp.status_code in (200, 201), resp.json()

    resp = client.post(
        "/order",
        json={
            "shipping_address_id": shop["address_id"],
            "billing_address_id": shop["address_id"],
        },
        headers=shop["buyer_auth"],
    )
    assert resp.status_code == 201, resp.json()
    return resp.json()["id"]


def _backdate(db_session: Session, order_id: int, days_ago: int, status: str = "pending") -> Order:
    """Move an order into the past so it lands in a known day bucket."""
    order = db_session.get(Order, order_id)
    order.order_date = datetime.now() - timedelta(days=days_ago)
    order.status = status
    db_session.commit()
    db_session.refresh(order)
    return order


def _trends(client: TestClient, shop, days: int = 30):
    resp = client.get(
        f"/admin/analytics/sales/trends?days={days}",
        headers=shop["admin_auth"],
    )
    assert resp.status_code == 200, resp.json()
    return resp.json()


class TestSalesTrendsPortability:
    def test_statement_compiles_for_postgresql(self):
        """
        The regression guard for the original bug.

        The suite runs on SQLite, so an endpoint test alone would have passed
        happily while production 500'd. Compiling against the PostgreSQL
        dialect catches a SQLite-only function without needing a live server.
        """
        from sqlalchemy.dialects import postgresql

        from app.api.v1.routes.admin import build_sales_trends_stmt

        sql = str(
            build_sales_trends_stmt(datetime.now()).compile(
                dialect=postgresql.dialect()
            )
        ).lower()

        assert "strftime" not in sql, f"SQLite-only function leaked into PostgreSQL SQL: {sql}"
        assert "date(" in sql, f"expected a day-truncation call, got: {sql}"

    def test_statement_compiles_for_sqlite(self):
        """The same statement must stay valid on the dialect the suite uses."""
        from sqlalchemy.dialects import sqlite

        from app.api.v1.routes.admin import build_sales_trends_stmt

        sql = str(
            build_sales_trends_stmt(datetime.now()).compile(dialect=sqlite.dialect())
        ).lower()

        assert "date(" in sql
        # CAST(x AS DATE) evaluates to just the year on SQLite, so it must not
        # be how this query truncates.
        assert "cast(" not in sql


class TestSalesTrendsAccess:
    def test_requires_authentication(self, client: TestClient):
        assert client.get("/admin/analytics/sales/trends").status_code == 401

    def test_rejects_non_admin(self, client: TestClient, shop):
        resp = client.get(
            "/admin/analytics/sales/trends", headers=shop["buyer_auth"]
        )
        assert resp.status_code == 403


class TestSalesTrendsResults:
    def test_returns_empty_list_when_no_orders(self, client: TestClient, shop):
        assert _trends(client, shop) == []

    def test_groups_orders_by_calendar_day(
        self, client: TestClient, db_session: Session, shop
    ):
        # Two orders three days ago, one order one day ago.
        first = _backdate(db_session, _place_order(client, shop), days_ago=3)
        _backdate(db_session, _place_order(client, shop), days_ago=3)
        recent = _backdate(db_session, _place_order(client, shop), days_ago=1)

        rows = _trends(client, shop)

        assert len(rows) == 2, rows
        older, newer = rows  # ordered ascending by day

        assert older["date"] == first.order_date.date().isoformat()
        assert older["orders_count"] == 2
        assert newer["date"] == recent.order_date.date().isoformat()
        assert newer["orders_count"] == 1

    def test_date_is_a_plain_yyyy_mm_dd_string(
        self, client: TestClient, db_session: Session, shop
    ):
        _backdate(db_session, _place_order(client, shop), days_ago=2)

        (row,) = _trends(client, shop)

        assert isinstance(row["date"], str)
        # Must parse as a bare date — no time component, no dialect artefacts.
        datetime.strptime(row["date"], "%Y-%m-%d")

    def test_revenue_sums_the_day(self, client: TestClient, db_session: Session, shop):
        one = _backdate(db_session, _place_order(client, shop, quantity=1), days_ago=2)
        two = _backdate(db_session, _place_order(client, shop, quantity=2), days_ago=2)

        (row,) = _trends(client, shop)

        assert row["orders_count"] == 2
        assert row["revenue"] == pytest.approx(
            float(one.total_amount) + float(two.total_amount)
        )

    def test_excludes_cancelled_orders(
        self, client: TestClient, db_session: Session, shop
    ):
        kept = _backdate(db_session, _place_order(client, shop), days_ago=2)
        _backdate(db_session, _place_order(client, shop), days_ago=2, status="cancelled")

        (row,) = _trends(client, shop)

        assert row["orders_count"] == 1
        assert row["revenue"] == pytest.approx(float(kept.total_amount))

    def test_respects_the_days_window(
        self, client: TestClient, db_session: Session, shop
    ):
        _backdate(db_session, _place_order(client, shop), days_ago=2)
        _backdate(db_session, _place_order(client, shop), days_ago=20)

        assert len(_trends(client, shop, days=30)) == 2
        assert len(_trends(client, shop, days=7)) == 1

    def test_rejects_out_of_range_days(self, client: TestClient, shop):
        for bad in (0, 366):
            resp = client.get(
                f"/admin/analytics/sales/trends?days={bad}",
                headers=shop["admin_auth"],
            )
            assert resp.status_code == 422
