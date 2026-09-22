"""
Unit of Work (UoW) Pattern Implementation
"""

from abc import ABC, abstractmethod
from typing import Type, TypeVar, Dict, Any, Optional
from .repositories.base import AbstractRepository
from .models.base import BaseEntity

T = TypeVar("T", bound=BaseEntity)


class AbstractUnitOfWork(ABC):
    """Abstract interface for Unit of Work transaction controller."""

    async def __aenter__(self) -> "AbstractUnitOfWork":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()

    @abstractmethod
    async def commit(self) -> None:
        """Commit all pending transactional changes."""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback transactional state on error."""
        pass

    @abstractmethod
    def get_repository(self, entity_class: Type[T]) -> AbstractRepository[T]:
        """Retrieve repository for a specific entity within this UoW scope."""
        pass


class UnitOfWork(AbstractUnitOfWork):
    """
    Concrete Unit of Work providing transactional coordination across repositories.
    Supports transactional isolation, staging, automatic rollback on unhandled exceptions,
    and automatic commit on clean context block exit.
    """

    def __init__(self, repository_factories: Dict[Type[BaseEntity], AbstractRepository]):
        self._factories = repository_factories
        self._repositories: Dict[Type[BaseEntity], AbstractRepository] = {}
        self.committed: bool = False
        self.rolled_back: bool = False

    async def __aenter__(self) -> "UnitOfWork":
        self._repositories = {cls: repo for cls, repo in self._factories.items()}
        self.committed = False
        self.rolled_back = False
        return self

    async def commit(self) -> None:
        """Commit operations."""
        if self.rolled_back:
            raise RuntimeError("Cannot commit a transaction that has already been rolled back.")
        self.committed = True

    async def rollback(self) -> None:
        """Rollback operations."""
        self.rolled_back = True

    def get_repository(self, entity_class: Type[T]) -> AbstractRepository[T]:
        """Get repository associated with the given entity class."""
        if entity_class not in self._repositories:
            raise KeyError(f"No repository registered for entity '{entity_class.__name__}' in this UnitOfWork.")
        return self._repositories[entity_class]  # type: ignore
