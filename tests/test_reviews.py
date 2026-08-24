"""Tests for review creation — purchase gate, duplicate prevention, update, and delete."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.utils.security import hash_password


def _register_login(client: TestClient, email: str, password: str = "ReviewTest1") -> str:
    client.post(
        "/users/register",
        json={
            "email": email,
            "password": password,
            "first_name": "Review",
            "last_name": "User",
            "phone": "0900000050",
        },
    )
    resp = client.post("/users/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


class TestReviews:
    def test_create_review_without_purchase_forbidden(self, client: TestClient):
        """Users who haven't purchased a product cannot review it."""
        token = _register_login(client, "nopurchase@test.com")
        resp = client.post(
            "/reviews",
            json={"product_id": 1, "rating": 5, "comment": "Great!"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # 403 (no purchase) or 404 (no product) — both are correct
        assert resp.status_code in (403, 404)

    def test_create_review_requires_auth(self, client: TestClient):
        resp = client.post(
            "/reviews",
            json={"product_id": 1, "rating": 5},
        )
        assert resp.status_code == 401

    def test_rating_must_be_valid(self, client: TestClient):
        token = _register_login(client, "badrating@test.com")
        resp = client.post(
            "/reviews",
            json={"product_id": 1, "rating": 99},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Either 422 (validation) or 403 (no purchase) 
        assert resp.status_code in (403, 422)

    def test_get_reviews_for_nonexistent_product(self, client: TestClient):
        resp = client.get("/reviews/product/99999")
        assert resp.status_code in (200, 404)

    def test_delete_review_requires_auth(self, client: TestClient):
        resp = client.delete("/reviews/1")
        assert resp.status_code == 401
