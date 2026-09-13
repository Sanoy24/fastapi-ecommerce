"""
Tests for guest checkout — placing, tracking, paying for, and later
claiming an order with no account.

Guest carts already worked end to end before this (session_id cookie,
anonymous get_or_create_cart — see app/api/v1/routes/cart.py); checkout was
the wall, since every table an order touches assumed a real user:
Order.user_id, Order.shipping_address_id/billing_address_id (real Address
rows), and InventoryReservation.user_id were all NOT NULL.

Tracing that also surfaced a real, pre-existing bug this feature would
otherwise have silently triggered: reservation release (on payment
success/failure/cancellation) filtered by InventoryReservation.user_id ==
order.user_id. For a guest order (user_id NULL), that filter becomes
"user_id IS NULL" — matching every other guest order's reservations, not
just this one's. TestReservationReleaseIsOrderScoped below covers the fix
directly (app/services/order_service.py, app/services/payment_service.py).
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.crud.order import OrderCrud
from app.models.coupon import Coupon
from app.models.inventory_reservation import InventoryReservation
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService
from app.utils.security import hash_password
from app.workers.arq_worker import WorkerSettings, send_guest_order_claim_email_task

VALID_ADDRESS = {
    "street": "1 Guest Ave",
    "city": "Guestville",
    "state": "GS",
    "postal_code": "00001",
    "country": "Guestland",
}


def _make_product(db_session: Session, *, stock: int = 100, price: float = 50.0, slug: str = "guest-widget") -> Product:
    product = Product(
        name="Guest Widget",
        slug=slug,
        description="For guest checkout tests",
        price=price,
        stock_quantity=stock,
        image_url="https://example.com/img.jpg",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


def _make_admin(db_session: Session, email: str = "guest_ck_admin@test.com") -> None:
    db_session.add(
        User(
            email=email,
            password_hash=hash_password("AdminGuest1"),
            first_name="Admin",
            last_name="Guest",
            phone="0955500099",
            is_verified=True,
            role="admin",
        )
    )
    db_session.commit()


def _register_and_login(client: TestClient, email: str, password: str) -> dict:
    client.post(
        "/users/register",
        json={"email": email, "password": password, "first_name": "Test", "last_name": "User", "phone": "0955500001"},
    )
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _add_to_guest_cart(client: TestClient, product_id: int, quantity: int = 1):
    resp = client.post("/cart/items", json={"product_id": product_id, "quantity": quantity})
    assert resp.status_code in (200, 201), resp.json()
    return resp


def _checkout_as_guest(client: TestClient, email: str = "guest@example.com", **overrides):
    payload = {
        "email": email,
        "shipping_address": VALID_ADDRESS,
        "billing_address": VALID_ADDRESS,
    }
    payload.update(overrides)
    return client.post("/order/guest", json=payload)


class TestGuestCheckoutHappyPath:
    def test_guest_can_check_out_without_an_account(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="happy-path")
        _add_to_guest_cart(client, product.id, quantity=2)

        resp = _checkout_as_guest(client, email="alice@example.com")

        assert resp.status_code == 201, resp.json()
        data = resp.json()
        assert data["status"] == "pending"
        assert data["total_amount"] == pytest.approx(100.0)

    def test_guest_order_has_no_user_id_but_has_guest_email(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="no-user-id")
        _add_to_guest_cart(client, product.id)

        resp = _checkout_as_guest(client, email="bob@example.com")
        order_id = resp.json()["id"]

        db_session.expire_all()
        order = db_session.get(Order, order_id)
        assert order.user_id is None
        assert order.guest_email == "bob@example.com"
        assert order.shipping_address_id is None
        assert order.shipping_address_snapshot["city"] == "Guestville"

    def test_guest_cart_is_cleared_after_checkout(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="cart-cleared")
        _add_to_guest_cart(client, product.id)
        checkout_resp = _checkout_as_guest(client)
        assert checkout_resp.status_code == 201, checkout_resp.json()

        cart_resp = client.get("/cart")
        assert cart_resp.status_code == 200
        assert cart_resp.json()["items"] == []

    def test_guest_checkout_requires_a_cart_session(self, client: TestClient):
        # No prior /cart call in this test — no session_id cookie exists yet.
        resp = _checkout_as_guest(client)
        assert resp.status_code == 400
        assert "cart" in resp.json()["detail"].lower()

    def test_guest_checkout_fails_when_cart_is_empty(self, client: TestClient):
        client.get("/cart")  # assigns a session_id cookie with an empty cart
        resp = _checkout_as_guest(client)
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()


class TestGuestCheckoutValidation:
    def test_guest_checkout_rejects_out_of_stock(self, client: TestClient, db_session: Session):
        """CartService already rejects an over-quantity add at cart time —
        this exercises OrderCrud.validate_stock instead: stock drops to 0
        between add-to-cart and checkout (a sold-out race), which checkout
        must still catch even though the add-to-cart call succeeded."""
        product = _make_product(db_session, stock=1, slug="out-of-stock")
        _add_to_guest_cart(client, product.id, quantity=1)

        product.stock_quantity = 0
        db_session.commit()

        resp = _checkout_as_guest(client)

        assert resp.status_code == 400
        assert "stock" in resp.json()["detail"].lower()

    def test_guest_checkout_rejects_a_cart_with_a_coupon(self, client: TestClient, db_session: Session):
        """CouponUsage.user_id is NOT NULL — there is no row to record a
        guest's usage against, so this must be rejected up front rather
        than silently dropping the discount or letting it be reused freely."""
        db_session.add(
            Coupon(code="GUESTSAVE", discount_type="fixed", discount_value=5.0, is_active=True)
        )
        db_session.commit()

        product = _make_product(db_session, slug="coupon-cart")
        _add_to_guest_cart(client, product.id)
        coupon_resp = client.post("/cart/coupon", params={"code": "GUESTSAVE"})
        assert coupon_resp.status_code == 200, coupon_resp.json()

        resp = _checkout_as_guest(client)

        assert resp.status_code == 400
        assert "sign in" in resp.json()["detail"].lower()

    def test_guest_checkout_rejects_invalid_shipping_method(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="bad-shipping")
        _add_to_guest_cart(client, product.id)

        resp = _checkout_as_guest(client, shipping_method_id=999999)

        assert resp.status_code == 400
        assert "shipping method" in resp.json()["detail"].lower()


class TestGuestOrderVisibleToAdmin:
    """Regression coverage for OrderCrud.get_all_orders: an inner join on
    User would silently exclude every guest order from the admin list."""

    def test_guest_order_appears_in_admin_order_list(self, client: TestClient, db_session: Session):
        _make_admin(db_session)
        product = _make_product(db_session, slug="admin-visible")
        _add_to_guest_cart(client, product.id)
        order_resp = _checkout_as_guest(client, email="carol@example.com")
        order_id = order_resp.json()["id"]

        admin_auth = _login(client, "guest_ck_admin@test.com", "AdminGuest1")
        listing = client.get("/admin/orders", headers=admin_auth)

        assert listing.status_code == 200
        matching = [o for o in listing.json()["orders"] if o["id"] == order_id]
        assert len(matching) == 1, "guest order missing from admin listing"
        assert matching[0]["is_guest_order"] is True
        assert matching[0]["user_email"] == "carol@example.com"

    def test_admin_can_update_guest_order_status(self, client: TestClient, db_session: Session):
        _make_admin(db_session, email="guest_ck_admin2@test.com")
        product = _make_product(db_session, slug="admin-status-update")
        _add_to_guest_cart(client, product.id)
        order_id = _checkout_as_guest(client, email="dana@example.com").json()["id"]

        admin_auth = _login(client, "guest_ck_admin2@test.com", "AdminGuest1")
        resp = client.put(
            f"/admin/orders/{order_id}/status", json={"status": "paid"}, headers=admin_auth
        )

        assert resp.status_code == 200, resp.json()
        assert resp.json()["user_email"] == "dana@example.com"


class TestGuestOrderLookup:
    def test_lookup_succeeds_with_correct_number_and_email(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="lookup-ok")
        _add_to_guest_cart(client, product.id)
        order = _checkout_as_guest(client, email="erin@example.com").json()

        resp = client.post(
            "/order/guest/lookup", json={"order_number": order["order_number"], "email": "erin@example.com"}
        )

        assert resp.status_code == 200
        assert resp.json()["id"] == order["id"]

    def test_lookup_is_case_insensitive_on_email(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="lookup-case")
        _add_to_guest_cart(client, product.id)
        order = _checkout_as_guest(client, email="Frank@Example.com").json()

        resp = client.post(
            "/order/guest/lookup", json={"order_number": order["order_number"], "email": "frank@example.com"}
        )

        assert resp.status_code == 200

    def test_lookup_fails_with_wrong_email(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="lookup-wrong-email")
        _add_to_guest_cart(client, product.id)
        order = _checkout_as_guest(client, email="grace@example.com").json()

        resp = client.post(
            "/order/guest/lookup", json={"order_number": order["order_number"], "email": "not-grace@example.com"}
        )

        assert resp.status_code == 404

    def test_lookup_fails_with_wrong_order_number(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="lookup-wrong-number")
        _add_to_guest_cart(client, product.id)
        _checkout_as_guest(client, email="henry@example.com")

        resp = client.post(
            "/order/guest/lookup", json={"order_number": "ORD-does-not-exist", "email": "henry@example.com"}
        )

        assert resp.status_code == 404


class TestGuestOrderPayment:
    def test_guest_can_create_a_payment_intent(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="guest-pay-ok")
        _add_to_guest_cart(client, product.id)
        order = _checkout_as_guest(client, email="iris@example.com").json()

        with patch("stripe.PaymentIntent.create") as mock_create:
            mock_create.return_value = MagicMock(id="pi_guest_1", client_secret="secret_guest_1")
            resp = client.post(
                "/payments/guest/create-intent",
                json={"order_number": order["order_number"], "email": "iris@example.com"},
            )

        assert resp.status_code == 200, resp.json()
        assert resp.json()["payment_intent_id"] == "pi_guest_1"

    def test_guest_payment_intent_fails_with_wrong_email(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="guest-pay-bad-email")
        _add_to_guest_cart(client, product.id)
        order = _checkout_as_guest(client, email="jack@example.com").json()

        resp = client.post(
            "/payments/guest/create-intent",
            json={"order_number": order["order_number"], "email": "not-jack@example.com"},
        )

        assert resp.status_code == 404


class TestGuestOrderClaim:
    async def _request_claim_token(self, db_session: Session, order_number: str, email: str) -> str:
        """Drive the real service method to get a real, usable token —
        exercises the exact Redis read/write path the route uses (the
        `client` fixture's mock Redis patches are active for the whole
        test), without needing to reach into Redis internals from the test.
        """
        service = OrderService(db_session)
        captured = {}

        async def _fake_send(to_address, order_number, claim_token):
            captured["token"] = claim_token

        with patch("app.services.email_service.send_guest_order_claim_email", _fake_send):
            await service.request_guest_order_claim_link(order_number, email, arq_pool=None)

        assert "token" in captured, "no claim email was sent — order/email did not match"
        return captured["token"]

    def test_request_claim_link_always_returns_200(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="claim-link-200")
        _add_to_guest_cart(client, product.id)
        order = _checkout_as_guest(client, email="karen@example.com").json()

        matching = client.post(
            "/order/guest/request-claim-link",
            json={"order_number": order["order_number"], "email": "karen@example.com"},
        )
        not_matching = client.post(
            "/order/guest/request-claim-link",
            json={"order_number": "ORD-nonexistent", "email": "nobody@example.com"},
        )

        assert matching.status_code == 200
        assert not_matching.status_code == 200
        assert matching.json() == not_matching.json(), "response must not reveal whether a match was found"

    def test_request_claim_link_enqueues_the_email_task(self, client: TestClient, db_session: Session):
        # `client` isn't used for an HTTP call here, but its fixture is what
        # patches redis_client to the in-memory mock — without it this test
        # would try to talk to a real, unconnected Redis client.
        product = _make_product(db_session, slug="claim-link-enqueue")
        # Build the guest order directly at the CRUD layer for this
        # unit-level test — no HTTP/cart round trip needed.
        from app.models.cart import Cart
        from app.models.cart_item import CartItem

        cart = Cart(session_id="sess-enqueue-test", user_id=None)
        db_session.add(cart)
        db_session.commit()
        db_session.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=1))
        db_session.commit()

        order = OrderCrud(db_session).create_guest_order(
            session_id="sess-enqueue-test",
            guest_email="liam@example.com",
            shipping_address=_guest_address(),
            billing_address=_guest_address(),
        )

        service = OrderService(db_session)
        arq_pool = MagicMock()
        arq_pool.enqueue_job = AsyncMock()

        asyncio.run(
            service.request_guest_order_claim_link(order.order_number, "liam@example.com", arq_pool)
        )

        arq_pool.enqueue_job.assert_awaited_once()
        args = arq_pool.enqueue_job.await_args.args
        assert args[0] == "send_guest_order_claim_email_task"
        assert args[1] == "liam@example.com"
        assert args[2] == order.order_number

    def test_claim_requires_authentication(self, client: TestClient):
        resp = client.post("/order/guest/claim", json={"claim_token": "whatever"})
        assert resp.status_code == 401

    def test_claim_with_invalid_token_fails(self, client: TestClient, db_session: Session):
        auth = _register_and_login(client, "claimant_bad_token@example.com", "ClaimBad1")
        resp = client.post("/order/guest/claim", json={"claim_token": "not-a-real-token"}, headers=auth)
        assert resp.status_code == 400

    def test_claim_attaches_order_to_the_authenticated_account(
        self, client: TestClient, db_session: Session
    ):
        product = _make_product(db_session, slug="claim-attach")
        _add_to_guest_cart(client, product.id)
        order = _checkout_as_guest(client, email="mona@example.com").json()

        token = asyncio.run(
            self._request_claim_token(db_session, order["order_number"], "mona@example.com")
        )

        auth = _register_and_login(client, "mona_account@example.com", "MonaClaim1")
        resp = client.post("/order/guest/claim", json={"claim_token": token}, headers=auth)

        assert resp.status_code == 200, resp.json()
        assert resp.json()["id"] == order["id"]

        db_session.expire_all()
        claimed = db_session.get(Order, order["id"])
        assert claimed.user_id is not None
        assert claimed.guest_email == "mona@example.com", "guest_email is kept as history, not cleared"

    def test_claimed_order_shows_up_in_the_accounts_order_list(
        self, client: TestClient, db_session: Session
    ):
        product = _make_product(db_session, slug="claim-shows-up")
        _add_to_guest_cart(client, product.id)
        order = _checkout_as_guest(client, email="nate@example.com").json()

        token = asyncio.run(
            self._request_claim_token(db_session, order["order_number"], "nate@example.com")
        )
        auth = _register_and_login(client, "nate_account@example.com", "NateClaim1")
        client.post("/order/guest/claim", json={"claim_token": token}, headers=auth)

        listing = client.get("/order", headers=auth)
        assert any(o["id"] == order["id"] for o in listing.json())

    def test_claim_token_is_one_time_use(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="claim-one-time")
        _add_to_guest_cart(client, product.id)
        order = _checkout_as_guest(client, email="olive@example.com").json()

        token = asyncio.run(
            self._request_claim_token(db_session, order["order_number"], "olive@example.com")
        )
        auth = _register_and_login(client, "olive_account@example.com", "OliveClaim1")

        first = client.post("/order/guest/claim", json={"claim_token": token}, headers=auth)
        second = client.post("/order/guest/claim", json={"claim_token": token}, headers=auth)

        assert first.status_code == 200
        assert second.status_code == 400

    def test_second_claim_link_fails_once_order_is_already_claimed(
        self, client: TestClient, db_session: Session
    ):
        product = _make_product(db_session, slug="claim-already-claimed")
        _add_to_guest_cart(client, product.id)
        order = _checkout_as_guest(client, email="paul@example.com").json()

        token_a = asyncio.run(
            self._request_claim_token(db_session, order["order_number"], "paul@example.com")
        )
        token_b = asyncio.run(
            self._request_claim_token(db_session, order["order_number"], "paul@example.com")
        )

        auth_1 = _register_and_login(client, "paul_account_1@example.com", "PaulClaim1")
        auth_2 = _register_and_login(client, "paul_account_2@example.com", "PaulClaim2")

        first = client.post("/order/guest/claim", json={"claim_token": token_a}, headers=auth_1)
        second = client.post("/order/guest/claim", json={"claim_token": token_b}, headers=auth_2)

        assert first.status_code == 200
        assert second.status_code == 400

    def test_guest_lookup_no_longer_works_once_claimed(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="claim-then-lookup")
        _add_to_guest_cart(client, product.id)
        order = _checkout_as_guest(client, email="quinn@example.com").json()

        token = asyncio.run(
            self._request_claim_token(db_session, order["order_number"], "quinn@example.com")
        )
        auth = _register_and_login(client, "quinn_account@example.com", "QuinnClaim1")
        client.post("/order/guest/claim", json={"claim_token": token}, headers=auth)

        resp = client.post(
            "/order/guest/lookup",
            json={"order_number": order["order_number"], "email": "quinn@example.com"},
        )
        assert resp.status_code == 404


class TestGuestOrderClaimEmailTaskIsRegistered:
    """The outbox-worker fix (see app/workers/arq_worker.py history) exists
    precisely because a task can be fully implemented and still never run
    if nobody adds it to WorkerSettings. Same guard, same reason, for the
    new task this feature adds."""

    def test_send_guest_order_claim_email_task_is_registered(self):
        assert send_guest_order_claim_email_task in WorkerSettings.functions


def _guest_address():
    from app.schema.order_schema import GuestAddressInput
    return GuestAddressInput(**VALID_ADDRESS)


class TestReservationReleaseIsOrderScoped:
    """
    The pre-existing bug this feature required fixing: reservation release
    used to filter by `InventoryReservation.user_id == order.user_id`. For
    two of the SAME user's simultaneous pending orders, that filter matches
    both orders' reservations — cancelling one incorrectly frees the
    other's stock too. For two guest orders (user_id NULL on both), it's
    worse: the filter becomes "user_id IS NULL", matching every in-flight
    guest reservation in the table at once.
    """

    def test_cancelling_one_order_does_not_release_a_different_orders_reservation(
        self, client: TestClient, db_session: Session
    ):
        auth = _register_and_login(client, "two_orders@example.com", "TwoOrders1")
        addr_resp = client.post(
            "/users/me/address",
            json={"type": "home", **VALID_ADDRESS, "is_default": True},
            headers=auth,
        )
        address_id = addr_resp.json()["id"]

        product_a = _make_product(db_session, slug="two-orders-a")
        product_b = _make_product(db_session, slug="two-orders-b")

        client.post("/cart/items", json={"product_id": product_a.id, "quantity": 1}, headers=auth)
        order_a = client.post(
            "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=auth
        ).json()

        client.post("/cart/items", json={"product_id": product_b.id, "quantity": 1}, headers=auth)
        order_b = client.post(
            "/order", json={"shipping_address_id": address_id, "billing_address_id": address_id}, headers=auth
        ).json()

        client.post(f"/order/{order_a['id']}/cancel", headers=auth)

        db_session.expire_all()
        remaining = db_session.scalars(
            select(InventoryReservation).where(InventoryReservation.order_id == order_b["id"])
        ).all()
        assert len(remaining) == 1, "cancelling order A released order B's reservation too"

    def test_two_concurrent_guest_orders_dont_release_each_others_reservation_on_payment_failure(
        self, db_session: Session
    ):
        from app.models.cart import Cart
        from app.models.cart_item import CartItem

        product_a = _make_product(db_session, slug="guest-concurrency-a")
        product_b = _make_product(db_session, slug="guest-concurrency-b")

        cart_a = Cart(session_id="sess-guest-a", user_id=None)
        cart_b = Cart(session_id="sess-guest-b", user_id=None)
        db_session.add_all([cart_a, cart_b])
        db_session.commit()
        db_session.add_all(
            [
                CartItem(cart_id=cart_a.id, product_id=product_a.id, quantity=1),
                CartItem(cart_id=cart_b.id, product_id=product_b.id, quantity=1),
            ]
        )
        db_session.commit()

        crud = OrderCrud(db_session)
        order_a = crud.create_guest_order(
            "sess-guest-a", "guest-a@example.com", _guest_address(), _guest_address()
        )
        order_b = crud.create_guest_order(
            "sess-guest-b", "guest-b@example.com", _guest_address(), _guest_address()
        )

        # Both orders' reservations share user_id IS NULL — the exact
        # condition that made the pre-fix filter dangerous.
        assert db_session.get(Order, order_a.id).user_id is None
        assert db_session.get(Order, order_b.id).user_id is None

        from app.models.payment import Payment
        payment_a = Payment(
            order_id=order_a.id, amount=order_a.total_amount, currency_code=order_a.currency_code,
            transaction_id="pi_fail_a", payment_method="stripe",
        )
        db_session.add(payment_a)
        db_session.commit()

        payment_service = PaymentService(db_session)
        payment_service._handle_failed_payment({"id": "pi_fail_a"})

        db_session.expire_all()
        order_b_reservations = db_session.scalars(
            select(InventoryReservation).where(InventoryReservation.order_id == order_b.id)
        ).all()
        assert len(order_b_reservations) == 1, (
            "order A's payment failure released order B's reservation — "
            "release must be scoped by order_id, not user_id"
        )
