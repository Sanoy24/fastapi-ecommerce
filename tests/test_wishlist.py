"""Tests for wishlist operations — add, list, remove items."""
import pytest
from fastapi.testclient import TestClient


def _register_login(client: TestClient) -> str:
    client.post(
        "/users/register",
        json={
            "email": "wishlist@test.com",
            "password": "Wishlist1",
            "first_name": "Wish",
            "last_name": "List",
            "phone": "0900000060",
        },
    )
    resp = client.post(
        "/users/login",
        json={"email": "wishlist@test.com", "password": "Wishlist1"},
    )
    return resp.json()["access_token"]


class TestWishlist:
    def test_list_wishlist_requires_auth(self, client: TestClient):
        resp = client.get("/wishlist")
        assert resp.status_code == 401

    def test_list_wishlist_authenticated(self, client: TestClient):
        token = _register_login(client)
        resp = client.get("/wishlist", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_add_nonexistent_product_fails(self, client: TestClient):
        token = _register_login(client)
        resp = client.post(
            "/wishlist",
            json={"product_id": 99999},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (400, 404)

    def test_add_requires_auth(self, client: TestClient):
        resp = client.post("/wishlist", json={"product_id": 1})
        assert resp.status_code == 401

    def test_remove_nonexistent_item_fails(self, client: TestClient):
        token = _register_login(client)
        resp = client.delete(
            "/wishlist/99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (400, 404)

    def test_remove_requires_auth(self, client: TestClient):
        resp = client.delete("/wishlist/1")
        assert resp.status_code == 401
