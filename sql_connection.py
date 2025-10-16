#%%
from contextlib import closing
from functools import lru_cache
from typing import Any, Optional, Sequence
import pandas as pd
import pymssql
import re

try:
    import streamlit as st
except ModuleNotFoundError:
    st = None


@lru_cache(maxsize=1)
def _default_connection_string() -> str:
    """Fetch the default connection string from Streamlit secrets."""
    connection_string = None

    if st is not None:
        try:
            connection_string = st.secrets["DB_AILAB_CONN"]
        except Exception:
            connection_string = None

    if not connection_string:
        raise RuntimeError(
            "Database connection string not configured. "
            "Define DB_AILAB_CONN via Streamlit secrets (.streamlit/secrets.toml)."
        )

    return connection_string


def _parse_connection_string(connection_string: str) -> dict[str, str]:
    """Parse a semi-colon separated connection string into a normalized dict."""
    settings: dict[str, str] = {}
    for part in connection_string.split(";"):
        if not part.strip() or "=" not in part:
            continue
        key, value = part.split("=", 1)
        normalized_key = key.strip().upper().replace(" ", "")
        settings[normalized_key] = value.strip()
    return settings


def _build_connection_kwargs(connection_string: str) -> dict[str, Any]:
    """Build pymssql kwargs from an ODBC-style connection string."""
    settings = _parse_connection_string(connection_string)

    server = settings.get("SERVER") or settings.get("ADDRESS") or settings.get("HOST")
    database = settings.get("DATABASE") or settings.get("DB")
    user = settings.get("UID") or settings.get("USERID") or settings.get("USER")
    password = settings.get("PWD") or settings.get("PASSWORD")

    if not all([server, database, user, password]):
        raise RuntimeError(
            "DB_AILAB_CONN must include SERVER, DATABASE, UID, and PWD entries for pymssql."
        )

    port = settings.get("PORT")
    if server:
        server = server.strip()
        if server.lower().startswith("tcp:"):
            server = server[4:]
        if "," in server:
            server, inferred_port = server.split(",", 1)
            port = port or inferred_port
        server = server.strip()

    kwargs: dict[str, Any] = {
        "server": server,
        "user": user,
        "password": password,
        "database": database,
    }

    if port:
        try:
            kwargs["port"] = int(port)
        except ValueError:
            raise RuntimeError("PORT in DB_AILAB_CONN must be an integer if provided.") from None

    timeout = settings.get("CONNECTIONTIMEOUT") or settings.get("TIMEOUT")
    if timeout:
        try:
            kwargs["login_timeout"] = int(timeout)
        except ValueError:
            raise RuntimeError("Connection timeout must be numeric.") from None

    return kwargs


def get_connection(connection_str: Optional[str] = None) -> pymssql.Connection:
    """Return a live pymssql connection using the provided connection string."""
    if not connection_str:
        connection_str = _default_connection_string()

    kwargs = _build_connection_kwargs(connection_str)
    return pymssql.connect(**kwargs)


VALID_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _format_identifier(identifier: str) -> str:
    """Format identifier with brackets for SQL Server."""
    if not VALID_IDENTIFIER.match(identifier):
        raise ValueError(f"Invalid identifier: {identifier}")
    return f"[{identifier}]"


def fetch_ticker_reference(schema: Optional[str] = "dbo") -> pd.DataFrame:
    """Fetch the Ticker_Reference table.

    Returns:
        DataFrame with columns: Ticker, Name, Sector, Data_Source, Active
    """
    qualified_table = _format_identifier("Ticker_Reference")
    if schema:
        qualified_table = f"{_format_identifier(schema)}.{qualified_table}"

    query = f"SELECT * FROM {qualified_table}"

    with closing(get_connection()) as conn:
        result = pd.read_sql(query, conn)

    # Clean up string columns
    if not result.empty:
        if 'Name' in result.columns:
            result['Name'] = result['Name'].str.strip()
        if 'Ticker' in result.columns:
            result['Ticker'] = result['Ticker'].str.strip()
        if 'Sector' in result.columns:
            result['Sector'] = result['Sector'].str.strip()

    return result


def fetch_sector_data(sector_name: str, schema: Optional[str] = "dbo") -> pd.DataFrame:
    """Fetch data from a specific sector table.

    Args:
        sector_name: Name of the sector table (e.g., 'Steel', 'Agriculture')
        schema: Database schema (default: 'dbo')

    Returns:
        DataFrame with columns: Ticker, Date, Price
    """
    qualified_table = _format_identifier(sector_name)
    if schema:
        qualified_table = f"{_format_identifier(schema)}.{qualified_table}"

    query = f"SELECT * FROM {qualified_table}"

    with closing(get_connection()) as conn:
        result = pd.read_sql(query, conn)

    # Convert data types
    if not result.empty:
        if 'Date' in result.columns:
            result['Date'] = pd.to_datetime(result['Date'])
        if 'Price' in result.columns:
            result['Price'] = pd.to_numeric(result['Price'], errors='coerce')
        if 'Ticker' in result.columns:
            result['Ticker'] = result['Ticker'].str.strip()

    return result


