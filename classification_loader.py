#%%
import pandas as pd

def load_classification():
    """
    Load commodity classification from commo_list.xlsx.
    Returns dictionaries for Group, Region, and Sector mappings.
    """
    classification = pd.read_excel('commo_list.xlsx')
    classification['Item'] = classification['Item'].str.strip()

    group_map = classification.set_index('Item')['Group'].to_dict()
    region_map = classification.set_index('Item')['Region'].to_dict()
    sector_map = classification.set_index('Item')['Sector'].to_dict()

    return group_map, region_map, sector_map


def get_classification_df():
    """
    Load and return the classification DataFrame directly.
    Returns: DataFrame with Sector, Group, Region, Item columns.
    """
    classification = pd.read_excel('commo_list.xlsx')
    classification['Item'] = classification['Item'].str.strip()
    return classification

def apply_classification(df):
    """
    Apply classification to a dataframe with a 'Ticker' column.
    Returns dataframe with Group, Region, and Sector columns added.
    """
    group_map, region_map, sector_map = load_classification()

    df = df.copy()
    df['Group'] = df['Ticker'].map(group_map)
    df['Region'] = df['Ticker'].map(region_map)
    df['Sector'] = df['Ticker'].map(sector_map)

    return df

def load_data_with_classification(price_data_path='data/cleaned_data.csv'):
    """
    Load price data and apply latest classification.
    This allows instant classification updates without regenerating price data.
    """
    df = pd.read_csv(price_data_path)
    df['Date'] = pd.to_datetime(df['Date'])

    # If classification columns exist, drop them (we'll reload fresh)
    cols_to_drop = [col for col in ['Group', 'Region', 'Sector'] if col in df.columns]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)

    # Apply fresh classification
    df = apply_classification(df)

    return df


def load_sql_data_with_classification(start_date='2024-01-01'):
    """
    Load price data from SQL Server and apply classification.

    Args:
        start_date: Filter data from this date onwards (YYYY-MM-DD format)

    Returns:
        DataFrame with columns: Ticker, Date, Price, Name, Sector, Group, Region
    """
    from sql_connection import fetch_all_commodity_data

    # Fetch all commodity data from SQL
    df = fetch_all_commodity_data(start_date=start_date, parallel=True)

    # Apply classification (Group, Region, Sector based on Ticker)
    df = apply_classification(df)

    return df
