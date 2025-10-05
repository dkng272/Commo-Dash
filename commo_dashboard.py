#%%
import pandas as pd
import numpy as np

#%%
df = pd.read_csv('data/cleaned_data.csv')
df['Date'] = pd.to_datetime(df['Date'])

#%% Equal Weight Index Function
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

    # Pivot to get prices for each ticker by date
    pivot_df = group_df.pivot(index='Date', columns='Ticker', values='Price')

    # Calculate daily returns
    returns_df = pivot_df.pct_change(fill_method=None)

    # Equal weight - average returns across available tickers each day
    avg_returns = returns_df.mean(axis=1, skipna=True)

    # Build index starting from base value
    index_values = (1 + avg_returns).cumprod() * base_value
    index_values.iloc[0] = base_value

    result = pd.DataFrame({
        'Date': index_values.index,
        'Index_Value': index_values.values
    })

    return result

#%% Custom Weight Index Function
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

#%% Create all equal-weight indexes
all_groups = df['Group'].unique()
all_indexes = {}

for group in all_groups:
    if group not in ['Pangaseus', 'Crack Spread']:
        all_indexes[group] = create_equal_weight_index(df, group)

# Handle Crack Spread separately - use average absolute value
crack_spread_df = df[df['Group'] == 'Crack Spread'].copy()
crack_spread_df = crack_spread_df.drop_duplicates(subset=['Date', 'Ticker'], keep='last')
crack_pivot = crack_spread_df.pivot(index='Date', columns='Ticker', values='Price')
crack_avg = crack_pivot.abs().mean(axis=1)
all_indexes['Crack Spread'] = pd.DataFrame({
    'Date': crack_avg.index,
    'Index_Value': crack_avg.values
})

# Combine all indexes into a single dataframe
first_group = list(all_indexes.keys())[0]
combined_df = all_indexes[first_group].copy()
combined_df.rename(columns={'Index_Value': first_group}, inplace=True)

for group in list(all_indexes.keys())[1:]:
    temp_df = all_indexes[group].copy()
    temp_df.rename(columns={'Index_Value': group}, inplace=True)
    combined_df = combined_df.merge(temp_df, on='Date', how='outer')

combined_df = combined_df.sort_values('Date')
combined_df = combined_df.ffill() #front fill to propagate last valid observation
# combined_df = combined_df[combined_df['Date'] >= '2024-01-01'] # remove hog before 1/1/2024

#%% Visualization Function
import plotly.graph_objects as go

def plot_index(group_name, combined_df):
    """
    Plot a single commodity group index

    Parameters:
    - group_name: Name of the group to plot
    - combined_df: DataFrame with all indexes
    """
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=combined_df['Date'],
        y=combined_df[group_name],
        mode='lines',
        name=group_name,
        line=dict(width=2)
    ))

    fig.update_layout(
        title=f'{group_name} Index',
        xaxis_title='Date',
        yaxis_title='Index Value' if group_name != 'Crack Spread' else 'Average Absolute Value',
        hovermode='x unified',
        template='plotly_white',
        height=500
    )

    fig.show()

def plot_all_indexes(combined_df, groups_list):
    """
    Plot all commodity group indices on one chart

    Parameters:
    - combined_df: DataFrame with all indexes
    - groups_list: List of group names to plot
    """
    fig = go.Figure()

    for group in groups_list:
        fig.add_trace(go.Scatter(
            x=combined_df['Date'],
            y=combined_df[group],
            mode='lines',
            name=group
        ))

    fig.update_layout(
        title='Commodity Group Indices (Equal-Weighted)',
        xaxis_title='Date',
        yaxis_title='Index Value (Base = 100)',
        hovermode='x unified',
        template='plotly_white',
        height=600
    )

    fig.show()

#%% Create Regional Sub-Indexes
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

        # Skip Pangaseus
        if group == 'Pangaseus':
            continue

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

# Create regional indexes
regional_indexes = create_regional_indexes(df)

# Combine all regional indexes into a single dataframe
if len(regional_indexes) > 0:
    first_regional = list(regional_indexes.keys())[0]
    regional_combined_df = regional_indexes[first_regional].copy()
    regional_combined_df.rename(columns={'Index_Value': first_regional}, inplace=True)

    for key in list(regional_indexes.keys())[1:]:
        temp_df = regional_indexes[key].copy()
        temp_df.rename(columns={'Index_Value': key}, inplace=True)
        regional_combined_df = regional_combined_df.merge(temp_df, on='Date', how='outer')

    regional_combined_df = regional_combined_df.sort_values('Date')
    regional_combined_df = regional_combined_df.ffill()
else:
    regional_combined_df = pd.DataFrame()

# # Check available regional indexes
# print("Available Regional Indexes:")
# for key in regional_indexes.keys():
#     print(f"  - {key}")

# Example usage
# plot_index('HRC', combined_df)
# plot_all_indexes(combined_df, list(all_indexes.keys()))
# For regional:
# plot_index('HRC - VN', regional_combined_df)