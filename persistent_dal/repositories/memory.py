"""
In-Memory Storage Repository Implementation
"""

import asyncio
from typing import Type, TypeVar, List, Optional, Dict, Union, Any
from uuid import UUID
from ..models.base import BaseEntity
from ..query.specification import Specification, FilterOperator, SortOrder
from .base import AbstractRepository

T = TypeVar("T", bound=BaseEntity)


class MemoryRepository(AbstractRepository[T]):
    """
    Thread-safe, asynchronous in-memory repository store.
    Ideal for unit testing, fast mock testing, and short-lived caching stores.
    """

    def __init__(self, entity_class: Type[T]):
        self.entity_class = entity_class
        self._storage: Dict[str, T] = {}
        self._lock = asyncio.Lock()

    def _matches_filter(self, entity: T, field_name: str, operator: FilterOperator, target_value: Any) -> bool:
        """Evaluate a single filter criteria rule against an entity."""
        if not hasattr(entity, field_name):
            return False
        val = getattr(entity, field_name)

        if operator == FilterOperator.EQ:
            return str(val) == str(target_value) if isinstance(val, UUID) else val == target_value
        elif operator == FilterOperator.NEQ:
            return str(val) != str(target_value) if isinstance(val, UUID) else val != target_value
        elif operator == FilterOperator.GT:
            return val > target_value
        elif operator == FilterOperator.GTE:
            return val >= target_value
        elif operator == FilterOperator.LT:
            return val < target_value
        elif operator == FilterOperator.LTE:
            return val <= target_value
        elif operator == FilterOperator.IN:
            return val in target_value
        elif operator == FilterOperator.NOT_IN:
            return val not in target_value
        elif operator == FilterOperator.CONTAINS:
            return target_value.lower() in str(val).lower() if isinstance(val, str) else target_value in val
        elif operator == FilterOperator.STARTS_WITH:
            return str(val).startswith(str(target_value))
        elif operator == FilterOperator.ENDS_WITH:
            return str(val).endswith(str(target_value))
        return False

    def _apply_spec(self, items: List[T], spec: Specification) -> List[T]:
        """Filter, sort, and paginate a list of items using a Specification."""
        # 1. Soft-delete filter
        if not spec.include_deleted:
            items = [item for item in items if not item.is_deleted]

        # 2. Apply criteria filters
        for f in spec.filters:
            items = [item for item in items if self._matches_filter(item, f.field, f.operator, f.value)]

        # 3. Sorting
        if spec.sort_by:
            field_name = spec.sort_by
            reverse = (spec.sort_order == SortOrder.DESC)
            items = sorted(
                items,
                key=lambda x: getattr(x, field_name, None) if getattr(x, field_name, None) is not None else "",
                reverse=reverse
            )

        # 4. Pagination
        if spec.offset is not None:
            items = items[spec.offset:]
        if spec.limit is not None:
            items = items[:spec.limit]

        return items

    async def add(self, entity: T) -> T:
        async with self._lock:
            key = str(entity.id)
            # Store a clean model clone
            self._storage[key] = entity.model_copy(deep=True)
            return entity.model_copy(deep=True)

    async def add_many(self, entities: List[T]) -> List[T]:
        async with self._lock:
            for entity in entities:
                self._storage[str(entity.id)] = entity.model_copy(deep=True)
            return [e.model_copy(deep=True) for e in entities]

    async def get_by_id(self, entity_id: Union[UUID, str]) -> Optional[T]:
        async with self._lock:
            key = str(entity_id)
            entity = self._storage.get(key)
            if entity and not entity.is_deleted:
                return entity.model_copy(deep=True)
            return None

    async def find(self, spec: Specification) -> List[T]:
        async with self._lock:
            all_items = [e.model_copy(deep=True) for e in self._storage.values()]
            return self._apply_spec(all_items, spec)

    async def list_all(self, include_deleted: bool = False) -> List[T]:
        async with self._lock:
            results = []
            for item in self._storage.values():
                if include_deleted or not item.is_deleted:
                    results.append(item.model_copy(deep=True))
            return results

    async def update(self, entity: T) -> T:
        async with self._lock:
            key = str(entity.id)
            existing = self._storage.get(key)
            if not existing:
                raise KeyError(f"Entity with ID '{key}' does not exist.")

            entity.touch()
            self._storage[key] = entity.model_copy(deep=True)
            return entity.model_copy(deep=True)

    async def delete(self, entity_id: Union[UUID, str], soft: bool = True) -> bool:
        async with self._lock:
            key = str(entity_id)
            if key not in self._storage:
                return False

            if soft:
                self._storage[key].mark_deleted()
            else:
                del self._storage[key]
            return True

    async def count(self, spec: Optional[Specification] = None) -> int:
        if spec is None:
            spec = Specification()
        results = await self.find(spec)
        return len(results)

    async def exists(self, entity_id: Union[UUID, str]) -> bool:
        item = await self.get_by_id(entity_id)
        return item is not None
