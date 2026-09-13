"""
Tests for multi-currency support: admin-managed exchange rates, the public
currency list, cart currency selection with converted display amounts, and
checkout/payment actually charging in the selected currency.

Product prices and every Order monetary column stay in the store's base
currency (USD in these tests) always — see app/models/currency.py and
Order.currency_code's docstring for why. These tests check the conversion
happens at the right layer (display on the cart, the actual Stripe charge)
without ever touching that base-currency accounting.
"""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.payment import Payment
from app.models.product import Product
from app.models.user import User
from app.utils.security import hash_password


def _make_admin(db_session: Session, email: str = "cur_admin@test.com") -> None:
    db_session.add(
        User(
            email=email, password_hash=hash_password("CurAdmin123"),
            first_name="Admin", last_name="Cur", phone="0977700009",
            is_verified=True, role="admin",
        )
    )
    db_session.commit()


def _register_and_login(client: TestClient, email: str, password: str) -> dict:
    client.post(
        "/users/register",
        json={"email": email, "password": password, "first_name": "Test", "last_name": "User", "phone": "0977700010"},
    )
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _make_eur(client: TestClient, admin_headers: dict, rate: float = 0.90) -> None:
    resp = client.post(
        "/admin/currencies",
        json={"code": "EUR", "name": "Euro", "symbol": "€", "exchange_rate_to_base": rate},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.json()


def _make_product(db_session: Session, *, slug: str = "cur-widget", price: float = 100.0, stock: int = 20) -> Product:
    product = Product(
        name="Currency Widget", slug=slug, sku=f"SKU-{slug}", description="d",
        price=price, stock_quantity=stock, image_url="http://t.com/i.jpg", status="active",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


def _make_address(client: TestClient, headers: dict) -> int:
    resp = client.post(
        "/users/me/address",
        json={"type": "shipping", "street": "1 Cur St", "city": "Cur City", "state": "CS", "zip_code": "33333", "country": "Curland"},
        headers=headers,
    )
    return resp.json()["id"]


class TestAdminCurrencyCrud:
    def test_create_requires_admin(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "cur_cust1@test.com", "CurCust123")
        resp = client.post(
            "/admin/currencies",
            json={"code": "EUR", "name": "Euro", "symbol": "€", "exchange_rate_to_base": 0.9},
            headers=customer,
        )
        assert resp.status_code == 403

    def test_admin_can_create_a_currency(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "cur_admin1@test.com")
        admin = _login(client, "cur_admin1@test.com", "CurAdmin123")

        resp = client.post(
            "/admin/currencies",
            json={"code": "eur", "name": "Euro", "symbol": "€", "exchange_rate_to_base": 0.9},
            headers=admin,
        )

        assert resp.status_code == 201, resp.json()
        assert resp.json()["code"] == "EUR"
        assert resp.json()["is_active"] is True

    def test_rejects_a_duplicate_code(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "cur_admin2@test.com")
        admin = _login(client, "cur_admin2@test.com", "CurAdmin123")
        _make_eur(client, admin)

        resp = client.post(
            "/admin/currencies",
            json={"code": "EUR", "name": "Euro Again", "symbol": "€", "exchange_rate_to_base": 0.85},
            headers=admin,
        )

        assert resp.status_code == 400

    def test_admin_can_update_the_exchange_rate(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "cur_admin3@test.com")
        admin = _login(client, "cur_admin3@test.com", "CurAdmin123")
        _make_eur(client, admin, rate=0.90)

        resp = client.patch("/admin/currencies/EUR/rate", json={"exchange_rate_to_base": 0.95}, headers=admin)

        assert resp.status_code == 200
        assert resp.json()["exchange_rate_to_base"] == 0.95

    def test_admin_can_deactivate_and_reactivate(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "cur_admin4@test.com")
        admin = _login(client, "cur_admin4@test.com", "CurAdmin123")
        _make_eur(client, admin)

        deactivate_resp = client.post("/admin/currencies/EUR/deactivate", headers=admin)
        assert deactivate_resp.status_code == 200
        assert deactivate_resp.json()["is_active"] is False
        assert "EUR" not in [c["code"] for c in client.get("/currencies").json()]

        reactivate_resp = client.post("/admin/currencies/EUR/activate", headers=admin)
        assert reactivate_resp.status_code == 200
        assert "EUR" in [c["code"] for c in client.get("/currencies").json()]

    def test_cannot_deactivate_the_base_currency(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "cur_admin5@test.com")
        admin = _login(client, "cur_admin5@test.com", "CurAdmin123")

        resp = client.post("/admin/currencies/USD/deactivate", headers=admin)

        assert resp.status_code == 400


class TestPublicCurrencyList:
    def test_lists_the_base_currency_by_default(self, client: TestClient, db_session: Session):
        resp = client.get("/currencies")
        assert resp.status_code == 200
        assert any(c["code"] == "USD" for c in resp.json())


class TestCartCurrency:
    def test_set_currency_requires_it_to_exist_and_be_active(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "cur_cart1@test.com", "CurCart123")

        resp = client.put("/cart/currency", json={"currency_code": "EUR"}, headers=customer)

        assert resp.status_code == 404

    def test_cart_shows_converted_display_amount(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "cur_admin6@test.com")
        admin = _login(client, "cur_admin6@test.com", "CurAdmin123")
        _make_eur(client, admin, rate=0.90)

        customer = _register_and_login(client, "cur_cart2@test.com", "CurCart223")
        product = _make_product(db_session, slug="cart-eur-widget", price=100.0)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)

        set_resp = client.put("/cart/currency", json={"currency_code": "EUR"}, headers=customer)
        assert set_resp.status_code == 200

        cart = client.get("/cart", headers=customer).json()
        assert cart["currency_code"] == "EUR"
        assert cart["subtotal"] == 100.0  # base currency, unchanged
        assert cart["display_subtotal"] == 90.0  # 100 * 0.90

    def test_clearing_currency_reverts_to_base(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "cur_admin7@test.com")
        admin = _login(client, "cur_admin7@test.com", "CurAdmin123")
        _make_eur(client, admin)

        customer = _register_and_login(client, "cur_cart3@test.com", "CurCart323")
        client.put("/cart/currency", json={"currency_code": "EUR"}, headers=customer)

        resp = client.delete("/cart/currency", headers=customer)
        assert resp.status_code == 200

        cart = client.get("/cart", headers=customer).json()
        assert cart["currency_code"] == "USD"
        assert cart["display_subtotal"] == cart["subtotal"]


class TestCheckoutAndPaymentInSelectedCurrency:
    def test_order_snapshots_the_selected_currency_and_rate(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "cur_admin8@test.com")
        admin = _login(client, "cur_admin8@test.com", "CurAdmin123")
        _make_eur(client, admin, rate=0.90)

        customer = _register_and_login(client, "cur_checkout1@test.com", "CurCheck123")
        product = _make_product(db_session, slug="checkout-eur-widget", price=50.0)
        address_id = _make_address(client, customer)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 2}, headers=customer)
        client.put("/cart/currency", json={"currency_code": "EUR"}, headers=customer)

        order_resp = client.post(
            "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=customer
        )

        assert order_resp.status_code == 201, order_resp.json()
        data = order_resp.json()
        assert data["currency_code"] == "EUR"
        assert data["exchange_rate_at_purchase"] == 0.9
        assert data["total_amount"] == 100.0  # still base currency (2 * 50)

    def test_order_without_a_selected_currency_defaults_to_base(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "cur_checkout2@test.com", "CurCheck223")
        product = _make_product(db_session, slug="checkout-base-widget", price=20.0)
        address_id = _make_address(client, customer)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)

        order_resp = client.post(
            "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=customer
        )

        assert order_resp.status_code == 201, order_resp.json()
        assert order_resp.json()["currency_code"] == "USD"
        assert order_resp.json()["exchange_rate_at_purchase"] == 1.0

    def test_stripe_is_charged_in_the_converted_amount_and_currency(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "cur_admin9@test.com")
        admin = _login(client, "cur_admin9@test.com", "CurAdmin123")
        _make_eur(client, admin, rate=0.90)

        customer = _register_and_login(client, "cur_checkout3@test.com", "CurCheck323")
        product = _make_product(db_session, slug="checkout-charge-widget", price=50.0)
        address_id = _make_address(client, customer)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 2}, headers=customer)
        client.put("/cart/currency", json={"currency_code": "EUR"}, headers=customer)
        order = client.post(
            "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=customer
        ).json()

        with patch("stripe.PaymentIntent.create") as mock_create:
            mock_create.return_value = MagicMock(id="pi_eur_charge", client_secret="secret_eur")
            resp = client.post("/payments/create-intent", json={"order_id": order["id"]}, headers=customer)

        assert resp.status_code == 200, resp.json()
        assert resp.json()["currency"] == "eur"
        assert resp.json()["amount"] == 90.0  # 100 (base subtotal, no tax/shipping) * 0.90

        mock_create.assert_called_once()
        assert mock_create.call_args.kwargs["currency"] == "eur"
        assert mock_create.call_args.kwargs["amount"] == 9000  # cents

        db_session.expire_all()
        payment = db_session.query(Payment).filter_by(order_id=order["id"]).first()
        assert payment.currency_code == "EUR"
        assert float(payment.amount) == 90.0

    def test_zero_decimal_currency_amount_is_not_multiplied_by_100(self, client: TestClient, db_session: Session):
        """JPY (and friends) take Stripe's amount as-is — multiplying by
        100 the way every other currency needs would overcharge 100x."""
        _make_admin(db_session, "cur_admin10@test.com")
        admin = _login(client, "cur_admin10@test.com", "CurAdmin123")
        client.post(
            "/admin/currencies",
            json={"code": "JPY", "name": "Japanese Yen", "symbol": "¥", "exchange_rate_to_base": 150},
            headers=admin,
        )

        customer = _register_and_login(client, "cur_checkout4@test.com", "CurCheck423")
        product = _make_product(db_session, slug="checkout-jpy-widget", price=10.0)
        address_id = _make_address(client, customer)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
        client.put("/cart/currency", json={"currency_code": "JPY"}, headers=customer)
        order = client.post(
            "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=customer
        ).json()

        with patch("stripe.PaymentIntent.create") as mock_create:
            mock_create.return_value = MagicMock(id="pi_jpy_charge", client_secret="secret_jpy")
            client.post("/payments/create-intent", json={"order_id": order["id"]}, headers=customer)

        assert mock_create.call_args.kwargs["amount"] == 1500  # 10 * 150, NOT * 100
        assert mock_create.call_args.kwargs["currency"] == "jpy"


