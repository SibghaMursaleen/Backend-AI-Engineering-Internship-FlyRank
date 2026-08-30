import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app
from app.db.session import get_db
from app.models import Base, Plan, Customer, Subscription, UsageEvent, Invoice

# Shared in-memory SQLite URI allows multiple connections to share the same memory space
TEST_DB_URL = "sqlite:///file:test_mem_db?mode=memory&cache=shared&uri=true"

# Mock Redis implementation for tests
class MockRedis:
    def __init__(self):
        self.store = {}
        self.ttl = {}

    def exists(self, key):
        return key in self.store

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None):
        self.store[key] = str(value)
        if ex:
            self.ttl[key] = ex
        return True

    def expire(self, key, seconds):
        if key in self.store:
            self.ttl[key] = seconds
            return True
        return False

    def incrby(self, key, amount):
        val = int(self.store.get(key, 0))
        new_val = val + amount
        self.store[key] = str(new_val)
        return new_val

    def ping(self):
        return True

    def flushall(self):
        self.store.clear()
        self.ttl.clear()


@pytest.fixture(scope="function", autouse=True)
def mock_redis():
    mock_r = MockRedis()
    # Patch the redis_client instance in all imports
    with patch("app.core.redis.redis_client", mock_r), \
         patch("app.jobs.scheduler.redis_client", mock_r), \
         patch("app.api.routes.redis_client", mock_r):
        yield mock_r


@pytest.fixture(scope="session")
def db_engine():
    # Keep one connection open for the entire test session to prevent the DB from being garbage-collected
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False}
    )
    connection = engine.connect()
    
    # Create all tables once for the entire session
    Base.metadata.create_all(bind=engine)
    
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        connection.close()


@pytest.fixture(scope="function")
def db_session(db_engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    
    db = TestingSessionLocal()
    
    # Seed the required plans for tests
    free_plan = Plan(id="free", name="Free Plan", monthly_quota=1000, price_cents=0)
    pro_plan = Plan(id="pro", name="Pro Plan", monthly_quota=50000, price_cents=2900)
    db.add(free_plan)
    db.add(pro_plan)
    db.commit()
    
    try:
        yield db
    finally:
        db.close()
        
        # Clean up all data after each test function (truncation) to ensure test isolation
        clean_db = TestingSessionLocal()
        try:
            # Delete records in correct dependency order (reverse topological sort)
            for table in reversed(Base.metadata.sorted_tables):
                clean_db.execute(table.delete())
            clean_db.commit()
        except Exception:
            clean_db.rollback()
        finally:
            clean_db.close()


@pytest.fixture(scope="function", autouse=True)
def mock_session_local(db_session):
    def session_factory():
        return db_session
        
    # Prevent background jobs from closing the shared test db_session
    original_close = db_session.close
    db_session.close = lambda: None
    
    try:
        with patch("app.jobs.scheduler.SessionLocal", session_factory), \
             patch("app.db.session.SessionLocal", session_factory):
            yield
    finally:
        db_session.close = original_close


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
            
    # Override FastAPI database session dependency
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
        
    app.dependency_overrides.clear()
