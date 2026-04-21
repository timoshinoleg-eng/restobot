# shared/sql_utils.py
"""Safe SQL query formatter with schema name validation."""

import re

SCHEMA_NAME_PATTERN: re.Pattern[str] = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,62}$")


def format_sql(template: str, *schemas: str) -> str:
    """Format SQL template with validated schema name(s).

    Args:
        template: SQL template with '{}' placeholders for schemas.
        schemas: One or more tenant schema names (validated against whitelist).

    Returns:
        Formatted SQL string.

    Raises:
        ValueError: If any schema name contains invalid characters.
    """
    for schema in schemas:
        if not SCHEMA_NAME_PATTERN.match(schema):
            raise ValueError(f"Invalid schema name: {schema}")
    return template.format(*schemas)
