"""
True-concurrency test for the row-level stock lock used at checkout.

tests/test_variant_inventory.py::TestVariantOversellPrevention already proves
the *logic* is correct: place one order, then attempt a second for the same
scarce variant — the second is correctly rejected. But that test calls the
two checkouts one after another. It never exercises `with_for_update()` under
two transactions actually racing for the same row, which is the mechanism
the logic depends on (see OrderCrud.validate_stock in app/crud/order.py).

This could not be tested at all before the suite moved off SQLite (see
conftest.py) — SQLite has no concept of row-level locking, so
`with_for_update()` is silently a no-op there and this class of bug is
untestable by construction, not just untested.

This test drives two independent SQLAlchemy sessions — real, separate
DB connections against the same PostgreSQL container — from two threads,
synchronized with a barrier so both call OrderCrud.create_order for the
last unit of the same variant at essentially the same instant. If the row
lock did not actually serialize them, both could read available_stock=1
before either commits its reservation, and both would succeed —
overselling the unit.
"""
import threading

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import OrderException
from app.crud.order import OrderCrud
from app.models.user import User

from tests.test_variant_inventory import (
    _add_default_address,
    _make_product_with_variant,
    _register_login,
)


class TestConcurrentStockLocking:
    def test_two_simultaneous_orders_for_the_last_unit_dont_both_succeed(
        self, client: TestClient, db_session: Session, _engine
    ):
        product, variant = _make_product_with_variant(
            db_session, product_stock=5, variant_stock=1
        )

        # Build both users' carts through the normal setup session — only the
        # checkout call itself needs to run on independent sessions/threads.
        headers_a = _register_login(client, "concurrent_a@test.com", "ConcurrentA1")
        address_a = _add_default_address(client, headers_a)
        resp_a = client.post(
            "/cart/items",
            json={"product_id": product.id, "variant_id": variant.id, "quantity": 1},
            headers=headers_a,
        )
        assert resp_a.status_code in (200, 201), resp_a.json()

        headers_b = _register_login(client, "concurrent_b@test.com", "ConcurrentB1")
        address_b = _add_default_address(client, headers_b)
        resp_b = client.post(
            "/cart/items",
            json={"product_id": product.id, "variant_id": variant.id, "quantity": 1},
            headers=headers_b,
        )
        assert resp_b.status_code in (200, 201), resp_b.json()

        user_a = db_session.query(User).filter_by(email="concurrent_a@test.com").one()
        user_b = db_session.query(User).filter_by(email="concurrent_b@test.com").one()

        # A brand-new Session per thread — a SQLAlchemy Session is not
        # thread-safe, and reusing the fixture's shared db_session here would
        # only prove the two calls don't corrupt one Python object. Real
        # separate connections against the shared container are what make
        # this a genuine test of PostgreSQL row locking rather than of
        # SQLAlchemy's in-process behaviour.
        ThreadSession = sessionmaker(bind=_engine)
        barrier = threading.Barrier(2)
        results: dict[str, tuple[str, str]] = {}

        def _checkout(name: str, user_id: int, address_id: int) -> None:
            session = ThreadSession()
            try:
                barrier.wait(timeout=5)  # both threads hit create_order together
                order = OrderCrud(session).create_order(
                    user_id=user_id, shipping_id=address_id, billing_id=address_id
                )
                results[name] = ("ok", str(order.id))
            except OrderException as e:
                results[name] = ("rejected", str(e))
            except Exception as e:  # surfaced via the assertions below, not silently lost
                results[name] = ("error", repr(e))
            finally:
                session.close()

        t_a = threading.Thread(target=_checkout, args=("a", user_a.id, address_a))
        t_b = threading.Thread(target=_checkout, args=("b", user_b.id, address_b))
        t_a.start()
        t_b.start()
        t_a.join(timeout=15)
        t_b.join(timeout=15)

        assert set(results) == {"a", "b"}, f"a thread didn't finish in time: {results}"
        outcomes = [results["a"][0], results["b"][0]]

        assert outcomes.count("ok") == 1, (
            "exactly one of two simultaneous orders for the last unit should "
            f"succeed under a real row lock — both succeeding means the unit "
            f"was oversold; got {results}"
        )
        assert outcomes.count("rejected") == 1, (
            f"the loser should be cleanly rejected as out of stock, not error "
            f"out some other way; got {results}"
        )
        loser = "a" if results["a"][0] == "rejected" else "b"
        assert "variant" in results[loser][1].lower(), results[loser]
