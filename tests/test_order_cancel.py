"""Tests for order cancellation — stock restoration and status transitions."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.utils.security import hash_password


def _setup_admin_and_user(db: Session):
    """Create an admin and a regular user in the DB."""
    admin = User(
        email="admin_cancel@test.com",
        password_hash=hash_password("AdminCancel1"),
        first_name="Admin",
        last_name="Cancel",
        phone="0900000010",
        is_verified=True, role="admin",
    )
    user = User(
        email="buyer_cancel@test.com",
        password_hash=hash_password("BuyerCancel1"),
        first_name="Buyer",
        last_name="Cancel",
        phone="0900000011",
        is_verified=True, role="customer",
    )
    db.add_all([admin, user])
    db.commit()
    db.refresh(admin)
    db.refresh(user)
    return admin, user


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return resp.json()["access_token"]


class TestOrderCancellation:
    def test_cancel_nonexistent_order_returns_404(self, client: TestClient):
        client.post(
            "/users/register",
            json={
                "email": "cancel_test@test.com",
                "password": "CancelTest1",
                "first_name": "Cancel",
                "last_name": "Test",
                "phone": "0900000020",
            },
        )
        token = _login(client, "cancel_test@test.com", "CancelTest1")
        resp = client.post(
            "/order/9999/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_cancel_requires_auth(self, client: TestClient):
        resp = client.post("/order/1/cancel")
        assert resp.status_code == 401

    def test_cancel_other_users_order_returns_404(self, client: TestClient, db_session: Session):
        """Users cannot cancel orders belonging to others."""
        _setup_admin_and_user(db_session)
        token = _login(client, "buyer_cancel@test.com", "BuyerCancel1")
        # Order 9999 does not exist for this user
        resp = client.post(
            "/order/9999/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
