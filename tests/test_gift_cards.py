"""
Tests for gift cards (admin-issued, redeemed once into store credit) and
store credit (a fungible wallet balance spent at checkout), mirroring the
loyalty-points test suite's structure and rigor — see test_loyalty_points.py
for the reasoning behind going through the real webhook/cancel/refund paths
rather than poking Order fields directly.
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.product import Product
from app.models.store_credit_transaction import StoreCreditTransaction
from app.models.user import User
from app.utils.security import hash_password

VALID_ADDRESS = {
    "street": "1 Gift Ave",
    "city": "Giftville",
    "state": "GS",
    "postal_code": "00001",
    "country": "Giftland",
}


def _make_admin(db: Session, email: str = "gift_admin@test.com") -> None:
    db.add(User(
        email=email, password_hash=hash_password("GiftAdmin1"),
        first_name="Admin", last_name="Gift", phone="0977700001",
        is_verified=True, role="admin",
    ))
    db.commit()


def _register_and_login(client: TestClient, email: str, password: str) -> dict:
    client.post(
        "/users/register",
        json={"email": email, "password": password, "first_name": "Test", "last_name": "User", "phone": "0977700002"},
    )
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _make_address(client: TestClient, headers: dict) -> int:
    resp = client.post("/users/me/address", headers=headers, json={"type": "home", "is_default": True, **VALID_ADDRESS})
    return resp.json()["id"]


def _make_product(db: Session, *, slug: str, price: float = 100.0, stock: int = 50) -> Product:
    product = Product(
        name="Gift Widget", slug=slug, description="For gift card tests",
        price=price, stock_quantity=stock, image_url="https://example.com/img.jpg",
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def _issue_gift_card(client: TestClient, admin: dict, value: float = 50.0, **overrides) -> dict:
    payload = {"value": value, **overrides}
    resp = client.post("/admin/gift-cards", json=payload, headers=admin)
    assert resp.status_code == 201, resp.json()
    return resp.json()


def _get_user(db: Session, email: str) -> User:
    db.expire_all()
    return db.query(User).filter(User.email == email).one()


def _get_order(db: Session, order_id: int) -> Order:
    db.expire_all()
    return db.query(Order).filter(Order.id == order_id).one()


def _pay_order_via_webhook(client: TestClient, order_id: int, headers: dict, transaction_id: str):
    with patch("stripe.PaymentIntent.create") as mock_create:
        mock_create.return_value = MagicMock(id=transaction_id, client_secret="s")
        resp = client.post("/payments/create-intent", json={"order_id": order_id}, headers=headers)
        assert resp.status_code == 200, resp.json()

    with patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = {
            "id": f"evt_{transaction_id}",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": transaction_id}},
        }
        resp = client.post("/payments/webhook", content=b"{}", headers={"Stripe-Signature": "test_signature"})
        assert resp.status_code == 200, resp.json()


class TestGiftCardIssuance:
    def test_non_admin_cannot_issue_gift_cards(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "gc_nonadmin@test.com", "GcNonadmin1")
        resp = client.post("/admin/gift-cards", json={"value": 50.0}, headers=customer)
        assert resp.status_code == 403

    def test_admin_can_issue_and_list_gift_cards(self, client: TestClient, db_session: Session):
        _make_admin(db_session)
        admin = _login(client, "gift_admin@test.com", "GiftAdmin1")

        card = _issue_gift_card(client, admin, value=25.0, note="Goodwill credit")
        assert card["value"] == 25.0
        assert card["is_redeemed"] is False
        assert card["code"].startswith("GIFT-")

        listing = client.get("/admin/gift-cards", headers=admin)
        assert listing.status_code == 200
        assert any(c["code"] == card["code"] for c in listing.json())


class TestGiftCardRedemption:
    def test_redeeming_a_code_credits_store_credit_balance(self, client: TestClient, db_session: Session):
        _make_admin(db_session)
        admin = _login(client, "gift_admin@test.com", "GiftAdmin1")
        card = _issue_gift_card(client, admin, value=40.0)

        customer = _register_and_login(client, "gc_redeem@test.com", "GcRedeem123")
        resp = client.post("/gift-cards/redeem", json={"code": card["code"]}, headers=customer)
        assert resp.status_code == 200, resp.json()
        assert resp.json()["is_redeemed"] is True

        user = _get_user(db_session, "gc_redeem@test.com")
        assert float(user.store_credit_balance) == 40.0

        ledger = db_session.query(StoreCreditTransaction).filter_by(user_id=user.id).one()
        assert ledger.transaction_type == "redeem_gift_card"
        assert float(ledger.amount) == 40.0

    def test_redeeming_an_already_redeemed_code_fails(self, client: TestClient, db_session: Session):
        _make_admin(db_session)
        admin = _login(client, "gift_admin@test.com", "GiftAdmin1")
        card = _issue_gift_card(client, admin, value=20.0)

        customer_a = _register_and_login(client, "gc_first@test.com", "GcFirst123")
        client.post("/gift-cards/redeem", json={"code": card["code"]}, headers=customer_a)

        customer_b = _register_and_login(client, "gc_second@test.com", "GcSecond123")
        resp = client.post("/gift-cards/redeem", json={"code": card["code"]}, headers=customer_b)
        assert resp.status_code == 400
        assert "already" in resp.json()["detail"].lower()

    def test_redeeming_an_expired_code_fails(self, client: TestClient, db_session: Session):
        _make_admin(db_session)
        admin = _login(client, "gift_admin@test.com", "GiftAdmin1")
        past = (datetime.now() - timedelta(days=1)).isoformat()
        card = _issue_gift_card(client, admin, value=20.0, expires_at=past)

        customer = _register_and_login(client, "gc_expired@test.com", "GcExpired123")
        resp = client.post("/gift-cards/redeem", json={"code": card["code"]}, headers=customer)
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower()

    def test_redeeming_an_unknown_code_returns_404(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "gc_unknown@test.com", "GcUnknown123")
        resp = client.post("/gift-cards/redeem", json={"code": "GIFT-DOESNOTEXIST"}, headers=customer)
        assert resp.status_code == 404


def _set_store_credit(db: Session, email: str, amount: float) -> None:
    user = db.query(User).filter(User.email == email).one()
    user.store_credit_balance = amount
    db.commit()


class TestApplyStoreCreditToCart:
    def test_anonymous_cannot_apply_store_credit(self, client: TestClient, db_session: Session):
        resp = client.put("/cart/store-credit", json={"amount": 10.0})
        assert resp.status_code == 401

    def test_applying_more_than_balance_is_rejected(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "gc_over@test.com", "GcOver123")
        _set_store_credit(db_session, "gc_over@test.com", 5.0)
        resp = client.put("/cart/store-credit", json={"amount": 50.0}, headers=customer)
        assert resp.status_code == 400

    def test_applying_store_credit_reduces_cart_total(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "gc_cart@test.com", "GcCart123")
        _set_store_credit(db_session, "gc_cart@test.com", 100.0)
        product = _make_product(db_session, slug="gc-cart-widget", price=100.0)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)

        resp = client.put("/cart/store-credit", json={"amount": 30.0}, headers=customer)
        assert resp.status_code == 200, resp.json()

        cart = client.get("/cart", headers=customer).json()
        assert cart["store_credit_applied"] == 30.0
        assert cart["store_credit_discount_amount"] == 30.0
        assert cart["total_amount"] == 70.0

    def test_removing_store_credit_resets_discount(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "gc_remove@test.com", "GcRemove123")
        _set_store_credit(db_session, "gc_remove@test.com", 100.0)
        product = _make_product(db_session, slug="gc-remove-widget", price=100.0)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
        client.put("/cart/store-credit", json={"amount": 30.0}, headers=customer)

        resp = client.delete("/cart/store-credit", headers=customer)
        assert resp.status_code == 200, resp.json()

        cart = client.get("/cart", headers=customer).json()
        assert cart["store_credit_applied"] == 0.0
        assert cart["total_amount"] == 100.0


class TestCheckoutStoreCreditRedemption:
    def test_placing_an_order_deducts_store_credit_and_snapshots_it(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "gc_checkout@test.com", "GcCheckout123")
        _set_store_credit(db_session, "gc_checkout@test.com", 100.0)
        product = _make_product(db_session, slug="gc-checkout-widget", price=100.0)
        address_id = _make_address(client, customer)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
        client.put("/cart/store-credit", json={"amount": 40.0}, headers=customer)

        order_resp = client.post(
            "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=customer
        )
        assert order_resp.status_code == 201, order_resp.json()
        order = order_resp.json()
        assert order["store_credit_applied"] == 40.0
        assert order["total_amount"] == 60.0

        user = _get_user(db_session, "gc_checkout@test.com")
        assert float(user.store_credit_balance) == 60.0

        ledger = db_session.query(StoreCreditTransaction).filter_by(order_id=order["id"]).one()
        assert ledger.transaction_type == "spend"
        assert float(ledger.amount) == -40.0

    def test_checkout_rechecks_balance_and_rejects_a_since_reduced_balance(
        self, client: TestClient, db_session: Session
    ):
        customer = _register_and_login(client, "gc_recheck@test.com", "GcRecheck123")
        _set_store_credit(db_session, "gc_recheck@test.com", 50.0)
        product = _make_product(db_session, slug="gc-recheck-widget", price=100.0)
        address_id = _make_address(client, customer)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
        client.put("/cart/store-credit", json={"amount": 50.0}, headers=customer)

        _set_store_credit(db_session, "gc_recheck@test.com", 10.0)

        order_resp = client.post(
            "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=customer
        )
        assert order_resp.status_code == 400
        assert "store credit" in order_resp.json()["detail"].lower()

        user = _get_user(db_session, "gc_recheck@test.com")
        assert float(user.store_credit_balance) == 10.0


class TestStoreCreditReversal:
    def test_cancelling_a_pending_order_restores_store_credit(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "gc_cancel@test.com", "GcCancel123")
        _set_store_credit(db_session, "gc_cancel@test.com", 100.0)
        product = _make_product(db_session, slug="gc-cancel-widget", price=100.0)
        address_id = _make_address(client, customer)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
        client.put("/cart/store-credit", json={"amount": 40.0}, headers=customer)
        order = client.post(
            "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=customer
        ).json()
        assert float(_get_user(db_session, "gc_cancel@test.com").store_credit_balance) == 60.0

        resp = client.post(f"/order/{order['id']}/cancel", headers=customer)
        assert resp.status_code == 200, resp.json()

        user = _get_user(db_session, "gc_cancel@test.com")
        assert float(user.store_credit_balance) == 100.0

    def test_refunding_an_order_restores_applied_store_credit(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "gc_refund_admin@test.com")
        admin = _login(client, "gc_refund_admin@test.com", "GiftAdmin1")
        customer = _register_and_login(client, "gc_refund@test.com", "GcRefund123")
        _set_store_credit(db_session, "gc_refund@test.com", 100.0)
        product = _make_product(db_session, slug="gc-refund-widget", price=100.0)
        address_id = _make_address(client, customer)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
        client.put("/cart/store-credit", json={"amount": 40.0}, headers=customer)
        order = client.post(
            "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=customer
        ).json()
        assert order["total_amount"] == 60.0

        _pay_order_via_webhook(client, order["id"], customer, "pi_gc_refund")
        assert float(_get_user(db_session, "gc_refund@test.com").store_credit_balance) == 60.0

        with patch("stripe.Refund.create") as mock_refund:
            mock_refund.return_value = MagicMock(id="re_gc_refund")
            resp = client.post(
                f"/admin/orders/{order['id']}/refund",
                json={"amount": 60.0, "reason": "requested_by_customer"},
                headers=admin,
            )
        assert resp.status_code == 200, resp.json()

        user = _get_user(db_session, "gc_refund@test.com")
        assert float(user.store_credit_balance) == 100.0

        reversal = (
            db_session.query(StoreCreditTransaction)
            .filter_by(order_id=order["id"], transaction_type="reversal")
            .one()
        )
        assert float(reversal.amount) == 40.0


class TestCombinedDiscountsDoNotGoNegative:
    def test_points_and_store_credit_stacked_are_capped_at_zero(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "gc_stack@test.com", "GcStack123")
        _set_store_credit(db_session, "gc_stack@test.com", 1000.0)
        db_session.query(User).filter(User.email == "gc_stack@test.com").update({"loyalty_points_balance": 100000})
        db_session.commit()

        product = _make_product(db_session, slug="gc-stack-widget", price=10.0)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
        client.put("/cart/points", json={"points": 100000}, headers=customer)  # $1000 off
        client.put("/cart/store-credit", json={"amount": 1000.0}, headers=customer)  # another $1000 off

        cart = client.get("/cart", headers=customer).json()
        assert cart["total_amount"] == 0.0
