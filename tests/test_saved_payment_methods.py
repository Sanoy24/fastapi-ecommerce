"""
Tests for saved payment methods (/payments/methods) and their use at
checkout (POST /payments/create-intent with saved_payment_method_id).

Stripe itself is always mocked, same as tests/test_payments.py — these
tests are about this app's own logic (customer-id lifecycle, ownership
checks, default-card bookkeeping, one bad row never means much here since
it's per-request) rather than Stripe's behavior. No raw card data ever
appears here or in the code under test: only a PaymentMethod id (a string
Stripe would have generated) and the display fields
(brand/last4/exp_month/exp_year) Stripe's API would return for it.
"""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.saved_payment_method import SavedPaymentMethod
from app.models.user import User


def _register_and_login(client: TestClient, email: str, password: str) -> dict:
    client.post(
        "/users/register",
        json={"email": email, "password": password, "first_name": "Test", "last_name": "User", "phone": "0977700001"},
    )
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _make_product(db_session: Session, *, slug: str = "pay-widget", price: float = 20.0) -> Product:
    product = Product(
        name="Payment Method Widget",
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


def _mock_card_payment_method(pm_id: str, customer: str | None = None, brand: str = "visa", last4: str = "4242"):
    card = MagicMock(brand=brand, last4=last4, exp_month=12, exp_year=2030)
    return MagicMock(id=pm_id, type="card", card=card, customer=customer)


def _save_card(client: TestClient, headers: dict, pm_id: str, *, customer: str | None = None, set_default: bool = False):
    with patch("stripe.Customer.create") as mock_customer_create, patch(
        "stripe.PaymentMethod.retrieve"
    ) as mock_retrieve, patch("stripe.PaymentMethod.attach"):
        mock_customer_create.return_value = MagicMock(id=customer or "cus_test")
        mock_retrieve.return_value = _mock_card_payment_method(pm_id, customer=customer)
        return client.post(
            "/payments/methods",
            json={"payment_method_id": pm_id, "set_default": set_default},
            headers=headers,
        )


class TestSetupIntent:
    def test_requires_authentication(self, client: TestClient, db_session: Session):
        resp = client.post("/payments/methods/setup-intent")
        assert resp.status_code == 401

    def test_creates_a_stripe_customer_lazily_and_returns_a_client_secret(
        self, client: TestClient, db_session: Session
    ):
        customer = _register_and_login(client, "spm_cust1@test.com", "SpmCust123")

        with patch("stripe.Customer.create") as mock_customer_create, patch(
            "stripe.SetupIntent.create"
        ) as mock_setup_create:
            mock_customer_create.return_value = MagicMock(id="cus_new123")
            mock_setup_create.return_value = MagicMock(client_secret="seti_secret_123")

            resp = client.post("/payments/methods/setup-intent", headers=customer)

            assert resp.status_code == 200, resp.json()
            assert resp.json() == {"client_secret": "seti_secret_123"}
            mock_customer_create.assert_called_once()
            mock_setup_create.assert_called_once_with(
                customer="cus_new123", automatic_payment_methods={"enabled": True}
            )

        db_session.expire_all()
        user = db_session.query(User).filter_by(email="spm_cust1@test.com").first()
        assert user.stripe_customer_id == "cus_new123"

    def test_reuses_the_existing_stripe_customer_on_a_second_call(
        self, client: TestClient, db_session: Session
    ):
        customer = _register_and_login(client, "spm_cust2@test.com", "SpmCust123")

        with patch("stripe.Customer.create") as mock_customer_create, patch(
            "stripe.SetupIntent.create"
        ) as mock_setup_create:
            mock_customer_create.return_value = MagicMock(id="cus_reuse123")
            mock_setup_create.return_value = MagicMock(client_secret="seti_1")
            client.post("/payments/methods/setup-intent", headers=customer)

            mock_setup_create.return_value = MagicMock(client_secret="seti_2")
            client.post("/payments/methods/setup-intent", headers=customer)

            assert mock_customer_create.call_count == 1


class TestSavePaymentMethod:
    def test_requires_authentication(self, client: TestClient, db_session: Session):
        resp = client.post("/payments/methods", json={"payment_method_id": "pm_123"})
        assert resp.status_code == 401

    def test_saves_a_card_and_makes_the_first_one_default(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "spm_cust3@test.com", "SpmCust123")

        resp = _save_card(client, customer, "pm_first")

        assert resp.status_code == 201, resp.json()
        data = resp.json()
        assert data["brand"] == "visa"
        assert data["last4"] == "4242"
        assert data["is_default"] is True

    def test_a_second_card_is_not_default_unless_requested(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "spm_cust4@test.com", "SpmCust123")
        _save_card(client, customer, "pm_one")

        resp = _save_card(client, customer, "pm_two")

        assert resp.status_code == 201, resp.json()
        assert resp.json()["is_default"] is False

    def test_set_default_true_on_save_makes_it_default_and_unsets_the_previous_one(
        self, client: TestClient, db_session: Session
    ):
        customer = _register_and_login(client, "spm_cust5@test.com", "SpmCust123")
        _save_card(client, customer, "pm_one")

        resp = _save_card(client, customer, "pm_two", set_default=True)

        assert resp.status_code == 201
        assert resp.json()["is_default"] is True

        methods = client.get("/payments/methods", headers=customer).json()
        defaults = [m for m in methods if m["is_default"]]
        assert len(defaults) == 1
        assert defaults[0]["last4"] == "4242" and defaults[0]["is_default"] is True

    def test_resaving_the_same_payment_method_id_does_not_duplicate(
        self, client: TestClient, db_session: Session
    ):
        customer = _register_and_login(client, "spm_cust6@test.com", "SpmCust123")
        first = _save_card(client, customer, "pm_dup")
        second = _save_card(client, customer, "pm_dup")

        assert first.json()["id"] == second.json()["id"]
        assert len(client.get("/payments/methods", headers=customer).json()) == 1

    def test_rejects_a_non_card_payment_method(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "spm_cust7@test.com", "SpmCust123")

        with patch("stripe.Customer.create") as mock_customer_create, patch(
            "stripe.PaymentMethod.retrieve"
        ) as mock_retrieve:
            mock_customer_create.return_value = MagicMock(id="cus_test")
            mock_retrieve.return_value = MagicMock(id="pm_bank", type="us_bank_account", card=None, customer=None)

            resp = client.post(
                "/payments/methods", json={"payment_method_id": "pm_bank"}, headers=customer
            )

        assert resp.status_code == 400
        assert "card" in resp.json()["detail"].lower()

    def test_rejects_a_payment_method_belonging_to_a_different_customer(
        self, client: TestClient, db_session: Session
    ):
        customer = _register_and_login(client, "spm_cust8@test.com", "SpmCust123")

        with patch("stripe.Customer.create") as mock_customer_create, patch(
            "stripe.PaymentMethod.retrieve"
        ) as mock_retrieve:
            mock_customer_create.return_value = MagicMock(id="cus_mine")
            mock_retrieve.return_value = _mock_card_payment_method("pm_stolen", customer="cus_someone_else")

            resp = client.post(
                "/payments/methods", json={"payment_method_id": "pm_stolen"}, headers=customer
            )

        assert resp.status_code == 403


class TestListAndDelete:
    def test_lists_only_my_saved_methods(self, client: TestClient, db_session: Session):
        a = _register_and_login(client, "spm_list_a@test.com", "SpmListA1")
        b = _register_and_login(client, "spm_list_b@test.com", "SpmListB1")
        _save_card(client, a, "pm_a1")

        a_methods = client.get("/payments/methods", headers=a).json()
        b_methods = client.get("/payments/methods", headers=b).json()

        assert len(a_methods) == 1
        assert b_methods == []

    def test_delete_detaches_and_removes_the_record(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "spm_del1@test.com", "SpmDel123")
        method_id = _save_card(client, customer, "pm_del1").json()["id"]

        with patch("stripe.PaymentMethod.detach") as mock_detach:
            resp = client.delete(f"/payments/methods/{method_id}", headers=customer)

        assert resp.status_code == 204
        mock_detach.assert_called_once_with("pm_del1")
        assert client.get("/payments/methods", headers=customer).json() == []

    def test_cannot_delete_someone_elses_payment_method(self, client: TestClient, db_session: Session):
        owner = _register_and_login(client, "spm_owner1@test.com", "SpmOwner1")
        attacker = _register_and_login(client, "spm_attacker1@test.com", "SpmAttack1")
        method_id = _save_card(client, owner, "pm_owner1").json()["id"]

        with patch("stripe.PaymentMethod.detach"):
            resp = client.delete(f"/payments/methods/{method_id}", headers=attacker)

        assert resp.status_code == 404
        assert len(client.get("/payments/methods", headers=owner).json()) == 1

    def test_deleting_the_default_promotes_the_oldest_remaining_card(
        self, client: TestClient, db_session: Session
    ):
        customer = _register_and_login(client, "spm_promote1@test.com", "SpmProm123")
        default_id = _save_card(client, customer, "pm_default").json()["id"]
        other = _save_card(client, customer, "pm_other").json()

        with patch("stripe.PaymentMethod.detach"):
            client.delete(f"/payments/methods/{default_id}", headers=customer)

        db_session.expire_all()
        remaining = db_session.get(SavedPaymentMethod, other["id"])
        assert remaining.is_default is True


class TestSetDefault:
    def test_set_default_switches_the_default_card(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "spm_setdef1@test.com", "SpmSetDef1")
        _save_card(client, customer, "pm_a")
        second = _save_card(client, customer, "pm_b").json()

        resp = client.post(f"/payments/methods/{second['id']}/default", headers=customer)

        assert resp.status_code == 200
        assert resp.json()["is_default"] is True
        methods = client.get("/payments/methods", headers=customer).json()
        assert sum(1 for m in methods if m["is_default"]) == 1

    def test_cannot_set_default_on_someone_elses_method(self, client: TestClient, db_session: Session):
        owner = _register_and_login(client, "spm_owner2@test.com", "SpmOwner2")
        attacker = _register_and_login(client, "spm_attacker2@test.com", "SpmAttack2")
        method_id = _save_card(client, owner, "pm_owner2").json()["id"]

        resp = client.post(f"/payments/methods/{method_id}/default", headers=attacker)

        assert resp.status_code == 404


class TestCheckoutWithSavedCard:
    def test_paying_with_a_saved_card_passes_customer_and_payment_method_to_stripe(
        self, client: TestClient, db_session: Session
    ):
        customer = _register_and_login(client, "spm_checkout1@test.com", "SpmCheck1")
        method = _save_card(client, customer, "pm_checkout", customer="cus_checkout").json()

        product = _make_product(db_session, slug="checkout-widget")
        addr = client.post(
            "/users/me/address",
            json={"type": "shipping", "street": "s", "city": "c", "state": "s", "zip_code": "1", "country": "c"},
            headers=customer,
        ).json()
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
        order = client.post(
            "/order", json={"shipping_address_id": addr["id"], "billing_address_id": addr["id"]}, headers=customer
        ).json()

        with patch("stripe.PaymentIntent.create") as mock_create:
            mock_create.return_value = MagicMock(id="pi_saved_card", client_secret="secret_saved")
            resp = client.post(
                "/payments/create-intent",
                json={"order_id": order["id"], "saved_payment_method_id": method["id"]},
                headers=customer,
            )

        assert resp.status_code == 200, resp.json()
        assert resp.json()["payment_intent_id"] == "pi_saved_card"
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["customer"] == "cus_checkout"
        assert call_kwargs["payment_method"] == "pm_checkout"
        assert "automatic_payment_methods" not in call_kwargs

    def test_rejects_a_saved_payment_method_belonging_to_someone_else(
        self, client: TestClient, db_session: Session
    ):
        owner = _register_and_login(client, "spm_checkout_owner@test.com", "SpmCheckO1")
        attacker = _register_and_login(client, "spm_checkout_attacker@test.com", "SpmCheckA1")
        method = _save_card(client, owner, "pm_checkout_owner", customer="cus_owner").json()

        product = _make_product(db_session, slug="checkout-attacker-widget")
        addr = client.post(
            "/users/me/address",
            json={"type": "shipping", "street": "s", "city": "c", "state": "s", "zip_code": "1", "country": "c"},
            headers=attacker,
        ).json()
        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=attacker)
        order = client.post(
            "/order", json={"shipping_address_id": addr["id"], "billing_address_id": addr["id"]}, headers=attacker
        ).json()

        resp = client.post(
            "/payments/create-intent",
            json={"order_id": order["id"], "saved_payment_method_id": method["id"]},
            headers=attacker,
        )

        assert resp.status_code == 404
