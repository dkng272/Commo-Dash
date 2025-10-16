#%%
from contextlib import closing
from functools import lru_cache
from typing import Any, Optional, Sequence
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import pymssql
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
    schema: Optional[str] = "dbo",
    parallel: bool = True,
    max_workers: int = 5
) -> pd.DataFrame:
    """Fetch all commodity data from all sector tables.

    This function replicates the logic from commo.py:
    1. Load Ticker_Reference to get all sectors
    2. Loop through each sector table and load data (parallel or sequential)
    3. Concatenate all data
    4. Add Name column from ticker reference

    Args:
        exclude_sectors: List of sector names to exclude (e.g., ['Textile'])
        start_date: Filter data from this date onwards (YYYY-MM-DD format)
        schema: Database schema (default: 'dbo')
        parallel: Use parallel loading for faster performance (default: True)
        max_workers: Max threads for parallel loading (default: 5)

    Returns:
        DataFrame with columns: Ticker, Date, Price, Name, Sector
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
    parallel: bool = True,
    max_workers: int = 5
) -> pd.DataFrame:
    """Implementation of fetch_all_commodity_data."""
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
    failed_sectors = []

    if parallel:
        # Parallel loading (faster - ~10-15s instead of 30s)
        def load_sector(sector_name):
            try:
                df = fetch_sector_data(sector_name, schema=schema)
                df['Sector'] = sector_name
                return df, None
            except Exception as e:
                return None, (sector_name, str(e))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(load_sector, sector) for sector in sectors]

            for future in futures:
                df, error = future.result()
                if df is not None:
                    full_data.append(df)
                elif error:
                    sector_name, error_msg = error
                    failed_sectors.append((sector_name, error_msg))
                    print(f"Warning: Could not load sector '{sector_name}': {error_msg}")
    else:
        # Sequential loading (original approach)
        for sector_name in sectors:
            try:
                df = fetch_sector_data(sector_name, schema=schema)
                df['Sector'] = sector_name
                full_data.append(df)
            except Exception as e:
                failed_sectors.append((sector_name, str(e)))
                print(f"Warning: Could not load sector '{sector_name}': {e}")
                continue

    # Log summary
    print(f"Loaded {len(full_data)} sectors successfully")
    if failed_sectors:
        print(f"Failed to load {len(failed_sectors)} sectors: {[s[0] for s in failed_sectors]}")

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


def fetch_specific_sectors(
    sector_names: Sequence[str],
    start_date: Optional[str] = None,
    schema: Optional[str] = "dbo"
) -> pd.DataFrame:
    """Fetch data from specific sectors only (faster than loading all).

    Useful for pages that only need 1-2 sectors.

    Args:
        sector_names: List of sector names to load (e.g., ['Steel', 'Agriculture'])
        start_date: Filter data from this date onwards (YYYY-MM-DD format)
        schema: Database schema (default: 'dbo')

    Returns:
        DataFrame with columns: Ticker, Date, Price, Name, Sector
    """
    # Load ticker reference for name mapping
    ticker_ref = fetch_ticker_reference(schema=schema)
    ticker_name_dict = dict(zip(ticker_ref['Ticker'], ticker_ref['Name']))

    # Load specified sectors
    full_data = []
    for sector_name in sector_names:
        try:
            df = fetch_sector_data(sector_name, schema=schema)
            df['Sector'] = sector_name
            full_data.append(df)
        except Exception as e:
            print(f"Warning: Could not load sector '{sector_name}': {e}")
            continue

    # Concatenate all data
    if not full_data:
        return pd.DataFrame(columns=['Ticker', 'Date', 'Price', 'Name', 'Sector'])

    result = pd.concat(full_data, ignore_index=True)

    # Add Name column
    result['Name'] = result['Ticker'].map(ticker_name_dict)

    # Filter by start date if specified
    if start_date and 'Date' in result.columns:
        result = result[result['Date'] >= start_date]

    return result
