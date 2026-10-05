import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.config import settings

logger = logging.getLogger("shopping_agent.database")

Base = declarative_base()


def get_engine():
    """Try connecting to primary PostgreSQL database; gracefully fallback to SQLite."""
    try:
        engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        with engine.connect() as conn:
            logger.info("Successfully connected to primary PostgreSQL database.")
        return engine
    except Exception as exc:
        logger.warning(
            f"Failed to connect to primary DB ({exc}). Falling back to SQLite: {settings.FALLBACK_SQLITE_URL}"
        )
        engine = create_engine(
            settings.FALLBACK_SQLITE_URL,
            connect_args={"check_same_thread": False},
        )
        return engine


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI DB session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables and seed default user."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully.")
        from backend.models import User
        with SessionLocal() as session:
            guest_user = session.query(User).filter_by(id=1).first()
            if not guest_user:
                guest = User(
                    id=1,
                    name="Guest User",
                    email="guest@ai-shopping.local",
                )
                session.add(guest)
                session.commit()
                logger.info("Default guest user seeded (ID: 1).")
    except Exception as exc:
        logger.error(f"Error initializing database: {exc}")
