"""
Tests for price-drop alerts: subscribing to a product's price and actually
getting notified once it falls.

ProductRelation/PriceHistory-style "watch a product" mechanisms already
existed for other things, but nothing let a customer ask to be emailed when
a price falls. This covers the new subscription CRUD (subscribe with or
without a target price, list, unsubscribe, re-subscribing after already
being notified) and the notification trigger wired into
app/crud/product.py update_product, watching Product.effective_price (which
accounts for sale_price/sale windows, not just the raw price column) rather
than price alone — so putting an item on sale is itself a "drop" a
subscriber can hear about.

Emailing runs through the existing outbox worker
(app/workers/arq_worker.py process_outbox_events_task), same as
back-in-stock — see tests/test_back_in_stock.py for the sibling suite this
one mirrors.
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.outbox_event import OutboxEvent
from app.models.price_drop_subscription import PriceDropSubscription
from app.models.product import Product
from app.models.user import User
from app.utils.security import hash_password
from app.workers.arq_worker import process_outbox_events_task


@pytest.fixture
def _use_test_db_for_worker(_engine, monkeypatch):
    """Point the worker's SessionLocal at the test container instead of
    the app's real database — same fixture as test_back_in_stock.py."""
    monkeypatch.setattr(
        "app.workers.arq_worker.SessionLocal", sessionmaker(bind=_engine)
    )


def _make_admin(db_session: Session, email: str = "pda_admin@test.com") -> None:
    db_session.add(
        User(
            email=email,
            password_hash=hash_password("PdaAdmin1"),
            first_name="Admin",
            last_name="Pda",
            phone="0933300001",
            is_verified=True,
            role="admin",
        )
    )
    db_session.commit()


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _register_and_login(client: TestClient, email: str, password: str) -> dict:
    client.post(
        "/users/register",
        json={"email": email, "password": password, "first_name": "Test", "last_name": "User", "phone": "0933300002"},
    )
    return _login(client, email, password)


