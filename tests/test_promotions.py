"""
Tests for the promotions admin CRUD, and for two bugs found while building
it that the CRUD would otherwise let an admin configure without warning:

1. "free_shipping" has been a valid Promotion.type since the enum was
   defined, but calculate_promotion_discount only ever handled
   percentage_on_category and buy_x_get_y — creating a free_shipping
   promotion did nothing at checkout, silently. See
   TestFreeShippingPromotion.

2. Nothing checked Promotion.starts_at/ends_at anywhere — only is_active
   was checked, so a promotion scheduled for the future (or already
   expired) applied at checkout today regardless. See
   TestPromotionDateWindow. Since the CRUD this file otherwise tests lets
   an admin set exactly those two fields, shipping it without this fix
   would mean scheduling silently doesn't work.
"""
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.product import Product
from app.models.promotion import Promotion
from app.models.user import User
from app.utils.security import hash_password


def _make_admin(db_session: Session, email: str = "promo_admin@test.com") -> None:
    db_session.add(
        User(
            email=email,
            password_hash=hash_password("PromoAdmin1"),
            first_name="Admin",
            last_name="Promo",
            phone="0988800001",
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
        json={"email": email, "password": password, "first_name": "Test", "last_name": "User", "phone": "0988800002"},
    )
    return _login(client, email, password)


def _make_category(db_session: Session, name: str = "Promo Category") -> Category:
    category = Category(name=name, slug=name.lower().replace(" ", "-"))
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


def _make_product(db_session: Session, *, category_id: int | None = None, price: float = 40.0, stock: int = 50, slug: str = "promo-widget") -> Product:
    product = Product(
        name="Promo Widget",
        slug=slug,
        description="d",
        price=price,
        stock_quantity=stock,
        category_id=category_id,
        image_url="http://test.com/img.jpg",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


class TestPromotionCreateValidation:
    def test_requires_admin(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "promo_notadmin@test.com", "NotAdmin1")
        resp = client.post(
            "/promotions",
            json={"name": "X", "type": "free_shipping", "conditions": {}, "rewards": {}},
            headers=customer,
        )
        assert resp.status_code == 403

    def test_percentage_on_category_requires_category_id(self, client: TestClient, db_session: Session):
        _make_admin(db_session)
        admin = _login(client, "promo_admin@test.com", "PromoAdmin1")
        resp = client.post(
            "/promotions",
            json={"name": "Bad", "type": "percentage_on_category", "conditions": {}, "rewards": {"discount_percentage": 10}},
            headers=admin,
        )
        assert resp.status_code == 422

    def test_percentage_on_category_rejects_out_of_range_percentage(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "promo_admin2@test.com")
        admin = _login(client, "promo_admin2@test.com", "PromoAdmin1")
        category = _make_category(db_session, "Cat Range")
        resp = client.post(
            "/promotions",
            json={
                "name": "Bad Pct",
                "type": "percentage_on_category",
                "conditions": {"category_id": category.id},
                "rewards": {"discount_percentage": 150},
            },
            headers=admin,
        )
        assert resp.status_code == 422

    def test_rejects_a_nonexistent_category(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "promo_admin3@test.com")
        admin = _login(client, "promo_admin3@test.com", "PromoAdmin1")
        resp = client.post(
            "/promotions",
            json={
                "name": "Ghost Category",
                "type": "percentage_on_category",
                "conditions": {"category_id": 999999},
                "rewards": {"discount_percentage": 10},
            },
            headers=admin,
        )
        assert resp.status_code == 400
        assert "does not exist" in resp.json()["detail"]

    def test_buy_x_get_y_requires_product_id_and_get_quantity(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "promo_admin4@test.com")
        admin = _login(client, "promo_admin4@test.com", "PromoAdmin1")
        resp = client.post(
            "/promotions",
            json={"name": "Bad BXGY", "type": "buy_x_get_y", "conditions": {"buy_quantity": 2}, "rewards": {}},
            headers=admin,
        )
        assert resp.status_code == 422

    def test_rejects_a_nonexistent_product(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "promo_admin5@test.com")
        admin = _login(client, "promo_admin5@test.com", "PromoAdmin1")
        resp = client.post(
            "/promotions",
            json={
                "name": "Ghost Product",
                "type": "buy_x_get_y",
                "conditions": {"product_id": 999999, "buy_quantity": 1},
                "rewards": {"get_quantity": 1},
            },
            headers=admin,
        )
        assert resp.status_code == 400
        assert "does not exist" in resp.json()["detail"]

    def test_free_shipping_min_order_value_must_be_non_negative(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "promo_admin6@test.com")
        admin = _login(client, "promo_admin6@test.com", "PromoAdmin1")
        resp = client.post(
            "/promotions",
            json={"name": "Bad Free Ship", "type": "free_shipping", "conditions": {"min_order_value": -5}, "rewards": {}},
            headers=admin,
        )
        assert resp.status_code == 422

    def test_rejects_starts_at_after_ends_at(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "promo_admin7@test.com")
        admin = _login(client, "promo_admin7@test.com", "PromoAdmin1")
        now = datetime.now()
        resp = client.post(
            "/promotions",
            json={
                "name": "Backwards Window",
                "type": "free_shipping",
                "conditions": {},
                "rewards": {},
                "starts_at": (now + timedelta(days=5)).isoformat(),
                "ends_at": now.isoformat(),
            },
            headers=admin,
        )
        assert resp.status_code == 422

    def test_successful_creation(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "promo_admin8@test.com")
        admin = _login(client, "promo_admin8@test.com", "PromoAdmin1")
        category = _make_category(db_session, "Cat Success")
        resp = client.post(
            "/promotions",
            json={
                "name": "10% Off Category",
                "type": "percentage_on_category",
                "conditions": {"category_id": category.id},
                "rewards": {"discount_percentage": 10},
            },
            headers=admin,
        )
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["is_active"] is True
        assert data["conditions"] == {"category_id": category.id}


class TestPromotionCrudLifecycle:
    def test_list_get_update_delete(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "promo_lifecycle@test.com")
        admin = _login(client, "promo_lifecycle@test.com", "PromoAdmin1")

        create_resp = client.post(
            "/promotions",
            json={"name": "Lifecycle Promo", "type": "free_shipping", "conditions": {}, "rewards": {}},
            headers=admin,
        )
        promo_id = create_resp.json()["id"]

        listing = client.get("/promotions", headers=admin)
        assert any(p["id"] == promo_id for p in listing.json())

        get_resp = client.get(f"/promotions/{promo_id}", headers=admin)
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Lifecycle Promo"

        update_resp = client.put(
            f"/promotions/{promo_id}", json={"is_active": False}, headers=admin
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["is_active"] is False
        assert update_resp.json()["type"] == "free_shipping", "unrelated fields must survive a partial update"

        delete_resp = client.delete(f"/promotions/{promo_id}", headers=admin)
        assert delete_resp.status_code == 204
        assert client.get(f"/promotions/{promo_id}", headers=admin).status_code == 404

    def test_update_revalidates_the_merged_shape(self, client: TestClient, db_session: Session):
        """Flipping is_active alone must not bypass validation of the
        promotion's own existing conditions/rewards against its type."""
        _make_admin(db_session, "promo_revalidate@test.com")
        admin = _login(client, "promo_revalidate@test.com", "PromoAdmin1")
        category = _make_category(db_session, "Cat Revalidate")

        promo_id = client.post(
            "/promotions",
            json={
                "name": "Revalidate Me",
                "type": "percentage_on_category",
                "conditions": {"category_id": category.id},
                "rewards": {"discount_percentage": 10},
            },
            headers=admin,
        ).json()["id"]

        # Switching type without updating conditions/rewards to match is
        # now internally inconsistent (buy_x_get_y needs product_id, not
        # category_id) and must be rejected.
        resp = client.put(f"/promotions/{promo_id}", json={"type": "buy_x_get_y"}, headers=admin)
        assert resp.status_code == 400


class TestFreeShippingPromotion:
    """free_shipping existed as an enum value with zero implementation
    anywhere in app/services/pricing.py before this."""

    def _place_order_with_shipping(self, client: TestClient, customer_auth: dict, admin_auth: dict, product_id: int) -> dict:
        client.post("/cart/items", json={"product_id": product_id, "quantity": 1}, headers=customer_auth)
        addr = client.post(
            "/users/me/address",
            json={"type": "shipping", "street": "s", "city": "c", "state": "s", "postal_code": "1", "country": "c"},
            headers=customer_auth,
        ).json()
        method = client.post(
            "/admin/shipping/methods",
            json={"name": "Standard", "carrier": "Test Carrier", "base_rate": 15.0, "per_kg_rate": 0.0},
            headers=admin_auth,
        ).json()
        return client.post(
            "/order",
            json={
                "shipping_address_id": addr["id"],
                "billing_address_id": addr["id"],
                "shipping_method_id": method["id"],
            },
            headers=customer_auth,
        ).json()

    def test_active_free_shipping_promotion_zeroes_shipping_cost(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "freeship_admin1@test.com")
        customer = _register_and_login(client, "freeship_cust1@test.com", "FreeShipCust1")
        admin = _login(client, "freeship_admin1@test.com", "PromoAdmin1")

        product = _make_product(db_session, slug="freeship-widget-1")
        db_session.add(Promotion(name="Free Ship", type="free_shipping", conditions={}, rewards={}, is_active=True))
        db_session.commit()

        order = self._place_order_with_shipping(client, customer, admin, product.id)

        assert order["shipping_amount"] == 0.0

    def test_free_shipping_respects_min_order_value(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "freeship_admin2@test.com")
        customer = _register_and_login(client, "freeship_cust2@test.com", "FreeShipCust2")
        admin = _login(client, "freeship_admin2@test.com", "PromoAdmin1")

        product = _make_product(db_session, price=5.0, slug="freeship-widget-2")
        db_session.add(
            Promotion(
                name="Free Ship Over 100",
                type="free_shipping",
                conditions={"min_order_value": 100},
                rewards={},
                is_active=True,
            )
        )
        db_session.commit()

        order = self._place_order_with_shipping(client, customer, admin, product.id)

        assert order["shipping_amount"] == 15.0, "order subtotal ($5) is below the $100 threshold"

    def test_no_free_shipping_promotion_charges_normally(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "freeship_admin3@test.com")
        customer = _register_and_login(client, "freeship_cust3@test.com", "FreeShipCust3")
        admin = _login(client, "freeship_admin3@test.com", "PromoAdmin1")

        product = _make_product(db_session, slug="freeship-widget-3")

        order = self._place_order_with_shipping(client, customer, admin, product.id)

        assert order["shipping_amount"] == 15.0


class TestPromotionDateWindow:
    """Regression coverage: starts_at/ends_at were never checked anywhere."""

    def test_promotion_scheduled_for_the_future_does_not_apply_yet(self, client: TestClient, db_session: Session):
        category = _make_category(db_session, "Future Cat")
        product = _make_product(db_session, category_id=category.id, price=100.0, slug="future-promo-widget")
        customer = _register_and_login(client, "future_promo_cust@test.com", "FuturePromo1")

        db_session.add(
            Promotion(
                name="Future Discount",
                type="percentage_on_category",
                conditions={"category_id": category.id},
                rewards={"discount_percentage": 50},
                is_active=True,
                starts_at=datetime.now() + timedelta(days=7),
            )
        )
        db_session.commit()

        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
        addr = client.post(
            "/users/me/address",
            json={"type": "shipping", "street": "s", "city": "c", "state": "s", "postal_code": "1", "country": "c"},
            headers=customer,
        ).json()
        order = client.post(
            "/order",
            json={"shipping_address_id": addr["id"], "billing_address_id": addr["id"]},
            headers=customer,
        ).json()

        assert order["discount_amount"] == 0.0
        assert order["subtotal"] == 100.0

    def test_expired_promotion_no_longer_applies(self, client: TestClient, db_session: Session):
        category = _make_category(db_session, "Expired Cat")
        product = _make_product(db_session, category_id=category.id, price=100.0, slug="expired-promo-widget")
        customer = _register_and_login(client, "expired_promo_cust@test.com", "ExpiredPromo1")

        db_session.add(
            Promotion(
                name="Expired Discount",
                type="percentage_on_category",
                conditions={"category_id": category.id},
                rewards={"discount_percentage": 50},
                is_active=True,
                ends_at=datetime.now() - timedelta(days=1),
            )
        )
        db_session.commit()

        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
        addr = client.post(
            "/users/me/address",
            json={"type": "shipping", "street": "s", "city": "c", "state": "s", "postal_code": "1", "country": "c"},
            headers=customer,
        ).json()
        order = client.post(
            "/order",
            json={"shipping_address_id": addr["id"], "billing_address_id": addr["id"]},
            headers=customer,
        ).json()

        assert order["discount_amount"] == 0.0

    def test_currently_active_window_still_applies(self, client: TestClient, db_session: Session):
        category = _make_category(db_session, "Currently Active Cat")
        product = _make_product(db_session, category_id=category.id, price=100.0, slug="active-window-widget")
        customer = _register_and_login(client, "active_window_cust@test.com", "ActiveWindow1")

        db_session.add(
            Promotion(
                name="Active Window Discount",
                type="percentage_on_category",
                conditions={"category_id": category.id},
                rewards={"discount_percentage": 50},
                is_active=True,
                starts_at=datetime.now() - timedelta(days=1),
                ends_at=datetime.now() + timedelta(days=1),
            )
        )
        db_session.commit()

        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer)
        addr = client.post(
            "/users/me/address",
            json={"type": "shipping", "street": "s", "city": "c", "state": "s", "postal_code": "1", "country": "c"},
            headers=customer,
        ).json()
        order = client.post(
            "/order",
            json={"shipping_address_id": addr["id"], "billing_address_id": addr["id"]},
            headers=customer,
        ).json()

        assert order["discount_amount"] == 50.0
