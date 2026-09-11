"""
Tests for order tracking — exposing the Shipment row and OrderEvent
timeline that were already being written on every order but never
returned by any endpoint.

OrderResponse already flattened tracking_number/shipping_carrier/shipped_at
from the Order row itself (see test_fulfillment.py), so customers could see
*basic* tracking already. What was missing was the richer Shipment.status
(pending/shipped/in_transit/delivered/failed) and estimated_delivery, and
the OrderEvent status timeline — neither reachable from any response.

Tracing that surfaced a real bug: OrderCrud.update_order_status's
"delivered" transition set Order.delivered_at but never touched the
Shipment row at all, so shipment.status stayed "shipped" forever — the
richer status this feature exposes would have been actively wrong the
moment an order was actually delivered.
"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.shipment import Shipment
from app.models.user import User
from app.utils.security import hash_password


def _make_admin(db_session: Session, email: str = "tracking_admin@test.com") -> None:
    db_session.add(
        User(
            email=email,
            password_hash=hash_password("TrackAdmin1"),
            first_name="Admin",
            last_name="Tracking",
            phone="0966600001",
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
        json={"email": email, "password": password, "first_name": "Test", "last_name": "User", "phone": "0966600002"},
    )
    return _login(client, email, password)


def _place_order(client: TestClient, customer_auth: dict, admin_auth: dict) -> dict:
    client.post("/category", json={"name": "Tracking Cat", "description": "d"}, headers=admin_auth)
    product_resp = client.post(
        "/product",
        json={
            "name": "Tracking Widget",
            "description": "d",
            "price": 40.0,
            "stock_quantity": 20,
            "is_active": True,
            "category_id": 1,
            "image_url": "http://test.com/img.jpg",
        },
        headers=admin_auth,
    )
    product_id = product_resp.json()["id"]

    client.post("/cart/items", json={"product_id": product_id, "quantity": 1}, headers=customer_auth)
    addr_resp = client.post(
        "/users/me/address",
        json={"type": "shipping", "street": "1 Track St", "city": "City", "state": "State", "postal_code": "12345", "country": "Country"},
        headers=customer_auth,
    )
    address_id = addr_resp.json()["id"]

    order_resp = client.post(
        "/order",
        json={"shipping_address_id": address_id, "billing_address_id": address_id},
        headers=customer_auth,
    )
    assert order_resp.status_code == 201, order_resp.json()
    return order_resp.json()


class TestOrderEventTimeline:
    def test_new_order_has_a_placed_event(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "timeline_admin1@test.com")
        customer = _register_and_login(client, "timeline_cust1@test.com", "TimelineC1")
        admin = _login(client, "timeline_admin1@test.com", "TrackAdmin1")

        order = _place_order(client, customer, admin)

        resp = client.get(f"/order/{order['id']}", headers=customer)
        events = resp.json()["events"]

        assert len(events) == 1
        assert events[0]["to_status"] == "pending"
        assert events[0]["from_status"] is None

    def test_status_changes_are_appended_to_the_timeline(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "timeline_admin2@test.com")
        customer = _register_and_login(client, "timeline_cust2@test.com", "TimelineC2")
        admin = _login(client, "timeline_admin2@test.com", "TrackAdmin1")

        order = _place_order(client, customer, admin)
        client.put(f"/admin/orders/{order['id']}/status", json={"status": "paid"}, headers=admin)
        client.put(f"/admin/orders/{order['id']}/status", json={"status": "processing"}, headers=admin)

        resp = client.get(f"/order/{order['id']}", headers=customer)
        events = resp.json()["events"]

        assert len(events) == 3
        to_statuses = {e["to_status"] for e in events}
        assert to_statuses == {"pending", "paid", "processing"}


class TestShipmentTracking:
    def test_shipment_appears_after_admin_ships_the_order(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "ship_admin1@test.com")
        customer = _register_and_login(client, "ship_cust1@test.com", "ShipCust1")
        admin = _login(client, "ship_admin1@test.com", "TrackAdmin1")

        order = _place_order(client, customer, admin)
        client.put(f"/admin/orders/{order['id']}/status", json={"status": "paid"}, headers=admin)
        client.put(
            f"/admin/orders/{order['id']}/shipping",
            json={"tracking_number": "TRK-999", "shipping_carrier": "DHL"},
            headers=admin,
        )

        resp = client.get(f"/order/{order['id']}", headers=customer)
        shipments = resp.json()["shipments"]

        assert len(shipments) == 1
        assert shipments[0]["tracking_number"] == "TRK-999"
        assert shipments[0]["carrier"] == "DHL"
        assert shipments[0]["status"] == "shipped"
        assert shipments[0]["delivered_at"] is None

    def test_shipment_status_becomes_delivered_when_order_is_marked_delivered(
        self, client: TestClient, db_session: Session
    ):
        """Regression test: update_order_status's "delivered" transition
        used to touch only Order.delivered_at, leaving the Shipment row
        stuck at status="shipped" forever."""
        _make_admin(db_session, "ship_admin2@test.com")
        customer = _register_and_login(client, "ship_cust2@test.com", "ShipCust2")
        admin = _login(client, "ship_admin2@test.com", "TrackAdmin1")

        order = _place_order(client, customer, admin)
        client.put(f"/admin/orders/{order['id']}/status", json={"status": "paid"}, headers=admin)
        client.put(
            f"/admin/orders/{order['id']}/shipping",
            json={"tracking_number": "TRK-1000", "shipping_carrier": "UPS"},
            headers=admin,
        )

        resp = client.put(
            f"/admin/orders/{order['id']}/status", json={"status": "delivered"}, headers=admin
        )
        assert resp.status_code == 200, resp.json()

        db_session.expire_all()
        shipment = db_session.query(Shipment).filter(Shipment.order_id == order["id"]).first()
        assert shipment.status == "delivered"
        assert shipment.delivered_at is not None

        # And the API surface reflects it too, not just the DB row.
        order_resp = client.get(f"/order/{order['id']}", headers=customer)
        shipment_data = order_resp.json()["shipments"][0]
        assert shipment_data["status"] == "delivered"
        assert shipment_data["delivered_at"] is not None

    def test_order_with_no_shipment_yet_returns_an_empty_list(
        self, client: TestClient, db_session: Session
    ):
        _make_admin(db_session, "ship_admin3@test.com")
        customer = _register_and_login(client, "ship_cust3@test.com", "ShipCust3")
        admin = _login(client, "ship_admin3@test.com", "TrackAdmin1")

        order = _place_order(client, customer, admin)

        resp = client.get(f"/order/{order['id']}", headers=customer)
        assert resp.json()["shipments"] == []


class TestGuestOrderTracking:
    def test_guest_order_lookup_includes_shipment_and_timeline(
        self, client: TestClient, db_session: Session
    ):
        _make_admin(db_session, "ship_admin4@test.com")
        admin = _login(client, "ship_admin4@test.com", "TrackAdmin1")

        client.post("/category", json={"name": "Guest Track Cat", "description": "d"}, headers=admin)
        product_resp = client.post(
            "/product",
            json={
                "name": "Guest Tracking Widget",
                "description": "d",
                "price": 25.0,
                "stock_quantity": 10,
                "is_active": True,
                "category_id": 1,
                "image_url": "http://test.com/img.jpg",
            },
            headers=admin,
        )
        product_id = product_resp.json()["id"]

        client.post("/cart/items", json={"product_id": product_id, "quantity": 1})
        order_resp = client.post(
            "/order/guest",
            json={
                "email": "guest_tracking@example.com",
                "shipping_address": {
                    "street": "1 Guest Track Ave",
                    "city": "City",
                    "state": "ST",
                    "postal_code": "00001",
                    "country": "Country",
                },
                "billing_address": {
                    "street": "1 Guest Track Ave",
                    "city": "City",
                    "state": "ST",
                    "postal_code": "00001",
                    "country": "Country",
                },
            },
        )
        order = order_resp.json()

        client.put(f"/admin/orders/{order['id']}/status", json={"status": "paid"}, headers=admin)
        client.put(
            f"/admin/orders/{order['id']}/shipping",
            json={"tracking_number": "TRK-GUEST-1", "shipping_carrier": "FedEx"},
            headers=admin,
        )

        lookup_resp = client.post(
            "/order/guest/lookup",
            json={"order_number": order["order_number"], "email": "guest_tracking@example.com"},
        )

        assert lookup_resp.status_code == 200
        data = lookup_resp.json()
        assert data["shipments"][0]["tracking_number"] == "TRK-GUEST-1"
        assert any(e["to_status"] == "pending" for e in data["events"])
