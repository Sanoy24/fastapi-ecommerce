"""Tests for wishlist operations — add, list, remove items."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User


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

    def test_move_to_cart(self, client: TestClient, db_session: Session):
        _register_login(client)
        db_session.query(User).filter(User.email == "wishlist@test.com").update(
            {"role": "admin"}
        )
        db_session.commit()
        admin_login = client.post(
            "/users/login",
            json={"email": "wishlist@test.com", "password": "Wishlist1"},
        )
        headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

        product_resp = client.post(
            "/product",
            json={
                "name": "Wishlist Product",
                "price": 15.0,
                "stock_quantity": 10,
                "status": "active",
            },
            headers=headers,
        )
        product_id = product_resp.json()["id"]

        client.post("/wishlist", json={"product_id": product_id}, headers=headers)

        resp = client.post(f"/wishlist/{product_id}/move-to-cart", headers=headers)
        assert resp.status_code == 200

        cart_resp = client.get("/cart", headers=headers)
        product_ids = [item["product_id"] for item in cart_resp.json()["items"]]
        assert product_id in product_ids

        wishlist_resp = client.get("/wishlist", headers=headers)
        remaining_ids = [item["product_id"] for item in wishlist_resp.json()["items"]]
        assert product_id not in remaining_ids

    def test_move_to_cart_nonexistent_product_fails(self, client: TestClient):
        token = _register_login(client)
        resp = client.post(
            "/wishlist/99999/move-to-cart",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
