"""
Comprehensive Test Suite for Storage Repositories
"""

import pytest
import os
import tempfile
from pathlib import Path
from uuid import uuid4

from persistent_dal import (
    MemoryRepository,
    JSONFileRepository,
    SQLiteRepository,
    CachedRepository,
    Specification,
    FilterOperator,
    SortOrder,
    User,
    Document
)


@pytest.mark.asyncio
async def test_memory_repository_crud():
    repo = MemoryRepository(User)

    user1 = User(username="alice", email="alice@example.com", full_name="Alice Smith", role="admin")
    user2 = User(username="bob", email="bob@example.com", full_name="Bob Jones", role="user")

    # Add
    saved1 = await repo.add(user1)
    saved2 = await repo.add(user2)
    assert saved1.id == user1.id

    # Get by ID
    fetched = await repo.get_by_id(user1.id)
    assert fetched is not None
    assert fetched.username == "alice"

    # Count
    count = await repo.count()
    assert count == 2

    # Update
    saved1.full_name = "Alice W. Smith"
    updated = await repo.update(saved1)
    assert updated.full_name == "Alice W. Smith"
    assert updated.version == 2

    # Soft Delete
    deleted = await repo.delete(user2.id, soft=True)
    assert deleted is True
    assert await repo.get_by_id(user2.id) is None
    assert await repo.count() == 1
    assert len(await repo.list_all(include_deleted=True)) == 2


@pytest.mark.asyncio
async def test_specification_filtering_and_sorting():
    repo = MemoryRepository(Document)

    doc1 = Document(title="Python Guide", author_id="u1", status="published", tags=["python", "coding"])
    doc2 = Document(title="Data Layer Design", author_id="u1", status="published", tags=["architecture"])
    doc3 = Document(title="Draft Article", author_id="u2", status="draft", tags=["draft"])

    await repo.add_many([doc1, doc2, doc3])

    # Filter published docs for author u1
    spec = Specification()
    spec.add_filter("author_id", FilterOperator.EQ, "u1")
    spec.add_filter("status", FilterOperator.EQ, "published")
    results = await repo.find(spec)
    assert len(results) == 2

    # Search with CONTAINS
    spec_contains = Specification().add_filter("title", FilterOperator.CONTAINS, "Data")
    results_contains = await repo.find(spec_contains)
    assert len(results_contains) == 1
    assert results_contains[0].title == "Data Layer Design"

    # Sorting & Pagination
    spec_sort = Specification()
    spec_sort.set_sorting("title", SortOrder.ASC)
    spec_sort.set_pagination(limit=2, offset=0)
    sorted_docs = await repo.find(spec_sort)
    assert len(sorted_docs) == 2
    assert sorted_docs[0].title == "Data Layer Design"


@pytest.mark.asyncio
async def test_json_file_repository_persistence():
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "users.json")
        repo = JSONFileRepository(User, file_path)

        u = User(username="charlie", email="charlie@example.com", full_name="Charlie Brown")
        await repo.add(u)

        assert os.path.exists(file_path)

        # Create a fresh repository reading from the same file
        new_repo = JSONFileRepository(User, file_path)
        loaded_user = await new_repo.get_by_id(u.id)
        assert loaded_user is not None
        assert loaded_user.username == "charlie"


@pytest.mark.asyncio
async def test_sqlite_repository_persistence():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_dal.db")
        repo = SQLiteRepository(User, db_path)

        u = User(username="diana", email="diana@example.com", full_name="Diana Prince", role="admin")
        await repo.add(u)

        # Retrieve
        fetched = await repo.get_by_id(u.id)
        assert fetched is not None
        assert fetched.username == "diana"

        # Query Specification
        spec = Specification().add_filter("role", FilterOperator.EQ, "admin")
        results = await repo.find(spec)
        assert len(results) == 1
        assert results[0].username == "diana"

        # Update & Verify Persistence
        u.full_name = "Wonder Woman"
        await repo.update(u)

        new_repo = SQLiteRepository(User, db_path)
        reloaded = await new_repo.get_by_id(u.id)
        assert reloaded is not None
        assert reloaded.full_name == "Wonder Woman"


@pytest.mark.asyncio
async def test_cached_repository():
    mem_repo = MemoryRepository(User)
    cached_repo = CachedRepository(mem_repo, ttl_seconds=60)

    u = User(username="eve", email="eve@example.com", full_name="Eve Online")
    await cached_repo.add(u)

    # First fetch (Cache Hit because add writes-through)
    fetched1 = await cached_repo.get_by_id(u.id)
    assert fetched1 is not None
    assert cached_repo.hits == 1

    # Clear cache manually to simulate cache miss
    cached_repo.clear_cache()
    fetched2 = await cached_repo.get_by_id(u.id)
    assert fetched2 is not None
    assert cached_repo.misses == 1

    # Next fetch should hit cache
    fetched3 = await cached_repo.get_by_id(u.id)
    assert cached_repo.hits == 2
    assert cached_repo.hit_ratio > 0.6
