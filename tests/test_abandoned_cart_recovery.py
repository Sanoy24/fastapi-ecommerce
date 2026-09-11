"""
Tests for the abandoned-cart recovery cron
(app.workers.arq_worker.detect_abandoned_carts_task).

The task already correctly found carts idle more than 24h with items and a
user attached — it just logged a line and then `pass`ed instead of sending
anything. Wiring that up naively would have introduced a second bug:
without some way to remember a cart was already notified, the cron (which
runs twice a day) would re-email the same still-abandoned cart forever.
Cart.abandoned_email_sent_at and the tests below are about that specific
correctness property as much as the "does an email get sent" happy path.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.product import Product
from app.models.user import User
from app.utils.security import hash_password
from app.workers.arq_worker import WorkerSettings, detect_abandoned_carts_task


@pytest.fixture
def _use_test_db_for_worker(_engine, monkeypatch):
    """Point the worker's SessionLocal at the test container instead of
    the app's real database — same fixture as test_outbox_worker.py.
    """
    monkeypatch.setattr(
        "app.workers.arq_worker.SessionLocal", sessionmaker(bind=_engine)
    )


def _make_user(db_session: Session, email: str) -> User:
    user = User(
        email=email,
        password_hash=hash_password("AbandonedCart1"),
        first_name="Test",
        last_name="User",
        phone="0999900001",
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_product(db_session: Session, slug: str) -> Product:
    product = Product(
        name="Abandoned Widget",
        slug=slug,
        description="d",
        price=20.0,
        stock_quantity=50,
        image_url="http://test.com/img.jpg",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


def _make_cart(
    db_session: Session,
    user: User,
    product: Product,
    *,
    last_activity_hours_ago: float,
    abandoned_email_sent_hours_ago: float | None = None,
    quantity: int = 1,
) -> Cart:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cart = Cart(user_id=user.id, session_id=None)
    db_session.add(cart)
    db_session.commit()
    db_session.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=quantity))
    db_session.commit()

    # last_activity_at/created_at have onupdate/default triggers that would
    # otherwise overwrite the backdated value on this same commit — set
    # them directly via a core UPDATE, matching the pattern used elsewhere
    # in this suite for backdating timestamp columns.
    values = {"last_activity_at": now - timedelta(hours=last_activity_hours_ago)}
    if abandoned_email_sent_hours_ago is not None:
        values["abandoned_email_sent_at"] = now - timedelta(hours=abandoned_email_sent_hours_ago)
    db_session.execute(Cart.__table__.update().where(Cart.id == cart.id).values(**values))
    db_session.commit()
    db_session.refresh(cart)
    return cart


def _run_detection():
    with patch("app.services.email_service.send_email", new_callable=AsyncMock) as mock_send:
        asyncio.run(detect_abandoned_carts_task({}))
        return mock_send


class TestAbandonedCartTaskIsRegistered:
    def test_task_is_registered(self):
        assert detect_abandoned_carts_task in WorkerSettings.functions

    def test_task_has_a_cron_schedule(self):
        scheduled = {job.coroutine for job in WorkerSettings.cron_jobs}
        assert detect_abandoned_carts_task in scheduled


class TestAbandonedCartDetection:
    def test_sends_an_email_for_a_cart_idle_over_24h(self, db_session: Session, _use_test_db_for_worker):
        user = _make_user(db_session, "abandoned1@test.com")
        product = _make_product(db_session, "abandoned-widget-1")
        _make_cart(db_session, user, product, last_activity_hours_ago=25)

        mock_send = _run_detection()

        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs["to_address"] == "abandoned1@test.com"
        assert "cart" in mock_send.call_args.kwargs["subject"].lower()

    def test_does_not_notify_a_cart_idle_less_than_24h(self, db_session: Session, _use_test_db_for_worker):
        user = _make_user(db_session, "abandoned2@test.com")
        product = _make_product(db_session, "abandoned-widget-2")
        _make_cart(db_session, user, product, last_activity_hours_ago=1)

        mock_send = _run_detection()

        mock_send.assert_not_called()

    def test_does_not_notify_a_guest_cart(self, db_session: Session, _use_test_db_for_worker):
        product = _make_product(db_session, "abandoned-widget-3")
        cart = Cart(user_id=None, session_id="guest-session-abandoned")
        db_session.add(cart)
        db_session.commit()
        db_session.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=1))
        db_session.commit()
        db_session.execute(
            Cart.__table__.update()
            .where(Cart.id == cart.id)
            .values(last_activity_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=48))
        )
        db_session.commit()

        mock_send = _run_detection()

        mock_send.assert_not_called()

    def test_does_not_notify_an_empty_cart(self, db_session: Session, _use_test_db_for_worker):
        user = _make_user(db_session, "abandoned4@test.com")
        cart = Cart(user_id=user.id, session_id=None)
        db_session.add(cart)
        db_session.commit()
        db_session.execute(
            Cart.__table__.update()
            .where(Cart.id == cart.id)
            .values(last_activity_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=48))
        )
        db_session.commit()

        mock_send = _run_detection()

        mock_send.assert_not_called()

    def test_email_reports_the_correct_item_count(self, db_session: Session, _use_test_db_for_worker):
        """item_count is the number of distinct line items on the cart
        (len(cart.cart_items)), not the sum of quantities — a single line
        item with quantity=3 is still reported as "1 item"."""
        user = _make_user(db_session, "abandoned5@test.com")
        product = _make_product(db_session, "abandoned-widget-5")
        _make_cart(db_session, user, product, last_activity_hours_ago=30, quantity=3)

        mock_send = _run_detection()

        assert "1 item" in mock_send.call_args.kwargs["html_body"]
        assert "1 item" in mock_send.call_args.kwargs["text_body"]


class TestAbandonedCartSuppression:
    """The specific bug this feature required fixing: without
    abandoned_email_sent_at, every run of this twice-daily cron would
    re-email the same still-abandoned cart forever."""

    def test_marks_the_cart_as_notified(self, db_session: Session, _use_test_db_for_worker):
        user = _make_user(db_session, "suppress1@test.com")
        product = _make_product(db_session, "suppress-widget-1")
        cart = _make_cart(db_session, user, product, last_activity_hours_ago=25)

        _run_detection()

        db_session.expire_all()
        assert db_session.get(Cart, cart.id).abandoned_email_sent_at is not None

    def test_does_not_re_notify_an_already_notified_cart(self, db_session: Session, _use_test_db_for_worker):
        user = _make_user(db_session, "suppress2@test.com")
        product = _make_product(db_session, "suppress-widget-2")
        # Notified 12h ago, no activity since — still idle, already handled.
        _make_cart(
            db_session, user, product,
            last_activity_hours_ago=36,
            abandoned_email_sent_hours_ago=12,
        )

        mock_send = _run_detection()

        mock_send.assert_not_called()

    def test_re_notifies_once_the_cart_has_new_activity_since_the_last_email(
        self, db_session: Session, _use_test_db_for_worker
    ):
        user = _make_user(db_session, "suppress3@test.com")
        product = _make_product(db_session, "suppress-widget-3")
        # Notified 48h ago; activity since then (25h ago) means the
        # customer came back and touched the cart again before abandoning
        # it a second time — a fresh reminder is warranted.
        _make_cart(
            db_session, user, product,
            last_activity_hours_ago=25,
            abandoned_email_sent_hours_ago=48,
        )

        mock_send = _run_detection()

        mock_send.assert_called_once()

    def test_two_consecutive_runs_only_send_one_email(self, db_session: Session, _use_test_db_for_worker):
        """The realistic scenario: the cron actually runs twice a day
        against the same untouched cart."""
        user = _make_user(db_session, "suppress4@test.com")
        product = _make_product(db_session, "suppress-widget-4")
        _make_cart(db_session, user, product, last_activity_hours_ago=25)

        first_run = _run_detection()
        second_run = _run_detection()

        first_run.assert_called_once()
        second_run.assert_not_called()
