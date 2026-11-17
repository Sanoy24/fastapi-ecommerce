"""
A Stripe webhook that crashes halfway must not be lost.

Stripe retries an event until the endpoint returns 2xx. The handler used to
commit the event id first and process the payment afterwards, so a crash
during processing left the event recorded but the order unpaid, and every
retry was then ignored as a duplicate: the customer was charged and never
got their order. These tests drive the real webhook endpoint, crash the
first delivery partway through, and check that the retry still completes
the payment exactly once.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.payment import Payment
from app.models.payment_event import PaymentEvent
from app.models.product import Product

VALID_ADDRESS = {
    "street": "1 Retry Road",
    "city": "Retryville",
    "state": "RT",
    "postal_code": "00002",
    "country": "Retryland",
}


def _register_and_login(client: TestClient, email: str, password: str) -> dict:
    client.post(
        "/users/register",
        json={"email": email, "password": password, "first_name": "Test", "last_name": "User", "phone": "0966600003"},
    )
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _paid_intent_for_new_order(client: TestClient, db: Session, transaction_id: str) -> tuple[int, int]:
    """Create a customer, a product with 10 in stock and an order for 2,
    then a payment intent for it. Returns (order_id, product_id)."""
    headers = _register_and_login(client, f"{transaction_id}@test.com", "RetryPass123")
    product = Product(
        name="Retry Widget", slug=f"retry-widget-{transaction_id}", description="For retry tests",
        price=50.0, stock_quantity=10, image_url="https://example.com/img.jpg",
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    address_id = client.post(
        "/users/me/address", headers=headers, json={"type": "home", "is_default": True, **VALID_ADDRESS}
    ).json()["id"]
    client.post("/cart/items", json={"product_id": product.id, "quantity": 2}, headers=headers)
    order = client.post(
        "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=headers
    ).json()

    with patch("stripe.PaymentIntent.create") as mock_create:
        mock_create.return_value = MagicMock(id=transaction_id, client_secret="s")
        resp = client.post("/payments/create-intent", json={"order_id": order["id"]}, headers=headers)
        assert resp.status_code == 200, resp.json()
    return order["id"], product.id


def _deliver(client: TestClient, event_id: str, transaction_id: str):
    with patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = {
            "id": event_id,
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": transaction_id}},
        }
        return client.post("/payments/webhook", content=b"{}", headers={"Stripe-Signature": "test_signature"})


def test_retry_after_a_crash_completes_the_payment(client: TestClient, db_session: Session):
    order_id, product_id = _paid_intent_for_new_order(client, db_session, "pi_retry_crash")

    # First delivery crashes partway through processing (while recording the
    # stock deduction, after the payment status has already been set).
    with patch(
        "app.services.payment_service.InventoryTransaction", side_effect=RuntimeError("worker died")
    ), pytest.raises(RuntimeError):
        _deliver(client, "evt_retry_crash", "pi_retry_crash")

    db_session.expire_all()
    assert db_session.query(PaymentEvent).filter_by(provider_event_id="evt_retry_crash").count() == 0
    assert db_session.get(Order, order_id).payment_status != "success"
    assert db_session.query(Payment).filter_by(transaction_id="pi_retry_crash").one().status != "completed"

    # Stripe retries the same event: this time it must be processed.
    resp = _deliver(client, "evt_retry_crash", "pi_retry_crash")
    assert resp.status_code == 200
    assert resp.json() == {"status": "success"}

    db_session.expire_all()
    order = db_session.get(Order, order_id)
    assert order.payment_status == "success"
    assert order.status == "paid"
    assert db_session.query(Payment).filter_by(transaction_id="pi_retry_crash").one().status == "completed"
    assert db_session.get(Product, product_id).stock_quantity == 8


def test_true_duplicate_is_still_ignored(client: TestClient, db_session: Session):
    order_id, product_id = _paid_intent_for_new_order(client, db_session, "pi_retry_dup")

    assert _deliver(client, "evt_retry_dup", "pi_retry_dup").json() == {"status": "success"}
    second = _deliver(client, "evt_retry_dup", "pi_retry_dup")
    assert second.status_code == 200
    assert second.json()["detail"] == "Duplicate event ignored"

    db_session.expire_all()
    assert db_session.get(Order, order_id).payment_status == "success"
    # Stock is deducted once, not twice.
    assert db_session.get(Product, product_id).stock_quantity == 8
    assert db_session.query(PaymentEvent).filter_by(provider_event_id="evt_retry_dup").count() == 1
