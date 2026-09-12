"""
Tests for back-in-stock notifications: subscribing while an item is out
of stock, and actually getting notified once it's restocked.

Wishlist and variant-aware stock tracking both already existed — there was
no subscription mechanism connecting the two, and nothing watched for a
stock increase at all. This covers the new subscription CRUD (subscribe,
list, unsubscribe, and re-subscribing after already being notified), and
the notification trigger wired into every place stock_quantity can
increase: bulk inventory update, a general product/variant edit, and
return-approval restocking (see app/services/back_in_stock_service.py and
its four call sites).

Emailing runs through the existing outbox worker
(app/workers/arq_worker.py process_outbox_events_task) rather than a
parallel mechanism — a subscription firing writes a
"product.back_in_stock" outbox event in the same transaction as the stock
update, and the worker turns that into an actual email. Those tests use
the same _use_test_db_for_worker fixture as test_abandoned_cart_recovery.py
and test_outbox_worker.py.
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.back_in_stock_subscription import BackInStockSubscription
from app.models.category import Category
from app.models.outbox_event import OutboxEvent
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.user import User
from app.utils.security import hash_password
from app.workers.arq_worker import process_outbox_events_task


@pytest.fixture
def _use_test_db_for_worker(_engine, monkeypatch):
    """Point the worker's SessionLocal at the test container instead of
    the app's real database — same fixture as test_outbox_worker.py and
    test_abandoned_cart_recovery.py."""
    monkeypatch.setattr(
        "app.workers.arq_worker.SessionLocal", sessionmaker(bind=_engine)
    )


def _make_admin(db_session: Session, email: str = "bis_admin@test.com") -> None:
    db_session.add(
        User(
            email=email,
            password_hash=hash_password("BisAdmin1"),
            first_name="Admin",
            last_name="Bis",
            phone="0922200001",
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
        json={"email": email, "password": password, "first_name": "Test", "last_name": "User", "phone": "0922200002"},
    )
    return _login(client, email, password)


def _make_product(db_session: Session, *, stock: int = 0, slug: str = "bis-widget") -> Product:
    product = Product(
        name="Back In Stock Widget",
        slug=slug,
        sku=f"SKU-{slug}",
        description="d",
        price=25.0,
        stock_quantity=stock,
        image_url="http://test.com/img.jpg",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


def _make_variant(db_session: Session, product: Product, *, stock: int = 0, sku: str = "BIS-VAR-1") -> ProductVariant:
    variant = ProductVariant(product_id=product.id, sku=sku, name="Variant", price=25.0, stock_quantity=stock)
    db_session.add(variant)
    db_session.commit()
    db_session.refresh(variant)
    return variant


class TestSubscribeValidation:
    def test_requires_authentication(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, stock=0, slug="auth-widget")
        resp = client.post("/back-in-stock", json={"product_id": product.id})
        assert resp.status_code == 401

    def test_rejects_nonexistent_product(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "bis_cust1@test.com", "BisCust1")
        resp = client.post("/back-in-stock", json={"product_id": 999999}, headers=customer)
        assert resp.status_code == 404

    def test_rejects_subscribing_to_an_in_stock_product(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, stock=10, slug="in-stock-widget")
        customer = _register_and_login(client, "bis_cust2@test.com", "BisCust2")

        resp = client.post("/back-in-stock", json={"product_id": product.id}, headers=customer)

        assert resp.status_code == 400
        assert "in stock" in resp.json()["detail"].lower()

    def test_rejects_a_variant_not_belonging_to_the_product(self, client: TestClient, db_session: Session):
        product_a = _make_product(db_session, stock=0, slug="variant-mismatch-a")
        product_b = _make_product(db_session, stock=0, slug="variant-mismatch-b")
        variant_of_b = _make_variant(db_session, product_b, stock=0, sku="MISMATCH-SKU")
        customer = _register_and_login(client, "bis_cust3@test.com", "BisCust3")

        resp = client.post(
            "/back-in-stock",
            json={"product_id": product_a.id, "variant_id": variant_of_b.id},
            headers=customer,
        )

        assert resp.status_code == 404

    def test_successful_subscribe_to_out_of_stock_product(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, stock=0, slug="subscribe-ok-widget")
        customer = _register_and_login(client, "bis_cust4@test.com", "BisCust4")

        resp = client.post("/back-in-stock", json={"product_id": product.id}, headers=customer)

        assert resp.status_code == 201, resp.json()
        data = resp.json()
        assert data["product_id"] == product.id
        assert data["variant_id"] is None
        assert data["notified_at"] is None

    def test_successful_subscribe_to_out_of_stock_variant(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, stock=50, slug="variant-parent-widget")
        variant = _make_variant(db_session, product, stock=0, sku="VARIANT-OOS-SKU")
        customer = _register_and_login(client, "bis_cust5@test.com", "BisCust5")

        # The PRODUCT itself is in stock, but this specific variant isn't —
        # variant subscriptions must be judged by the variant's own pool.
        resp = client.post(
            "/back-in-stock",
            json={"product_id": product.id, "variant_id": variant.id},
            headers=customer,
        )

        assert resp.status_code == 201, resp.json()
        assert resp.json()["variant_id"] == variant.id


class TestSubscriptionLifecycle:
    def test_list_shows_only_my_subscriptions(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, stock=0, slug="list-widget")
        customer_a = _register_and_login(client, "bis_list_a@test.com", "BisListA1")
        customer_b = _register_and_login(client, "bis_list_b@test.com", "BisListB1")

        client.post("/back-in-stock", json={"product_id": product.id}, headers=customer_a)

        a_subs = client.get("/back-in-stock", headers=customer_a).json()
        b_subs = client.get("/back-in-stock", headers=customer_b).json()

        assert len(a_subs) == 1
        assert b_subs == []

    def test_unsubscribe_removes_it(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, stock=0, slug="unsub-widget")
        customer = _register_and_login(client, "bis_unsub@test.com", "BisUnsub1")

        sub_id = client.post("/back-in-stock", json={"product_id": product.id}, headers=customer).json()["id"]
        delete_resp = client.delete(f"/back-in-stock/{sub_id}", headers=customer)

        assert delete_resp.status_code == 204
        assert client.get("/back-in-stock", headers=customer).json() == []

    def test_cannot_unsubscribe_someone_elses_subscription(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, stock=0, slug="unsub-other-widget")
        owner = _register_and_login(client, "bis_owner@test.com", "BisOwner1")
        attacker = _register_and_login(client, "bis_attacker@test.com", "BisAttack1")

        sub_id = client.post("/back-in-stock", json={"product_id": product.id}, headers=owner).json()["id"]
        resp = client.delete(f"/back-in-stock/{sub_id}", headers=attacker)

        assert resp.status_code == 404
        assert len(client.get("/back-in-stock", headers=owner).json()) == 1

    def test_resubscribing_while_still_waiting_does_not_duplicate(
        self, client: TestClient, db_session: Session
    ):
        product = _make_product(db_session, stock=0, slug="resub-waiting-widget")
        customer = _register_and_login(client, "bis_resub1@test.com", "BisResub1")

        first = client.post("/back-in-stock", json={"product_id": product.id}, headers=customer)
        second = client.post("/back-in-stock", json={"product_id": product.id}, headers=customer)

        assert first.json()["id"] == second.json()["id"]
        assert len(client.get("/back-in-stock", headers=customer).json()) == 1


class TestNotificationTrigger:
    """Each of the four places stock_quantity can increase."""

    def test_bulk_inventory_update_triggers_notification(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "bis_bulk_admin@test.com")
        product = _make_product(db_session, stock=0, slug="bulk-trigger-widget")
        customer = _register_and_login(client, "bis_bulk_cust@test.com", "BisBulk1")
        client.post("/back-in-stock", json={"product_id": product.id}, headers=customer)

        admin = _login(client, "bis_bulk_admin@test.com", "BisAdmin1")
        resp = client.patch(
            "/admin/inventory/bulk-update",
            json={"updates": [{"product_id": product.id, "stock_quantity": 20}]},
            headers=admin,
        )
        assert resp.status_code == 200, resp.json()

        db_session.expire_all()
        sub = db_session.scalars(
            select(BackInStockSubscription).where(BackInStockSubscription.product_id == product.id)
        ).first()
        assert sub.notified_at is not None

        outbox = db_session.scalars(
            select(OutboxEvent).where(OutboxEvent.topic == "product.back_in_stock")
        ).first()
        assert outbox is not None
        assert outbox.payload["email"] == "bis_bulk_cust@test.com"

    def test_general_product_update_triggers_notification(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "bis_edit_admin@test.com")
        category = Category(name="Bis Edit Cat", slug="bis-edit-cat")
        db_session.add(category)
        db_session.commit()
        product = _make_product(db_session, stock=0, slug="edit-trigger-widget")
        customer = _register_and_login(client, "bis_edit_cust@test.com", "BisEdit1")
        client.post("/back-in-stock", json={"product_id": product.id}, headers=customer)

        admin = _login(client, "bis_edit_admin@test.com", "BisAdmin1")
        resp = client.put(f"/product/{product.id}", json={"stock_quantity": 15}, headers=admin)
        assert resp.status_code == 200, resp.json()

        db_session.expire_all()
        sub = db_session.scalars(
            select(BackInStockSubscription).where(BackInStockSubscription.product_id == product.id)
        ).first()
        assert sub.notified_at is not None

    def test_variant_update_triggers_notification_scoped_to_the_variant(
        self, client: TestClient, db_session: Session
    ):
        _make_admin(db_session, "bis_variant_admin@test.com")
        product = _make_product(db_session, stock=50, slug="variant-trigger-widget")
        variant = _make_variant(db_session, product, stock=0, sku="VARIANT-TRIGGER-SKU")
        customer = _register_and_login(client, "bis_variant_cust@test.com", "BisVariant1")
        client.post(
            "/back-in-stock",
            json={"product_id": product.id, "variant_id": variant.id},
            headers=customer,
        )

        admin = _login(client, "bis_variant_admin@test.com", "BisAdmin1")
        resp = client.put(f"/product/variants/{variant.id}", json={"stock_quantity": 10}, headers=admin)
        assert resp.status_code == 200, resp.json()

        db_session.expire_all()
        sub = db_session.scalars(
            select(BackInStockSubscription).where(BackInStockSubscription.variant_id == variant.id)
        ).first()
        assert sub.notified_at is not None

    def test_no_notification_when_stock_goes_from_positive_to_positive(
        self, client: TestClient, db_session: Session
    ):
        """Restocking an already-in-stock item isn't a 0 -> positive
        transition and shouldn't fire anything — there's nothing to
        notify about since it was never unavailable."""
        _make_admin(db_session, "bis_noop_admin@test.com")
        product = _make_product(db_session, stock=5, slug="noop-widget")

        admin = _login(client, "bis_noop_admin@test.com", "BisAdmin1")
        resp = client.patch(
            "/admin/inventory/bulk-update",
            json={"updates": [{"product_id": product.id, "stock_quantity": 20}]},
            headers=admin,
        )
        assert resp.status_code == 200

        db_session.expire_all()
        assert (
            db_session.scalars(
                select(OutboxEvent).where(OutboxEvent.topic == "product.back_in_stock")
            ).first()
            is None
        )

    def test_no_notification_when_stock_stays_at_zero(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "bis_stillzero_admin@test.com")
        product = _make_product(db_session, stock=0, slug="stillzero-widget")

        admin = _login(client, "bis_stillzero_admin@test.com", "BisAdmin1")
        resp = client.patch(
            "/admin/inventory/bulk-update",
            json={"updates": [{"product_id": product.id, "stock_quantity": 0}]},
            headers=admin,
        )
        assert resp.status_code == 200

        db_session.expire_all()
        assert (
            db_session.scalars(
                select(OutboxEvent).where(OutboxEvent.topic == "product.back_in_stock")
            ).first()
            is None
        )

    def test_resubscribing_after_notification_rearms_the_same_row(
        self, client: TestClient, db_session: Session
    ):
        _make_admin(db_session, "bis_rearm_admin@test.com")
        product = _make_product(db_session, stock=0, slug="rearm-widget")
        customer = _register_and_login(client, "bis_rearm_cust@test.com", "BisRearm1")

        sub_id = client.post("/back-in-stock", json={"product_id": product.id}, headers=customer).json()["id"]

        admin = _login(client, "bis_rearm_admin@test.com", "BisAdmin1")
        client.patch(
            "/admin/inventory/bulk-update",
            json={"updates": [{"product_id": product.id, "stock_quantity": 5}]},
            headers=admin,
        )
        # Sell back out.
        client.patch(
            "/admin/inventory/bulk-update",
            json={"updates": [{"product_id": product.id, "stock_quantity": 0}]},
            headers=admin,
        )

        resp = client.post("/back-in-stock", json={"product_id": product.id}, headers=customer)

        assert resp.status_code == 201
        assert resp.json()["id"] == sub_id, "re-subscribing should re-arm the same row, not create a new one"
        assert resp.json()["notified_at"] is None


class TestReturnApprovalTriggersNotification:
    def test_restocking_via_an_approved_return_triggers_notification(
        self, client: TestClient, db_session: Session
    ):
        from unittest.mock import MagicMock

        _make_admin(db_session, "bis_return_admin@test.com")
        customer = _register_and_login(client, "bis_return_cust@test.com", "BisReturn1")
        admin = _login(client, "bis_return_admin@test.com", "BisAdmin1")

        client.post("/category", json={"name": "Bis Return Cat", "description": "d"}, headers=admin)
        product = client.post(
            "/product",
            json={
                "name": "Bis Return Widget", "description": "d", "price": 30.0,
                "stock_quantity": 1, "is_active": True, "category_id": 1,
                "image_url": "http://t.com/i.jpg",
            },
            headers=admin,
        ).json()

        client.post("/cart/items", json={"product_id": product["id"], "quantity": 1}, headers=customer)
        addr = client.post(
            "/users/me/address",
            json={"type": "shipping", "street": "s", "city": "c", "state": "s", "postal_code": "1", "country": "c"},
            headers=customer,
        ).json()
        order = client.post(
            "/order", json={"shipping_address_id": addr["id"], "billing_address_id": addr["id"]}, headers=customer
        ).json()

        with patch("stripe.PaymentIntent.create") as mock_create:
            mock_create.return_value = MagicMock(id=f"pi_bis_{order['id']}", client_secret="secret")
            client.post("/payments/create-intent", json={"order_id": order["id"]}, headers=customer)
        with patch("stripe.Webhook.construct_event") as mock_event:
            mock_event.return_value = {
                "id": f"evt_bis_{order['id']}",
                "type": "payment_intent.succeeded",
                "data": {"object": {"id": f"pi_bis_{order['id']}"}},
            }
            client.post("/payments/webhook", content=b"{}", headers={"stripe-signature": "t"})

        client.put(
            f"/admin/orders/{order['id']}/shipping",
            json={"tracking_number": "TRK-BIS-1", "shipping_carrier": "UPS"},
            headers=admin,
        )
        client.put(f"/admin/orders/{order['id']}/status", json={"status": "delivered"}, headers=admin)

        # NOW the product is out of stock (the one unit was sold) — a
        # different customer subscribes before the return is approved.
        another_customer = _register_and_login(client, "bis_return_other@test.com", "BisOther1")
        client.post("/back-in-stock", json={"product_id": product["id"]}, headers=another_customer)

        order_detail = client.get(f"/order/{order['id']}", headers=customer).json()
        order_item_id = order_detail["order_items"][0]["id"]
        return_id = client.post(
            f"/order/{order['id']}/return",
            json={"reason": "wrong size", "items": [{"order_item_id": order_item_id, "quantity": 1, "reason": "n/a"}]},
            headers=customer,
        ).json()["id"]

        with patch("stripe.Refund.create") as mock_refund:
            mock_refund.return_value = MagicMock(id="re_bis_test")
            resolve_resp = client.patch(
                f"/admin/returns/{return_id}",
                json={"status": "approved", "resolution_note": "confirmed"},
                headers=admin,
            )
        assert resolve_resp.status_code == 200, resolve_resp.json()

        db_session.expire_all()
        outbox = db_session.scalars(
            select(OutboxEvent).where(OutboxEvent.topic == "product.back_in_stock")
        ).first()
        assert outbox is not None
        assert outbox.payload["email"] == "bis_return_other@test.com"


class TestEndToEndEmailDelivery:
    """The outbox worker actually turning a queued notification into an
    email, not just writing the outbox row."""

    def test_worker_sends_the_back_in_stock_email(
        self, client: TestClient, db_session: Session, _use_test_db_for_worker
    ):
        _make_admin(db_session, "bis_worker_admin@test.com")
        product = _make_product(db_session, stock=0, slug="worker-widget")
        customer = _register_and_login(client, "bis_worker_cust@test.com", "BisWorker1")
        client.post("/back-in-stock", json={"product_id": product.id}, headers=customer)

        admin = _login(client, "bis_worker_admin@test.com", "BisAdmin1")
        client.patch(
            "/admin/inventory/bulk-update",
            json={"updates": [{"product_id": product.id, "stock_quantity": 10}]},
            headers=admin,
        )

        with patch("app.services.email_service.send_email", new_callable=AsyncMock) as mock_send:
            asyncio.run(process_outbox_events_task({}))

        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs["to_address"] == "bis_worker_cust@test.com"
        assert "back in stock" in mock_send.call_args.kwargs["subject"].lower()

        db_session.expire_all()
        outbox = db_session.scalars(
            select(OutboxEvent).where(OutboxEvent.topic == "product.back_in_stock")
        ).first()
        assert outbox.status == "completed"
