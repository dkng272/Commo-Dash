import pandas as pd
import numpy as np
from datetime import datetime

def create_equal_weight_index(df, group_name, base_value=100):
    """
    Creates an equal-weighted index for a commodity group based on daily returns.
    Uses available data on each day, accounting for different starting dates.

    Parameters:
    - df: DataFrame with columns ['Date', 'Ticker', 'Price', 'Group']
    - group_name: Name of the group to create index for
    - base_value: Starting value of the index (default: 100)

    Returns:
    - DataFrame with ['Date', 'Index_Value'] for the group
    """
    # Filter for the group
    group_df = df[df['Group'] == group_name].copy()

    # Remove duplicates, keep last value for each Date-Ticker combination
    group_df = group_df.drop_duplicates(subset=['Date', 'Ticker'], keep='last')

    # Return empty DataFrame if no data
    if len(group_df) == 0:
        return pd.DataFrame(columns=['Date', 'Index_Value'])

    # Pivot to get prices for each ticker by date
    pivot_df = group_df.pivot(index='Date', columns='Ticker', values='Price')

    # Return empty DataFrame if pivot is empty
    if len(pivot_df) == 0:
        return pd.DataFrame(columns=['Date', 'Index_Value'])

    # Calculate daily returns
    returns_df = pivot_df.pct_change(fill_method=None)

    # Equal weight - average returns across available tickers each day
    avg_returns = returns_df.mean(axis=1, skipna=True)

    # Build index starting from base value
    index_values = (1 + avg_returns).cumprod() * base_value
    if len(index_values) > 0:
        index_values.iloc[0] = base_value

    result = pd.DataFrame({
        'Date': index_values.index,
        'Index_Value': index_values.values
    })

    return result

def create_weighted_index(df, group_name, weights_dict, base_value=100):
    """
    Creates a custom-weighted index for a commodity group based on user-defined weights.
    Uses available data on each day, accounting for different starting dates.

    Parameters:
    - df: DataFrame with columns ['Date', 'Ticker', 'Price', 'Group']
    - group_name: Name of the group to create index for
    - weights_dict: Dictionary mapping Ticker names to their weights (e.g., {'Gold': 0.5, 'Silver': 0.5})
    - base_value: Starting value of the index (default: 100)

    Returns:
    - DataFrame with ['Date', 'Index_Value'] for the group
    """
    # Filter for the group
    group_df = df[df['Group'] == group_name].copy()

    # Remove duplicates, keep last value for each Date-Ticker combination
    group_df = group_df.drop_duplicates(subset=['Date', 'Ticker'], keep='last')

    # Pivot to get prices for each ticker by date
    pivot_df = group_df.pivot(index='Date', columns='Ticker', values='Price')

    # Calculate daily returns
    returns_df = pivot_df.pct_change(fill_method=None)

    # Apply weights - normalize by available tickers each day
    weighted_returns = pd.Series(0.0, index=returns_df.index)

    for date in returns_df.index:
        available_tickers = returns_df.loc[date].dropna().index
        available_weights = {t: weights_dict.get(t, 0) for t in available_tickers}
        total_weight = sum(available_weights.values())

        if total_weight > 0:
            normalized_weights = {t: w/total_weight for t, w in available_weights.items()}
            weighted_returns.loc[date] = sum(returns_df.loc[date, t] * normalized_weights[t]
                                             for t in available_tickers if not pd.isna(returns_df.loc[date, t]))

    # Build index starting from base value
    index_values = (1 + weighted_returns).cumprod() * base_value
    index_values.iloc[0] = base_value

    result = pd.DataFrame({
        'Date': index_values.index,
        'Index_Value': index_values.values
    })

    return result

