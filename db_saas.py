"""
Database Engine & Session Manager for Blogger Auto-Pilot SaaS
Supports Managed PostgreSQL (Supabase / AWS RDS) with seamless local SQLite fallback.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models_saas import Base

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_database_url() -> str:
    raw_url = os.environ.get('DATABASE_URL', '').strip()
    if raw_url:
        # Normalize postgres:// to postgresql:// for modern SQLAlchemy
        if raw_url.startswith('postgres://'):
            raw_url = raw_url.replace('postgres://', 'postgresql://', 1)
        return raw_url
        
    # Local fallback SQLite
    sqlite_path = os.environ.get('BLOGGER_SAAS_DB_PATH', os.path.join(BASE_DIR, 'data_saas.db'))
    return f"sqlite:///{sqlite_path}"

DB_URL = get_database_url()
is_sqlite = DB_URL.startswith('sqlite')

# Create Engine with production-ready connection pool settings
if is_sqlite:
    engine = create_engine(
        DB_URL,
        connect_args={'check_same_thread': False},
        echo=False
    )
else:
    # PostgreSQL / Supabase pool configuration
    engine = create_engine(
        DB_URL,
        pool_size=10,
        max_overflow=20,
        pool_recycle=300,
        pool_pre_ping=True,
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_saas_db():
    """
    FastAPI dependency that yields a SQLAlchemy database session per request.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_saas_db():
    """
    Initializes all tables defined in models_saas.
    """
    Base.metadata.create_all(bind=engine)
    print(f"SaaS Database initialized with tables: {list(Base.metadata.tables.keys())}")
    print(f"Target DB: {'SQLite (Local)' if is_sqlite else 'PostgreSQL (Supabase/Remote)'}")

if __name__ == '__main__':
    init_saas_db()
