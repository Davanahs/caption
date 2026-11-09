# Phase 1: PostgreSQL Database Migration & Unified Connection Pool

## 🎯 Goal
Replace the embedded SQLite database (`aiosqlite` + `sqlite3`) with PostgreSQL to eliminate database locks, WAL corruption, and transaction deadlocks in multi-process Celery worker environments.

---

## 🛠️ Implementation Tasks

### 1. PostgreSQL Service & Dependency Setup
- **Target Files:** `docker-compose.yml`, `backend/requirements.txt`, `backend/core/config.py`
- Add `postgres:16-alpine` container service to `docker-compose.yml` with health checks.
- Add `asyncpg` and `psycopg2-binary` to `backend/requirements.txt`.
- Update `backend/core/config.py` to add PostgreSQL database configuration settings:
  ```python
  POSTGRES_USER: str = "clipforge"
  POSTGRES_PASSWORD: str = "clipforge_secret"
  POSTGRES_SERVER: str = "db"
  POSTGRES_PORT: int = 5432
  POSTGRES_DB: str = "clipforge"
  DATABASE_URL: str = "postgresql+asyncpg://clipforge:clipforge_secret@db:5432/clipforge"
  SYNC_DATABASE_URL: str = "postgresql+psycopg2://clipforge:clipforge_secret@db:5432/clipforge"
  ```

### 2. Unified SQLAlchemy Session Factory & Connection Resilience
- **Target Files:** `backend/models/database.py`, `backend/models/db_sync.py`
- Replace raw `aiosqlite` pragmas in `database.py` with resilient SQLAlchemy `create_async_engine`:
  ```python
  engine = create_async_engine(
      settings.DATABASE_URL,
      pool_size=20,
      max_overflow=10,
      pool_pre_ping=True,  # Auto-reconnect broken idle connections
      pool_recycle=3600    # Recycle connections hourly to prevent stale sockets
  )
  AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
  ```
- Refactor `db_sync.py` to use a thread-safe synchronous engine pool (`create_engine(settings.SYNC_DATABASE_URL, pool_pre_ping=True)`) instead of raw `sqlite3.connect()` calls.

### 3. Alembic Database Migration Setup
- **Target Files:** `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/`
- Initialize Alembic migration environment in `backend/alembic`.
- Create initial migration script generating proper indexes for `videos.youtube_id`, `clips.video_id`, and `jobs.status`.

### 4. Data Migration Script from SQLite
- **Target File:** `backend/scripts/migrate_sqlite_to_postgres.py`
- Build a robust migration script that reads existing records from `clipforge.db` and writes them into PostgreSQL, preserving UUIDs, timestamps, and clip foreign keys.

---

## 🧪 Verification & Acceptance Criteria

1. **Concurrent Write Test:** Run 10 parallel Celery pipeline workers writing job status updates simultaneously. Ensure 0 database lock errors occur.
2. **Auto-Reconnect Test:** Simulate database service restart. Verify `pool_pre_ping=True` seamlessly reconnects without raising unhandled 500 errors.
3. **Alembic Test:** Verify `alembic upgrade head` runs cleanly on fresh container startups.