def create_sector_indexes(df, base_value=100):
    """
    Create equal-weighted indexes for each Sector by aggregating all groups within that sector

    Parameters:
    - df: DataFrame with columns ['Date', 'Ticker', 'Price', 'Group', 'Sector']
    - base_value: Starting value of the index (default: 100)

    Returns:
    - Dictionary with sector names as keys and index DataFrames as values
    """
    sector_indexes = {}

    # Get unique sectors
    sectors = df['Sector'].dropna().unique()

    for sector in sectors:
        # Filter for this sector
        sector_df = df[df['Sector'] == sector].copy()
        sector_df = sector_df.drop_duplicates(subset=['Date', 'Ticker'], keep='last')

        # Skip if no data
        if len(sector_df) == 0:
            continue

        # Pivot to get prices for each ticker by date
        pivot_df = sector_df.pivot(index='Date', columns='Ticker', values='Price')

        # Calculate daily returns
        returns_df = pivot_df.pct_change(fill_method=None)

        # Equal weight - average returns across available tickers each day
        avg_returns = returns_df.mean(axis=1, skipna=True)

        # Build index starting from base value
        index_values = (1 + avg_returns).cumprod() * base_value
        index_values.iloc[0] = base_value

        sector_indexes[sector] = pd.DataFrame({
            'Date': index_values.index,
            'Index_Value': index_values.values
        })

    return sector_indexes

def create_regional_indexes(df, base_value=100):
    """
    Create equal-weighted indexes for each Group-Region combination

    Parameters:
    - df: DataFrame with columns ['Date', 'Ticker', 'Price', 'Group', 'Region']
    - base_value: Starting value of the index (default: 100)

    Returns:
    - Dictionary with keys as 'Group - Region' and values as index DataFrames
    """
    regional_indexes = {}

    # Get unique Group-Region combinations
    group_region_combos = df[['Group', 'Region']].drop_duplicates()
    group_region_combos = group_region_combos[~group_region_combos['Region'].isna()]

    for _, row in group_region_combos.iterrows():
        group = row['Group']
        region = row['Region']
        key = f"{group} - {region}"

        # Filter for this group-region combination
        region_df = df[(df['Group'] == group) & (df['Region'] == region)].copy()
        region_df = region_df.drop_duplicates(subset=['Date', 'Ticker'], keep='last')

        # Skip if no data
        if len(region_df) == 0:
            continue

        # For Crack Spread, use average absolute value
        if group == 'Crack Spread':
            pivot_df = region_df.pivot(index='Date', columns='Ticker', values='Price')
            avg_values = pivot_df.abs().mean(axis=1)
            regional_indexes[key] = pd.DataFrame({
                'Date': avg_values.index,
                'Index_Value': avg_values.values
            })
        else:
            # Create equal-weight index
            pivot_df = region_df.pivot(index='Date', columns='Ticker', values='Price')
            returns_df = pivot_df.pct_change(fill_method=None)
            avg_returns = returns_df.mean(axis=1, skipna=True)
            index_values = (1 + avg_returns).cumprod() * base_value
            index_values.iloc[0] = base_value
            regional_indexes[key] = pd.DataFrame({
                'Date': index_values.index,
                'Index_Value': index_values.values
            })

    return regional_indexes

def load_latest_news(group_name):
    """
    Load the latest news for a specific commodity group from MongoDB

    Parameters:
    - group_name: Name of the commodity group

    Returns:
    - List of dict with 'date', 'report_file', and 'news' for the group
    """
    try:
        from mongodb_utils import load_reports
        reports = load_reports()

        # Extract news for this commodity group
        news_items = []
        for report in reports:
            commodity_news = report.get('commodity_news', {})
            group_news = commodity_news.get(group_name, "")

            if group_news and group_news.strip():
                news_items.append({
                    'date': report.get('report_date', 'Unknown'),
                    'report_file': report.get('report_file', ''),
                    'news': group_news
                })

        return news_items

    except Exception as e:
        print(f"Error loading news: {e}")
        return []

def get_all_news_summary(limit=5):
    """
    Get a summary of all recent news across all commodity groups from MongoDB

    Parameters:
    - limit: Maximum number of reports to return (default: 5)

    Returns:
    - List of recent reports (limited by limit parameter)
    """
    try:
        from mongodb_utils import load_reports
        reports = load_reports()

        # Return limited number of reports (already sorted newest first)
        return reports[:limit]

    except Exception as e:
        print(f"Error loading news summary: {e}")
        return []
