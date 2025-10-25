#%%
import pandas as pd
import streamlit as st

def load_classification():
    """
    Load commodity classification from MongoDB.
    Returns dictionaries for Group, Region, and Sector mappings.
    """
    from mongodb_utils import load_commodity_classifications
    classifications = load_commodity_classifications()

    # Convert list of dicts to DataFrame
    classification = pd.DataFrame(classifications)

    # Ensure Item column exists and is stripped
    if 'item' in classification.columns:
        classification.rename(columns={'item': 'Item'}, inplace=True)
    classification['Item'] = classification['Item'].str.strip()

    # Capitalize column names if needed
    for col in ['sector', 'group', 'region']:
        if col in classification.columns:
            classification.rename(columns={col: col.capitalize()}, inplace=True)

    group_map = classification.set_index('Item')['Group'].to_dict()
    region_map = classification.set_index('Item')['Region'].to_dict()
    sector_map = classification.set_index('Item')['Sector'].to_dict()

    return group_map, region_map, sector_map


def get_classification_df():
    """
    Load and return the classification DataFrame directly from MongoDB.
    Returns: DataFrame with Sector, Group, Region, Item columns.
    """
    from mongodb_utils import load_commodity_classifications
    classifications = load_commodity_classifications()

    # Convert list of dicts to DataFrame
    classification = pd.DataFrame(classifications)

    # Ensure Item column exists and is stripped
    if 'item' in classification.columns:
        classification.rename(columns={'item': 'Item'}, inplace=True)
    classification['Item'] = classification['Item'].str.strip()

    # Capitalize column names if needed
    for col in ['sector', 'group', 'region']:
        if col in classification.columns:
            classification.rename(columns={col: col.capitalize()}, inplace=True)

    return classification

def apply_classification(df):
    """
    Apply classification to a dataframe with a 'Ticker' or 'Name' column.
    Uses 'Name' column if available (from SQL), otherwise falls back to 'Ticker'.
    Returns dataframe with Group, Region, and Sector columns added.
    """
    group_map, region_map, sector_map = load_classification()

    df = df.copy()

    # Use 'Name' column if it exists (from SQL), otherwise use 'Ticker' (legacy CSV)
    mapping_column = 'Name' if 'Name' in df.columns else 'Ticker'

    df['Group'] = df[mapping_column].map(group_map)
    df['Region'] = df[mapping_column].map(region_map)
    df['Sector'] = df[mapping_column].map(sector_map)

    return df



@st.cache_data(ttl=21600)  # 6 hours - GLOBAL cache shared across all pages
def load_raw_sql_data_cached(start_date=None):
    """
    Load RAW commodity price data from SQL Server (cached 6 hours GLOBALLY).

    ⚠️ IMPORTANT: This function is cached ONCE and shared across ALL pages in the app.
    Date filtering should happen AFTER this call (in-memory filtering is fast).

    This is the SINGLE source of truth for SQL data loading. All pages should use this
    function instead of defining their own cached loaders.

    Args:
        start_date: Optional start date filter (YYYY-MM-DD format).
                   Default None fetches all available data.
                   Recommended: Use None and filter in-memory for maximum cache reusability.

    Returns:
        DataFrame with columns: Ticker, Date, Price, Name (NO Sector/Group/Region classifications)
    """
    from sql_connection import fetch_all_commodity_data

    # Fetch all commodity data from SQL (expensive operation - cached 6 hours)
    df = fetch_all_commodity_data(start_date=start_date, parallel=True)

    # Drop classification columns if they somehow exist
    cols_to_drop = [col for col in ['Group', 'Region', 'Sector'] if col in df.columns]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)

    return df


