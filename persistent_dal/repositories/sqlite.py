"""
Asynchronous SQLite Relational Repository Driver
"""

import json
import sqlite3
from pathlib import Path
from typing import Type, TypeVar, List, Optional, Union, Any
from uuid import UUID
import aiosqlite

from ..models.base import BaseEntity
from ..query.specification import Specification, FilterOperator, SortOrder
from .base import AbstractRepository

T = TypeVar("T", bound=BaseEntity)


class SQLiteRepository(AbstractRepository[T]):
    """
    Asynchronous relational SQLite persistence driver using aiosqlite.
    Stores entities using a hybrid Relational + JSON Document approach
    allowing schema flexibility with relational query performance.
    """

    def __init__(self, entity_class: Type[T], db_path: Union[str, Path]):
        self.entity_class = entity_class
        self.db_path = str(db_path)
        self.table_name = f"{entity_class.__name__.lower()}s"
        self._initialized = False

    async def _init_db(self) -> None:
        """Create database table and indexes if they do not exist."""
        if self._initialized:
            return

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            query = f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                version INTEGER NOT NULL DEFAULT 1,
                payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_is_deleted ON {self.table_name}(is_deleted);
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_created_at ON {self.table_name}(created_at);
            """
            await db.executescript(query)
            await db.commit()
        self._initialized = True

    def _row_to_entity(self, row: tuple) -> T:
        """Parse database row payload into target entity model."""
        payload_json = row[4]
        data = json.loads(payload_json)
        return self.entity_class.from_dict(data)

    async def add(self, entity: T) -> T:
        await self._init_db()
        async with aiosqlite.connect(self.db_path) as db:
            payload = json.dumps(entity.to_dict())
            await db.execute(
                f"""
                INSERT INTO {self.table_name} (id, created_at, updated_at, is_deleted, version, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(entity.id),
                    entity.created_at.isoformat(),
                    entity.updated_at.isoformat(),
                    1 if entity.is_deleted else 0,
                    entity.version,
                    payload
                )
            )
            await db.commit()
        return entity.model_copy(deep=True)

    async def add_many(self, entities: List[T]) -> List[T]:
        await self._init_db()
        async with aiosqlite.connect(self.db_path) as db:
            params = [
                (
                    str(e.id),
                    e.created_at.isoformat(),
                    e.updated_at.isoformat(),
                    1 if e.is_deleted else 0,
                    e.version,
                    json.dumps(e.to_dict())
                )
                for e in entities
            ]
            await db.executemany(
                f"""
                INSERT INTO {self.table_name} (id, created_at, updated_at, is_deleted, version, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                params
            )
            await db.commit()
        return [e.model_copy(deep=True) for e in entities]

    async def get_by_id(self, entity_id: Union[UUID, str]) -> Optional[T]:
        await self._init_db()
        key = str(entity_id)
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                f"SELECT id, created_at, updated_at, is_deleted, payload FROM {self.table_name} WHERE id = ? AND is_deleted = 0",
                (key,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_entity(row)
        return None

    async def find(self, spec: Specification) -> List[T]:
        await self._init_db()
        # Fetch records and evaluate criteria
        async with aiosqlite.connect(self.db_path) as db:
            query = f"SELECT id, created_at, updated_at, is_deleted, payload FROM {self.table_name}"
            conditions = []
            params = []

            if not spec.include_deleted:
                conditions.append("is_deleted = 0")

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY created_at ASC"

            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()

        entities = [self._row_to_entity(row) for row in rows]

        # Apply Specification filtering, sorting, and pagination
        from .memory import MemoryRepository
        mem_repo = MemoryRepository(self.entity_class)
        return mem_repo._apply_spec(entities, spec)

    async def list_all(self, include_deleted: bool = False) -> List[T]:
        spec = Specification(include_deleted=include_deleted)
        return await self.find(spec)

    async def update(self, entity: T) -> T:
        await self._init_db()
        key = str(entity.id)
        async with aiosqlite.connect(self.db_path) as db:
            # Verify existence
            async with db.execute(f"SELECT id FROM {self.table_name} WHERE id = ?", (key,)) as cursor:
                if not await cursor.fetchone():
                    raise KeyError(f"Entity with ID '{key}' does not exist in SQLite table '{self.table_name}'.")

            entity.touch()
            payload = json.dumps(entity.to_dict())

            await db.execute(
                f"""
                UPDATE {self.table_name}
                SET updated_at = ?, is_deleted = ?, version = ?, payload = ?
                WHERE id = ?
                """,
                (
                    entity.updated_at.isoformat(),
                    1 if entity.is_deleted else 0,
                    entity.version,
                    payload,
                    key
                )
            )
            await db.commit()
        return entity.model_copy(deep=True)

    async def delete(self, entity_id: Union[UUID, str], soft: bool = True) -> bool:
        await self._init_db()
        key = str(entity_id)
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(f"SELECT payload FROM {self.table_name} WHERE id = ?", (key,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return False

            if soft:
                entity = self._row_to_entity(row)
                entity.mark_deleted()
                payload = json.dumps(entity.to_dict())
                await db.execute(
                    f"UPDATE {self.table_name} SET is_deleted = 1, updated_at = ?, payload = ? WHERE id = ?",
                    (entity.updated_at.isoformat(), payload, key)
                )
            else:
                await db.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (key,))

            await db.commit()
            return True

    async def count(self, spec: Optional[Specification] = None) -> int:
        if spec is None:
            spec = Specification()
        results = await self.find(spec)
        return len(results)

    async def exists(self, entity_id: Union[UUID, str]) -> bool:
        entity = await self.get_by_id(entity_id)
        return entity is not None
