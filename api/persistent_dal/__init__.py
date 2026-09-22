"""
Persistent Data Layer Architecture Package
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A modular, high-performance Data Access Layer (DAL) framework in Python
implementing Repository, Unit of Work, Query Specification, and Caching patterns.
"""

from .models.base import BaseEntity
from .models.entities import User, Document, AuditLog
from .query.specification import FilterCriteria, Specification, SortOrder, FilterOperator
from .repositories.base import AbstractRepository
from .repositories.memory import MemoryRepository
from .repositories.json_file import JSONFileRepository
from .repositories.sqlite import SQLiteRepository
from .repositories.cached import CachedRepository
from .unit_of_work import UnitOfWork, AbstractUnitOfWork
from .services.data_service import DataService

__version__ = "1.0.0"

__all__ = [
    "BaseEntity",
    "User",
    "Document",
    "AuditLog",
    "FilterCriteria",
    "Specification",
    "SortOrder",
    "FilterOperator",
    "AbstractRepository",
    "MemoryRepository",
    "JSONFileRepository",
    "SQLiteRepository",
    "CachedRepository",
    "UnitOfWork",
    "AbstractUnitOfWork",
    "DataService",
]
