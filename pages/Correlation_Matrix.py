#%%
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import sys
import os

# Get the parent directory path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)
from commo_dashboard import create_equal_weight_index, create_regional_indexes
from ssi_api import fetch_historical_price

# Global start date for all data
GLOBAL_START_DATE = '2024-01-01'

# Load data
@st.cache_data
def load_data():
    data_path = os.path.join(parent_dir, 'data', 'cleaned_data.csv')
    df = pd.read_csv(data_path)
    df['Date'] = pd.to_datetime(df['Date'])
    # Filter to global start date
    df = df[df['Date'] >= GLOBAL_START_DATE]
    return df

@st.cache_data
def load_ticker_mapping():
    mapping_path = os.path.join(parent_dir, 'ticker_mappings_final.json')
    with open(mapping_path, 'r') as f:
        return json.load(f)

@st.cache_data
def build_indexes(df):
    """Build both group-level and regional indexes"""
    all_groups = df['Group'].unique()
    all_indexes = {}

    for group in all_groups:
        if group not in ['Pangaseus', 'Crack Spread']:
            all_indexes[group] = create_equal_weight_index(df, group)

    # Handle Crack Spread separately
    crack_spread_df = df[df['Group'] == 'Crack Spread'].copy()
    if len(crack_spread_df) > 0:
        crack_spread_df = crack_spread_df.drop_duplicates(subset=['Date', 'Ticker'], keep='last')
        crack_pivot = crack_spread_df.pivot(index='Date', columns='Ticker', values='Price')
        crack_avg = crack_pivot.abs().mean(axis=1)
        all_indexes['Crack Spread'] = pd.DataFrame({
            'Date': crack_avg.index,
            'Index_Value': crack_avg.values
        })

    # Regional indexes
    regional_indexes = create_regional_indexes(df)

    return all_indexes, regional_indexes

def calculate_stock_vs_indexes_correlation(ticker, df, all_indexes, regional_indexes, correlation_type='price'):
    """
    Calculate correlation between a stock and all commodity indexes.

    Parameters:
    - ticker: Stock ticker symbol
    - df: Main dataframe
    - all_indexes: Group-level indexes
    - regional_indexes: Regional indexes
    - correlation_type: 'price' or 'return'

    Returns: Dictionary with index names as keys and correlation values as values
    """
    stock_data = fetch_historical_price(ticker, start_date=GLOBAL_START_DATE)

    if stock_data is None or stock_data.empty:
        return {}

    stock_df = stock_data[['Date', 'Price']].copy()
    stock_df['Date'] = pd.to_datetime(stock_df['Date']).dt.tz_localize(None)
    stock_df = stock_df.rename(columns={'Price': 'Stock_Price'})

    correlations = {}

    # Calculate correlations with regional indexes only
    for region_name, index_data in regional_indexes.items():
        index_df = index_data.copy()
        index_df['Date'] = pd.to_datetime(index_df['Date']).dt.tz_localize(None)
        index_df = index_df.rename(columns={'Index_Value': 'Index_Price'})

        merged = pd.merge(stock_df, index_df[['Date', 'Index_Price']], on='Date', how='inner')

        if len(merged) > 1:
            if correlation_type == 'return':
                merged['Stock_Return'] = merged['Stock_Price'].pct_change(fill_method=None)
                merged['Index_Return'] = merged['Index_Price'].pct_change(fill_method=None)
                corr = merged['Stock_Return'].corr(merged['Index_Return'])
            else:
                corr = merged['Stock_Price'].corr(merged['Index_Price'])

            correlations[region_name] = corr

    return correlations

# Load data
df = load_data()
ticker_mapping = load_ticker_mapping()
all_indexes, regional_indexes = build_indexes(df)

# Get all tickers
all_tickers = sorted([item['ticker'] for item in ticker_mapping])

st.title('Stock vs Commodity Index Correlation Matrix')

# Sidebar controls
st.sidebar.header('Settings')
selected_ticker = st.sidebar.selectbox('Select Stock Ticker', options=all_tickers)
correlation_type = st.sidebar.radio('Correlation Type', options=['Price Level', 'Daily Returns'], index=1)

corr_type_param = 'return' if correlation_type == 'Daily Returns' else 'price'

# Calculate correlations
correlations = calculate_stock_vs_indexes_correlation(
    selected_ticker, df, all_indexes, regional_indexes, correlation_type=corr_type_param
)

if correlations:
    st.subheader(f'{selected_ticker} - {correlation_type} Correlations')

    # Create correlation dataframe (all regional indexes)
    corr_data = []
    for name, corr in correlations.items():
        corr_data.append({'Regional Index': name, 'Correlation': corr})

    corr_df = pd.DataFrame(corr_data).sort_values('Correlation', ascending=False)

    # Display top positive and negative correlations
    col1, col2 = st.columns(2)

    with col1:
        st.write('**Top 5 Positive Correlations**')
        top_positive = corr_df.nlargest(5, 'Correlation')
        st.dataframe(top_positive.style.format({'Correlation': '{:.3f}'}).background_gradient(
            subset=['Correlation'], cmap='RdYlGn', vmin=-1, vmax=1
        ), hide_index=True)

    with col2:
        st.write('**Top 5 Negative Correlations**')
        top_negative = corr_df.nsmallest(5, 'Correlation')
        st.dataframe(top_negative.style.format({'Correlation': '{:.3f}'}).background_gradient(
            subset=['Correlation'], cmap='RdYlGn', vmin=-1, vmax=1
        ), hide_index=True)

    # All regional correlations
    st.divider()
    st.subheader('All Regional Index Correlations')

    st.dataframe(corr_df.style.format({'Correlation': '{:.3f}'}).background_gradient(
        subset=['Correlation'], cmap='RdYlGn', vmin=-1, vmax=1
    ), hide_index=True, use_container_width=True)

else:
    st.error(f'No stock price data available for {selected_ticker}')
