"""Database schema initialization for the MVP."""

from app.db.db_models import Base
from app.db.session import engine


def init_db() -> None:
    """Create missing database tables without running migrations."""

    Base.metadata.create_all(bind=engine)
