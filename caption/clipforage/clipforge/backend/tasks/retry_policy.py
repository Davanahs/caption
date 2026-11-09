from requests.exceptions import RequestException
from urllib3.exceptions import TimeoutError as Urllib3TimeoutError
from sqlalchemy.exc import OperationalError
from redis.exceptions import ConnectionError as RedisConnectionError

# A well-defined list of exceptions that represent transient failures 
# suitable for an automatic Celery retry.
# Do NOT include logic errors like ValueError, KeyError, or TypeError here.
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    RequestException,
    Urllib3TimeoutError,
    OperationalError,
    RedisConnectionError,
)

# A predefined dict of kwargs to spread into @celery_app.task() for tasks 
# that perform network/database I/O.
DEFAULT_RETRY_KWARGS = {
    "autoretry_for": RETRYABLE_EXCEPTIONS,
    "max_retries": 3,
    "retry_backoff": True,  # Exponential backoff
    "retry_jitter": True,   # Add jitter to prevent thundering herd
}
