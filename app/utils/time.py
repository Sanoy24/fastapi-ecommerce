"""Shared UTC-now helper.

datetime.utcnow() is deprecated and scheduled for removal — it returns a
naive datetime that looks like local time but is actually UTC, exactly the
implicit-timezone footgun the replacement API (datetime.now(timezone.utc))
exists to avoid. Every DateTime column in this app is a naive
`timestamp without time zone` column, though, so switching to a genuinely
timezone-aware value would introduce a new naive/aware mismatch instead of
fixing the old one. utcnow() below keeps the exact current semantics — a
naive UTC timestamp — while using the non-deprecated call, and is meant to
be used everywhere datetime.utcnow() used to be: as a plain call
(utcnow()) and as a SQLAlchemy column default/onupdate callable
(default=utcnow).
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
