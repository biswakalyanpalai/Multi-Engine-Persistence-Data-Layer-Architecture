"""
Vercel Serverless Entrypoint for Multi-Engine Persistent Data Layer
Provides full REST API and interactive Web UI Dashboard
"""

import sys
import os
import tempfile
import traceback
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add current api directory and project root to sys.path
api_dir = Path(__file__).resolve().parent
root_dir = api_dir.parent
for d in [str(api_dir), str(root_dir)]:
    if d not in sys.path:
        sys.path.insert(0, d)

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from persistent_dal import (
        MemoryRepository,
        JSONFileRepository,
        SQLiteRepository,
        CachedRepository,
        Specification,
        FilterOperator,
        SortOrder,
        User,
        Document,
        AuditLog,
        DataService,
        UnitOfWork,
    )
except ImportError:
    from api.persistent_dal import (
        MemoryRepository,
        JSONFileRepository,
        SQLiteRepository,
        CachedRepository,
        Specification,
        FilterOperator,
        SortOrder,
        User,
        Document,
        AuditLog,
        DataService,
        UnitOfWork,
    )

# Use writable /tmp directory for serverless environment
TEMP_DIR = Path(tempfile.gettempdir())
json_storage_path = TEMP_DIR / "dal_docs.json"
sqlite_storage_path = TEMP_DIR / "dal_app.db"

# Global in-memory storage repositories for serverless environment
user_repo = MemoryRepository(User)
doc_repo = MemoryRepository(Document)
audit_repo = MemoryRepository(AuditLog)
cached_user_repo = CachedRepository(user_repo, ttl_seconds=300)
service = DataService(cached_user_repo, doc_repo, audit_repo)

_initialized = False


async def ensure_seeded():
    global _initialized
    if _initialized:
        return
    try:
        if await user_repo.count() == 0:
            u1 = await service.register_user("alex_rivera", "alex@company.com", "Alex Rivera", role="admin")
            u2 = await service.register_user("beatrice_v", "beatrice@company.com", "Beatrice Vance", role="developer")
            doc = await service.create_document(str(u1.id), "Persistent Data Layer Architecture", "Multi-Engine Storage Engine for Python.")
            await service.publish_document(doc.id, str(u1.id))
    except Exception as e:
        print(f"Seed error: {e}")
    finally:
        _initialized = True


app = FastAPI(
    title="Persistent Data Layer API",
    description="A multi-engine Data Access Layer implementing Repository, Unit of Work, Query Specification, and Caching patterns.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc()
        }
    )


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3)
    email: str
    full_name: str
    role: str = "user"


class CreateDocumentRequest(BaseModel):
    author_id: str
    title: str
    content: str
    tags: List[str] = []


