"""
Abstract Base Repository Interface
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional, Union
from uuid import UUID
from ..models.base import BaseEntity
from ..query.specification import Specification

T = TypeVar("T", bound=BaseEntity)


class AbstractRepository(ABC, Generic[T]):
    """
    Abstract Generic Repository Interface defining standard CRUD operations
    and query specifications across all persistence storage engines.
    """

    @abstractmethod
    async def add(self, entity: T) -> T:
        """Persist a new entity to storage."""
        pass

    @abstractmethod
    async def add_many(self, entities: List[T]) -> List[T]:
        """Persist multiple entities in a single batch operation."""
        pass

    @abstractmethod
    async def get_by_id(self, entity_id: Union[UUID, str]) -> Optional[T]:
        """Retrieve an entity by its unique ID."""
        pass

    @abstractmethod
    async def find(self, spec: Specification) -> List[T]:
        """Find entities matching specified search specification criteria."""
        pass

    @abstractmethod
    async def list_all(self, include_deleted: bool = False) -> List[T]:
        """Retrieve all persisted entities."""
        pass

    @abstractmethod
    async def update(self, entity: T) -> T:
        """Update an existing entity."""
        pass

    @abstractmethod
    async def delete(self, entity_id: Union[UUID, str], soft: bool = True) -> bool:
        """Delete an entity by ID (soft delete by default, hard delete if soft=False)."""
        pass

    @abstractmethod
    async def count(self, spec: Optional[Specification] = None) -> int:
        """Count total matching entities."""
        pass

    @abstractmethod
    async def exists(self, entity_id: Union[UUID, str]) -> bool:
        """Check whether an entity with the given ID exists."""
        pass
