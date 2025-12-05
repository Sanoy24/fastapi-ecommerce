from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from app.models.product import Product


def create_test_product(db_session: Session):
    """Helper to create a product in DB."""
    product = Product(
        name="Payment Product",
        slug="payment-product",
        description="For testing payments",
        price=50.0,
        stock_quantity=100,
        image_url="https://example.com/img.jpg"
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


def test_create_payment_intent(client: TestClient, db_session: Session):
    # 1. Register User
    register_payload = {
        "email": "payment_user@example.com",
        "password": "password123",
        "first_name": "Payment",
        "last_name": "User",
        "address": "123 Pay St",
        "city": "Pay City",
        "country": "Pay Country",
        "zip_code": "12345",
        "phone": "1234567890"
    }
    client.post("/users/register", json=register_payload)

    # 2. Login
    login_payload = {
        "email": "payment_user@example.com",
        "password": "password123"
    }
    login_res = client.post("/users/login", json=login_payload)
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Setup Order
    address_payload = {
        "type": "billing",
        "street": "123 Pay St",
        "city": "Pay City",
        "country": "Pay Country",
        "zip_code": "12345",
        "state": "Test State"
    }
    addr_res = client.post("/users/me/address", json=address_payload, headers=headers)
    address_id = addr_res.json()["id"]

    product = create_test_product(db_session)

    cart_payload = {"product_id": product.id, "quantity": 1}
    client.post("/cart/items", json=cart_payload, headers=headers)

    order_payload = {"shipping_address_id": address_id, "billing_address_id": address_id}
    order_res = client.post("/order", json=order_payload, headers=headers)
    order_id = order_res.json()["id"]

    # 4. Mock Stripe and Create Intent
    with patch("stripe.PaymentIntent.create") as mock_create:
        mock_create.return_value = MagicMock(
            id="pi_12345",
            client_secret="secret_12345"
        )
        
        payload = {"order_id": order_id}
        response = client.post("/payments/create-intent", json=payload, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["payment_intent_id"] == "pi_12345"
        assert data["client_secret"] == "secret_12345"


def test_stripe_webhook_success(client: TestClient):
    # Mock Stripe Webhook construction
    with patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_12345"
                }
            }
        }
        
        headers = {"Stripe-Signature": "test_signature"}
        payload = b'{"type": "payment_intent.succeeded"}'
        
        response = client.post("/payments/webhook", content=payload, headers=headers)
        assert response.status_code == 200
        assert response.json() == {"status": "success"}
