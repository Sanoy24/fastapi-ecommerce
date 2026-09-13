"""
Tests for GET /order/{order_id}/invoice — a downloadable PDF invoice for a
placed order.

Reuses OrderService.get_one_order for the actual order lookup, so the same
ownership check as GET /order/{order_id} applies here for free: an order
that isn't yours 404s instead of leaking someone else's invoice.
"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.product import Product


def _register_and_login(client: TestClient, email: str, password: str) -> dict:
    client.post(
        "/users/register",
        json={"email": email, "password": password, "first_name": "Test", "last_name": "User", "phone": "0944400001"},
    )
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _make_product(db_session: Session, *, slug: str = "invoice-widget", price: float = 25.0) -> Product:
    product = Product(
        name="Invoice Widget",
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


def _place_order(client: TestClient, headers: dict, product: Product, *, quantity: int = 2) -> dict:
    addr = client.post(
        "/users/me/address",
        json={
            "type": "shipping", "street": "123 Invoice St", "city": "Invoice City",
            "country": "Invoice Country", "zip_code": "12345", "state": "Invoice State",
        },
        headers=headers,
    ).json()
    client.post("/cart/items", json={"product_id": product.id, "quantity": quantity}, headers=headers)
    resp = client.post(
        "/order",
        json={"shipping_address_id": addr["id"], "billing_address_id": addr["id"]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.json()
    return resp.json()


class TestInvoiceAccess:
    def test_requires_authentication(self, client: TestClient, db_session: Session):
        resp = client.get("/order/1/invoice")
        assert resp.status_code == 401

    def test_rejects_nonexistent_order(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "inv_cust1@test.com", "InvCust1")
        resp = client.get("/order/999999/invoice", headers=customer)
        assert resp.status_code == 404

    def test_cannot_download_someone_elses_invoice(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="invoice-other-widget")
        owner = _register_and_login(client, "inv_owner@test.com", "InvOwner1")
        attacker = _register_and_login(client, "inv_attacker@test.com", "InvAttack1")

        order = _place_order(client, owner, product)
        resp = client.get(f"/order/{order['id']}/invoice", headers=attacker)

        assert resp.status_code == 404


class TestInvoiceContent:
    def test_returns_a_valid_pdf(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="invoice-pdf-widget", price=25.0)
        customer = _register_and_login(client, "inv_pdf_cust@test.com", "InvPdf123")

        order = _place_order(client, customer, product, quantity=2)
        resp = client.get(f"/order/{order['id']}/invoice", headers=customer)

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert order["order_number"] in resp.headers["content-disposition"]
        assert resp.content.startswith(b"%PDF-")
        assert len(resp.content) > 0
