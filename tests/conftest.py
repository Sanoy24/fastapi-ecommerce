import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, patch
from testcontainers.community.postgres import PostgresContainer

from app.main import app
from app.db.database import Base
from app.dependencies import get_db

# The suite runs against a real PostgreSQL container, not SQLite.
#
# It used to run on `sqlite:///:memory:`, while every real environment
# (local docker-compose, CI, production) runs PostgreSQL. That gap let a
# genuine bug ship straight to main: an admin analytics endpoint grouped by
# `func.strftime(...)`, a SQLite-only function, and 500'd on every call in
# production while the full suite stayed green. It also meant
# `with_for_update(skip_locked=True)` — used by both the outbox worker and
# the inventory-reservation concurrency path — was never exercised against
# real row-level locking, since SQLite has no concept of it.
#
# Pinned to postgres:15-alpine to match docker-compose.yml and the CI
# `migrations` job, so the schema this suite runs against is the same one
# production runs against.
_POSTGRES_IMAGE = "postgres:15-alpine"


@pytest.fixture(scope="session")
def _postgres_container():
    """One PostgreSQL container for the whole test session, not per test.

    Starting a real container per test would make the suite unusably slow;
    starting it once and isolating tests at the data level (see `db_session`
    below) keeps the real-database guarantee without that cost.
    """
    with PostgresContainer(_POSTGRES_IMAGE) as container:
        yield container


@pytest.fixture(scope="session")
def _engine(_postgres_container):
    engine = create_engine(_postgres_container.get_connection_url(), pool_pre_ping=True)
    # Created once per session — native Postgres ENUM types in particular
    # don't tolerate being dropped and recreated on every test the way a
    # SQLite file conceptually could.
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(_engine):
    """A DB session backed by the shared container, reset before every test.

    Truncating (rather than the old drop-all/create-all-per-test approach)
    is what keeps this fast against a real, network-attached database:
    DDL against ~30 tables on every test would dominate the suite's runtime,
    where one DML statement does not. RESTART IDENTITY keeps primary keys
    predictable across tests; CASCADE handles FK ordering so table order
    here doesn't matter.
    """
    with _engine.begin() as conn:
        table_names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))
        # The real migration seeds this row (see
        # alembic/versions/359fcf445d5a_add_multi_currency_support.py) —
        # this suite creates tables straight from the models instead of
        # running migrations, so nothing else would insert it, and
        # Order/Payment.currency_code is a NOT NULL FK to it.
        conn.execute(
            text(
                "INSERT INTO currencies (code, name, symbol, exchange_rate_to_base, is_active, created_at, updated_at) "
                "VALUES ('USD', 'US Dollar', '$', 1, true, now(), now())"
            )
        )

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session):
    """Create a TestClient with database dependency override and mocked Redis."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    from app.services.user_service import UserService
    from app.dependencies import get_user_service_dep
    from app.core.redis import redis_client
    
    class TestUserService(UserService):
        def create_user(self, user_create_data):
            user = super().create_user(user_create_data)
            user.is_verified = True
            self.db.commit()
            self.db.refresh(user)
            return user
            
    app.dependency_overrides[get_user_service_dep] = lambda: TestUserService(db_session, redis_client)
    
    # Disable rate limiter for testing
    from app.core.limiter import limiter
    limiter.enabled = False
    
    # Use patch.object to mock methods on the singleton instance directly
    from app.core.redis import redis_client
    
    mock_store = {}
    
    async def mock_get_json(key):
        import json
        val = mock_store.get(key)
        if val is None: return None
        if isinstance(val, str):
            try: return json.loads(val)
            except: return val
        return val

    async def mock_set_json(key, value, ex=None):
        import json
        mock_store[key] = json.dumps(value)

    async def mock_delete(key):
        if key in mock_store:
            del mock_store[key]
            return 1
        return 0

    async def mock_delete_pattern(pattern):
        import fnmatch
        keys_to_delete = [k for k in mock_store.keys() if fnmatch.fnmatch(k, pattern)]
        for k in keys_to_delete:
            del mock_store[k]
        return len(keys_to_delete)
    
    class MockRedisClientInstance:
        async def get(self, key):
            return mock_store.get(key)
        async def setex(self, key, time, value):
            mock_store[key] = value
        async def set(self, key, value, nx=False, ex=None):
            if nx and key in mock_store:
                return False
            mock_store[key] = value
            return True
        async def delete(self, key):
            if key in mock_store:
                del mock_store[key]
                return 1
            return 0
            
    mock_redis_client_instance = MockRedisClientInstance()
    
    with patch.object(redis_client, "connect", new_callable=AsyncMock), \
         patch.object(redis_client, "close", new_callable=AsyncMock), \
         patch.object(redis_client, "get_json", side_effect=mock_get_json), \
         patch.object(redis_client, "set_json", side_effect=mock_set_json), \
         patch.object(redis_client, "delete", side_effect=mock_delete), \
         patch.object(redis_client, "delete_pattern", side_effect=mock_delete_pattern):
        
        # We also need to mock the `client` property to prevent RuntimeError
        with patch("app.core.redis.RedisClient.client", property(lambda self: mock_redis_client_instance)):
            with TestClient(app) as test_client:
                yield test_client
    
    app.dependency_overrides.clear()
