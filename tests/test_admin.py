"""Tests for admin endpoints — dashboard, analytics, user management, order management."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.utils.security import hash_password


def _make_admin(db: Session, email: str = "admin_main@test.com") -> None:
    admin = User(
        email=email,
        password_hash=hash_password("AdminMain1"),
        first_name="Admin",
        last_name="Main",
        phone="0900000070",
        is_verified=True, role="admin",
    )
    db.add(admin)
    db.commit()


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return resp.json()["access_token"]


class TestAdminAccess:
    def test_dashboard_requires_admin(self, client: TestClient):
        client.post(
            "/users/register",
            json={
                "email": "notadmin_adm@test.com",
                "password": "NotAdmin1",
                "first_name": "Not",
                "last_name": "Admin",
                "phone": "0900000071",
            },
        )
        token = _login(client, "notadmin_adm@test.com", "NotAdmin1")
        resp = client.get(
            "/admin/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_dashboard_unauthenticated_returns_401(self, client: TestClient):
        resp = client.get("/admin/dashboard")
        assert resp.status_code == 401

    def test_dashboard_as_admin_succeeds(self, client: TestClient, db_session: Session):
        _make_admin(db_session)
        token = _login(client, "admin_main@test.com", "AdminMain1")
        resp = client.get(
            "/admin/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "sales" in data or "total_orders" in data or "revenue" in data

    def test_sales_analytics_as_admin(self, client: TestClient, db_session: Session):
        _make_admin(db_session)
        token = _login(client, "admin_main@test.com", "AdminMain1")
        resp = client.get(
            "/admin/analytics/sales",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_user_analytics_as_admin(self, client: TestClient, db_session: Session):
        _make_admin(db_session)
        token = _login(client, "admin_main@test.com", "AdminMain1")
        resp = client.get(
            "/admin/analytics/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_product_analytics_as_admin(self, client: TestClient, db_session: Session):
        _make_admin(db_session)
        token = _login(client, "admin_main@test.com", "AdminMain1")
        resp = client.get(
            "/admin/analytics/products",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_list_all_users_as_admin(self, client: TestClient, db_session: Session):
        _make_admin(db_session)
        token = _login(client, "admin_main@test.com", "AdminMain1")
        resp = client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_list_all_orders_as_admin(self, client: TestClient, db_session: Session):
        _make_admin(db_session)
        token = _login(client, "admin_main@test.com", "AdminMain1")
        resp = client.get(
            "/admin/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_low_stock_alerts_as_admin(self, client: TestClient, db_session: Session):
        _make_admin(db_session)
        token = _login(client, "admin_main@test.com", "AdminMain1")
        resp = client.get(
            "/admin/inventory/low-stock",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_pending_reviews_as_admin(self, client: TestClient, db_session: Session):
        _make_admin(db_session)
        token = _login(client, "admin_main@test.com", "AdminMain1")
        resp = client.get(
            "/admin/reviews/pending",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
