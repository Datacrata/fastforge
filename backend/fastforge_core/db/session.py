"""
FastForge Database Configuration
===================================
Database session management and configuration.
"""
from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator


class DatabaseConfig:
    """Database configuration holder."""

    def __init__(
        self,
        url: str = "postgresql://localhost/fastforge",
        echo: bool = False,
        pool_size: int = 10,
        max_overflow: int = 20,
    ):
        self.url = url
        self.echo = echo

        engine_kwargs = {"echo": echo}
        if not url.startswith("sqlite"):
            engine_kwargs["pool_size"] = pool_size
            engine_kwargs["max_overflow"] = max_overflow

        self.engine = create_engine(url, **engine_kwargs)
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )

    def get_db(self) -> Generator[Session, None, None]:
        """FastAPI dependency for database sessions."""
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def create_tables(self, base):
        """Create all tables from a declarative base."""
        base.metadata.create_all(bind=self.engine)
