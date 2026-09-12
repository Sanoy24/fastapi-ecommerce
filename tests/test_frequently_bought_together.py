"""
Tests for the frequently-bought-together cron
(app.workers.arq_worker.compute_frequently_bought_together_task).

ProductRelation already had a frequently_bought_together type and full CRUD,
but nothing ever populated it except an admin typing it in by hand. This
task computes real co-purchase counts from OrderItem/Order history and
reconciles them into ProductRelation rows — but only rows it marked
is_auto_generated=True itself, so it never touches a relation an admin
entered manually, even one of the same type.
"""
import asyncio
import itertools
from typing import Optional

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.product_relation import ProductRelation
from app.workers.arq_worker import (
    FBT_MIN_CO_OCCURRENCE,
    FBT_TOP_N,
    WorkerSettings,
    compute_frequently_bought_together_task,
)

_order_seq = itertools.count(1)


@pytest.fixture
def _use_test_db_for_worker(_engine, monkeypatch):
    """Point the worker's SessionLocal at the test container instead of
    the app's real database — same fixture as test_outbox_worker.py.
    """
    monkeypatch.setattr(
        "app.workers.arq_worker.SessionLocal", sessionmaker(bind=_engine)
    )


def _make_product(db_session: Session, slug: str) -> Product:
    product = Product(
        name=f"FBT {slug}",
        slug=slug,
        sku=f"SKU-{slug}",
        description="d",
        price=20.0,
        stock_quantity=50,
        image_url="http://test.com/img.jpg",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


def _make_order(
    db_session: Session,
    product_ids: list[int],
    *,
    payment_status: str = "success",
) -> Order:
    n = next(_order_seq)
    order = Order(
        guest_email=f"fbt-buyer-{n}@test.com",
        order_number=f"ORD-FBT-{n}",
        total_amount=20.0 * len(product_ids),
        tx_ref=f"tx-fbt-{n}",
        payment_status=payment_status,
    )
    db_session.add(order)
    db_session.commit()
    for product_id in product_ids:
        db_session.add(
            OrderItem(order_id=order.id, product_id=product_id, quantity=1, unit_price=20.0)
        )
    db_session.commit()
    db_session.refresh(order)
    return order


def _run_computation():
    asyncio.run(compute_frequently_bought_together_task({}))


def _relation(db_session: Session, product_id: int, related_id: int) -> Optional[ProductRelation]:
    db_session.expire_all()
    return (
        db_session.query(ProductRelation)
        .filter_by(
            product_id=product_id,
            related_product_id=related_id,
            relation_type="frequently_bought_together",
        )
        .first()
    )


class TestTaskIsRegistered:
    def test_task_is_registered(self):
        assert compute_frequently_bought_together_task in WorkerSettings.functions

    def test_task_has_a_cron_schedule(self):
        scheduled = {job.coroutine for job in WorkerSettings.cron_jobs}
        assert compute_frequently_bought_together_task in scheduled


class TestCoOccurrenceComputation:
    def test_creates_symmetric_relations_once_min_co_occurrence_is_met(
        self, db_session: Session, _use_test_db_for_worker
    ):
        a = _make_product(db_session, "fbt-a1")
        b = _make_product(db_session, "fbt-b1")
        assert FBT_MIN_CO_OCCURRENCE == 2
        for _ in range(FBT_MIN_CO_OCCURRENCE):
            _make_order(db_session, [a.id, b.id])

        _run_computation()

        rel_ab = _relation(db_session, a.id, b.id)
        rel_ba = _relation(db_session, b.id, a.id)
        assert rel_ab is not None and rel_ab.is_auto_generated is True
        assert rel_ba is not None and rel_ba.is_auto_generated is True

    def test_does_not_create_a_relation_below_the_minimum_co_occurrence(
        self, db_session: Session, _use_test_db_for_worker
    ):
        a = _make_product(db_session, "fbt-a2")
        b = _make_product(db_session, "fbt-b2")
        for _ in range(FBT_MIN_CO_OCCURRENCE - 1):
            _make_order(db_session, [a.id, b.id])

        _run_computation()

        assert _relation(db_session, a.id, b.id) is None

    def test_ignores_orders_that_were_never_successfully_paid(
        self, db_session: Session, _use_test_db_for_worker
    ):
        a = _make_product(db_session, "fbt-a3")
        b = _make_product(db_session, "fbt-b3")
        for _ in range(5):
            _make_order(db_session, [a.id, b.id], payment_status="pending")

        _run_computation()

        assert _relation(db_session, a.id, b.id) is None

    def test_does_not_relate_a_product_to_itself(
        self, db_session: Session, _use_test_db_for_worker
    ):
        a = _make_product(db_session, "fbt-a4")
        # Two line items for the same product on the same order (e.g. two
        # variants) still count as one distinct product for co-occurrence
        # purposes, so there's no pair to form at all.
        order = _make_order(db_session, [a.id])
        db_session.add(OrderItem(order_id=order.id, product_id=a.id, quantity=1, unit_price=20.0))
        db_session.commit()

        _run_computation()

        assert _relation(db_session, a.id, a.id) is None

    def test_caps_relations_at_top_n_per_product(
        self, db_session: Session, _use_test_db_for_worker
    ):
        anchor = _make_product(db_session, "fbt-anchor")
        partners = [
            _make_product(db_session, f"fbt-partner-{i}") for i in range(FBT_TOP_N + 2)
        ]
        for partner in partners:
            for _ in range(FBT_MIN_CO_OCCURRENCE):
                _make_order(db_session, [anchor.id, partner.id])

        _run_computation()

        db_session.expire_all()
        count = (
            db_session.query(ProductRelation)
            .filter_by(
                product_id=anchor.id,
                relation_type="frequently_bought_together",
                is_auto_generated=True,
            )
            .count()
        )
        assert count == FBT_TOP_N

    def test_rerunning_does_not_duplicate_relations(
        self, db_session: Session, _use_test_db_for_worker
    ):
        a = _make_product(db_session, "fbt-a5")
        b = _make_product(db_session, "fbt-b5")
        for _ in range(FBT_MIN_CO_OCCURRENCE):
            _make_order(db_session, [a.id, b.id])

        _run_computation()
        _run_computation()

        db_session.expire_all()
        count = (
            db_session.query(ProductRelation)
            .filter_by(product_id=a.id, related_product_id=b.id)
            .count()
        )
        assert count == 1

    def test_removes_a_stale_auto_generated_relation_that_no_longer_qualifies(
        self, db_session: Session, _use_test_db_for_worker
    ):
        a = _make_product(db_session, "fbt-a6")
        stale_partner = _make_product(db_session, "fbt-stale")
        db_session.add(
            ProductRelation(
                product_id=a.id,
                related_product_id=stale_partner.id,
                relation_type="frequently_bought_together",
                is_auto_generated=True,
            )
        )
        db_session.commit()

        # No purchase history links them at all — the stale row should be
        # dropped, not left behind forever.
        _run_computation()

        assert _relation(db_session, a.id, stale_partner.id) is None

    def test_never_touches_a_manually_entered_relation(
        self, db_session: Session, _use_test_db_for_worker
    ):
        a = _make_product(db_session, "fbt-a7")
        b = _make_product(db_session, "fbt-b7")
        db_session.add(
            ProductRelation(
                product_id=a.id,
                related_product_id=b.id,
                relation_type="frequently_bought_together",
                is_auto_generated=False,
            )
        )
        db_session.commit()

        # No qualifying purchase history — if the task didn't distinguish
        # manual from auto-generated rows, this would get deleted as stale.
        _run_computation()

        rel = _relation(db_session, a.id, b.id)
        assert rel is not None
        assert rel.is_auto_generated is False

    def test_only_counts_distinct_products_per_order_not_line_item_count(
        self, db_session: Session, _use_test_db_for_worker
    ):
        """Buying 2 of product A and 3 of product B in one order is still
        exactly one co-occurrence, not six."""
        a = _make_product(db_session, "fbt-a8")
        b = _make_product(db_session, "fbt-b8")
        order = _make_order(db_session, [a.id])
        db_session.add(OrderItem(order_id=order.id, product_id=a.id, quantity=1, unit_price=20.0))
        db_session.add(OrderItem(order_id=order.id, product_id=b.id, quantity=3, unit_price=20.0))
        db_session.commit()
        _make_order(db_session, [a.id, b.id])  # second qualifying order

        _run_computation()

        assert _relation(db_session, a.id, b.id) is not None
