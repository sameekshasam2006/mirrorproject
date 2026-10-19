from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

database_url = settings.database_url
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(
    database_url,
    connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_database_schema() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    with engine.begin() as conn:
        existing = conn.execute(text("PRAGMA table_info(users)")).fetchall()
        columns = {row[1] for row in existing}

        if "password_reset_token" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN password_reset_token VARCHAR"))
        if "password_reset_expires_at" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN password_reset_expires_at DATETIME"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
