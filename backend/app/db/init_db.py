"""Database schema initialization for the MVP."""

from sqlalchemy import inspect, text

from app.db.db_models import Base
from app.db.session import engine


def init_db() -> None:
    """Create missing tables and add compatible report fields for local SQLite data."""

    Base.metadata.create_all(bind=engine)
    if engine.dialect.name != "sqlite":
        return

    existing_columns = {
        column["name"] for column in inspect(engine).get_columns("investigations")
    }
    additions = {
        "investigation_plan": "JSON",
        "datasets": "JSON",
    }
    with engine.begin() as connection:
        for name, column_type in additions.items():
            if name not in existing_columns:
                connection.execute(text(f"ALTER TABLE investigations ADD COLUMN {name} {column_type}"))
