"""
Database Engine & Session Manager for Blogger Auto-Pilot SaaS
Supports Managed PostgreSQL (Supabase / AWS RDS) with seamless local SQLite fallback.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.models.models import Base

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE_DIR = PROJECT_ROOT

def get_database_url() -> str:
    raw_url = os.environ.get('DATABASE_URL', '').strip()
    if raw_url:
        # Normalize postgres:// or postgresql:// to postgresql+psycopg2:// for seamless driver compatibility
        if raw_url.startswith('postgres://'):
            raw_url = 'postgresql+psycopg2://' + raw_url[len('postgres://'):]
        elif raw_url.startswith('postgresql://'):
            raw_url = 'postgresql+psycopg2://' + raw_url[len('postgresql://'):]
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
    Initializes and migrates database tables using Alembic if available,
    falling back to Base.metadata.create_all.
    """
    alembic_ini = os.path.join(BASE_DIR, 'alembic.ini')
    migrated_via_alembic = False
    if os.path.exists(alembic_ini):
        try:
            from alembic.config import Config
            from alembic import command
            alembic_cfg = Config(alembic_ini)
            alembic_cfg.set_main_option("script_location", os.path.join(BASE_DIR, 'alembic'))
            command.upgrade(alembic_cfg, "head")
            migrated_via_alembic = True
        except Exception as e:
            print(f"Notice: Alembic auto-upgrade warning ({e}), falling back to metadata.create_all")

    if not migrated_via_alembic:
        Base.metadata.create_all(bind=engine)

    print(f"SaaS Database initialized with tables: {list(Base.metadata.tables.keys())}")
    print(f"Target DB: {'SQLite (Local)' if is_sqlite else 'PostgreSQL (Supabase/Remote)'}")

if __name__ == '__main__':
    init_saas_db()
