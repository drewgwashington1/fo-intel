from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import app_settings

engine = create_engine(app_settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session():
    """Non-generator version for use in background tasks."""
    return SessionLocal()
