"""
Regression tests for checkout pricing correctness.

Previously, the cart display (CartService.get_cart_details) and order
creation (OrderCrud.create_order) computed prices independently and had
drifted apart:

- The cart used Product.effective_price (sale-aware); checkout used the
  plain Product.price, so a product shown on sale in the cart was charged
  at full price when the order was actually placed.
- The cart evaluated active Promotions into the displayed total; checkout
  never touched Promotion at all, so a promotional discount shown to the
  customer was never actually applied to what they paid.

Both now share app/services/pricing.py, so the charged total always
matches the displayed total.
"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.promotion import Promotion


def _register_login(client: TestClient, email: str, password: str) -> dict:
    client.post(
        "/users/register",
        json={
            "email": email,
            "password": password,
            "first_name": "Pricing",
            "last_name": "Customer",
            "phone": "0933000001",
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
            "street": "1 Pricing St",
            "city": "Pricingville",
            "state": "PS",
            "postal_code": "00002",
            "country": "Pricingland",
            "is_default": True,
        },
    )
    return resp.json()["id"]


class TestSalePriceChargedAtCheckout:
    def test_sale_price_matches_between_cart_and_order(self, client: TestClient, db_session: Session):
        product = Product(
            name="On Sale Widget",
            slug="on-sale-widget",
            description="Widget with an active sale",
            price=100.0,
            sale_price=60.0,
            stock_quantity=10,
            image_url="https://example.com/img.jpg",
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)

        headers = _register_login(client, "sale_customer@test.com", "SaleCustomer1")
        address_id = _add_default_address(client, headers)

        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=headers)

        cart_resp = client.get("/cart", headers=headers)
        assert cart_resp.status_code == 200
        cart_data = cart_resp.json()
        assert cart_data["subtotal"] == 60.0
        assert cart_data["items"][0]["unit_price"] == 60.0

        order_resp = client.post(
            "/order",
            json={"shipping_address_id": address_id, "billing_address_id": address_id},
            headers=headers,
        )
        assert order_resp.status_code == 201, order_resp.json()
        order_id = order_resp.json()["id"]

        # The charged total must match what the cart displayed, not the full price.
        assert order_resp.json()["total_amount"] == 60.0

        order_item = db_session.query(OrderItem).filter(OrderItem.order_id == order_id).one()
        assert float(order_item.unit_price) == 60.0


class TestPromotionsAppliedAtCheckout:
    def test_category_promotion_matches_between_cart_and_order(self, client: TestClient, db_session: Session):
        category = Category(name="PromoCat", slug="promo-cat")
        db_session.add(category)
        db_session.commit()
        db_session.refresh(category)

        product = Product(
            name="Promo Widget",
            slug="promo-widget",
            description="Widget under an active category promotion",
            price=100.0,
            stock_quantity=10,
            category_id=category.id,
            image_url="https://example.com/img.jpg",
        )
        db_session.add(product)

        promotion = Promotion(
            name="10% off PromoCat",
            type="percentage_on_category",
            conditions={"category_id": category.id},
            rewards={"discount_percentage": 10},
            is_active=True,
        )
        db_session.add(promotion)
        db_session.commit()
        db_session.refresh(product)

        headers = _register_login(client, "promo_customer@test.com", "PromoCustomer1")
        address_id = _add_default_address(client, headers)

        client.post("/cart/items", json={"product_id": product.id, "quantity": 1}, headers=headers)

        cart_resp = client.get("/cart", headers=headers)
        assert cart_resp.status_code == 200
        cart_data = cart_resp.json()
        assert cart_data["subtotal"] == 100.0
        assert cart_data["total_amount"] == 90.0
        assert "10% off PromoCat" in cart_data["applied_promotions"]

        order_resp = client.post(
            "/order",
            json={"shipping_address_id": address_id, "billing_address_id": address_id},
            headers=headers,
        )
        assert order_resp.status_code == 201, order_resp.json()
        order_id = order_resp.json()["id"]

        # The order must reflect the same 10% promotion the cart displayed —
        # previously this was ignored entirely at checkout.
        assert order_resp.json()["total_amount"] == 90.0

        order = db_session.query(Order).filter(Order.id == order_id).one()
        assert float(order.subtotal) == 100.0
        assert float(order.discount_amount) == 10.0
