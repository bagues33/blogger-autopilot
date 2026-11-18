import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import app
from src.core.database import SessionLocal, init_saas_db
from src.core.security import hash_password, create_access_token
from src.models.models import User, Subscription
from src.core.dependencies import get_or_create_default_admin

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Ensure database schema is ready before running tests."""
    init_saas_db()

@pytest.fixture
def db_session():
    """Provides a fresh database session for a test."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def client():
    """Provides an unauthenticated FastAPI TestClient."""
    with TestClient(app) as c:
        yield c

@pytest.fixture
def admin_client(db_session: Session):
    """Provides a TestClient authenticated as the default Superadmin."""
    admin = get_or_create_default_admin(db_session)
    token = create_access_token({"sub": admin.id, "email": admin.email, "role": admin.role})
    
    with TestClient(app) as c:
        c.cookies.set("saas_token", token)
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c

@pytest.fixture
def tenant_factory(db_session: Session):
    """
    Factory to generate authenticated tenant sessions with specific roles and tiers.
    Usage:
        client_a, user_a = tenant_factory(plan="pro")
    """
    def _create_tenant(plan="free", role="subscriber", name=None):
        uid = uuid.uuid4().hex[:8]
        email = f"tenant_{uid}@example.test"
        full_name = name or f"Tenant {uid}"
        
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            hashed_password=hash_password("Password123!"),
            full_name=full_name,
            role=role,
            is_active=True
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        credits = 3 if plan == "free" else (120 if plan == "pro" else 500)
        sub = Subscription(
            user_id=user.id,
            plan_tier=plan,
            status="active",
            article_credits_limit=credits,
            article_credits_used=0
        )
        db_session.add(sub)
        db_session.commit()

        token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
        c = TestClient(app)
        c.cookies.set("saas_token", token)
        c.headers.update({"Authorization": f"Bearer {token}"})
        return c, user

    return _create_tenant

