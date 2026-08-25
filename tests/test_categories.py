"""Tests for category CRUD operations."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.utils.security import hash_password


def _make_admin(db: Session) -> None:
    admin = User(
        email="admin_cat@test.com",
        password_hash=hash_password("AdminCat1"),
        first_name="Admin",
        last_name="Cat",
        phone="0900000030",
        is_verified=True, role="admin",
    )
    db.add(admin)
    db.commit()


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/users/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


class TestCategories:
    def test_get_categories_empty(self, client: TestClient):
        resp = client.get("/category")
        assert resp.status_code == 200

    def test_create_category_requires_admin(self, client: TestClient):
        client.post(
            "/users/register",
            json={
                "email": "notadmin_cat@test.com",
                "password": "NotAdmin1",
                "first_name": "Not",
                "last_name": "Admin",
                "phone": "0900000031",
            },
        )
        token = _login(client, "notadmin_cat@test.com", "NotAdmin1")
        resp = client.post(
            "/category",
            json={"name": "Electronics", "description": "Electronic products"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_create_category_as_admin(self, client: TestClient, db_session: Session):
        _make_admin(db_session)
        token = _login(client, "admin_cat@test.com", "AdminCat1")
        resp = client.post(
            "/category",
            json={"name": "Electronics", "description": "Electronic products"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["name"] == "Electronics"

    def test_create_duplicate_category_fails(self, client: TestClient, db_session: Session):
        _make_admin(db_session)
        token = _login(client, "admin_cat@test.com", "AdminCat1")
        client.post(
            "/category",
            json={"name": "Clothing", "description": "Clothing items"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.post(
            "/category",
            json={"name": "Clothing", "description": "Clothing items"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (400, 409)

    def test_create_category_unauthenticated_returns_401(self, client: TestClient):
        resp = client.post(
            "/category",
            json={"name": "Furniture"},
        )
        assert resp.status_code == 401
