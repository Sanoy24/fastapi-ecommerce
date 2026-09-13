"""
Tests for loyalty points: earning on a successful payment, redeeming for a
checkout discount, and reversing both on cancellation/refund.

Points are only ever earned/reversed inside PaymentService's real webhook
handler (_handle_successful_payment / refund_payment) — the same place
stock is deducted/restored — so tests that need points actually awarded go
through POST /payments/webhook rather than poking Order.payment_status
directly the way some other tests' "paid order" helpers do.
"""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.loyalty_transaction import LoyaltyTransaction
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.utils.security import hash_password

VALID_ADDRESS = {
    "street": "1 Loyalty Ave",
    "city": "Loyaltyville",
    "state": "LS",
    "postal_code": "00001",
    "country": "Loyaltyland",
}


def _make_admin(db: Session, email: str = "loyalty_admin@test.com") -> None:
    db.add(User(
        email=email, password_hash=hash_password("LoyaltyAdmin1"),
        first_name="Admin", last_name="Loyalty", phone="0966600001",
        is_verified=True, role="admin",
    ))
    db.commit()


def _register_and_login(client: TestClient, email: str, password: str) -> dict:
    client.post(
        "/users/register",
        json={"email": email, "password": password, "first_name": "Test", "last_name": "User", "phone": "0966600002"},
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
        name="Loyalty Widget", slug=slug, description="For loyalty tests",
        price=price, stock_quantity=stock, image_url="https://example.com/img.jpg",
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def _set_balance(db: Session, email: str, points: int) -> None:
    user = db.query(User).filter(User.email == email).one()
    user.loyalty_points_balance = points
    db.commit()


def _get_user(db: Session, email: str) -> User:
    db.expire_all()
    return db.query(User).filter(User.email == email).one()


def _get_order(db: Session, order_id: int) -> Order:
    db.expire_all()
    return db.query(Order).filter(Order.id == order_id).one()


def _pay_order_via_webhook(client: TestClient, order_id: int, headers: dict, transaction_id: str):
    """Drive an order to paid + points-earned through the real webhook
    path, not a direct DB write — _handle_successful_payment (stock
    deduction, points earning) only runs from here."""
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
        resp = client.post(
            "/payments/webhook", content=b"{}", headers={"Stripe-Signature": "test_signature"}
        )
        assert resp.status_code == 200, resp.json()


class TestRedeemPointsValidation:
    def test_anonymous_cannot_redeem_points(self, client: TestClient, db_session: Session):
        resp = client.put("/cart/points", json={"points": 100})
        assert resp.status_code == 401

    def test_redeeming_more_points_than_balance_is_rejected(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "loy_over@test.com", "LoyOver123")
        _set_balance(db_session, "loy_over@test.com", 10)

        resp = client.put("/cart/points", json={"points": 500}, headers=customer)
        assert resp.status_code == 400
        assert "10" in resp.json()["detail"]

    def test_redeeming_zero_or_negative_points_is_rejected(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "loy_zero@test.com", "LoyZero123")
        resp = client.put("/cart/points", json={"points": 0}, headers=customer)
        assert resp.status_code == 422


class TestCartPointsDiscount:
    def test_redeeming_points_reduces_cart_total_and_is_shown_on_get_cart(
        self, client: TestClient, db_session: Session
    ):
        customer = _register_and_login(client, "loy_cart@test.com", "LoyCart123")
        _set_balance(db_session, "loy_cart@test.com", 1000)
        product = _make_product(db_session, slug="loy-cart-widget", price=100.0)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)

        before = client.get("/cart", headers=customer).json()
        assert before["total_amount"] == 100.0
        assert before["loyalty_points_balance"] == 1000

        resp = client.put("/cart/points", json={"points": 500}, headers=customer)
        assert resp.status_code == 200, resp.json()

        after = client.get("/cart", headers=customer).json()
        # 500 points * settings.POINTS_REDEMPTION_VALUE (0.01) == $5 off
        assert after["points_redeemed"] == 500
        assert after["points_discount_amount"] == 5.0
        assert after["total_amount"] == 95.0

    def test_removing_points_resets_the_discount(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "loy_remove@test.com", "LoyRemove123")
        _set_balance(db_session, "loy_remove@test.com", 1000)
        product = _make_product(db_session, slug="loy-remove-widget", price=100.0)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
        client.put("/cart/points", json={"points": 500}, headers=customer)

        resp = client.delete("/cart/points", headers=customer)
        assert resp.status_code == 200, resp.json()

        after = client.get("/cart", headers=customer).json()
        assert after["points_redeemed"] == 0
        assert after["points_discount_amount"] == 0.0
        assert after["total_amount"] == 100.0

    def test_a_redemption_that_would_exceed_the_subtotal_is_capped_not_negative(
        self, client: TestClient, db_session: Session
    ):
        customer = _register_and_login(client, "loy_cap@test.com", "LoyCap123")
        _set_balance(db_session, "loy_cap@test.com", 100000)
        product = _make_product(db_session, slug="loy-cap-widget", price=10.0)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)

        # 100000 points * 0.01 == $1000 off a $10 cart — must cap at $10.
        client.put("/cart/points", json={"points": 100000}, headers=customer)
        after = client.get("/cart", headers=customer).json()
        assert after["points_discount_amount"] == 10.0
        assert after["total_amount"] == 0.0


