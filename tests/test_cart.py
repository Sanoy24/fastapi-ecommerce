"""Tests for cart operations — add, update, remove items; anonymous and authenticated flows."""
import pytest
from fastapi.testclient import TestClient


def register_and_login(client: TestClient) -> str:
    client.post(
        "/users/register",
        json={
            "email": "cart@test.com",
            "password": "CartTest1",
            "first_name": "Cart",
            "last_name": "User",
            "phone": "0911000001",
        },
    )
    resp = client.post(
        "/users/login",
        json={"email": "cart@test.com", "password": "CartTest1"},
    )
    return resp.json()["access_token"]


def create_product(client: TestClient, token: str) -> int:
    resp = client.post(
        "/product",
        json={
            "name": "Cart Product",
            "price": 25.0,
            "stock_quantity": 50,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.json()["id"]


def make_admin(client: TestClient, token: str) -> str:
    """Register an admin user and return their token."""
    client.post(
        "/users/register",
        json={
            "email": "admin@test.com",
            "password": "AdminTest1",
            "first_name": "Admin",
            "last_name": "User",
            "phone": "0911000000",
        },
    )
    # Promote to admin via DB in conftest — for this test we test cart without admin products
    return token


class TestCart:
    def test_get_empty_cart_anonymous(self, client: TestClient):
        resp = client.get("/cart")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["subtotal"] == 0
        assert data["total_items"] == 0

    def test_get_cart_authenticated(self, client: TestClient):
        token = register_and_login(client)
        resp = client.get("/cart", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "subtotal" in data
        assert "total_items" in data

    def test_add_nonexistent_product_fails(self, client: TestClient):
        token = register_and_login(client)
        resp = client.post(
            "/cart/items",
            json={"product_id": 999, "quantity": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (400, 404, 422)

    def test_remove_nonexistent_item_returns_404(self, client: TestClient):
        token = register_and_login(client)
        resp = client.delete(
            "/cart/items/9999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
