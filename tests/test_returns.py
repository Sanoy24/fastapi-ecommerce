"""
Tests for the returns lifecycle: filing a return, listing your own, and an
admin approving/rejecting one.

Before this, a customer could file a return (POST /order/{id}/return) and
an admin could flip its status (PATCH /admin/returns/{id}) — and that flip
did nothing else. No restocking, no refund, and no way for the customer to
even see their own return requests afterward. This file covers the three
things that changed: GET /order/returns, automatic restocking on approval,
and the automatic refund that follows it — plus the guard against
double-restocking/double-refunding a second return on the same item, and
the quantity validation that makes an over-claiming return impossible to
approve.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.models.user import User
from app.utils.security import hash_password


def _make_admin(db_session: Session, email: str = "returns_admin@test.com") -> None:
    db_session.add(
        User(
            email=email,
            password_hash=hash_password("ReturnsAdmin1"),
            first_name="Admin",
            last_name="Returns",
            phone="0977700001",
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
        json={"email": email, "password": password, "first_name": "Test", "last_name": "User", "phone": "0977700002"},
    )
    return _login(client, email, password)


def _place_delivered_order(
    client: TestClient, customer_auth: dict, admin_auth: dict, *, price: float = 50.0, stock: int = 20, quantity: int = 2
) -> dict:
    """Place an order, pay it, ship it, and mark it delivered — the only
    state a return can be filed from."""
    client.post("/category", json={"name": "Returns Cat", "description": "d"}, headers=admin_auth)
    product_resp = client.post(
        "/product",
        json={
            "name": "Returns Widget",
            "description": "d",
            "price": price,
            "stock_quantity": stock,
            "is_active": True,
            "category_id": 1,
            "image_url": "http://test.com/img.jpg",
        },
        headers=admin_auth,
    )
    product_id = product_resp.json()["id"]

    client.post("/cart/items", json={"product_id": product_id, "quantity": quantity}, headers=customer_auth)
    addr_resp = client.post(
        "/users/me/address",
        json={"type": "shipping", "street": "1 Return St", "city": "City", "state": "State", "postal_code": "12345", "country": "Country"},
        headers=customer_auth,
    )
    address_id = addr_resp.json()["id"]

    order_resp = client.post(
        "/order",
        json={"shipping_address_id": address_id, "billing_address_id": address_id},
        headers=customer_auth,
    )
    assert order_resp.status_code == 201, order_resp.json()
    order = order_resp.json()

    with patch("stripe.PaymentIntent.create") as mock_create:
        mock_create.return_value = MagicMock(id=f"pi_return_{order['id']}", client_secret="secret")
        intent_resp = client.post("/payments/create-intent", json={"order_id": order["id"]}, headers=customer_auth)
        assert intent_resp.status_code == 200, intent_resp.json()

    with patch("stripe.Webhook.construct_event") as mock_event:
        mock_event.return_value = {
            "id": f"evt_return_{order['id']}",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": f"pi_return_{order['id']}"}},
        }
        webhook_resp = client.post("/payments/webhook", content=b"{}", headers={"stripe-signature": "t"})
        assert webhook_resp.status_code == 200, webhook_resp.json()

    client.put(
        f"/admin/orders/{order['id']}/shipping",
        json={"tracking_number": "TRK-RET-1", "shipping_carrier": "UPS"},
        headers=admin_auth,
    )
    client.put(f"/admin/orders/{order['id']}/status", json={"status": "delivered"}, headers=admin_auth)

    order_id = order["id"]
    order_items = client.get(f"/order/{order_id}", headers=customer_auth).json()["order_items"]
    return {"order_id": order_id, "product_id": product_id, "order_items": order_items}


class TestRequestReturn:
    def test_only_delivered_orders_can_be_returned(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "req_admin1@test.com")
        customer = _register_and_login(client, "req_cust1@test.com", "ReqCust1")
        admin = _login(client, "req_admin1@test.com", "ReturnsAdmin1")

        client.post("/category", json={"name": "Req Cat", "description": "d"}, headers=admin)
        product = client.post(
            "/product",
            json={"name": "Widget", "description": "d", "price": 10.0, "stock_quantity": 5, "is_active": True, "category_id": 1, "image_url": "http://t.com/i.jpg"},
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

        resp = client.post(
            f"/order/{order['id']}/return",
            json={"reason": "changed mind", "items": [{"order_item_id": order["order_items"][0]["id"], "quantity": 1, "reason": "n/a"}]},
            headers=customer,
        )

        assert resp.status_code == 400
        assert "delivered" in resp.json()["detail"].lower()

    def test_rejects_a_quantity_exceeding_what_was_ordered(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "req_admin2@test.com")
        customer = _register_and_login(client, "req_cust2@test.com", "ReqCust2")
        admin = _login(client, "req_admin2@test.com", "ReturnsAdmin1")

        placed = _place_delivered_order(client, customer, admin, quantity=2)
        order_item_id = placed["order_items"][0]["id"]

        resp = client.post(
            f"/order/{placed['order_id']}/return",
            json={"reason": "too many", "items": [{"order_item_id": order_item_id, "quantity": 99, "reason": "n/a"}]},
            headers=customer,
        )

        assert resp.status_code == 400
        assert "only 2 were ordered" in resp.json()["detail"]

    def test_successful_return_request(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "req_admin3@test.com")
        customer = _register_and_login(client, "req_cust3@test.com", "ReqCust3")
        admin = _login(client, "req_admin3@test.com", "ReturnsAdmin1")

        placed = _place_delivered_order(client, customer, admin, quantity=2)
        order_item_id = placed["order_items"][0]["id"]

        resp = client.post(
            f"/order/{placed['order_id']}/return",
            json={"reason": "wrong size", "items": [{"order_item_id": order_item_id, "quantity": 1, "reason": "too small"}]},
            headers=customer,
        )

        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["status"] == "pending"
        assert data["items"] == [{"order_item_id": order_item_id, "quantity": 1, "reason": "too small"}]

        order_resp = client.get(f"/order/{placed['order_id']}", headers=customer)
        assert order_resp.json()["status"] == "return_requested"


class TestListMyReturns:
    def test_customer_sees_only_their_own_returns(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "list_admin1@test.com")
        customer_a = _register_and_login(client, "list_a@test.com", "ListCustA1")
        customer_b = _register_and_login(client, "list_b@test.com", "ListCustB1")
        admin = _login(client, "list_admin1@test.com", "ReturnsAdmin1")

        placed_a = _place_delivered_order(client, customer_a, admin, quantity=1)
        client.post(
            f"/order/{placed_a['order_id']}/return",
            json={"reason": "r", "items": [{"order_item_id": placed_a["order_items"][0]["id"], "quantity": 1, "reason": "n/a"}]},
            headers=customer_a,
        )

        a_returns = client.get("/order/returns", headers=customer_a).json()
        b_returns = client.get("/order/returns", headers=customer_b).json()

        assert len(a_returns) == 1
        assert a_returns[0]["order_id"] == placed_a["order_id"]
        assert b_returns == []

    def test_requires_authentication(self, client: TestClient):
        assert client.get("/order/returns").status_code == 401


class TestResolveReturnApproval:
    def test_approving_restocks_the_returned_quantity(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "resolve_admin1@test.com")
        customer = _register_and_login(client, "resolve_cust1@test.com", "ResolveCust1")
        admin = _login(client, "resolve_admin1@test.com", "ReturnsAdmin1")

        placed = _place_delivered_order(client, customer, admin, stock=20, quantity=2)
        order_item_id = placed["order_items"][0]["id"]

        return_resp = client.post(
            f"/order/{placed['order_id']}/return",
            json={"reason": "defective", "items": [{"order_item_id": order_item_id, "quantity": 2, "reason": "broken"}]},
            headers=customer,
        )
        return_id = return_resp.json()["id"]

        db_session.expire_all()
        stock_before = db_session.get(Product, placed["product_id"]).stock_quantity

        with patch("stripe.Refund.create") as mock_refund:
            mock_refund.return_value = MagicMock(id="re_test_1")
            resolve_resp = client.patch(
                f"/admin/returns/{return_id}",
                json={"status": "approved", "resolution_note": "confirmed defective"},
                headers=admin,
            )

        assert resolve_resp.status_code == 200, resolve_resp.json()

        db_session.expire_all()
        stock_after = db_session.get(Product, placed["product_id"]).stock_quantity
        assert stock_after == stock_before + 2

        tx = (
            db_session.query(InventoryTransaction)
            .filter(InventoryTransaction.order_id == placed["order_id"], InventoryTransaction.transaction_type == "return")
            .first()
        )
        assert tx is not None
        assert tx.quantity_change == 2

    def test_approving_triggers_an_automatic_refund(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "resolve_admin2@test.com")
        customer = _register_and_login(client, "resolve_cust2@test.com", "ResolveCust2")
        admin = _login(client, "resolve_admin2@test.com", "ReturnsAdmin1")

        placed = _place_delivered_order(client, customer, admin, price=30.0, quantity=2)
        order_item_id = placed["order_items"][0]["id"]

        return_id = client.post(
            f"/order/{placed['order_id']}/return",
            json={"reason": "r", "items": [{"order_item_id": order_item_id, "quantity": 1, "reason": "n/a"}]},
            headers=customer,
        ).json()["id"]

        with patch("stripe.Refund.create") as mock_refund:
            mock_refund.return_value = MagicMock(id="re_test_2")
            resolve_resp = client.patch(
                f"/admin/returns/{return_id}",
                json={"status": "approved", "resolution_note": "ok"},
                headers=admin,
            )

        assert resolve_resp.status_code == 200
        assert resolve_resp.json()["refund_error"] is None
        mock_refund.assert_called_once()
        assert mock_refund.call_args.kwargs["amount"] == 3000  # $30 * 1 unit, in cents

        order_resp = client.get(f"/order/{placed['order_id']}", headers=customer)
        assert order_resp.json()["status"] == "refunded"

    def test_refund_failure_still_leaves_the_return_approved_and_restocked(
        self, client: TestClient, db_session: Session
    ):
        """An automatic refund failing (e.g. a Stripe error) must not undo
        the restocking or the approval itself — the physical item is back
        regardless of whether the payment side succeeded, and blocking the
        whole approval on a payment hiccup would leave inventory wrong."""
        _make_admin(db_session, "resolve_admin3@test.com")
        customer = _register_and_login(client, "resolve_cust3@test.com", "ResolveCust3")
        admin = _login(client, "resolve_admin3@test.com", "ReturnsAdmin1")

        placed = _place_delivered_order(client, customer, admin, quantity=1)
        order_item_id = placed["order_items"][0]["id"]

        return_id = client.post(
            f"/order/{placed['order_id']}/return",
            json={"reason": "r", "items": [{"order_item_id": order_item_id, "quantity": 1, "reason": "n/a"}]},
            headers=customer,
        ).json()["id"]

        db_session.expire_all()
        stock_before = db_session.get(Product, placed["product_id"]).stock_quantity

        import stripe
        with patch("stripe.Refund.create", side_effect=stripe.error.StripeError("card issuer unreachable")):
            resolve_resp = client.patch(
                f"/admin/returns/{return_id}",
                json={"status": "approved", "resolution_note": "ok"},
                headers=admin,
            )

        assert resolve_resp.status_code == 200, resolve_resp.json()
        assert resolve_resp.json()["status"] == "approved"
        assert resolve_resp.json()["refund_error"] is not None

        db_session.expire_all()
        assert db_session.get(Product, placed["product_id"]).stock_quantity == stock_before + 1

    def test_cannot_double_approve_returns_covering_the_same_item(
        self, client: TestClient, db_session: Session
    ):
        _make_admin(db_session, "resolve_admin4@test.com")
        customer = _register_and_login(client, "resolve_cust4@test.com", "ResolveCust4")
        admin = _login(client, "resolve_admin4@test.com", "ReturnsAdmin1")

        placed = _place_delivered_order(client, customer, admin, quantity=1)
        order_item_id = placed["order_items"][0]["id"]

        return_id_1 = client.post(
            f"/order/{placed['order_id']}/return",
            json={"reason": "r1", "items": [{"order_item_id": order_item_id, "quantity": 1, "reason": "n/a"}]},
            headers=customer,
        ).json()["id"]

        with patch("stripe.Refund.create") as mock_refund:
            mock_refund.return_value = MagicMock(id="re_test_3")
            first = client.patch(
                f"/admin/returns/{return_id_1}",
                json={"status": "approved", "resolution_note": "ok"},
                headers=admin,
            )
        assert first.status_code == 200

        # A second return request somehow filed against the same item
        # (e.g. two pending requests existed before the first was
        # resolved) must not be approvable afterward.
        from app.models.return_request import ReturnRequest
        second_return = ReturnRequest(
            order_id=placed["order_id"],
            user_id=db_session.query(ReturnRequest).filter_by(id=return_id_1).first().user_id,
            reason="r2",
            items=[{"order_item_id": order_item_id, "quantity": 1, "reason": "n/a"}],
        )
        db_session.add(second_return)
        db_session.commit()

        second_resp = client.patch(
            f"/admin/returns/{second_return.id}",
            json={"status": "approved", "resolution_note": "ok"},
            headers=admin,
        )

        assert second_resp.status_code == 400
        assert "already covered" in second_resp.json()["detail"]

    def test_rejecting_a_return_does_not_restock_or_refund(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "resolve_admin5@test.com")
        customer = _register_and_login(client, "resolve_cust5@test.com", "ResolveCust5")
        admin = _login(client, "resolve_admin5@test.com", "ReturnsAdmin1")

        placed = _place_delivered_order(client, customer, admin, quantity=1)
        order_item_id = placed["order_items"][0]["id"]

        return_id = client.post(
            f"/order/{placed['order_id']}/return",
            json={"reason": "r", "items": [{"order_item_id": order_item_id, "quantity": 1, "reason": "n/a"}]},
            headers=customer,
        ).json()["id"]

        db_session.expire_all()
        stock_before = db_session.get(Product, placed["product_id"]).stock_quantity

        with patch("stripe.Refund.create") as mock_refund:
            resp = client.patch(
                f"/admin/returns/{return_id}",
                json={"status": "rejected", "resolution_note": "not eligible"},
                headers=admin,
            )
            mock_refund.assert_not_called()

        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

        db_session.expire_all()
        assert db_session.get(Product, placed["product_id"]).stock_quantity == stock_before

        order_resp = client.get(f"/order/{placed['order_id']}", headers=customer)
        assert order_resp.json()["status"] == "delivered"

    def test_cannot_resolve_an_already_resolved_return(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "resolve_admin6@test.com")
        customer = _register_and_login(client, "resolve_cust6@test.com", "ResolveCust6")
        admin = _login(client, "resolve_admin6@test.com", "ReturnsAdmin1")

        placed = _place_delivered_order(client, customer, admin, quantity=1)
        order_item_id = placed["order_items"][0]["id"]

        return_id = client.post(
            f"/order/{placed['order_id']}/return",
            json={"reason": "r", "items": [{"order_item_id": order_item_id, "quantity": 1, "reason": "n/a"}]},
            headers=customer,
        ).json()["id"]

        with patch("stripe.Refund.create") as mock_refund:
            mock_refund.return_value = MagicMock(id="re_test_4")
            client.patch(f"/admin/returns/{return_id}", json={"status": "approved", "resolution_note": "ok"}, headers=admin)

        second = client.patch(
            f"/admin/returns/{return_id}", json={"status": "rejected", "resolution_note": "too late"}, headers=admin
        )

        assert second.status_code == 400
        assert "already" in second.json()["detail"].lower()
