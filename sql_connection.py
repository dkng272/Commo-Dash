#%%
from contextlib import closing
from functools import lru_cache
from typing import Any, Optional, Sequence
import pandas as pd
import pyodbc
import re

try:
    import streamlit as st
except ModuleNotFoundError:
    st = None


#%% Connection Management

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


def get_connection(connection_str: Optional[str] = None) -> pyodbc.Connection:
    """Return a live pyodbc connection using the ODBC connection string."""
    if not connection_str:
        connection_str = _default_connection_string()

    return pyodbc.connect(connection_str)


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


#%% Helper Functions

VALID_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _format_identifier(identifier: str) -> str:
    """Format identifier with brackets for SQL Server."""
    if not VALID_IDENTIFIER.match(identifier):
        raise ValueError(f"Invalid identifier: {identifier}")
    return f"[{identifier}]"


#%% Core Data Fetching Functions

def fetch_ticker_reference(schema: Optional[str] = "dbo") -> pd.DataFrame:
    """Fetch the Ticker_Reference table.

    Returns:
        DataFrame with columns: Ticker, Name, Sector, Data_Source, Active
    """
    if st is not None:
        return _cached_fetch_ticker_reference(schema)
    else:
        return _fetch_ticker_reference_impl(schema)


def _cached_fetch_ticker_reference(schema: Optional[str] = "dbo") -> pd.DataFrame:
    """Cached version for Streamlit (1 hour TTL)."""
    return _fetch_ticker_reference_impl(schema)

# Apply caching decorator if Streamlit is available
if st is not None:
    _cached_fetch_ticker_reference = st.cache_data(ttl=3600)(_cached_fetch_ticker_reference)


def _fetch_ticker_reference_impl(schema: Optional[str] = "dbo") -> pd.DataFrame:
    """Implementation of fetch_ticker_reference."""
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


def fetch_commodity_data(
    sector_filter: Optional[str] = None,
    start_date: Optional[str] = None,
    schema: Optional[str] = "dbo"
) -> pd.DataFrame:
    """Fetch data from the centralized Commodity table.

    Args:
        sector_filter: Optional sector to filter (e.g., 'Steel', 'Metals')
        start_date: Filter data from this date onwards (YYYY-MM-DD format)
        schema: Database schema (default: 'dbo')

    Returns:
        DataFrame with columns: Ticker, Sector, Date, Price
    """
    qualified_table = _format_identifier("Commodity")
    if schema:
        qualified_table = f"{_format_identifier(schema)}.{qualified_table}"

    # Build query with optional filters
    query = f"SELECT * FROM {qualified_table}"
    where_clauses = []

    if sector_filter:
        where_clauses.append(f"Sector = '{sector_filter}'")
    if start_date:
        where_clauses.append(f"Date >= '{start_date}'")

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

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
        if 'Sector' in result.columns:
            result['Sector'] = result['Sector'].str.strip()

    return result


def fetch_all_commodity_data(
    exclude_sectors: Optional[Sequence[str]] = None,
    start_date: Optional[str] = None,
    schema: Optional[str] = "dbo",
    parallel: bool = True,  # Kept for API compatibility, no longer used
    max_workers: int = 5    # Kept for API compatibility, no longer used
) -> pd.DataFrame:
    """Fetch all commodity data from the centralized Commodity table.

    Simplified version that queries the single Commodity table instead of
    looping through multiple sector tables. Much faster and simpler!

    Args:
        exclude_sectors: List of sector names to exclude (e.g., ['Textile'])
        start_date: Filter data from this date onwards (YYYY-MM-DD format)
        schema: Database schema (default: 'dbo')
        parallel: Deprecated - kept for API compatibility
        max_workers: Deprecated - kept for API compatibility

    Returns:
        DataFrame with columns: Ticker, Sector, Date, Price, Name
    """
    if st is not None:
        # Convert list to tuple for caching (lists are not hashable)
        exclude_tuple = tuple(exclude_sectors) if exclude_sectors else None
        return _cached_fetch_all_commodity_data(exclude_tuple, start_date, schema, parallel, max_workers)
    else:
        return _fetch_all_commodity_data_impl(exclude_sectors, start_date, schema, parallel, max_workers)


def _cached_fetch_all_commodity_data(
    exclude_sectors: Optional[tuple] = None,
    start_date: Optional[str] = None,
    schema: Optional[str] = "dbo",
    parallel: bool = True,
    max_workers: int = 5
) -> pd.DataFrame:
    """Cached version for Streamlit (1 hour TTL)."""
    # Convert tuple back to list for implementation
    exclude_list = list(exclude_sectors) if exclude_sectors else None
    return _fetch_all_commodity_data_impl(exclude_list, start_date, schema, parallel, max_workers)

# Apply caching decorator if Streamlit is available
if st is not None:
    _cached_fetch_all_commodity_data = st.cache_data(ttl=3600)(_cached_fetch_all_commodity_data)


def _fetch_all_commodity_data_impl(
    exclude_sectors: Optional[Sequence[str]] = None,
    start_date: Optional[str] = None,
    schema: Optional[str] = "dbo",
    parallel: bool = True,  # Kept for API compatibility
    max_workers: int = 5    # Kept for API compatibility
) -> pd.DataFrame:
    """Implementation of fetch_all_commodity_data.

    Simplified version using centralized Commodity table - no more parallel loading needed!
    """
    # Load ticker reference for Name mapping
    ticker_ref = fetch_ticker_reference(schema=schema)

    # Create ticker to name mapping
    ticker_name_dict = dict(zip(ticker_ref['Ticker'], ticker_ref['Name']))

    # Fetch all commodity data from centralized table
    result = fetch_commodity_data(
        sector_filter=None,  # Get all sectors
        start_date=start_date,
        schema=schema
    )

    # Filter out excluded sectors if specified
    if exclude_sectors and not result.empty:
        exclude_set = set(s.strip() for s in exclude_sectors)
        result = result[~result['Sector'].isin(exclude_set)]

    # Add Name column from ticker reference
    if not result.empty:
        result['Name'] = result['Ticker'].map(ticker_name_dict)
    else:
        # Return empty DataFrame with expected columns
        result = pd.DataFrame(columns=['Ticker', 'Sector', 'Date', 'Price', 'Name'])

    print(f"Loaded {len(result)} commodity price records from centralized Commodity table")

    return result


