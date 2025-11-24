from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.user import User


def test_create_product_as_admin(client: TestClient, db_session: Session):
    # 1. Register a user
    register_payload = {
        "email": "admin@example.com",
        "password": "password123",
        "first_name": "Admin",
        "last_name": "User",
        "address": "123 Admin St",
        "city": "Admin City",
        "country": "Admin Country",
        "zip_code": "12345",
        "phone": "1234567890"
    }
    client.post("/users/register", json=register_payload)

    # 2. Promote to admin
    stmt = select(User).where(User.email == "admin@example.com")
    user = db_session.scalars(stmt).first()
    user.role = "admin"
    db_session.commit()

    # 3. Login
    login_payload = {
        "email": "admin@example.com",
        "password": "password123"
    }
    login_res = client.post("/users/login", json=login_payload)
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 4. Create Product
    product_payload = {
        "name": "Test Product",
        "description": "A test product",
        "price": 99.99,
        "stock_quantity": 10,
        "image_url": "https://example.com/image.jpg"
    }
    response = client.post("/product", json=product_payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == product_payload["name"]
    assert data["price"] == product_payload["price"]


def test_get_products(client: TestClient):
    response = client.get("/product")
    assert response.status_code == 200
    data = response.json()
    
    # Validate PaginatedResponse structure
    assert isinstance(data, dict)
    assert "data" in data
    assert "meta" in data
    assert isinstance(data["data"], list)
    
    # Validate pagination metadata
    meta = data["meta"]
    assert "current_page" in meta
    assert "per_page" in meta
    assert "total_pages" in meta
    assert "total_items" in meta
    assert meta["current_page"] == 1
    assert meta["per_page"] == 10