class TestCheckoutPointsRedemption:
    def test_placing_an_order_deducts_points_and_snapshots_the_redemption(
        self, client: TestClient, db_session: Session
    ):
        customer = _register_and_login(client, "loy_checkout@test.com", "LoyCheckout123")
        _set_balance(db_session, "loy_checkout@test.com", 1000)
        product = _make_product(db_session, slug="loy-checkout-widget", price=100.0)
        address_id = _make_address(client, customer)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
        client.put("/cart/points", json={"points": 500}, headers=customer)

        order_resp = client.post(
            "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=customer
        )
        assert order_resp.status_code == 201, order_resp.json()
        order = order_resp.json()

        assert order["points_redeemed"] == 500
        assert order["total_amount"] == 95.0

        user = _get_user(db_session, "loy_checkout@test.com")
        assert user.loyalty_points_balance == 500

        ledger = db_session.query(LoyaltyTransaction).filter_by(order_id=order["id"]).one()
        assert ledger.transaction_type == "redeem"
        assert ledger.points == -500

    def test_checkout_rechecks_balance_and_rejects_a_since_reduced_balance(
        self, client: TestClient, db_session: Session
    ):
        """Regression target for the same class of bug as coupon reuse:
        cart.points_redeemed is only validated against the balance at the
        moment PUT /cart/points was called — the balance could have since
        dropped (e.g. spent by a concurrent order), so checkout must
        re-check it rather than trusting what the cart already recorded."""
        customer = _register_and_login(client, "loy_recheck@test.com", "LoyRecheck123")
        _set_balance(db_session, "loy_recheck@test.com", 500)
        product = _make_product(db_session, slug="loy-recheck-widget", price=100.0)
        address_id = _make_address(client, customer)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
        client.put("/cart/points", json={"points": 500}, headers=customer)

        # Balance drops after the cart already recorded the redemption.
        _set_balance(db_session, "loy_recheck@test.com", 100)

        order_resp = client.post(
            "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=customer
        )
        assert order_resp.status_code == 400
        assert "loyalty points" in order_resp.json()["detail"].lower()

        # Nothing should have been deducted from the now-insufficient balance.
        user = _get_user(db_session, "loy_recheck@test.com")
        assert user.loyalty_points_balance == 100