def fetch_all_commodity_data(
    exclude_sectors: Optional[Sequence[str]] = None,
    start_date: Optional[str] = None,
    schema: Optional[str] = "dbo"
) -> pd.DataFrame:
    """Fetch all commodity data from all sector tables.

    This function replicates the logic from commo.py:
    1. Load Ticker_Reference to get all sectors
    2. Loop through each sector table and load data
    3. Concatenate all data
    4. Add Name column from ticker reference

    Args:
        exclude_sectors: List of sector names to exclude (e.g., ['Textile'])
        start_date: Filter data from this date onwards (YYYY-MM-DD format)
        schema: Database schema (default: 'dbo')

    Returns:
        DataFrame with columns: Ticker, Date, Price, Name, Sector
    """
    # Load ticker reference
    ticker_ref = fetch_ticker_reference(schema=schema)

    # Create ticker to name mapping
    ticker_name_dict = dict(zip(ticker_ref['Ticker'], ticker_ref['Name']))

    # Get unique sectors
    sectors = ticker_ref['Sector'].unique()

    # Filter out excluded sectors
    if exclude_sectors:
        exclude_set = set(s.strip() for s in exclude_sectors)
        sectors = [s for s in sectors if s not in exclude_set]

    # Load data from each sector table
    full_data = []
    for sector_name in sectors:
        try:
            df = fetch_sector_data(sector_name, schema=schema)
            df['Sector'] = sector_name  # Add sector column
            full_data.append(df)
        except Exception as e:
            # Skip sectors that don't have tables (or have errors)
            print(f"Warning: Could not load sector '{sector_name}': {e}")
            continue

    # Concatenate all data
    if not full_data:
        return pd.DataFrame(columns=['Ticker', 'Date', 'Price', 'Name', 'Sector'])

    result = pd.concat(full_data, ignore_index=True)

    # Add Name column from ticker reference
    result['Name'] = result['Ticker'].map(ticker_name_dict)

    # Filter by start date if specified
    if start_date and 'Date' in result.columns:
        result = result[result['Date'] >= start_date]

    return result


def fetch_tables(schema: Optional[str] = None) -> pd.DataFrame:
    """Return a DataFrame of base tables available in the target database."""
    query = (
        "SELECT TABLE_SCHEMA, TABLE_NAME "
        "FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_TYPE = 'BASE TABLE'"
    )
    params = None
    if schema:
        query += " AND TABLE_SCHEMA = %s"
        params = (schema,)

    with closing(get_connection()) as conn:
        tables = pd.read_sql(query, conn, params=params)

    return tables.sort_values(["TABLE_SCHEMA", "TABLE_NAME"]).reset_index(drop=True)


def fetch_top_rows(
    table: str,
    schema: Optional[str] = "dbo",
    limit: Optional[int] = 100
) -> pd.DataFrame:
    """Return up to limit rows for the requested table; pass None for all rows.

    Args:
        table: Table name
        schema: Schema name (default: 'dbo')
        limit: Number of rows to return (None for all rows)

    Returns:
        DataFrame with table contents
    """
    if limit is not None and limit <= 0:
        raise ValueError("limit must be a positive integer or None")

    qualified_table = _format_identifier(table)
    if schema:
        qualified_table = f"{_format_identifier(schema)}.{qualified_table}"

    if limit is None:
        query = f"SELECT * FROM {qualified_table}"
    else:
        query = f"SELECT TOP {limit} * FROM {qualified_table}"

    with closing(get_connection()) as conn:
        return pd.read_sql(query, conn)


def fetch_table_columns(table: str, schema: Optional[str] = None) -> pd.DataFrame:
    """Return column metadata for the requested table."""
    params = [table]
    query = (
        "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH, ORDINAL_POSITION "
        "FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_NAME = %s"
    )
    if schema:
        query += " AND TABLE_SCHEMA = %s"
        params.append(schema)

    query += " ORDER BY ORDINAL_POSITION"

    with closing(get_connection()) as conn:
        columns = pd.read_sql(query, conn, params=params)

    return columns.rename(columns={"CHARACTER_MAXIMUM_LENGTH": "MAX_LENGTH"})


def test_connection() -> bool:
    """Test the database connection.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            return True
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False


#%% Test script if run directly
if __name__ == "__main__":
    print("Testing SQL connection...")
    if test_connection():
        print("✓ Connection successful!")

        print("\n--- Fetching ticker reference ---")
        ticker_ref = fetch_ticker_reference()
        print(f"Loaded {len(ticker_ref)} tickers")
        print(f"Sectors: {ticker_ref['Sector'].unique()}")

        print("\n--- Fetching all commodity data ---")
        # Exclude 'Textile' as per commo.py
        full_data = fetch_all_commodity_data(exclude_sectors=['Textile'])
        print(f"Total rows: {len(full_data)}")
        print(f"Date range: {full_data['Date'].min()} to {full_data['Date'].max()}")
        print(f"Unique tickers: {full_data['Ticker'].nunique()}")
        print(f"\nFirst few rows:")
        print(full_data.head())

    else:
        print("✗ Connection failed!")
