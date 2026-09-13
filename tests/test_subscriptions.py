"""
Tests for recurring-order subscriptions (/subscriptions): creation
validation, listing, and the pause/resume/skip/cancel lifecycle.

The actual renewal billing (charging Stripe on a schedule, dunning,
auto-cancel after repeated failures) is covered separately in
tests/test_subscription_billing.py, which drives
app.workers.arq_worker.process_due_subscriptions_task directly rather than
through the API.
"""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.product_variant import ProductVariant


def _register_and_login(client: TestClient, email: str, password: str) -> dict:
    client.post(
        "/users/register",
        json={"email": email, "password": password, "first_name": "Test", "last_name": "User", "phone": "0999900001"},
    )
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _make_product(db_session: Session, *, slug: str = "sub-widget", price: float = 15.0, stock: int = 50) -> Product:
    product = Product(
        name="Subscription Widget",
        slug=slug,
        sku=f"SKU-{slug}",
        description="d",
        price=price,
        stock_quantity=stock,
        image_url="http://test.com/img.jpg",
        status="active",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


def _make_variant(db_session: Session, product: Product, *, price: float = 18.0, stock: int = 30) -> ProductVariant:
    variant = ProductVariant(product_id=product.id, sku=f"VAR-{product.slug}", name="Variant", price=price, stock_quantity=stock)
    db_session.add(variant)
    db_session.commit()
    db_session.refresh(variant)
    return variant


def _make_address(client: TestClient, headers: dict) -> int:
    resp = client.post(
        "/users/me/address",
        json={"type": "shipping", "street": "1 Sub St", "city": "Sub City", "state": "SS", "zip_code": "11111", "country": "Subland"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.json()
    return resp.json()["id"]


def _save_card(client: TestClient, headers: dict, pm_id: str = "pm_sub_default") -> int:
    card = MagicMock(brand="visa", last4="4242", exp_month=12, exp_year=2035)
    payment_method = MagicMock(id=pm_id, type="card", card=card, customer=None)
    with patch("stripe.Customer.create") as mock_customer, patch(
        "stripe.PaymentMethod.retrieve"
    ) as mock_retrieve, patch("stripe.PaymentMethod.attach"):
        # Unique per call: User.stripe_customer_id is UNIQUE, and each
        # test here registers its own user(s) that each need their own.
        mock_customer.return_value = MagicMock(id=f"cus_{pm_id}")
        mock_retrieve.return_value = payment_method
        resp = client.post("/payments/methods", json={"payment_method_id": pm_id}, headers=headers)
    assert resp.status_code == 201, resp.json()
    return resp.json()["id"]


def _full_setup(client: TestClient, db_session: Session, email: str, password: str, *, slug: str = "sub-widget"):
    headers = _register_and_login(client, email, password)
    product = _make_product(db_session, slug=slug)
    address_id = _make_address(client, headers)
    payment_method_id = _save_card(client, headers, pm_id=f"pm_{slug}")
    return headers, product, address_id, payment_method_id


def _create_subscription(client: TestClient, headers: dict, product_id: int, address_id: int, payment_method_id: int, **overrides):
    payload = {
        "product_id": product_id,
        "quantity": 1,
        "interval": "monthly",
        "saved_payment_method_id": payment_method_id,
        "shipping_address_id": address_id,
        "billing_address_id": address_id,
    }
    payload.update(overrides)
    return client.post("/subscriptions", json=payload, headers=headers)


class TestCreateSubscription:
    def test_requires_authentication(self, client: TestClient, db_session: Session):
        product = _make_product(db_session)
        resp = client.post(
            "/subscriptions",
            json={
                "product_id": product.id, "quantity": 1, "interval": "monthly",
                "saved_payment_method_id": 1, "shipping_address_id": 1, "billing_address_id": 1,
            },
        )
        assert resp.status_code == 401

    def test_creates_a_subscription_with_a_computed_next_billing_date(self, client: TestClient, db_session: Session):
        headers, product, address_id, pm_id = _full_setup(client, db_session, "sub_cust1@test.com", "SubCust123")

        resp = _create_subscription(client, headers, product.id, address_id, pm_id)

        assert resp.status_code == 201, resp.json()
        data = resp.json()
        assert data["status"] == "active"
        assert data["failure_count"] == 0
        assert data["next_billing_date"] is not None

    def test_rejects_a_nonexistent_product(self, client: TestClient, db_session: Session):
        headers, product, address_id, pm_id = _full_setup(client, db_session, "sub_cust2@test.com", "SubCust123")

        resp = _create_subscription(client, headers, 999999, address_id, pm_id)

        assert resp.status_code == 404

    def test_rejects_a_draft_product(self, client: TestClient, db_session: Session):
        headers, _, address_id, pm_id = _full_setup(client, db_session, "sub_cust3@test.com", "SubCust123")
        draft_product = Product(
            name="Draft Widget", slug="draft-sub-widget", sku="SKU-draft-sub",
            description="d", price=10.0, stock_quantity=5, image_url="http://t.com/i.jpg", status="draft",
        )
        db_session.add(draft_product)
        db_session.commit()
        db_session.refresh(draft_product)

        resp = _create_subscription(client, headers, draft_product.id, address_id, pm_id)

        assert resp.status_code == 404

    def test_rejects_someone_elses_payment_method(self, client: TestClient, db_session: Session):
        owner_headers, product, address_id, pm_id = _full_setup(client, db_session, "sub_owner1@test.com", "SubOwner1")
        attacker_headers = _register_and_login(client, "sub_attacker1@test.com", "SubAttack1")

        resp = _create_subscription(client, attacker_headers, product.id, address_id, pm_id)

        assert resp.status_code == 404

    def test_rejects_someone_elses_address(self, client: TestClient, db_session: Session):
        owner_headers, product, address_id, _ = _full_setup(client, db_session, "sub_owner2@test.com", "SubOwner2")
        attacker_headers = _register_and_login(client, "sub_attacker2@test.com", "SubAttack2")
        attacker_pm_id = _save_card(client, attacker_headers, pm_id="pm_attacker2")

        resp = _create_subscription(client, attacker_headers, product.id, address_id, attacker_pm_id)

        assert resp.status_code == 400

    def test_rejects_a_variant_not_belonging_to_the_product(self, client: TestClient, db_session: Session):
        headers, product, address_id, pm_id = _full_setup(client, db_session, "sub_cust4@test.com", "SubCust123")
        other_product = _make_product(db_session, slug="other-sub-widget")
        mismatched_variant = _make_variant(db_session, other_product)

        resp = _create_subscription(
            client, headers, product.id, address_id, pm_id, variant_id=mismatched_variant.id
        )

        assert resp.status_code == 404


class TestListAndGet:
    def test_lists_only_my_subscriptions(self, client: TestClient, db_session: Session):
        headers_a, product, address_id, pm_id = _full_setup(client, db_session, "sub_list_a@test.com", "SubListA1")
        headers_b = _register_and_login(client, "sub_list_b@test.com", "SubListB1")

        _create_subscription(client, headers_a, product.id, address_id, pm_id)

        a_subs = client.get("/subscriptions", headers=headers_a).json()
        b_subs = client.get("/subscriptions", headers=headers_b).json()

        assert len(a_subs) == 1
        assert b_subs == []

    def test_cannot_get_someone_elses_subscription(self, client: TestClient, db_session: Session):
        owner_headers, product, address_id, pm_id = _full_setup(client, db_session, "sub_get_owner@test.com", "SubGetOwn1")
        attacker_headers = _register_and_login(client, "sub_get_attacker@test.com", "SubGetAtk1")
        sub_id = _create_subscription(client, owner_headers, product.id, address_id, pm_id).json()["id"]

        resp = client.get(f"/subscriptions/{sub_id}", headers=attacker_headers)

        assert resp.status_code == 404


class TestLifecycle:
    def test_pause_then_resume(self, client: TestClient, db_session: Session):
        headers, product, address_id, pm_id = _full_setup(client, db_session, "sub_pause1@test.com", "SubPause1")
        sub_id = _create_subscription(client, headers, product.id, address_id, pm_id).json()["id"]

        pause_resp = client.post(f"/subscriptions/{sub_id}/pause", headers=headers)
        assert pause_resp.status_code == 200
        assert pause_resp.json()["status"] == "paused"

        resume_resp = client.post(f"/subscriptions/{sub_id}/resume", headers=headers)
        assert resume_resp.status_code == 200
        assert resume_resp.json()["status"] == "active"

    def test_cannot_pause_an_already_paused_subscription(self, client: TestClient, db_session: Session):
        headers, product, address_id, pm_id = _full_setup(client, db_session, "sub_pause2@test.com", "SubPause2")
        sub_id = _create_subscription(client, headers, product.id, address_id, pm_id).json()["id"]
        client.post(f"/subscriptions/{sub_id}/pause", headers=headers)

        resp = client.post(f"/subscriptions/{sub_id}/pause", headers=headers)

        assert resp.status_code == 400

    def test_cannot_resume_an_active_subscription(self, client: TestClient, db_session: Session):
        headers, product, address_id, pm_id = _full_setup(client, db_session, "sub_resume1@test.com", "SubResume1")
        sub_id = _create_subscription(client, headers, product.id, address_id, pm_id).json()["id"]

        resp = client.post(f"/subscriptions/{sub_id}/resume", headers=headers)

        assert resp.status_code == 400

    def test_skip_pushes_the_next_billing_date_out_by_one_interval(self, client: TestClient, db_session: Session):
        headers, product, address_id, pm_id = _full_setup(client, db_session, "sub_skip1@test.com", "SubSkip123")
        created = _create_subscription(client, headers, product.id, address_id, pm_id).json()
        original_date = created["next_billing_date"]

        resp = client.post(f"/subscriptions/{created['id']}/skip", headers=headers)

        assert resp.status_code == 200
        assert resp.json()["next_billing_date"] != original_date
        assert resp.json()["status"] == "active"

    def test_cancel_removes_it_from_future_billing(self, client: TestClient, db_session: Session):
        headers, product, address_id, pm_id = _full_setup(client, db_session, "sub_cancel1@test.com", "SubCancel1")
        sub_id = _create_subscription(client, headers, product.id, address_id, pm_id).json()["id"]

        resp = client.delete(f"/subscriptions/{sub_id}", headers=headers)

        assert resp.status_code == 204
        assert client.get(f"/subscriptions/{sub_id}", headers=headers).json()["status"] == "cancelled"

    def test_cannot_cancel_twice(self, client: TestClient, db_session: Session):
        headers, product, address_id, pm_id = _full_setup(client, db_session, "sub_cancel2@test.com", "SubCancel2")
        sub_id = _create_subscription(client, headers, product.id, address_id, pm_id).json()["id"]
        client.delete(f"/subscriptions/{sub_id}", headers=headers)

        resp = client.delete(f"/subscriptions/{sub_id}", headers=headers)

        assert resp.status_code == 400

    def test_cannot_pause_someone_elses_subscription(self, client: TestClient, db_session: Session):
        owner_headers, product, address_id, pm_id = _full_setup(client, db_session, "sub_pause_owner@test.com", "SubPauseOwn1")
        attacker_headers = _register_and_login(client, "sub_pause_attacker@test.com", "SubPauseAtk1")
        sub_id = _create_subscription(client, owner_headers, product.id, address_id, pm_id).json()["id"]

        resp = client.post(f"/subscriptions/{sub_id}/pause", headers=attacker_headers)

        assert resp.status_code == 404


class TestDeletePaymentMethodGuard:
    def test_cannot_delete_a_payment_method_used_by_an_active_subscription(
        self, client: TestClient, db_session: Session
    ):
        headers, product, address_id, pm_id = _full_setup(client, db_session, "sub_pm_guard@test.com", "SubPmGuard1")
        _create_subscription(client, headers, product.id, address_id, pm_id)

        resp = client.delete(f"/payments/methods/{pm_id}", headers=headers)

        assert resp.status_code == 409

    def test_stays_blocked_even_after_cancelling_the_subscription(
        self, client: TestClient, db_session: Session
    ):
        """Mirrors Order.shipping_address_id/billing_address_id: this app
        never drops a historical FK reference just because the referencing
        record (here, a cancelled subscription) is no longer active."""
        headers, product, address_id, pm_id = _full_setup(client, db_session, "sub_pm_guard2@test.com", "SubPmGuard2")
        sub_id = _create_subscription(client, headers, product.id, address_id, pm_id).json()["id"]
        client.delete(f"/subscriptions/{sub_id}", headers=headers)

        resp = client.delete(f"/payments/methods/{pm_id}", headers=headers)

        assert resp.status_code == 409

    def test_an_unused_payment_method_can_still_be_deleted(self, client: TestClient, db_session: Session):
        headers = _register_and_login(client, "sub_pm_unused@test.com", "SubPmUnused1")
        pm_id = _save_card(client, headers, pm_id="pm_never_subscribed")

        with patch("stripe.PaymentMethod.detach"):
            resp = client.delete(f"/payments/methods/{pm_id}", headers=headers)

        assert resp.status_code == 204
