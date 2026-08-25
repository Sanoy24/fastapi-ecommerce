import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.user import User
from app.utils.security import hash_password

def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/users/login", json={"email": email, "password": password})
    return resp.json()["access_token"]

class TestFulfillment:
    def test_admin_update_shipping(self, client: TestClient, db_session: Session):
        # 1. Setup admin and user
        admin = User(
            email="admin_full@test.com", password_hash=hash_password("AdminFull1"),
            first_name="Admin", last_name="Full", phone="0900000072", role="admin"
        )
        db_session.add(admin)
        
        user = User(
            email="user_full@test.com", password_hash=hash_password("UserFull1"),
            first_name="User", last_name="Full", phone="0900000071", role="customer"
        )
        db_session.add(user)
        db_session.commit()
        
        admin_token = _login(client, "admin_full@test.com", "AdminFull1")
        user_token = _login(client, "user_full@test.com", "UserFull1")
        
        client.post("/category", json={"name": "Cat3", "description": "Desc"}, headers={"Authorization": f"Bearer {admin_token}"})
        
        # 2. Setup product
        resp = client.post(
            "/product",
            json={"name": "Full Shirt", "description": "Test", "price": 100.0, "stock_quantity": 10, "is_active": True, "category_id": 1, "image_url": "http://test.com/img.jpg"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        product_id = resp.json()["id"]
        
        # 3. Create order
        client.post("/cart/items", json={"product_id": product_id, "quantity": 1}, headers={"Authorization": f"Bearer {user_token}"})
        resp = client.post("/users/me/address", json={"type": "shipping", "street": "123 Main St", "city": "City", "state": "State", "zip_code": "12345", "country": "Country"}, headers={"Authorization": f"Bearer {user_token}"})
        address_id = resp.json()["id"]
        
        resp = client.post(
            "/order",
            json={"shipping_address_id": address_id, "billing_address_id": address_id},
            headers={"Authorization": f"Bearer {user_token}"}
        )
        order_id = resp.json()["id"]
        
        # 4. Admin updates shipping
        resp = client.put(
            f"/admin/orders/{order_id}/shipping",
            json={"tracking_number": "TRK123456", "shipping_carrier": "FedEx"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "shipped"
        assert data["shipped_at"] is not None
        
        # 5. Check user can see tracking info
        resp = client.get(
            f"/order/{order_id}",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tracking_number"] == "TRK123456"
        assert data["shipping_carrier"] == "FedEx"
        assert data["status"] == "shipped"
