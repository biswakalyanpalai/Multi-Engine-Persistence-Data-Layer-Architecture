"""
Cached Decorator Repository (Read-Through / Write-Through Caching)
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import TypeVar, List, Optional, Dict, Union, Tuple, Any
from uuid import UUID

from ..models.base import BaseEntity
from ..query.specification import Specification
from .base import AbstractRepository

T = TypeVar("T", bound=BaseEntity)


class CacheEntry:
    """Internal cache entry wrapper with timestamp tracking."""
    def __init__(self, data: Any, ttl_seconds: Optional[int] = None):
        self.data = data
        self.created_at = datetime.now(timezone.utc)
        self.ttl_seconds = ttl_seconds

    def is_expired(self) -> bool:
        if self.ttl_seconds is None:
            return False
        return datetime.now(timezone.utc) > self.created_at + timedelta(seconds=self.ttl_seconds)


class CachedRepository(AbstractRepository[T]):
    """
    Decorator repository adding an in-memory caching tier over any target repository store.
    Features:
    - Read-Through caching for get_by_id lookup.
    - Write-Through caching on add/update.
    - Automatic Cache Invalidation on delete and collection mutations.
    - Cache Performance Metrics (Hits, Misses, Hit Ratio).
    """

    def __init__(self, underlying_repo: AbstractRepository[T], ttl_seconds: Optional[int] = 300):
        self.underlying_repo = underlying_repo
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()

        # Cache stats
        self.hits: int = 0
        self.misses: int = 0

    @property
    def hit_ratio(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total) if total > 0 else 0.0

    async def add(self, entity: T) -> T:
        async with self._lock:
            result = await self.underlying_repo.add(entity)
            self._cache[str(result.id)] = CacheEntry(result.model_copy(deep=True), self.ttl_seconds)
            return result

    async def add_many(self, entities: List[T]) -> List[T]:
        async with self._lock:
            results = await self.underlying_repo.add_many(entities)
            for item in results:
                self._cache[str(item.id)] = CacheEntry(item.model_copy(deep=True), self.ttl_seconds)
            return results

    async def get_by_id(self, entity_id: Union[UUID, str]) -> Optional[T]:
        key = str(entity_id)
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if not entry.is_expired():
                    self.hits += 1
                    return entry.data.model_copy(deep=True)
                else:
                    del self._cache[key]

            self.misses += 1

        # Cache Miss -> Fetch from underlying repository
        entity = await self.underlying_repo.get_by_id(entity_id)
        if entity:
            async with self._lock:
                self._cache[key] = CacheEntry(entity.model_copy(deep=True), self.ttl_seconds)
            return entity.model_copy(deep=True)
        return None

    async def find(self, spec: Specification) -> List[T]:
        # Queries pass through to underlying storage for complete dataset guarantees
        return await self.underlying_repo.find(spec)

    async def list_all(self, include_deleted: bool = False) -> List[T]:
        return await self.underlying_repo.list_all(include_deleted=include_deleted)

    async def update(self, entity: T) -> T:
        async with self._lock:
            result = await self.underlying_repo.update(entity)
            self._cache[str(result.id)] = CacheEntry(result.model_copy(deep=True), self.ttl_seconds)
            return result

    async def delete(self, entity_id: Union[UUID, str], soft: bool = True) -> bool:
        async with self._lock:
            key = str(entity_id)
            result = await self.underlying_repo.delete(entity_id, soft=soft)
            if key in self._cache:
                del self._cache[key]
            return result

    async def count(self, spec: Optional[Specification] = None) -> int:
        return await self.underlying_repo.count(spec)

    async def exists(self, entity_id: Union[UUID, str]) -> bool:
        item = await self.get_by_id(entity_id)
        return item is not None

    def clear_cache(self) -> None:
        """Purge all cached entries."""
        self._cache.clear()
