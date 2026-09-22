"""
JSON File Persistent Storage Repository Implementation
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Type, TypeVar, List, Optional, Dict, Union
from uuid import UUID
from ..models.base import BaseEntity
from ..query.specification import Specification
from .base import AbstractRepository
from .memory import MemoryRepository

T = TypeVar("T", bound=BaseEntity)


class JSONFileRepository(AbstractRepository[T]):
    """
    File-based persistent repository driver storing records in JSON format.
    Uses atomic temp file replacement to ensure zero data corruption on power/process failure.
    """

    def __init__(self, entity_class: Type[T], file_path: Union[str, Path]):
        self.entity_class = entity_class
        self.file_path = Path(file_path)
        self._lock = asyncio.Lock()
        self._mem_repo = MemoryRepository(entity_class)
        self._initialized = False

    async def _ensure_loaded(self) -> None:
        """Load data from JSON file on disk into internal memory store."""
        if self._initialized:
            return

        if not self.file_path.parent.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

        if self.file_path.exists() and self.file_path.stat().st_size > 0:
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item_data in data:
                        entity = self.entity_class.from_dict(item_data)
                        await self._mem_repo.add(entity)
            except (json.JSONDecodeError, ValueError) as e:
                # Malformed file backup safeguard
                backup_path = self.file_path.with_suffix(".corrupt.bak")
                self.file_path.rename(backup_path)
                print(f"[Warning] Corrupt storage file backed up to {backup_path}: {e}")

        self._initialized = True

    async def _flush(self) -> None:
        """Atomically serialize and write all entities to disk."""
        all_items = await self._mem_repo.list_all(include_deleted=True)
        json_data = [item.to_dict() for item in all_items]

        temp_path = self.file_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        # Atomic replacement of target file
        temp_path.replace(self.file_path)

    async def add(self, entity: T) -> T:
        async with self._lock:
            await self._ensure_loaded()
            result = await self._mem_repo.add(entity)
            await self._flush()
            return result

    async def add_many(self, entities: List[T]) -> List[T]:
        async with self._lock:
            await self._ensure_loaded()
            result = await self._mem_repo.add_many(entities)
            await self._flush()
            return result

    async def get_by_id(self, entity_id: Union[UUID, str]) -> Optional[T]:
        async with self._lock:
            await self._ensure_loaded()
            return await self._mem_repo.get_by_id(entity_id)

    async def find(self, spec: Specification) -> List[T]:
        async with self._lock:
            await self._ensure_loaded()
            return await self._mem_repo.find(spec)

    async def list_all(self, include_deleted: bool = False) -> List[T]:
        async with self._lock:
            await self._ensure_loaded()
            return await self._mem_repo.list_all(include_deleted=include_deleted)

    async def update(self, entity: T) -> T:
        async with self._lock:
            await self._ensure_loaded()
            result = await self._mem_repo.update(entity)
            await self._flush()
            return result

    async def delete(self, entity_id: Union[UUID, str], soft: bool = True) -> bool:
        async with self._lock:
            await self._ensure_loaded()
            result = await self._mem_repo.delete(entity_id, soft=soft)
            if result:
                await self._flush()
            return result

    async def count(self, spec: Optional[Specification] = None) -> int:
        async with self._lock:
            await self._ensure_loaded()
            return await self._mem_repo.count(spec)

    async def exists(self, entity_id: Union[UUID, str]) -> bool:
        async with self._lock:
            await self._ensure_loaded()
            return await self._mem_repo.exists(entity_id)
