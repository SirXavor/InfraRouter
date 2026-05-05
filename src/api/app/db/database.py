from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from ..settings import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(bind=None):
    from . import models  # noqa: ensure models are registered
    Base.metadata.create_all(bind=bind or engine)
