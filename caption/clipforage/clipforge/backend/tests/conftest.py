"""
pytest configuration for the ClipForge backend test suite.

pytest-asyncio 0.23.x + asyncio_mode=auto:
- All async test functions are automatically treated as asyncio coroutines.
- The module-scoped event_loop fixture below ensures that the disposable_pg_db
  and isolated_storage module-scoped fixtures share a single event loop with
  all async tests in the module, preventing "Future attached to a different loop"
  errors.

NOTE: In pytest-asyncio 0.23.x, overriding event_loop to a broader scope
emits a DeprecationWarning but still works correctly. This is intentional.
"""
import asyncio
import pytest


@pytest.fixture(scope="module")
def event_loop(request):
    """
    Module-scoped event loop shared by all tests in a module.
    Overrides the default function-scoped event_loop provided by
    pytest-asyncio so that module-scoped async fixtures work correctly.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True, scope="module")
async def _cleanup_database_engine(event_loop):
    """
    Ensures the centralized SQLAlchemy async engine connection pool is cleanly
    disposed at the end of each test module before the module event loop is closed.
    This prevents Windows asyncio ProactorEventLoop collision ('NoneType object
    has no attribute send' / 'Event loop is closed') when subsequent test modules
    attempt to reuse stale pooled connections attached to a terminated event loop.
    """
    yield
    try:
        from backend.models.database import engine
        await engine.dispose()
    except Exception:
        pass

