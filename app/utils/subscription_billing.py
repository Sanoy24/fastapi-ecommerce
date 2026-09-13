from datetime import datetime, timedelta

# Fixed day-counts rather than real calendar-month arithmetic (e.g.
# "the 14th of next month") — python-dateutil/pendulum are only ever
# transitive dependencies here (pulled in by other packages, not declared
# in pyproject.toml), so relying on them for a core billing calculation
# would leave this silently fragile to an unrelated dependency bump.
# "Every 30 days" is a common, acceptable approximation for a monthly
# subscription and keeps this a plain, dependency-free calculation.
INTERVAL_DAYS = {"weekly": 7, "biweekly": 14, "monthly": 30}

# Days after a failed renewal attempt before the next retry — three
# attempts (at +1, +3, +7 days) before the subscription is cancelled
# automatically. See app.workers.arq_worker.process_due_subscriptions_task.
RETRY_SCHEDULE_DAYS = [1, 3, 7]
MAX_RENEWAL_FAILURES = len(RETRY_SCHEDULE_DAYS)


def compute_next_billing_date(interval: str, *, from_dt: datetime) -> datetime:
    return from_dt + timedelta(days=INTERVAL_DAYS[interval])


def compute_retry_date(failure_count: int, *, from_dt: datetime) -> datetime:
    """failure_count is the count *after* incrementing for this failure
    (i.e. 1 for the first failure) — index it directly into the schedule."""
    days = RETRY_SCHEDULE_DAYS[min(failure_count, MAX_RENEWAL_FAILURES) - 1]
    return from_dt + timedelta(days=days)
