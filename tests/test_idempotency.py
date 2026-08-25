import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.user import User
from app.utils.security import hash_password
import uuid

def _make_user(db: Session) -> None:
    user = User(
        email="user_idem@test.com",
        password_hash=hash_password("UserIdem1"),
        first_name="User",
        last_name="Idem",
        phone="0900000061",
        is_verified=True, role="customer",
    )
    db.add(user)
    db.commit()

def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/users/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


class TestIdempotency:
    def test_idempotent_order_creation(self, client: TestClient, db_session: Session):
        _make_user(db_session)
        token = _login(client, "user_idem@test.com", "UserIdem1")
        
        # 1. Add item to cart
        # Create admin and product first
        admin = User(
            email="admin_idem@test.com", password_hash=hash_password("AdminIdem1"),
            first_name="Admin", last_name="Idem", phone="0900000062", is_verified=True, role="admin"
        )
        db_session.add(admin)
        db_session.commit()
        admin_token = _login(client, "admin_idem@test.com", "AdminIdem1")
        
        client.post("/category", json={"name": "Cat2", "description": "Desc"}, headers={"Authorization": f"Bearer {admin_token}"})
        
        resp = client.post(
            "/product",
            json={"name": "Idem Shirt", "description": "Test", "price": 100.0, "stock_quantity": 10, "is_active": True, "category_id": 1, "image_url": "http://test.com/img.jpg"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        product_id = resp.json()["id"]
        
        # Add to cart
        client.post("/cart/items", json={"product_id": product_id, "quantity": 1}, headers={"Authorization": f"Bearer {token}"})
        
        # Create addresses
        resp = client.post("/users/me/address", json={"type": "shipping", "street": "123 Main St", "city": "City", "state": "State", "zip_code": "12345", "country": "Country"}, headers={"Authorization": f"Bearer {token}"})
        address_id = resp.json()["id"]
        
        # 2. Place order with idempotency key
        idem_key = str(uuid.uuid4())
        resp1 = client.post(
            "/order",
            json={"shipping_address_id": address_id, "billing_address_id": address_id},
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idem_key}
        )
        assert resp1.status_code == 200
        order_number = resp1.json()["order_number"]
        
        # 3. Retry place order with same key
        resp2 = client.post(
            "/order",
            json={"shipping_address_id": address_id, "billing_address_id": address_id},
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idem_key}
        )
        assert resp2.status_code == 200
        assert resp2.json()["order_number"] == order_number
        
        # 4. Without idempotency key (requires non-empty cart first)
        client.post("/cart/items", json={"product_id": product_id, "quantity": 1}, headers={"Authorization": f"Bearer {token}"})
        
        resp4 = client.post(
            "/order",
            json={"shipping_address_id": address_id, "billing_address_id": address_id},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp4.status_code == 200