def _make_product(db_session: Session, *, price: float = 100.0, slug: str = "pda-widget") -> Product:
    product = Product(
        name="Price Drop Widget",
        slug=slug,
        sku=f"SKU-{slug}",
        description="d",
        price=price,
        stock_quantity=50,
        image_url="http://test.com/img.jpg",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


class TestSubscribeValidation:
    def test_requires_authentication(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="auth-widget")
        resp = client.post("/price-drop-alerts", json={"product_id": product.id})
        assert resp.status_code == 401

    def test_rejects_nonexistent_product(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "pda_cust1@test.com", "PdaCust1")
        resp = client.post("/price-drop-alerts", json={"product_id": 999999}, headers=customer)
        assert resp.status_code == 404

    def test_rejects_a_target_price_at_or_above_current_price(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, price=100.0, slug="bad-target-widget")
        customer = _register_and_login(client, "pda_cust2@test.com", "PdaCust2")

        resp = client.post(
            "/price-drop-alerts",
            json={"product_id": product.id, "target_price": 100.0},
            headers=customer,
        )

        assert resp.status_code == 400
        assert "target price" in resp.json()["detail"].lower()

    def test_successful_subscribe_without_a_target_price(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, price=50.0, slug="no-target-widget")
        customer = _register_and_login(client, "pda_cust3@test.com", "PdaCust3")

        resp = client.post("/price-drop-alerts", json={"product_id": product.id}, headers=customer)

        assert resp.status_code == 201, resp.json()
        data = resp.json()
        assert data["product_id"] == product.id
        assert data["target_price"] is None
        assert data["subscribed_price"] == 50.0
        assert data["notified_at"] is None

    def test_successful_subscribe_with_a_valid_target_price(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, price=50.0, slug="target-widget")
        customer = _register_and_login(client, "pda_cust4@test.com", "PdaCust4")

        resp = client.post(
            "/price-drop-alerts",
            json={"product_id": product.id, "target_price": 30.0},
            headers=customer,
        )

        assert resp.status_code == 201, resp.json()
        assert resp.json()["target_price"] == 30.0


class TestSubscriptionLifecycle:
    def test_list_shows_only_my_subscriptions(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="list-widget")
        customer_a = _register_and_login(client, "pda_list_a@test.com", "PdaListA1")
        customer_b = _register_and_login(client, "pda_list_b@test.com", "PdaListB1")

        client.post("/price-drop-alerts", json={"product_id": product.id}, headers=customer_a)

        a_subs = client.get("/price-drop-alerts", headers=customer_a).json()
        b_subs = client.get("/price-drop-alerts", headers=customer_b).json()

        assert len(a_subs) == 1
        assert b_subs == []

    def test_unsubscribe_removes_it(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="unsub-widget")
        customer = _register_and_login(client, "pda_unsub@test.com", "PdaUnsub1")

        sub_id = client.post("/price-drop-alerts", json={"product_id": product.id}, headers=customer).json()["id"]
        delete_resp = client.delete(f"/price-drop-alerts/{sub_id}", headers=customer)

        assert delete_resp.status_code == 204
        assert client.get("/price-drop-alerts", headers=customer).json() == []

    def test_cannot_unsubscribe_someone_elses_subscription(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="unsub-other-widget")
        owner = _register_and_login(client, "pda_owner@test.com", "PdaOwner1")
        attacker = _register_and_login(client, "pda_attacker@test.com", "PdaAttack1")

        sub_id = client.post("/price-drop-alerts", json={"product_id": product.id}, headers=owner).json()["id"]
        resp = client.delete(f"/price-drop-alerts/{sub_id}", headers=attacker)

        assert resp.status_code == 404
        assert len(client.get("/price-drop-alerts", headers=owner).json()) == 1

    def test_resubscribing_updates_the_same_row_instead_of_duplicating(
        self, client: TestClient, db_session: Session
    ):
        product = _make_product(db_session, price=100.0, slug="resub-widget")
        customer = _register_and_login(client, "pda_resub1@test.com", "PdaResub1")

        first = client.post("/price-drop-alerts", json={"product_id": product.id}, headers=customer)
        second = client.post(
            "/price-drop-alerts",
            json={"product_id": product.id, "target_price": 60.0},
            headers=customer,
        )

        assert first.json()["id"] == second.json()["id"]
        assert second.json()["target_price"] == 60.0
        assert len(client.get("/price-drop-alerts", headers=customer).json()) == 1


class TestNotificationTrigger:
    def test_price_decrease_triggers_notification_for_any_drop_subscription(
        self, client: TestClient, db_session: Session
    ):
        _make_admin(db_session, "pda_drop_admin@test.com")
        product = _make_product(db_session, price=100.0, slug="drop-trigger-widget")
        customer = _register_and_login(client, "pda_drop_cust@test.com", "PdaDrop1")
        client.post("/price-drop-alerts", json={"product_id": product.id}, headers=customer)

        admin = _login(client, "pda_drop_admin@test.com", "PdaAdmin1")
        resp = client.put(f"/product/{product.id}", json={"price": 80.0}, headers=admin)
        assert resp.status_code == 200, resp.json()

        db_session.expire_all()
        sub = db_session.scalars(
            select(PriceDropSubscription).where(PriceDropSubscription.product_id == product.id)
        ).first()
        assert sub.notified_at is not None

        outbox = db_session.scalars(
            select(OutboxEvent).where(OutboxEvent.topic == "product.price_drop")
        ).first()
        assert outbox is not None
        assert outbox.payload["email"] == "pda_drop_cust@test.com"
        assert outbox.payload["old_price"] == 100.0
        assert outbox.payload["new_price"] == 80.0

    def test_setting_a_sale_price_counts_as_a_drop(self, client: TestClient, db_session: Session):
        """effective_price, not the raw price column, is what a customer
        watches — putting an item on sale is a real price drop even though
        Product.price itself never changes."""
        _make_admin(db_session, "pda_sale_admin@test.com")
        product = _make_product(db_session, price=100.0, slug="sale-trigger-widget")
        customer = _register_and_login(client, "pda_sale_cust@test.com", "PdaSale1")
        client.post("/price-drop-alerts", json={"product_id": product.id}, headers=customer)

        admin = _login(client, "pda_sale_admin@test.com", "PdaAdmin1")
        resp = client.put(f"/product/{product.id}", json={"sale_price": 70.0}, headers=admin)
        assert resp.status_code == 200, resp.json()

        db_session.expire_all()
        sub = db_session.scalars(
            select(PriceDropSubscription).where(PriceDropSubscription.product_id == product.id)
        ).first()
        assert sub.notified_at is not None

    def test_does_not_notify_before_the_target_price_is_reached(
        self, client: TestClient, db_session: Session
    ):
        _make_admin(db_session, "pda_notyet_admin@test.com")
        product = _make_product(db_session, price=100.0, slug="notyet-widget")
        customer = _register_and_login(client, "pda_notyet_cust@test.com", "PdaNotYet1")
        client.post(
            "/price-drop-alerts",
            json={"product_id": product.id, "target_price": 30.0},
            headers=customer,
        )

        admin = _login(client, "pda_notyet_admin@test.com", "PdaAdmin1")
        # Dropped, but not far enough to hit the target.
        resp = client.put(f"/product/{product.id}", json={"price": 80.0}, headers=admin)
        assert resp.status_code == 200

        db_session.expire_all()
        sub = db_session.scalars(
            select(PriceDropSubscription).where(PriceDropSubscription.product_id == product.id)
        ).first()
        assert sub.notified_at is None

    def test_notifies_once_the_target_price_is_reached(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "pda_target_admin@test.com")
        product = _make_product(db_session, price=100.0, slug="target-hit-widget")
        customer = _register_and_login(client, "pda_target_cust@test.com", "PdaTarget1")
        client.post(
            "/price-drop-alerts",
            json={"product_id": product.id, "target_price": 30.0},
            headers=customer,
        )

        admin = _login(client, "pda_target_admin@test.com", "PdaAdmin1")
        resp = client.put(f"/product/{product.id}", json={"price": 25.0}, headers=admin)
        assert resp.status_code == 200

        db_session.expire_all()
        sub = db_session.scalars(
            select(PriceDropSubscription).where(PriceDropSubscription.product_id == product.id)
        ).first()
        assert sub.notified_at is not None

    def test_no_notification_when_price_increases(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "pda_increase_admin@test.com")
        product = _make_product(db_session, price=50.0, slug="increase-widget")
        customer = _register_and_login(client, "pda_increase_cust@test.com", "PdaIncr1")
        client.post("/price-drop-alerts", json={"product_id": product.id}, headers=customer)

        admin = _login(client, "pda_increase_admin@test.com", "PdaAdmin1")
        resp = client.put(f"/product/{product.id}", json={"price": 60.0}, headers=admin)
        assert resp.status_code == 200

        db_session.expire_all()
        assert (
            db_session.scalars(
                select(OutboxEvent).where(OutboxEvent.topic == "product.price_drop")
            ).first()
            is None
        )

    def test_no_notification_for_an_unrelated_field_update(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "pda_unrelated_admin@test.com")
        product = _make_product(db_session, price=50.0, slug="unrelated-widget")
        customer = _register_and_login(client, "pda_unrelated_cust@test.com", "PdaUnrelated1")
        client.post("/price-drop-alerts", json={"product_id": product.id}, headers=customer)

        admin = _login(client, "pda_unrelated_admin@test.com", "PdaAdmin1")
        resp = client.put(f"/product/{product.id}", json={"stock_quantity": 5}, headers=admin)
        assert resp.status_code == 200

        db_session.expire_all()
        assert (
            db_session.scalars(
                select(OutboxEvent).where(OutboxEvent.topic == "product.price_drop")
            ).first()
            is None
        )

    def test_does_not_re_notify_on_a_further_drop_until_resubscribed(
        self, client: TestClient, db_session: Session
    ):
        """One-shot, matching back-in-stock: once fired, the subscription
        needs to be re-armed (re-subscribing) before it fires again."""
        _make_admin(db_session, "pda_rearm_admin@test.com")
        product = _make_product(db_session, price=100.0, slug="rearm-widget")
        customer = _register_and_login(client, "pda_rearm_cust@test.com", "PdaRearm1")
        client.post("/price-drop-alerts", json={"product_id": product.id}, headers=customer)

        admin = _login(client, "pda_rearm_admin@test.com", "PdaAdmin1")
        client.put(f"/product/{product.id}", json={"price": 80.0}, headers=admin)
        client.put(f"/product/{product.id}", json={"price": 60.0}, headers=admin)

        db_session.expire_all()
        count = (
            db_session.query(OutboxEvent)
            .filter_by(topic="product.price_drop")
            .count()
        )
        assert count == 1

        resp = client.post("/price-drop-alerts", json={"product_id": product.id}, headers=customer)
        assert resp.status_code == 201
        assert resp.json()["notified_at"] is None
        assert resp.json()["subscribed_price"] == 60.0


class TestEndToEndEmailDelivery:
    def test_worker_sends_the_price_drop_email(
        self, client: TestClient, db_session: Session, _use_test_db_for_worker
    ):
        _make_admin(db_session, "pda_worker_admin@test.com")
        product = _make_product(db_session, price=100.0, slug="worker-widget")
        customer = _register_and_login(client, "pda_worker_cust@test.com", "PdaWorker1")
        client.post("/price-drop-alerts", json={"product_id": product.id}, headers=customer)

        admin = _login(client, "pda_worker_admin@test.com", "PdaAdmin1")
        client.put(f"/product/{product.id}", json={"price": 70.0}, headers=admin)

        with patch("app.services.email_service.send_email", new_callable=AsyncMock) as mock_send:
            asyncio.run(process_outbox_events_task({}))

        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs["to_address"] == "pda_worker_cust@test.com"
        assert "price drop" in mock_send.call_args.kwargs["subject"].lower()

        db_session.expire_all()
        outbox = db_session.scalars(
            select(OutboxEvent).where(OutboxEvent.topic == "product.price_drop")
        ).first()
        assert outbox.status == "completed"
