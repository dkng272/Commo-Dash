#%%
import pyodbc
import pandas as pd
import re
from pathlib import Path
import platform
from typing import Optional, Sequence

# Helper functions
def get_base_path():
    if platform.system() == 'Windows':
        return Path("G:/My Drive/Python")
    else:
        return Path("/Users/duynguyen/Library/CloudStorage/GoogleDrive-nkduy96@gmail.com/My Drive/Python")

# Connection string
DB_AILAB_STR = "DRIVER={ODBC Driver 18 for SQL Server};SERVER=tcp:dcdwhprod.database.windows.net,1433;DATABASE=dclab;UID=dclab_readonly;PWD=DHS#@vGESADdf!;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"


VALID_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _format_identifier(identifier: str) -> str:
    if not VALID_IDENTIFIER.match(identifier):
        raise ValueError(f"Invalid identifier: {identifier}")
    return f"[{identifier}]"


def _normalize_str_sequence(values: Sequence[str], name: str) -> list[str]:
    """Normalize a sequence of string-like values, removing empties and duplicates."""
    if values is None:
        raise ValueError(f"{name} cannot be None")

    cleaned = []
    for value in values:
        text = str(value).strip()
        if text:
            cleaned.append(text)

    if not cleaned:
        raise ValueError(f"{name} must contain at least one non-empty string")

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(cleaned))


def _normalize_date(value: object, name: str) -> str:
    """Return a YYYY-MM-DD string for a provided date-like value."""
    if isinstance(value, (datetime, date)):
        return value.strftime('%Y-%m-%d')

    text = str(value).strip()
    if not text:
        raise ValueError(f"{name} must contain a valid date value")

    try:
        parsed = pd.to_datetime(text)
    except Exception as exc:
        raise ValueError(f"Could not parse {name} value '{text}' as a date") from exc

    return parsed.strftime('%Y-%m-%d')


def get_connection(connection_str: str = DB_AILAB_STR) -> pyodbc.Connection:
    """Return a live pyodbc connection using the provided connection string."""
    return pyodbc.connect(connection_str)


def fetch_tables(schema: Optional[str] = None) -> pd.DataFrame:
    """Return a DataFrame of base tables available in the target database."""
    query = (
        "SELECT TABLE_SCHEMA, TABLE_NAME "
        "FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_TYPE = 'BASE TABLE'"
    )
    params = None
    if schema:
        query += " AND TABLE_SCHEMA = ?"
        params = (schema,)

    with get_connection() as conn:
        tables = pd.read_sql(query, conn, params=params)

    return tables.sort_values(["TABLE_SCHEMA", "TABLE_NAME"]).reset_index(drop=True)


def print_tables(schema: Optional[str] = None) -> None:
    """Print the list of available tables, optionally filtered by schema."""
    tables = fetch_tables(schema)
    if tables.empty:
        message = "No tables found in the database." if not schema else f"No tables found for schema '{schema}'."
        print(message)
        return

    for _, row in tables.iterrows():
        print(f"{row['TABLE_SCHEMA']}.{row['TABLE_NAME']}")


def fetch_top_rows(table: str, schema: Optional[str] = None, limit: Optional[int] = 100) -> pd.DataFrame:
    """Return up to limit rows for the requested table; pass None for all rows."""
    if limit is not None and limit <= 0:
        raise ValueError("limit must be a positive integer or None")

    qualified_table = _format_identifier(table)
    if schema:
        qualified_table = f"{_format_identifier(schema)}.{qualified_table}"

    if limit is None:
        query = f"SELECT * FROM {qualified_table}"
    else:
        query = f"SELECT TOP {limit} * FROM {qualified_table}"

    with get_connection() as conn:
        return pd.read_sql(query, conn)


def top_rows_dataframe(table: str, schema: Optional[str] = None, limit: Optional[int] = 100) -> pd.DataFrame:
    """Return the top rows from a table as a DataFrame; pass None for no row limit."""
    return fetch_top_rows(table, schema=schema, limit=limit)


def fetch_table_columns(table: str, schema: Optional[str] = None) -> pd.DataFrame:
    """Return column metadata for the requested table."""
    params = [table]
    query = (
        "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH, ORDINAL_POSITION "
        "FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_NAME = ?"
    )
    if schema:
        query += " AND TABLE_SCHEMA = ?"
        params.append(schema)

    query += " ORDER BY ORDINAL_POSITION"

    with get_connection() as conn:
        columns = pd.read_sql(query, conn, params=params)

    return columns.rename(columns={"CHARACTER_MAXIMUM_LENGTH": "MAX_LENGTH"})


def table_columns_dataframe(table: str, schema: Optional[str] = None) -> pd.DataFrame:
    """Convenience wrapper returning column headers and metadata as a DataFrame."""
    return fetch_table_columns(table, schema=schema)


def fetch_fa_quarterly(
    tickers: Sequence[str],
    keycodes: Sequence[str],
    start_year: Optional[int] = None,
    schema: Optional[str] = "dbo",
) -> pd.DataFrame:
    """Return FA_Quarterly rows filtered by tickers, keycodes, and an optional year cutoff."""
    normalized_tickers = _normalize_str_sequence(tickers, "tickers")
    normalized_keycodes = _normalize_str_sequence(keycodes, "keycodes")

    qualified_table = _format_identifier("FA_Quarterly")
    if schema:
        qualified_table = f"{_format_identifier(schema)}.{qualified_table}"

    ticker_placeholders = ",".join("?" for _ in normalized_tickers)
    keycode_placeholders = ",".join("?" for _ in normalized_keycodes)

    clauses = [
        "SELECT KEYCODE, TICKER, DATE, VALUE, YEAR, YoY",
        f"FROM {qualified_table}",
        f"WHERE KEYCODE IN ({keycode_placeholders})",
        f"AND TICKER IN ({ticker_placeholders})",
    ]

    params: list[object] = list(normalized_keycodes) + list(normalized_tickers)

    if start_year is not None:
        clauses.append("AND YEAR >= ?")
        params.append(int(start_year))

    clauses.append("ORDER BY TICKER, KEYCODE, YEAR, DATE")
    query = " ".join(clauses)

    with get_connection() as conn:
        return pd.read_sql(query, conn, params=params)


if __name__ == "__main__":
    print_tables()
    df = top_rows_dataframe('FA_Quarterly','dbo',limit = None)
    df

# %%