class TestPointsEarnedOnPayment:
    def test_successful_payment_awards_points_based_on_base_currency_total(
        self, client: TestClient, db_session: Session
    ):
        customer = _register_and_login(client, "loy_earn@test.com", "LoyEarn123")
        product = _make_product(db_session, slug="loy-earn-widget", price=100.0)
        address_id = _make_address(client, customer)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
        order = client.post(
            "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=customer
        ).json()

        _pay_order_via_webhook(client, order["id"], customer, "pi_loy_earn")

        # POINTS_EARNED_PER_BASE_CURRENCY_UNIT defaults to 1.0, so a $100
        # order earns 100 points.
        user = _get_user(db_session, "loy_earn@test.com")
        assert user.loyalty_points_balance == 100

        order_row = _get_order(db_session, order["id"])
        assert order_row.points_earned == 100

        ledger = db_session.query(LoyaltyTransaction).filter_by(order_id=order["id"]).one()
        assert ledger.transaction_type == "earn"
        assert ledger.points == 100

    def test_guest_order_payment_success_awards_no_points(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="loy-guest-widget", price=100.0)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1})
        order = client.post(
            "/order/guest",
            json={"email": "loy_guest@test.com", "shipping_address": VALID_ADDRESS, "billing_address": VALID_ADDRESS},
        ).json()

        with patch("stripe.PaymentIntent.create") as mock_create:
            mock_create.return_value = MagicMock(id="pi_loy_guest", client_secret="s")
            resp = client.post(
                "/payments/guest/create-intent",
                json={"order_number": order["order_number"], "email": "loy_guest@test.com"},
            )
            assert resp.status_code == 200, resp.json()

        with patch("stripe.Webhook.construct_event") as mock_construct:
            mock_construct.return_value = {
                "id": "evt_loy_guest",
                "type": "payment_intent.succeeded",
                "data": {"object": {"id": "pi_loy_guest"}},
            }
            resp = client.post(
                "/payments/webhook", content=b"{}", headers={"Stripe-Signature": "test_signature"}
            )
            assert resp.status_code == 200, resp.json()

        order_row = _get_order(db_session, order["id"])
        assert order_row.points_earned == 0
        assert db_session.query(LoyaltyTransaction).filter_by(order_id=order["id"]).count() == 0


