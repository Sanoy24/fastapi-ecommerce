"""
Tests for app.utils.order_utils.generate_order_number.

Previously built from datetime.date.today() — a date has no time
component, so '%H%M%S' always rendered as literal zeros and a stray comma
from the format string joined the date and (non-existent) time directly.
Every order number read like ORD-20260911,000000-A1B2C3D4E5 regardless of
when it was actually placed.
"""
import re
from datetime import datetime

from app.utils.order_utils import generate_order_number


class TestGenerateOrderNumber:
    def test_matches_the_expected_shape(self):
        # The trailing random suffix is a slice of uuid4()'s string form,
        # which can itself contain a hyphen (at string index 8) — not part
        # of what this fix touches, so the pattern tolerates it rather
        # than assuming a fixed dash count.
        number = generate_order_number()
        assert re.fullmatch(r"ORD-\d{8}-\d{6}-[0-9A-F-]{10}", number), number

    def test_contains_no_stray_comma(self):
        assert "," not in generate_order_number()

    def test_date_and_time_reflect_now(self):
        before = datetime.now()
        number = generate_order_number()
        after = datetime.now()

        _, date_part, time_part, _ = number.split("-", 3)
        parsed = datetime.strptime(f"{date_part}{time_part}", "%Y%m%d%H%M%S")

        # The time component must be a real clock reading, not a constant —
        # the original bug's exact symptom was every order reading 000000
        # regardless of when it was placed.
        assert before.replace(microsecond=0) <= parsed <= after.replace(microsecond=0)

    def test_two_calls_are_unique(self):
        assert generate_order_number() != generate_order_number()
