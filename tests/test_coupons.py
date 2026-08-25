import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.coupon import Coupon
from app.utils.security import hash_password
from datetime import datetime, timedelta

def _make_admin(db: Session) -> None:
    admin = User(
        email="admin_coupon@test.com",
        password_hash=hash_password("AdminCoupon1"),
        first_name="Admin",
        last_name="Coupon",
        phone="0900000050",
        role="admin",
    )
    db.add(admin)
    db.commit()

def _make_user(db: Session) -> None:
    user = User(
        email="user_coupon@test.com",
        password_hash=hash_password("UserCoupon1"),
        first_name="User",
        last_name="Coupon",
        phone="0900000051",
        role="customer",
    )
    db.add(user)
    db.commit()

def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/users/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


class TestCoupons:
    def test_admin_create_coupon(self, client: TestClient, db_session: Session):
        _make_admin(db_session)
        token = _login(client, "admin_coupon@test.com", "AdminCoupon1")
        
        # Test creating coupon
        resp = client.post(
            "/coupons",
            json={
                "code": "SUMMER20",
                "discount_type": "percentage",
                "discount_value": 20.0,
                "is_active": True,
                "usage_limit": 100,
                "min_purchase_amount": 50.0
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "SUMMER20"
        assert data["discount_value"] == 20.0

    def test_apply_coupon_to_cart(self, client: TestClient, db_session: Session):
        _make_admin(db_session)
        _make_user(db_session)
        
        # 1. Admin creates a coupon
        admin_token = _login(client, "admin_coupon@test.com", "AdminCoupon1")
        client.post(
            "/coupons",
            json={
                "code": "FIXED10",
                "discount_type": "fixed",
                "discount_value": 10.0,
                "is_active": True
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        
        # 2. User logs in and adds product to cart (we need a product)
        # Create category first
        client.post("/category", json={"name": "Cat1", "description": "Desc"}, headers={"Authorization": f"Bearer {admin_token}"})
        
        # Create product quickly via admin
        resp = client.post(
            "/product",
            json={
                "name": "Test Shirt",
                "description": "Test",
                "price": 100.0,
                "stock_quantity": 10,
                "is_active": True,
                "category_id": 1,
                "image_url": "http://test.com/img.jpg"
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        product_id = resp.json()["id"]
        
        user_token = _login(client, "user_coupon@test.com", "UserCoupon1")
        
        # Add to cart
        client.post(
            "/cart/items",
            json={"product_id": product_id, "quantity": 1},
            headers={"Authorization": f"Bearer {user_token}"}
        )
        
        # 3. User applies coupon
        resp = client.post(
            "/cart/coupon?code=FIXED10",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert resp.status_code == 200, f"Failed to apply coupon: {resp.text}"
        # Fetch cart to check totals
        resp = client.get("/cart", headers={"Authorization": f"Bearer {user_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["discount_amount"] == 10.0
        assert data["total_amount"] == 90.0
        
        # 4. User removes coupon
        resp = client.delete(
            "/cart/coupon",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        resp = client.get("/cart", headers={"Authorization": f"Bearer {user_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["discount_amount"] == 0.0
        assert data["total_amount"] == 100.0
