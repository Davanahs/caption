import re

# Technical driver, database, internal query, and credential keywords that must never be exposed in UI
TECHNICAL_ERROR_PATTERNS = [
    r"psycopg2",
    r"ProgrammingError",
    r"OperationalError",
    r"DataError",
    r"IntegrityError",
    r"InternalError",
    r"DatabaseError",
    r"InterfaceError",
    r"sqlalchemy",
    r"\[SQL:",
    r"can\'t adapt type",
    r"Traceback \(most recent call last\)",
    r"SELECT\s+.*\s+FROM",
    r"INSERT\s+INTO",
    r"UPDATE\s+.*\s+SET",
    r"DELETE\s+FROM",
    r"password=",
    r"secret=",
    r"token=",
    r"connection refused",
    r"ConnectionRefusedError",
]

COMPILED_TECH_PATTERNS = re.compile("|".join(TECHNICAL_ERROR_PATTERNS), re.IGNORECASE)

DEFAULT_SANITIZED_ERROR = "Processing failed. See server logs for diagnostic details."


def sanitize_user_facing_error(
    err_msg: str | None,
    default_msg: str = DEFAULT_SANITIZED_ERROR
) -> str | None:
    """
    Sanitize backend error messages before returning them to client/UI interfaces.
    
    1. Preserves safe, actionable application-level errors (e.g. duration limit exceedances,
       private video rejection, user cancellations).
    2. Completely masks technical driver exceptions (psycopg2, sqlalchemy, raw SQL queries,
       parameter dumps, internal stack traces, DB connection errors) with a clean diagnostic notice.
    3. Truncates overly long messages to prevent UI layout distortion.
    """
    if not err_msg or not isinstance(err_msg, str):
        return None

    trimmed = err_msg.strip()
    if not trimmed:
        return None

    # Check if the error message contains any raw database/driver/system technical strings
    if COMPILED_TECH_PATTERNS.search(trimmed):
        return default_msg

    # If message contains [SQL:, strip it and re-check
    if "[SQL:" in trimmed:
        trimmed = trimmed.split("[SQL:")[0].strip()
        if not trimmed or COMPILED_TECH_PATTERNS.search(trimmed):
            return default_msg

    # Keep useful, safe application-level errors
    # Limit user-facing string length to 300 chars to prevent layout distortion
    if len(trimmed) > 300:
        trimmed = trimmed[:297] + "..."

    return trimmed
