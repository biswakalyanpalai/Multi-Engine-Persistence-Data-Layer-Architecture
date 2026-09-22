# Persistent Data Layer Architecture

A high-performance, modular, multi-engine **Persistent Data Layer (DAL)** framework in Python. Built around enterprise design patterns including the **Repository Pattern**, **Unit of Work (UoW)**, **Query Specifications**, **Write-Through / Read-Through Caching**, and **Schema-Validated Domain Models**.

---

## 🏗 Architecture Overview

```
                        ┌─────────────────────────────────────┐
                        │          Application Layer          │
                        │    (CLI, Services, FastAPI/API)     │
                        └──────────────────┬──────────────────┘
                                           │
                                           ▼
                        ┌─────────────────────────────────────┐
                        │         DataService Facade          │
                        │   (Business Workflows & Audit Logs) │
                        └──────────────────┬──────────────────┘
                                           │
                                           ▼
                        ┌─────────────────────────────────────┐
                        │        Unit of Work (UoW)           │
                        │   (Transactions & Atomic Operations)│
                        └──────────────────┬──────────────────┘
                                           │
                                           ▼
                        ┌─────────────────────────────────────┐
                        │      Cached Repository Layer        │
                        │    (Read-Through / Write-Through)   │
                        └─────────┬─────────────────┬─────────┘
                                  │                 │
                ┌─────────────────┴─┐             ┌─┴─────────────────┐
                ▼                   ▼             ▼                   ▼
     ┌────────────────────┐  ┌──────────────┐  ┌─────────────┐  ┌────────────┐
     │ SQLite Relational  │  │ JSON/File    │  │ In-Memory   │  │ Extensible │
     │ Engine (aiosqlite) │  │ Persistence  │  │ Store (Test)│  │ Custom DAL │
     └────────────────────┘  └──────────────┘  └─────────────┘  └────────────┘
```

---

## 🌟 Core Features

- **Repository Pattern**: Uniform async generic interface (`add`, `get_by_id`, `find`, `list_all`, `update`, `delete`, `count`, `exists`) across all storage drivers.
- **Multiple Storage Engines**:
  - **MemoryRepository**: Fast, thread-safe memory store for unit testing & caching.
  - **JSONFileRepository**: File persistence using atomic `.tmp` swap writes to guarantee zero corrupt data states.
  - **SQLiteRepository**: Async relational database driver powered by `aiosqlite`.
  - **CachedRepository**: High-performance decorator supporting Read-Through and Write-Through caching with hit/miss analytics.
- **Unit of Work Pattern**: `async with UnitOfWork(factories) as uow:` for atomic multi-repository transactions, clean exit commits, and automatic exception rollbacks.
- **Query Specification Builder**: Decoupled query criteria (`FilterCriteria`, `FilterOperator`, `SortOrder`, `limit`, `offset`).
- **Domain Modeling & Schema Validation**: Built on **Pydantic v2** with auto-managed UUIDs, ISO timestamps (`created_at`, `updated_at`), soft-deletes (`is_deleted`), and optimistic version control (`version`).

---

## 📁 Directory Structure

```
Persistent Data Layer/
├── persistent_dal/
│   ├── __init__.py           # Package exports
│   ├── models/               # Domain Models
│   │   ├── base.py           # BaseEntity (Pydantic v2)
│   │   └── entities.py       # User, Document, AuditLog
│   ├── query/                # Query Specification
│   │   └── specification.py  # Specification, FilterCriteria, FilterOperator
│   ├── repositories/         # Storage Drivers
│   │   ├── base.py           # AbstractRepository interface
│   │   ├── memory.py         # In-memory storage driver
│   │   ├── json_file.py      # Atomic JSON file driver
│   │   ├── sqlite.py         # Async SQLite relational driver
│   │   └── cached.py         # Read-Through / Write-Through Caching decorator
│   ├── unit_of_work.py       # Unit of Work transaction manager
│   └── services/
│       └── data_service.py   # High-level business facade & audit logger
├── tests/                    # Automated Test Suite
│   ├── __init__.py
│   ├── test_repositories.py  # Repository & Caching tests
│   └── test_unit_of_work.py  # Unit of Work & DataService tests
├── pyproject.toml            # Project configuration & dependencies
├── demo.py                   # Comprehensive interactive demonstration
└── README.md                 # Architecture Documentation
```

---

## 🚀 Quick Start

### 1. Run the Interactive Demonstration

```bash
python demo.py
```

Outputs live execution logs of:
1. In-memory data store with query specifications.
2. Atomic JSON file storage write & reload.
3. Async SQLite database table creation & search.
4. Caching layer hit/miss telemetry.
5. Unit of Work transaction commit & exception rollback.
6. High-level DataService facade & audit log generation.

### 2. Run Automated Unit Tests

```bash
python -m pytest
```

---

## 💻 Code Examples

### Repository CRUD & Specification Filtering

```python
import asyncio
from persistent_dal import SQLiteRepository, User, Specification, FilterOperator

async def main():
    repo = SQLiteRepository(User, "app_data.db")

    # Add entity
    user = User(username="alice", email="alice@example.com", full_name="Alice Smith", role="admin")
    await repo.add(user)

    # Filter with Specification
    spec = Specification()
    spec.add_filter("role", FilterOperator.EQ, "admin")
    spec.add_filter("username", FilterOperator.STARTS_WITH, "al")

    admins = await repo.find(spec)
    for admin in admins:
        print(f"Found Admin: {admin.full_name} ({admin.email})")

asyncio.run(main())
```

### Unit of Work Transaction Management

```python
from persistent_dal import UnitOfWork, MemoryRepository, User, Document

async def run_transaction():
    factories = {
        User: MemoryRepository(User),
        Document: MemoryRepository(Document)
    }

    async with UnitOfWork(factories) as uow:
        user_repo = uow.get_repository(User)
        doc_repo = uow.get_repository(Document)

        u = User(username="writer", email="writer@example.com", full_name="Story Writer")
        await user_repo.add(u)

        d = Document(title="Chapter 1", author_id=str(u.id), content="Once upon a time...")
        await doc_repo.add(d)
        
        # If any exception occurs inside this block, changes are rolled back.
```

---

## 🧪 Verification & Testing

The project contains unit tests verifying:
- Full CRUD semantics across Memory, JSON File, and SQLite drivers.
- Criteria filter operators (`EQ`, `NEQ`, `GT`, `IN`, `CONTAINS`, `STARTS_WITH`).
- Pagination (limit/offset) and sorting (ASC/DESC).
- Soft-delete semantics and optimistic locking versions.
- Transaction rollback safety in Unit of Work context manager.
- Read-through / Write-through caching telemetry and cache invalidation.
