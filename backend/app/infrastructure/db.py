"""Infraestrutura de banco de dados e sessão SQLAlchemy."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Base declarativa para modelos SQLAlchemy."""
    pass


# Engine global com verificação de conexão.
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Fornece sessão por request usando dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
