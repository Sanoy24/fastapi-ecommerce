"""
Regression test for the outbox_events index drift (alembic migration
e5f6a7b8c9d0).

e71d0e330657 (add_auditlog_and_performance_indexes) created an index named
'ix_outbox_events_status' — the name SQLAlchemy's naming convention would
generate for OutboxEvent.status's `index=True` single-column index — but
gave it the wrong column list, ['status', 'created_at']. That's a
copy-paste duplicate of 'ix_outbox_events_status_created' (created
separately in the genesis migration, matching the model's __table_args__
composite Index), not the single-column index the name implies. Net
effect: two identical (status, created_at) indexes under different names,
and the actual single-column status index never existed.

The bug lived entirely in the migration scripts, not the model — the
model has always correctly declared both indexes. Because of that, this
can't be caught by the rest of the suite's usual approach
(conftest.py's db_session fixture builds tables straight from the models
via Base.metadata.create_all(), which reads the (correct) model
definitions directly and would never reproduce a migration-script-only
bug). This test instead runs the real Alembic migration chain — the exact
path the bug lived on — against a genuinely fresh database, mirroring what
CI's `migrations` job already does for the whole schema, but specifically
inspecting the resulting index state afterward.
"""
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine.url import make_url


@pytest.fixture
def _migrated_scratch_db(_postgres_container):
    """A genuinely fresh database, migrated with the real Alembic chain —
    not Base.metadata.create_all(). Created inside the same running
    Postgres container the rest of the suite already uses, so this adds
    one extra database rather than a whole extra container.
    """
    base_url = make_url(_postgres_container.get_connection_url())
    scratch_db_name = "outbox_index_migration_check"

    # CREATE/DROP DATABASE can't run inside a transaction block in
    # Postgres — isolation_level="AUTOCOMMIT" must be set at engine
    # creation to reliably apply to every connection it hands out.
    admin_engine = create_engine(base_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch_db_name}"'))
        conn.execute(text(f'CREATE DATABASE "{scratch_db_name}"'))
    admin_engine.dispose()

    scratch_url = base_url.set(
        database=scratch_db_name, drivername="postgresql+psycopg2"
    )

    repo_root = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(repo_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(repo_root / "alembic"))
    # str(url) masks the password as '***' by default — render_as_string
    # with hide_password=False is needed to get a URL that actually works.
    alembic_cfg.set_main_option("sqlalchemy.url", scratch_url.render_as_string(hide_password=False))

    command.upgrade(alembic_cfg, "head")

    scratch_engine = create_engine(scratch_url)
    try:
        yield scratch_engine
    finally:
        scratch_engine.dispose()
        cleanup_engine = create_engine(base_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
        with cleanup_engine.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch_db_name}"'))
        cleanup_engine.dispose()


class TestOutboxEventsIndexesAfterRealMigration:
    def test_status_index_covers_only_the_status_column(self, _migrated_scratch_db):
        indexes = inspect(_migrated_scratch_db).get_indexes("outbox_events")
        status_index = next(i for i in indexes if i["name"] == "ix_outbox_events_status")
        assert status_index["column_names"] == ["status"], (
            f"ix_outbox_events_status should cover only 'status', got {status_index['column_names']} "
            f"— this is the exact drift bug: it used to be a duplicate of the (status, created_at) composite"
        )

    def test_status_created_composite_index_is_unaffected(self, _migrated_scratch_db):
        indexes = inspect(_migrated_scratch_db).get_indexes("outbox_events")
        composite = next(i for i in indexes if i["name"] == "ix_outbox_events_status_created")
        assert composite["column_names"] == ["status", "created_at"]

    def test_no_two_indexes_cover_the_same_columns(self, _migrated_scratch_db):
        """The bug's actual symptom: two indexes with different names but
        identical column coverage — wasted disk space and write overhead
        maintaining a duplicate on every insert/update, for zero query
        benefit since Postgres only ever uses one of them."""
        indexes = inspect(_migrated_scratch_db).get_indexes("outbox_events")
        seen_column_sets = {}
        for index in indexes:
            key = tuple(index["column_names"])
            assert key not in seen_column_sets, (
                f"{index['name']} and {seen_column_sets[key]} both index {key} — "
                f"one of them is a redundant duplicate"
            )
            seen_column_sets[key] = index["name"]

    def test_topic_index_is_unaffected(self, _migrated_scratch_db):
        """Sanity check that the fix didn't touch the one index that was
        already correct."""
        indexes = inspect(_migrated_scratch_db).get_indexes("outbox_events")
        topic_index = next(i for i in indexes if i["name"] == "ix_outbox_events_topic")
        assert topic_index["column_names"] == ["topic"]
