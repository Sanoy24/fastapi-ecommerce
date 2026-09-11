"""
Regression tests for variant-scoped inventory reservations.

Previously, InventoryReservation had no variant_id column, so a reservation
for a product variant was recorded only against the parent product. Two
consequences:

1. OrderCrud.validate_stock checked the variant's raw stock_quantity (never
   reservation-aware), so two concurrent orders for the same variant could
   both pass the stock check even though only one unit existed.
2. PaymentService._handle_successful_payment always deducted from
   product.stock_quantity on a successful payment, even for variant order
   items — the variant's own stock_quantity was never actually decremented,
   and the wrong pool (the parent product's) was debited instead.
"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.services.payment_service import PaymentService


def _register_login(client: TestClient, email: str, password: str) -> dict:
    client.post(
        "/users/register",
        json={
            "email": email,
            "password": password,
            "first_name": "Variant",
            "last_name": "Customer",
            "phone": "0944000001",
        },
    )
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _add_default_address(client: TestClient, headers: dict) -> int:
    resp = client.post(
        "/users/me/address",
        headers=headers,
        json={
            "type": "home",
            "street": "1 Variant St",
            "city": "Variantville",
            "state": "VS",
            "postal_code": "00003",
            "country": "Variantland",
            "is_default": True,
        },
    )
    return resp.json()["id"]


def _make_product_with_variant(db_session: Session, product_stock: int, variant_stock: int):
    product = Product(
        name="Variant Widget",
        slug=f"variant-widget-{product_stock}-{variant_stock}",
        description="Widget with a single-unit variant",
        price=20.0,
        stock_quantity=product_stock,
        image_url="https://example.com/img.jpg",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)

    variant = ProductVariant(
        product_id=product.id,
        sku=f"VAR-{product.id}",
        name="Only Size",
        price=20.0,
        stock_quantity=variant_stock,
    )
    db_session.add(variant)
    db_session.commit()
    db_session.refresh(variant)

    return product, variant


class TestVariantOversellPrevention:
    def test_second_concurrent_order_for_same_variant_is_rejected(
        self, client: TestClient, db_session: Session
    ):
        product, variant = _make_product_with_variant(db_session, product_stock=5, variant_stock=1)

        headers_a = _register_login(client, "variant_buyer_a@test.com", "VariantA1")
        address_a = _add_default_address(client, headers_a)
        client.post(
            "/cart/items",
            json={"product_id": product.id, "variant_id": variant.id, "quantity": 1},
            headers=headers_a,
        )
        order_a = client.post(
            "/order",
            json={"shipping_address_id": address_a, "billing_address_id": address_a},
            headers=headers_a,
        )
        assert order_a.status_code == 201, order_a.json()

        headers_b = _register_login(client, "variant_buyer_b@test.com", "VariantB1")
        address_b = _add_default_address(client, headers_b)
        client.post(
            "/cart/items",
            json={"product_id": product.id, "variant_id": variant.id, "quantity": 1},
            headers=headers_b,
        )
        order_b = client.post(
            "/order",
            json={"shipping_address_id": address_b, "billing_address_id": address_b},
            headers=headers_b,
        )
        assert order_b.status_code == 400
        assert "variant" in order_b.json()["detail"].lower()

    def test_variant_reservation_does_not_consume_parent_product_pool(
        self, client: TestClient, db_session: Session
    ):
        product, variant = _make_product_with_variant(db_session, product_stock=5, variant_stock=1)

        headers = _register_login(client, "variant_buyer_c@test.com", "VariantC1")
        address_id = _add_default_address(client, headers)
        client.post(
            "/cart/items",
            json={"product_id": product.id, "variant_id": variant.id, "quantity": 1},
            headers=headers,
        )
        order_resp = client.post(
            "/order",
            json={"shipping_address_id": address_id, "billing_address_id": address_id},
            headers=headers,
        )
        assert order_resp.status_code == 201, order_resp.json()

        db_session.expire_all()
        product = db_session.query(Product).filter(Product.id == product.id).one()
        # Reserving the variant must not touch the parent product's own pool.
        assert product.available_stock == 5


class TestVariantStockDeductionOnPayment:
    def test_successful_payment_deducts_variant_not_product_stock(
        self, client: TestClient, db_session: Session
    ):
        from app.models.order import Order
        from app.models.payment import Payment

        product, variant = _make_product_with_variant(db_session, product_stock=5, variant_stock=1)

        headers = _register_login(client, "variant_buyer_d@test.com", "VariantD1")
        address_id = _add_default_address(client, headers)
        client.post(
            "/cart/items",
            json={"product_id": product.id, "variant_id": variant.id, "quantity": 1},
            headers=headers,
        )
        order_resp = client.post(
            "/order",
            json={"shipping_address_id": address_id, "billing_address_id": address_id},
            headers=headers,
        )
        assert order_resp.status_code == 201, order_resp.json()
        order_id = order_resp.json()["id"]

        order = db_session.query(Order).filter(Order.id == order_id).one()
        payment = Payment(
            order_id=order.id,
            payment_method="stripe",
            amount=order.total_amount,
            status="pending",
            transaction_id="pi_variant_test",
        )
        db_session.add(payment)
        db_session.commit()

        service = PaymentService(db_session)
        service._handle_successful_payment({"id": "pi_variant_test"})

        db_session.expire_all()
        variant = db_session.query(ProductVariant).filter(ProductVariant.id == variant.id).one()
        product = db_session.query(Product).filter(Product.id == product.id).one()

        assert variant.stock_quantity == 0
        assert product.stock_quantity == 5
