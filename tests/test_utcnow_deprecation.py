"""
Regression guard for the datetime.utcnow() deprecation cleanup.

datetime.utcnow() was scattered across 3 direct calls and 6 bare
`default=datetime.utcnow` SQLAlchemy column callables (the latter also
warn, just only at insert time rather than at import time, so a plain grep
for `.utcnow()` with call parens missed them). All 9 sites now go through
app.utils.time.utcnow, which keeps the exact same semantics — a naive UTC
timestamp — without the deprecated call.

The column-default cases are checked by inspecting the configured default
callable directly rather than inserting a full row per model — several of
the affected tables have foreign keys that would need an unrelated amount
of setup to satisfy just to prove a column default, and the default is a
fixed, inspectable part of the mapping regardless of what row is inserted.
"""
import warnings
from datetime import datetime, timezone

import pytest

from app.utils.time import utcnow


class TestUtcnowHelper:
    def test_returns_a_naive_datetime(self):
        """Every DateTime column in this app is naive (timestamp without
        time zone) — a tz-aware value here would be a new mismatch, not a
        fix, so the helper deliberately strips tzinfo before returning."""
        assert utcnow().tzinfo is None

    def test_matches_real_utc_time(self):
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        value = utcnow()
        after = datetime.now(timezone.utc).replace(tzinfo=None)

        assert before <= value <= after

    def test_does_not_raise_the_deprecation_warning(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            utcnow()  # would raise here if this were datetime.utcnow()


class TestDirectCallSitesUseTheSharedHelper:
    def test_inventory_reservation_is_expired_uses_it(self, db_session):
        from datetime import timedelta

        from app.models.inventory_reservation import InventoryReservation
        from app.models.product import Product

        product = Product(
            name="Dep Product A", slug="dep-product-a", description="d",
            price=10.0, stock_quantity=5, image_url="http://t.com/i.jpg",
        )
        db_session.add(product)
        db_session.commit()

        reservation = InventoryReservation(
            product_id=product.id, quantity=1,
            expires_at=utcnow() - timedelta(minutes=1),
        )
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            assert reservation.is_expired is True

    def test_product_variant_available_stock_uses_it(self, db_session):
        from app.models.product import Product
        from app.models.product_variant import ProductVariant

        product = Product(
            name="Dep Product B", slug="dep-product-b", description="d",
            price=10.0, stock_quantity=5, image_url="http://t.com/i.jpg",
        )
        db_session.add(product)
        db_session.commit()

        variant = ProductVariant(product_id=product.id, sku="DEP-SKU-B", name="V", price=10.0, stock_quantity=3)
        db_session.add(variant)
        db_session.commit()

        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            assert variant.available_stock == 3

    def test_payment_crud_update_status_uses_it(self, db_session):
        from app.crud.payment import PaymentCrud
        from app.models.order import Order
        from app.models.payment import Payment

        # A minimal Order satisfying just its NOT NULL/CHECK constraints —
        # Payment.order_id is a real FK, so a full row is needed regardless
        # of the checkout flow that would normally create one.
        order = Order(
            order_number="DEP-ORDER-1", total_amount=10.0, currency_code="USD",
            tx_ref="DEP-TX-1", guest_email="dep_payment@test.com",
        )
        db_session.add(order)
        db_session.commit()

        payment = Payment(
            order_id=order.id, amount=10.0, currency_code="USD",
            transaction_id="pi_dep_test", payment_method="stripe",
        )
        db_session.add(payment)
        db_session.commit()

        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            PaymentCrud(db_session).update_payment_status(payment, "completed")

        assert payment.paid_at is not None


class TestColumnDefaultsUseTheSharedHelper:
    @pytest.mark.parametrize(
        "module_path,class_name,column_name",
        [
            ("app.models.brand", "Brand", "created_at"),
            ("app.models.coupon_usage", "CouponUsage", "used_at"),
            ("app.models.inventory_transaction", "InventoryTransaction", "created_at"),
            ("app.models.product_image", "ProductImage", "created_at"),
            ("app.models.product_variant", "ProductVariant", "created_at"),
            ("app.models.shipment", "Shipment", "created_at"),
            ("app.models.shipment", "Shipment", "updated_at"),
        ],
    )
    def test_column_default_arg_is_the_shared_helper(self, module_path, class_name, column_name):
        import importlib

        # SQLAlchemy wraps a zero-argument callable passed to default= in
        # its own CallableColumnDefault wrapper (to normalize the calling
        # convention to always accept an execution context), so
        # column.default.arg is never the original function object by
        # identity even when it's correctly wired — checking that alone
        # would fail regardless of which callable was actually passed.
        # __module__/__name__ survive that wrapping, and actually calling
        # it proves it behaves like app.utils.time.utcnow rather than just
        # sharing its name by coincidence.
        model = getattr(importlib.import_module(module_path), class_name)
        default = model.__table__.columns[column_name].default
        assert default.arg.__module__ == "app.utils.time"
        assert default.arg.__name__ == "utcnow"
        value = default.arg(None)
        assert value.tzinfo is None

    def test_shipment_updated_at_onupdate_is_the_shared_helper(self):
        from app.models.shipment import Shipment

        onupdate = Shipment.__table__.columns["updated_at"].onupdate
        assert onupdate.arg.__module__ == "app.utils.time"
        assert onupdate.arg.__name__ == "utcnow"
