import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import AsyncMock, patch

from app.main import app
from app.db.database import Base
from app.dependencies import get_db


from testcontainers.postgres import PostgresContainer

postgres_container = PostgresContainer("postgres:15-alpine")

@pytest.fixture(scope="session", autouse=True)
def setup_postgres():
    postgres_container.start()
    yield
    postgres_container.stop()

@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test."""
    db_url = postgres_container.get_connection_url().replace("psycopg2", "psycopg")
    engine = create_engine(db_url)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


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