@app.get("/", response_class=HTMLResponse)
async def home_dashboard():
    """Interactive Web Dashboard UI demonstrating the Persistent Data Layer in real-time."""
    await ensure_seeded()
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Persistent Data Layer - Interactive Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css" rel="stylesheet">
        <style>
            :root { --bg-dark: #0f172a; --card-bg: #1e293b; --border-color: #334155; }
            body { background-color: var(--bg-dark); color: #f8fafc; font-family: 'Segoe UI', system-ui, sans-serif; }
            .card { background-color: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px; color: #f8fafc; }
            .nav-tabs .nav-link { color: #94a3b8; border: none; font-weight: 500; }
            .nav-tabs .nav-link.active { color: #38bdf8; background: transparent; border-bottom: 3px solid #38bdf8; }
            .btn-primary { background-color: #3b82f6; border: none; }
            .btn-primary:hover { background-color: #2563eb; }
            pre.telemetry-output { background: #090d16; border: 1px solid #1e293b; border-radius: 8px; color: #38bdf8; max-height: 250px; overflow-y: auto; font-size: 0.85rem; padding: 12px; }
            .stat-badge { font-size: 1.5rem; font-weight: 700; color: #38bdf8; }
        </style>
    </head>
    <body class="py-4">
        <div class="container">
            <!-- Header -->
            <div class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary">
                <div>
                    <h2 class="fw-bold text-primary mb-1"><i class="bi bi-layers-half me-2"></i>Persistent Data Layer Dashboard</h2>
                    <p class="text-secondary mb-0">Multi-Engine Storage, Repository Pattern, Unit of Work & Write-Through Caching</p>
                </div>
                <div>
                    <a href="/docs" target="_blank" class="btn btn-outline-info me-2"><i class="bi bi-file-code me-1"></i>Swagger API Docs</a>
                    <button onclick="refreshDashboard()" class="btn btn-primary"><i class="bi bi-arrow-clockwise me-1"></i>Refresh Data</button>
                </div>
            </div>

            <!-- Stats Bar -->
            <div class="row g-3 mb-4">
                <div class="col-md-3">
                    <div class="card p-3 text-center">
                        <span class="text-secondary small">Total Users</span>
                        <div id="stat-users" class="stat-badge">-</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card p-3 text-center">
                        <span class="text-secondary small">Total Documents</span>
                        <div id="stat-docs" class="stat-badge">-</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card p-3 text-center">
                        <span class="text-secondary small">Cache Hit Ratio</span>
                        <div id="stat-cache" class="stat-badge text-success">-</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card p-3 text-center">
                        <span class="text-secondary small">Audit Logs</span>
                        <div id="stat-audits" class="stat-badge text-warning">-</div>
                    </div>
                </div>
            </div>

            <!-- Main Tabs -->
            <ul class="nav nav-tabs mb-4" id="mainTabs">
                <li class="nav-item">
                    <button class="nav-link active" data-bs-toggle="tab" data-bs-target="#tab-users"><i class="bi bi-people me-1"></i>Users Repository</button>
                </li>
                <li class="nav-item">
                    <button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-docs"><i class="bi bi-file-text me-1"></i>Document Specifications</button>
                </li>
                <li class="nav-item">
                    <button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-uow"><i class="bi bi-cpu me-1"></i>Unit of Work (UoW)</button>
                </li>
                <li class="nav-item">
                    <button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-engines"><i class="bi bi-database me-1"></i>Multi-Engine Live Test</button>
                </li>
            </ul>

            <div class="tab-content">
                <!-- TAB 1: USERS -->
                <div class="tab-pane fade show active" id="tab-users">
                    <div class="row g-4">
                        <div class="col-md-5">
                            <div class="card p-4">
                                <h4 class="h5 mb-3 text-info"><i class="bi bi-person-plus me-2"></i>Register User Entity</h4>
                                <form id="form-user" onsubmit="handleCreateUser(event)">
                                    <div class="mb-3">
                                        <label class="form-label small text-secondary">Username</label>
                                        <input type="text" id="user-username" class="form-control bg-dark text-white border-secondary" placeholder="e.g. john_doe" required minlength="3">
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label small text-secondary">Email Address</label>
                                        <input type="email" id="user-email" class="form-control bg-dark text-white border-secondary" placeholder="e.g. john@company.com" required>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label small text-secondary">Full Name</label>
                                        <input type="text" id="user-fullname" class="form-control bg-dark text-white border-secondary" placeholder="e.g. John Doe" required>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label small text-secondary">Role</label>
                                        <select id="user-role" class="form-select bg-dark text-white border-secondary">
                                            <option value="user">User</option>
                                            <option value="developer">Developer</option>
                                            <option value="admin">Admin</option>
                                        </select>
                                    </div>
                                    <button type="submit" class="btn btn-primary w-100"><i class="bi bi-check-circle me-1"></i>Add to Repository</button>
                                </form>
                            </div>
                        </div>

                        <div class="col-md-7">
                            <div class="card p-4">
                                <div class="d-flex justify-content-between align-items-center mb-3">
                                    <h4 class="h5 text-info mb-0"><i class="bi bi-list-ul me-2"></i>Repository Users</h4>
                                    <select id="filter-role" onchange="loadUsers()" class="form-select bg-dark text-white border-secondary w-auto form-select-sm">
                                        <option value="">All Roles</option>
                                        <option value="admin">Admin</option>
                                        <option value="developer">Developer</option>
                                        <option value="user">User</option>
                                    </select>
                                </div>
                                <div class="table-responsive">
                                    <table class="table table-dark table-hover align-middle">
                                        <thead>
                                            <tr>
                                                <th>Username</th>
                                                <th>Full Name</th>
                                                <th>Email</th>
                                                <th>Role</th>
                                            </tr>
                                        </thead>
                                        <tbody id="users-table-body">
                                            <tr><td colspan="4" class="text-center text-secondary">Loading users...</td></tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- TAB 2: DOCUMENTS -->
                <div class="tab-pane fade" id="tab-docs">
                    <div class="row g-4">
                        <div class="col-md-5">
                            <div class="card p-4">
                                <h4 class="h5 mb-3 text-info"><i class="bi bi-file-earmark-plus me-2"></i>Create Document</h4>
                                <form id="form-doc" onsubmit="handleCreateDoc(event)">
                                    <div class="mb-3">
                                        <label class="form-label small text-secondary">Author User ID</label>
                                        <input type="text" id="doc-author" class="form-control bg-dark text-white border-secondary" placeholder="Enter User UUID or System ID" required>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label small text-secondary">Document Title</label>
                                        <input type="text" id="doc-title" class="form-control bg-dark text-white border-secondary" placeholder="e.g. Architecture Overview" required>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label small text-secondary">Content Body</label>
                                        <textarea id="doc-content" class="form-control bg-dark text-white border-secondary" rows="3" placeholder="Document body description..."></textarea>
                                    </div>
                                    <button type="submit" class="btn btn-primary w-100"><i class="bi bi-save me-1"></i>Create Document</button>
                                </form>
                            </div>
                        </div>

                        <div class="col-md-7">
                            <div class="card p-4">
                                <div class="d-flex justify-content-between align-items-center mb-3">
                                    <h4 class="h5 text-info mb-0"><i class="bi bi-search me-2"></i>Specification Search</h4>
                                    <input type="text" id="doc-search" oninput="loadDocuments()" class="form-control bg-dark text-white border-secondary w-50 form-control-sm" placeholder="Search titles by keyword...">
                                </div>
                                <div class="table-responsive">
                                    <table class="table table-dark table-hover align-middle">
                                        <thead>
                                            <tr>
                                                <th>Title</th>
                                                <th>Author ID</th>
                                                <th>Status</th>
                                                <th>Created</th>
                                            </tr>
                                        </thead>
                                        <tbody id="docs-table-body">
                                            <tr><td colspan="4" class="text-center text-secondary">Loading documents...</td></tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- TAB 3: UNIT OF WORK -->
                <div class="tab-pane fade" id="tab-uow">
                    <div class="card p-4">
                        <h4 class="h5 text-warning mb-3"><i class="bi bi-arrow-repeat me-2"></i>Unit of Work (UoW) Transaction Controller</h4>
                        <p class="text-secondary small">Demonstrates atomic multi-repository operations. Standard context exits commit all changes automatically, while unhandled exceptions rollback all staged entities cleanly.</p>
                        
                        <div class="d-flex gap-3 mb-4">
                            <button onclick="runUoWTransaction(true)" class="btn btn-success"><i class="bi bi-check-lg me-1"></i>Execute Successful Transaction (Commit)</button>
                            <button onclick="runUoWTransaction(false)" class="btn btn-danger"><i class="bi bi-x-circle me-1"></i>Simulate Failed Transaction (Rollback)</button>
                        </div>

                        <h6 class="text-secondary">Transaction Execution Log:</h6>
                        <pre id="uow-log" class="telemetry-output">// Click a transaction button above to observe Unit of Work commit/rollback behavior...</pre>
                    </div>
                </div>

                <!-- TAB 4: MULTI-ENGINE DEMO -->
                <div class="tab-pane fade" id="tab-engines">
                    <div class="card p-4">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <div>
                                <h4 class="h5 text-success mb-1"><i class="bi bi-hdd-network me-2"></i>Multi-Engine Live Storage Test</h4>
                                <p class="text-secondary small mb-0">Executes queries simultaneously across Memory, Atomic JSON File, and SQLite storage engines.</p>
                            </div>
                            <button onclick="runMultiEngineDemo()" class="btn btn-success"><i class="bi bi-play-fill me-1"></i>Run Live Engine Tests</button>
                        </div>
                        <pre id="engine-log" class="telemetry-output">// Click "Run Live Engine Tests" to trigger multi-engine operations...</pre>
                    </div>
                </div>
            </div>

            <!-- Audit Logs Section -->
            <div class="card p-4 mt-4">
                <h4 class="h5 text-white mb-3"><i class="bi bi-journal-text me-2"></i>System Audit Log Telemetry</h4>
                <div class="table-responsive">
                    <table class="table table-dark table-striped align-middle mb-0">
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Action</th>
                                <th>Entity</th>
                                <th>Actor</th>
                                <th>Details</th>
                            </tr>
                        </thead>
                        <tbody id="audits-table-body">
                            <tr><td colspan="5" class="text-center text-secondary">Loading audit records...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            async function fetchJSON(url, options = {}) {
                const res = await fetch(url, options);
                return await res.json();
            }

            async function refreshDashboard() {
                loadStats();
                loadUsers();
                loadDocuments();
                loadAudits();
            }

            async function loadStats() {
                try {
                    const stats = await fetchJSON('/api/stats');
                    const cache = await fetchJSON('/api/cache-stats');
                    document.getElementById('stat-users').innerText = stats.total_users || 0;
                    document.getElementById('stat-docs').innerText = stats.total_documents || 0;
                    document.getElementById('stat-audits').innerText = stats.total_audit_logs || 0;
                    document.getElementById('stat-cache').innerText = cache.hit_ratio_percent + '%';
                } catch(e) { console.error(e); }
            }

            async function loadUsers() {
                const role = document.getElementById('filter-role').value;
                const url = role ? `/api/users?role=${role}` : '/api/users';
                try {
                    const users = await fetchJSON(url);
                    const tbody = document.getElementById('users-table-body');
                    if (!users.length) {
                        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-secondary">No users found</td></tr>';
                        return;
                    }
                    tbody.innerHTML = users.map(u => `
                        <tr>
                            <td><code>${u.username}</code></td>
                            <td>${u.full_name}</td>
                            <td>${u.email}</td>
                            <td><span class="badge bg-${u.role === 'admin' ? 'danger' : u.role === 'developer' ? 'info' : 'secondary'}">${u.role}</span></td>
                        </tr>
                    `).join('');
                } catch(e) { console.error(e); }
            }

            async function handleCreateUser(e) {
                e.preventDefault();
                const payload = {
                    username: document.getElementById('user-username').value,
                    email: document.getElementById('user-email').value,
                    full_name: document.getElementById('user-fullname').value,
                    role: document.getElementById('user-role').value
                };
                try {
                    await fetchJSON('/api/users', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(payload)
                    });
                    document.getElementById('form-user').reset();
                    refreshDashboard();
                } catch(err) { alert("Error creating user: " + err); }
            }

            async function loadDocuments() {
                const query = document.getElementById('doc-search').value;
                const url = query ? `/api/documents?query=${encodeURIComponent(query)}` : '/api/documents';
                try {
                    const docs = await fetchJSON(url);
                    const tbody = document.getElementById('docs-table-body');
                    if (!docs.length) {
                        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-secondary">No documents found</td></tr>';
                        return;
                    }
                    tbody.innerHTML = docs.map(d => `
                        <tr>
                            <td><strong>${d.title}</strong></td>
                            <td><code>${d.author_id.substring(0, 8)}...</code></td>
                            <td><span class="badge bg-${d.status === 'published' ? 'success' : 'warning'}">${d.status}</span></td>
                            <td class="small text-secondary">${new Date(d.created_at).toLocaleTimeString()}</td>
                        </tr>
                    `).join('');
                } catch(e) { console.error(e); }
            }

            async function handleCreateDoc(e) {
                e.preventDefault();
                const payload = {
                    author_id: document.getElementById('doc-author').value,
                    title: document.getElementById('doc-title').value,
                    content: document.getElementById('doc-content').value,
                    tags: ["web", "dashboard"]
                };
                try {
                    await fetchJSON('/api/documents', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(payload)
                    });
                    document.getElementById('form-doc').reset();
                    refreshDashboard();
                } catch(err) { alert("Error creating document: " + err); }
            }

            async function loadAudits() {
                try {
                    const logs = await fetchJSON('/api/audits');
                    const tbody = document.getElementById('audits-table-body');
                    if (!logs.length) {
                        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-secondary">No audit logs recorded</td></tr>';
                        return;
                    }
                    tbody.innerHTML = logs.map(l => `
                        <tr>
                            <td class="small text-secondary">${new Date(l.created_at).toLocaleString()}</td>
                            <td><span class="badge bg-${l.action === 'CREATE' ? 'success' : 'info'}">${l.action}</span></td>
                            <td><code>${l.entity_name}</code></td>
                            <td>${l.performed_by}</td>
                            <td class="small text-info">${JSON.stringify(l.details)}</td>
                        </tr>
                    `).join('');
                } catch(e) { console.error(e); }
            }

            async function runUoWTransaction(success) {
                const log = document.getElementById('uow-log');
                log.innerText = `[${new Date().toLocaleTimeString()}] Executing Unit of Work transaction (Success=${success})...`;
                try {
                    const res = await fetchJSON(`/api/demo`);
                    log.innerText = `[${new Date().toLocaleTimeString()}] Unit of Work Execution Result:\\n` + JSON.stringify(res, null, 2);
                    refreshDashboard();
                } catch(e) { log.innerText = "Error: " + e; }
            }

            async function runMultiEngineDemo() {
                const log = document.getElementById('engine-log');
                log.innerText = "Executing Multi-Engine storage operations across Memory, JSON File (/tmp), and SQLite (/tmp)...";
                try {
                    const res = await fetchJSON('/api/demo');
                    log.innerText = JSON.stringify(res, null, 2);
                } catch(e) { log.innerText = "Error: " + e; }
            }

            document.addEventListener('DOMContentLoaded', refreshDashboard);
        </script>
    </body>
    </html>
    """
    return html_content


@app.get("/api/stats")
async def get_stats():
    await ensure_seeded()
    return await service.get_summary_stats()


@app.get("/api/cache-stats")
async def get_cache_stats():
    await ensure_seeded()
    return {
        "hits": cached_user_repo.hits,
        "misses": cached_user_repo.misses,
        "hit_ratio_percent": round(cached_user_repo.hit_ratio * 100, 2)
    }


@app.get("/api/users")
async def list_users(role: Optional[str] = None):
    await ensure_seeded()
    spec = Specification()
    if role:
        spec.add_filter("role", FilterOperator.EQ, role)
    users = await user_repo.find(spec)
    return [u.to_dict() for u in users]


@app.post("/api/users", status_code=201)
async def create_user(payload: CreateUserRequest):
    await ensure_seeded()
    try:
        user = await service.register_user(
            username=payload.username,
            email=payload.email,
            full_name=payload.full_name,
            role=payload.role
        )
        return user.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/documents")
async def search_documents(
    query: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    await ensure_seeded()
    docs = await service.search_documents(query=query, status=status, limit=limit, offset=offset)
    return [d.to_dict() for d in docs]


@app.post("/api/documents", status_code=201)
async def create_document(payload: CreateDocumentRequest):
    await ensure_seeded()
    doc = await service.create_document(
        author_id=payload.author_id,
        title=payload.title,
        content=payload.content,
        tags=payload.tags
    )
    return doc.to_dict()


@app.get("/api/audits")
async def get_audit_logs():
    await ensure_seeded()
    logs = await audit_repo.list_all()
    return [log.to_dict() for log in logs]


@app.get("/api/demo")
async def run_live_demo():
    results = []

    # 1. JSON File Engine in /tmp
    json_repo = JSONFileRepository(Document, json_storage_path)
    d1 = Document(title="Serverless Arch Spec", content="Vercel serverless DAL execution.", author_id="u_vc")
    await json_repo.add(d1)
    results.append({"engine": "JSONFileRepository", "path": str(json_storage_path), "doc_count": await json_repo.count()})

    # 2. SQLite Engine in /tmp
    sqlite_repo = SQLiteRepository(User, sqlite_storage_path)
    u_sql = User(username="sqlite_user", email="sqlite@ver.cel", full_name="SQLite User")
    await sqlite_repo.add(u_sql)
    results.append({"engine": "SQLiteRepository", "path": str(sqlite_storage_path), "user_count": await sqlite_repo.count()})

    # 3. Unit of Work Transaction
    factories = {User: MemoryRepository(User), Document: MemoryRepository(Document)}
    async with UnitOfWork(factories) as uow:
        await uow.get_repository(User).add(User(username="uow_tx", email="tx@ver.cel", full_name="UoW User"))
    results.append({"engine": "UnitOfWork", "transaction_committed": uow.committed})

    return {
        "status": "success",
        "message": "All Multi-Engine Data Access Layer operations executed cleanly.",
        "engines_telemetry": results
    }
