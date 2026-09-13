"""
Tests for the subscription renewal billing cron
(app.workers.arq_worker.process_due_subscriptions_task): successful
renewal, dunning retries on failure, auto-cancellation after the retry
schedule is exhausted, paused/not-yet-due subscriptions being left alone,
and an out-of-stock renewal being treated the same as a payment failure.

Stripe is always mocked — this suite is about this app's own dunning
state machine, not Stripe's behavior. Uses the same _use_test_db_for_worker
fixture as tests/test_back_in_stock.py and tests/test_outbox_worker.py.
"""
import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.models.order import Order
from app.models.product import Product
from app.models.subscription import Subscription
from app.utils.subscription_billing import MAX_RENEWAL_FAILURES
from app.utils.time import utcnow
from app.workers.arq_worker import process_due_subscriptions_task


@pytest.fixture
def _use_test_db_for_worker(_engine, monkeypatch):
    """Point the worker's SessionLocal at the test container instead of
    the app's real database — same fixture as test_back_in_stock.py."""
    monkeypatch.setattr(
        "app.workers.arq_worker.SessionLocal", sessionmaker(bind=_engine)
    )


def _register_and_login(client: TestClient, email: str, password: str) -> dict:
    client.post(
        "/users/register",
        json={"email": email, "password": password, "first_name": "Test", "last_name": "User", "phone": "0999900002"},
    )
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _make_product(db_session: Session, *, slug: str = "billing-widget", price: float = 25.0, stock: int = 10) -> Product:
    product = Product(
        name="Billing Widget", slug=slug, sku=f"SKU-{slug}", description="d",
        price=price, stock_quantity=stock, image_url="http://t.com/i.jpg", status="active",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


def _make_address(client: TestClient, headers: dict) -> int:
    resp = client.post(
        "/users/me/address",
        json={"type": "shipping", "street": "1 Bill St", "city": "Bill City", "state": "BS", "zip_code": "22222", "country": "Billand"},
        headers=headers,
    )
    return resp.json()["id"]


def _save_card(client: TestClient, headers: dict, pm_id: str) -> int:
    card = MagicMock(brand="visa", last4="4242", exp_month=12, exp_year=2035)
    payment_method = MagicMock(id=pm_id, type="card", card=card, customer=None)
    with patch("stripe.Customer.create") as mock_customer, patch(
        "stripe.PaymentMethod.retrieve"
    ) as mock_retrieve, patch("stripe.PaymentMethod.attach"):
        mock_customer.return_value = MagicMock(id=f"cus_{pm_id}")
        mock_retrieve.return_value = payment_method
        resp = client.post("/payments/methods", json={"payment_method_id": pm_id}, headers=headers)
    assert resp.status_code == 201, resp.json()
    return resp.json()["id"]


def _make_subscription(
    client: TestClient, db_session: Session, email: str, password: str, *, slug: str, price: float = 25.0, stock: int = 10
):
    headers = _register_and_login(client, email, password)
    product = _make_product(db_session, slug=slug, price=price, stock=stock)
    address_id = _make_address(client, headers)
    pm_id = _save_card(client, headers, pm_id=f"pm_{slug}")
    resp = client.post(
        "/subscriptions",
        json={
            "product_id": product.id, "quantity": 1, "interval": "monthly",
            "saved_payment_method_id": pm_id, "shipping_address_id": address_id, "billing_address_id": address_id,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.json()
    subscription_id = resp.json()["id"]
    return subscription_id, product


def _make_due_now(db_session: Session, subscription_id: int) -> None:
    """New subscriptions bill a full interval from now — backdate so the
    billing task picks it up on this run instead of waiting a month."""
    db_session.execute(
        Subscription.__table__.update()
        .where(Subscription.id == subscription_id)
        .values(next_billing_date=utcnow() - timedelta(hours=1))
    )
    db_session.commit()


def _run_billing():
    with patch("app.services.email_service.send_email", new_callable=AsyncMock) as mock_send:
        asyncio.run(process_due_subscriptions_task({}))
        return mock_send


class TestSuccessfulRenewal:
    def test_charges_the_saved_card_and_advances_the_next_billing_date(
        self, client: TestClient, db_session: Session, _use_test_db_for_worker
    ):
        sub_id, _ = _make_subscription(client, db_session, "bill_ok1@test.com", "BillOk123", slug="ok-widget-1")
        db_session.expire_all()
        before = db_session.get(Subscription, sub_id)
        original_next_billing = before.next_billing_date
        _make_due_now(db_session, sub_id)

        with patch("stripe.PaymentIntent.create") as mock_create:
            mock_create.return_value = MagicMock(id="pi_renew_1", status="succeeded")
            mock_send = _run_billing()

        db_session.expire_all()
        sub = db_session.get(Subscription, sub_id)
        assert sub.status == "active"
        assert sub.failure_count == 0
        assert sub.next_billing_date > original_next_billing - timedelta(hours=1)

        mock_create.assert_called_once()
        assert mock_create.call_args.kwargs["off_session"] is True
        assert mock_create.call_args.kwargs["confirm"] is True

        order = db_session.query(Order).filter_by(user_id=sub.user_id).first()
        assert order is not None
        assert order.notes and str(sub_id) in order.notes

        mock_send.assert_called_once()
        assert "renewed" in mock_send.call_args.kwargs["subject"].lower()

    def test_a_subscription_not_yet_due_is_left_alone(
        self, client: TestClient, db_session: Session, _use_test_db_for_worker
    ):
        sub_id, _ = _make_subscription(client, db_session, "bill_notdue@test.com", "BillNotDue1", slug="notdue-widget")

        with patch("stripe.PaymentIntent.create") as mock_create:
            _run_billing()

        mock_create.assert_not_called()
        db_session.expire_all()
        assert db_session.get(Subscription, sub_id).failure_count == 0

    def test_a_paused_subscription_is_never_charged_even_if_its_date_has_passed(
        self, client: TestClient, db_session: Session, _use_test_db_for_worker
    ):
        sub_id, _ = _make_subscription(client, db_session, "bill_paused@test.com", "BillPaused1", slug="paused-widget")
        headers = _register_and_login(client, "bill_paused@test.com", "BillPaused1")
        client.post(f"/subscriptions/{sub_id}/pause", headers=headers)
        _make_due_now(db_session, sub_id)

        with patch("stripe.PaymentIntent.create") as mock_create:
            _run_billing()

        mock_create.assert_not_called()


class TestFailedRenewal:
    def test_a_card_error_marks_the_subscription_past_due_and_schedules_a_retry(
        self, client: TestClient, db_session: Session, _use_test_db_for_worker
    ):
        import stripe

        sub_id, _ = _make_subscription(client, db_session, "bill_fail1@test.com", "BillFail123", slug="fail-widget-1")
        _make_due_now(db_session, sub_id)

        with patch("stripe.PaymentIntent.create") as mock_create:
            mock_create.side_effect = stripe.error.CardError("Your card was declined.", None, "card_declined")
            mock_send = _run_billing()

        db_session.expire_all()
        sub = db_session.get(Subscription, sub_id)
        assert sub.status == "past_due"
        assert sub.failure_count == 1
        assert sub.next_billing_date > utcnow()

        mock_send.assert_called_once()
        assert "failed" in mock_send.call_args.kwargs["subject"].lower()

    def test_the_failed_renewal_order_is_cancelled_and_stock_is_released(
        self, client: TestClient, db_session: Session, _use_test_db_for_worker
    ):
        import stripe

        sub_id, product = _make_subscription(
            client, db_session, "bill_fail2@test.com", "BillFail223", slug="fail-widget-2", stock=1
        )
        _make_due_now(db_session, sub_id)

        with patch("stripe.PaymentIntent.create") as mock_create:
            mock_create.side_effect = stripe.error.CardError("declined", None, "card_declined")
            _run_billing()

        db_session.expire_all()
        sub = db_session.get(Subscription, sub_id)
        order = db_session.query(Order).filter_by(user_id=sub.user_id).first()
        assert order.status == "cancelled"

        refreshed_product = db_session.get(Product, product.id)
        assert refreshed_product.available_stock == 1

    def test_out_of_stock_at_renewal_time_counts_as_a_failure_without_calling_stripe(
        self, client: TestClient, db_session: Session, _use_test_db_for_worker
    ):
        sub_id, product = _make_subscription(
            client, db_session, "bill_oos@test.com", "BillOos1234", slug="oos-widget", stock=1
        )
        _make_due_now(db_session, sub_id)
        db_session.execute(
            Product.__table__.update().where(Product.id == product.id).values(stock_quantity=0)
        )
        db_session.commit()

        with patch("stripe.PaymentIntent.create") as mock_create:
            _run_billing()

        mock_create.assert_not_called()
        db_session.expire_all()
        sub = db_session.get(Subscription, sub_id)
        assert sub.status == "past_due"
        assert sub.failure_count == 1

    def test_exceeding_the_retry_schedule_cancels_the_subscription(
        self, client: TestClient, db_session: Session, _use_test_db_for_worker
    ):
        import stripe

        sub_id, _ = _make_subscription(client, db_session, "bill_maxfail@test.com", "BillMaxFail1", slug="maxfail-widget")
        db_session.execute(
            Subscription.__table__.update()
            .where(Subscription.id == sub_id)
            .values(failure_count=MAX_RENEWAL_FAILURES, status="past_due")
        )
        _make_due_now(db_session, sub_id)

        with patch("stripe.PaymentIntent.create") as mock_create:
            mock_create.side_effect = stripe.error.CardError("declined", None, "card_declined")
            mock_send = _run_billing()

        db_session.expire_all()
        sub = db_session.get(Subscription, sub_id)
        assert sub.status == "cancelled"
        assert sub.cancelled_at is not None

        mock_send.assert_called_once()
        assert "cancelled" in mock_send.call_args.kwargs["subject"].lower()

    def test_a_non_succeeded_immediate_status_is_treated_as_a_failure(
        self, client: TestClient, db_session: Session, _use_test_db_for_worker
    ):
        sub_id, _ = _make_subscription(client, db_session, "bill_requires_action@test.com", "BillReqAct1", slug="reqaction-widget")
        _make_due_now(db_session, sub_id)

        with patch("stripe.PaymentIntent.create") as mock_create:
            mock_create.return_value = MagicMock(id="pi_requires_action", status="requires_action")
            _run_billing()

        db_session.expire_all()
        sub = db_session.get(Subscription, sub_id)
        assert sub.status == "past_due"
        assert sub.failure_count == 1