class TestRefundInChargedCurrency:
    def test_refund_amount_is_compared_against_the_charged_amount_not_base_total(
        self, client: TestClient, db_session: Session
    ):
        """Regression target: refund_payment used to compare the admin's
        requested amount against order.total_amount (base currency) even
        though payment.amount (and the admin's own input) are in the
        charged currency — for a non-base-currency order those aren't the
        same number, so the remaining-balance check must anchor on
        payment.amount instead. Deliberately a single refund call for an
        amount between the two (60, with charged=50 and base=100): a
        second call would confound this with refund_payment's own
        order.status transition to "refunded", which blocks any further
        refund regardless of amount and would make the assertion pass for
        the wrong reason.
        """
        _make_admin(db_session, "cur_admin11@test.com")
        admin = _login(client, "cur_admin11@test.com", "CurAdmin123")
        _make_eur(client, admin, rate=0.5)  # deliberately far from 1.0 to make a base-currency bug obvious

        customer = _register_and_login(client, "cur_refund1@test.com", "CurRefund123")
        product = _make_product(db_session, slug="refund-eur-widget", price=100.0)
        address_id = _make_address(client, customer)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
        client.put("/cart/currency", json={"currency_code": "EUR"}, headers=customer)
        order = client.post(
            "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=customer
        ).json()
        # order.total_amount (base) == 100.0; charged amount (EUR) == 50.0

        with patch("stripe.PaymentIntent.create") as mock_create:
            mock_create.return_value = MagicMock(id="pi_refund_eur", client_secret="s")
            client.post("/payments/create-intent", json={"order_id": order["id"]}, headers=customer)

        db_session.expire_all()
        payment = db_session.query(Payment).filter_by(order_id=order["id"]).first()
        payment.status = "completed"
        order_row = db_session.get(Order, order["id"])
        order_row.payment_status = "success"
        order_row.status = "paid"
        db_session.commit()

        # 60 is more than was actually charged (50 EUR) but less than the
        # base-currency total (100) — correct behavior refuses it before
        # ever calling Stripe; the bug this guards against would wrongly
        # let it through to a (here mocked) Stripe call instead. Without
        # mocking stripe.Refund.create, a wrongly-allowed request would
        # hit the real Stripe SDK with no API key and fail with its own
        # StripeError — which this endpoint also turns into a 400,
        # accidentally "passing" the assertion below for the wrong reason.
        with patch("stripe.Refund.create") as mock_refund:
            mock_refund.return_value = MagicMock(id="re_should_not_be_called")
            resp = client.post(
                f"/admin/orders/{order['id']}/refund",
                json={"amount": 60.0, "reason": "requested_by_customer"},
                headers=admin,
            )

        assert resp.status_code == 400, resp.json()
        mock_refund.assert_not_called()

    def test_stripe_refund_amount_reflects_the_charged_currency_not_base(
        self, client: TestClient, db_session: Session
    ):
        _make_admin(db_session, "cur_admin12@test.com")
        admin = _login(client, "cur_admin12@test.com", "CurAdmin123")
        _make_eur(client, admin, rate=0.5)

        customer = _register_and_login(client, "cur_refund2@test.com", "CurRefund223")
        product = _make_product(db_session, slug="refund-eur-widget-2", price=100.0)
        address_id = _make_address(client, customer)
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
        client.put("/cart/currency", json={"currency_code": "EUR"}, headers=customer)
        order = client.post(
            "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=customer
        ).json()

        with patch("stripe.PaymentIntent.create") as mock_create:
            mock_create.return_value = MagicMock(id="pi_refund_eur_2", client_secret="s")
            client.post("/payments/create-intent", json={"order_id": order["id"]}, headers=customer)

        db_session.expire_all()
        payment = db_session.query(Payment).filter_by(order_id=order["id"]).first()
        payment.status = "completed"
        order_row = db_session.get(Order, order["id"])
        order_row.payment_status = "success"
        order_row.status = "paid"
        db_session.commit()

        with patch("stripe.Refund.create") as mock_refund:
            mock_refund.return_value = MagicMock(id="re_eur_2")
            resp = client.post(
                f"/admin/orders/{order['id']}/refund",
                json={"amount": 50.0, "reason": "requested_by_customer"},
                headers=admin,
            )

        assert resp.status_code == 200, resp.json()
        assert mock_refund.call_args.kwargs["amount"] == 5000  # 50 EUR in cents, not 100

        db_session.expire_all()
        payment = db_session.query(Payment).filter_by(order_id=order["id"]).first()
        assert float(payment.refund_amount) == 50.0
