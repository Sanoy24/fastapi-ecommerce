from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.product import Product


def create_test_product(db_session: Session):
    """Helper to create a product in DB."""
    product = Product(
        name="Order Product",
        slug="order-product",
        description="For testing orders",
        price=50.0,
        stock_quantity=100,
        image_url="https://example.com/img.jpg"
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


def test_create_order(client: TestClient, db_session: Session):
    # 1. Register User
    register_payload = {
        "email": "order_user@example.com",
        "password": "password123",
        "first_name": "Order",
        "last_name": "User",
        "address": "123 Order St",
        "city": "Order City",
        "country": "Order Country",
        "zip_code": "12345",
        "phone": "1234567890"
    }
    client.post("/users/register", json=register_payload)

    # 2. Login
    login_payload = {
        "email": "order_user@example.com",
        "password": "password123"
    }
    login_res = client.post("/users/login", json=login_payload)
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Add Address
    address_payload = {
        "type": "shipping",
        "street": "123 Order St",
        "city": "Order City",
        "country": "Order Country",
        "zip_code": "12345",
        "state": "Test State"
    }
    addr_res = client.post("/users/me/address", json=address_payload, headers=headers)
    assert addr_res.status_code == 200
    address_id = addr_res.json()["id"]

    # 4. Create Product
    product = create_test_product(db_session)

    # 5. Add to Cart
    cart_payload = {"product_id": product.id, "quantity": 2}
    cart_res = client.post("/cart/items", json=cart_payload, headers=headers)
    assert cart_res.status_code == 200

    # 6. Place Order
    order_payload = {
        "shipping_address_id": address_id,
        "billing_address_id": address_id
    }
    order_res = client.post("/order", json=order_payload, headers=headers)
    assert order_res.status_code == 200
    order_data = order_res.json()
    assert order_data["total_amount"] == 100.0
    assert order_data["status"] == "pending"


def test_get_orders(client: TestClient, db_session: Session):
    # 1. Register User
    register_payload = {
        "email": "get_order_user@example.com",
        "password": "password123",
        "first_name": "Order",
        "last_name": "User",
        "address": "123 Order St",
        "city": "Order City",
        "country": "Order Country",
        "zip_code": "12345",
        "phone": "1234567890"
    }
    client.post("/users/register", json=register_payload)

    # 2. Login
    login_payload = {
        "email": "get_order_user@example.com",
        "password": "password123"
    }
    login_res = client.post("/users/login", json=login_payload)
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Setup data for an order
    address_payload = {
        "type": "shipping",
        "street": "123 Order St",
        "city": "Order City",
        "country": "Order Country",
        "zip_code": "12345",
        "state": "Test State"
    }
    addr_res = client.post("/users/me/address", json=address_payload, headers=headers)
    address_id = addr_res.json()["id"]

    product = create_test_product(db_session)

    cart_payload = {"product_id": product.id, "quantity": 1}
    client.post("/cart/items", json=cart_payload, headers=headers)

    order_payload = {"shipping_address_id": address_id, "billing_address_id": address_id}
    client.post("/order", json=order_payload, headers=headers)

    # 4. Get Orders
    response = client.get("/order", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
