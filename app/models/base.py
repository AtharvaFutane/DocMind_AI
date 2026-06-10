"""
SQLAlchemy DeclarativeBase — isolated to avoid circular imports.
Models import Base from here, and __init__.py re-exports everything.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass
