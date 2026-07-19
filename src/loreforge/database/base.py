"""SQLAlchemy declarative base for LoreForge persistence."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for LoreForge-owned relational models."""
