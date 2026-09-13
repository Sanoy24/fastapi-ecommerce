"""
Regression tests for refund authorization and amount integrity.

Previously, POST /order/{order_id}/refund let any authenticated customer
refund their own order with a client-supplied amount validated against
nothing — not the order total, not any amount already refunded — and
payment.refund_amount was overwritten rather than accumulated on each call.
That route is now removed entirely; refunds are admin-only, issued via
POST /admin/orders/{order_id}/refund after a customer files a return.
"""
import pytest
from unittest.mock import patch
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.payment import Payment
from app.models.product import Product
from app.models.user import User
from app.services.payment_service import PaymentService
from app.utils.security import hash_password


def _make_admin(db: Session, email: str = "refund_admin@test.com") -> None:
    admin = User(
        email=email,
        password_hash=hash_password("RefundAdmin1"),
        first_name="Refund",
        last_name="Admin",
        phone="0900000090",
        is_verified=True,
        role="admin",
    )
    db.add(admin)
    db.commit()


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return resp.json()["access_token"]


def _create_paid_order(client: TestClient, db_session: Session):
    """Register a customer, place a single-item order, and mark it paid —
    mirroring what the Stripe webhook handler does on payment_intent.succeeded.
    Returns (order_id, total_amount, customer_headers).
    """
    client.post(
        "/users/register",
        json={
            "email": "refund_customer@test.com",
            "password": "Customer1",
            "first_name": "Refund",
            "last_name": "Customer",
            "phone": "0900000091",
        },
    )
    token = _login(client, "refund_customer@test.com", "Customer1")
    headers = {"Authorization": f"Bearer {token}"}

    address_resp = client.post(
        "/users/me/address",
        headers=headers,
        json={
            "type": "home",
            "street": "1 Refund St",
            "city": "Refundville",
            "state": "RS",
            "postal_code": "00001",
            "country": "Refundland",
            "is_default": True,
        },
    )
    address_id = address_resp.json()["id"]

    product = Product(
        name="Refund Product",
        slug="refund-product",
        description="For testing refunds",
        price=50.0,
        stock_quantity=10,
        image_url="https://example.com/img.jpg",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)

    client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=headers)
    order_resp = client.post(
        "/order",
        json={"shipping_address_id": address_id, "billing_address_id": address_id},
        headers=headers,
    )
    assert order_resp.status_code == 201, order_resp.json()
    order_id = order_resp.json()["id"]
    total_amount = order_resp.json()["total_amount"]

    order = db_session.query(Order).filter(Order.id == order_id).one()
    payment = Payment(
        order_id=order.id,
        payment_method="stripe",
        amount=order.total_amount,
        currency_code=order.currency_code,
        status="completed",
        transaction_id="pi_refund_test",
    )
    db_session.add(payment)
    order.payment_status = "success"
    order.status = "paid"
    db_session.commit()

    return order_id, total_amount, headers


class TestCustomerRefundRouteRemoved:
    def test_customer_refund_endpoint_no_longer_exists(self, client: TestClient, db_session: Session):
        order_id, _, headers = _create_paid_order(client, db_session)
        resp = client.post(
            f"/order/{order_id}/refund",
            json={"amount": 50.0, "reason": "requested_by_customer"},
            headers=headers,
        )
        assert resp.status_code == 404


class TestAdminRefundAuthorization:
    def test_non_admin_cannot_use_admin_refund_route(self, client: TestClient, db_session: Session):
        order_id, total_amount, headers = _create_paid_order(client, db_session)
        resp = client.post(
            f"/admin/orders/{order_id}/refund",
            json={"amount": total_amount, "reason": "requested_by_customer"},
            headers=headers,
        )
        assert resp.status_code == 403

    def test_admin_can_refund_full_amount(self, client: TestClient, db_session: Session):
        order_id, total_amount, _ = _create_paid_order(client, db_session)
        _make_admin(db_session)
        admin_token = _login(client, "refund_admin@test.com", "RefundAdmin1")

        with patch("stripe.Refund.create", return_value={"id": "re_test_full", "status": "succeeded"}):
            resp = client.post(
                f"/admin/orders/{order_id}/refund",
                json={"amount": total_amount, "reason": "requested_by_customer"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert resp.status_code == 200, resp.json()

        db_session.expire_all()
        order = db_session.query(Order).filter(Order.id == order_id).one()
        payment = db_session.query(Payment).filter(Payment.order_id == order_id).one()
        assert order.status == "refunded"
        assert float(payment.refund_amount) == total_amount

    def test_admin_refund_exceeding_total_is_rejected(self, client: TestClient, db_session: Session):
        order_id, total_amount, _ = _create_paid_order(client, db_session)
        _make_admin(db_session)
        admin_token = _login(client, "refund_admin@test.com", "RefundAdmin1")

        with patch("stripe.Refund.create") as mock_refund:
            resp = client.post(
                f"/admin/orders/{order_id}/refund",
                json={"amount": total_amount + 1, "reason": "requested_by_customer"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert resp.status_code == 400
        mock_refund.assert_not_called()

    def test_admin_refund_with_non_positive_amount_is_rejected(self, client: TestClient, db_session: Session):
        order_id, _, _ = _create_paid_order(client, db_session)
        _make_admin(db_session)
        admin_token = _login(client, "refund_admin@test.com", "RefundAdmin1")

        with patch("stripe.Refund.create") as mock_refund:
            resp = client.post(
                f"/admin/orders/{order_id}/refund",
                json={"amount": 0, "reason": "requested_by_customer"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert resp.status_code == 400
        mock_refund.assert_not_called()


class TestRefundAmountAccumulates:
    """Service-level: payment.refund_amount accumulates across calls instead
    of being overwritten, so total refunded can never exceed the order total
    even across multiple partial refunds."""

    def test_partial_refunds_accumulate_and_clamp_total(self, client: TestClient, db_session: Session):
        order_id, total_amount, _ = _create_paid_order(client, db_session)
        service = PaymentService(db_session)

        with patch("stripe.Refund.create", return_value={"id": "re_partial_1"}):
            service.refund_payment(order_id=order_id, admin_id=1, amount=20.0, reason="requested_by_customer")

        # A real deployment gates further refunds on order status too, but this
        # isolates the amount-accumulation logic itself from that state machine.
        order = db_session.query(Order).filter(Order.id == order_id).one()
        order.status = "paid"
        db_session.commit()

        with patch("stripe.Refund.create", return_value={"id": "re_partial_2"}):
            service.refund_payment(order_id=order_id, admin_id=1, amount=30.0, reason="requested_by_customer")

        db_session.expire_all()
        payment = db_session.query(Payment).filter(Payment.order_id == order_id).one()
        assert float(payment.refund_amount) == total_amount

        order = db_session.query(Order).filter(Order.id == order_id).one()
        order.status = "paid"
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            service.refund_payment(order_id=order_id, admin_id=1, amount=0.01, reason="requested_by_customer")
        assert exc_info.value.status_code == 400