class TestPointsReversal:
    def test_cancelling_a_pending_order_restores_redeemed_points(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "loy_cancel@test.com", "LoyCancel123")
        _set_balance(db_session, "loy_cancel@test.com", 1000)
        product = _make_product(db_session, slug="loy-cancel-widget", price=100.0)
        address_id = _make_address(client, customer)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
        client.put("/cart/points", json={"points": 500}, headers=customer)
        order = client.post(
            "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=customer
        ).json()
        assert _get_user(db_session, "loy_cancel@test.com").loyalty_points_balance == 500

        resp = client.post(f"/order/{order['id']}/cancel", headers=customer)
        assert resp.status_code == 200, resp.json()

        user = _get_user(db_session, "loy_cancel@test.com")
        assert user.loyalty_points_balance == 1000

        reversal = (
            db_session.query(LoyaltyTransaction)
            .filter_by(order_id=order["id"], transaction_type="reversal")
            .one()
        )
        assert reversal.points == 500

    def test_refunding_an_order_claws_back_earned_points_and_restores_redeemed_points(
        self, client: TestClient, db_session: Session
    ):
        """A single order can both redeem existing points (as a checkout
        discount) and earn new ones (once paid) — refunding it should
        reverse both halves. With nothing else touching the balance in
        between, the net effect is the balance ending up exactly back
        where it started before this order.
        """
        _make_admin(db_session, "loy_refund_admin@test.com")
        admin = _login(client, "loy_refund_admin@test.com", "LoyaltyAdmin1")
        customer = _register_and_login(client, "loy_refund@test.com", "LoyRefund123")
        _set_balance(db_session, "loy_refund@test.com", 1000)
        product = _make_product(db_session, slug="loy-refund-widget", price=100.0)
        address_id = _make_address(client, customer)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
        client.put("/cart/points", json={"points": 500}, headers=customer)
        order = client.post(
            "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=customer
        ).json()
        assert order["total_amount"] == 95.0  # 100 - 500*0.01

        _pay_order_via_webhook(client, order["id"], customer, "pi_loy_refund")
        mid_balance = _get_user(db_session, "loy_refund@test.com").loyalty_points_balance
        assert mid_balance == 500 + 95  # redeemed 500 away, earned 95 back

        with patch("stripe.Refund.create") as mock_refund:
            mock_refund.return_value = MagicMock(id="re_loy_refund")
            resp = client.post(
                f"/admin/orders/{order['id']}/refund",
                json={"amount": 95.0, "reason": "requested_by_customer"},
                headers=admin,
            )
        assert resp.status_code == 200, resp.json()

        user = _get_user(db_session, "loy_refund@test.com")
        assert user.loyalty_points_balance == 1000

        reversals = (
            db_session.query(LoyaltyTransaction)
            .filter_by(order_id=order["id"], transaction_type="reversal")
            .all()
        )
        assert {(r.points) for r in reversals} == {-95, 500}

    def test_refund_clawback_is_capped_when_earned_points_were_already_spent(
        self, client: TestClient, db_session: Session
    ):
        """Regression target: naively subtracting order.points_earned on
        refund could drive the balance negative if the customer already
        spent those points on a later order — the clawback must be capped
        at whatever balance is still actually there."""
        _make_admin(db_session, "loy_cap_admin@test.com")
        admin = _login(client, "loy_cap_admin@test.com", "LoyaltyAdmin1")
        customer = _register_and_login(client, "loy_spent@test.com", "LoySpent123")

        product_a = _make_product(db_session, slug="loy-spent-widget-a", price=100.0)
        address_id = _make_address(client, customer)
        client.post("/cart/items", json={"product_id": product_a.id, "quantity": 1}, headers=customer)
        order_a = client.post(
            "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=customer
        ).json()
        _pay_order_via_webhook(client, order_a["id"], customer, "pi_loy_spent_a")
        assert _get_user(db_session, "loy_spent@test.com").loyalty_points_balance == 100

        # Spend all 100 earned points on a second order before order_a is refunded.
        product_b = _make_product(db_session, slug="loy-spent-widget-b", price=100.0)
        client.post("/cart/items", json={"product_id": product_b.id, "quantity": 1}, headers=customer)
        client.put("/cart/points", json={"points": 100}, headers=customer)
        client.post(
            "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=customer
        )
        assert _get_user(db_session, "loy_spent@test.com").loyalty_points_balance == 0

        with patch("stripe.Refund.create") as mock_refund:
            mock_refund.return_value = MagicMock(id="re_loy_spent")
            resp = client.post(
                f"/admin/orders/{order_a['id']}/refund",
                json={"amount": 100.0, "reason": "requested_by_customer"},
                headers=admin,
            )
        assert resp.status_code == 200, resp.json()

        # Capped at 0, not driven negative.
        user = _get_user(db_session, "loy_spent@test.com")
        assert user.loyalty_points_balance == 0

        # No zero-point no-op clawback row should have been written.
        assert db_session.query(LoyaltyTransaction).filter_by(
            order_id=order_a["id"], transaction_type="reversal"
        ).count() == 0


class TestLoyaltyEndpoints:
    def test_balance_and_transactions_endpoints(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "loy_endpoints@test.com", "LoyEndpoints123")
        product = _make_product(db_session, slug="loy-endpoints-widget", price=100.0)
        address_id = _make_address(client, customer)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
        order = client.post(
            "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=customer
        ).json()
        _pay_order_via_webhook(client, order["id"], customer, "pi_loy_endpoints")

        balance_resp = client.get("/loyalty/balance", headers=customer)
        assert balance_resp.status_code == 200
        assert balance_resp.json()["points_balance"] == 100

        tx_resp = client.get("/loyalty/transactions", headers=customer)
        assert tx_resp.status_code == 200
        body = tx_resp.json()
        assert body["total"] == 1
        assert body["transactions"][0]["transaction_type"] == "earn"
        assert body["transactions"][0]["points"] == 100

    def test_transactions_endpoint_requires_login(self, client: TestClient, db_session: Session):
        resp = client.get("/loyalty/transactions")
        assert resp.status_code == 401
