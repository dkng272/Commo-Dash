#%%
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
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

def calculate_custom_ticker_correlations(ticker, df, all_indexes, regional_indexes, correlation_type='price'):
    """
    Calculate correlation between a custom stock ticker and all commodity indexes.

    Parameters:
    - ticker: Stock ticker symbol
    - df: Main dataframe
    - all_indexes: Group-level indexes
    - regional_indexes: Regional indexes
    - correlation_type: 'price' or 'return'

    Returns: Tuple of (correlations dict, stock_data DataFrame)
    """
    stock_data = fetch_historical_price(ticker, start_date=GLOBAL_START_DATE)

    if stock_data is None or stock_data.empty:
        return {}, None

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

    return correlations, stock_data

# Load data
df = load_data()
all_indexes, regional_indexes = build_indexes(df)

st.title('Custom Ticker Correlation Analysis')

st.write("""
Test any stock ticker against our commodity indexes to discover potential correlations.
Enter a ticker symbol and click **Run Analysis** to see how it correlates with commodity prices.
""")

# Input section
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    custom_ticker = st.text_input('Enter Stock Ticker (e.g., HPG, VNM, AAA)', value='', max_chars=10).upper()

with col2:
    correlation_type = st.radio('Correlation Type', options=['Price Level', 'Daily Returns'], index=1, horizontal=True)

with col3:
    st.write('')  # Spacer
    st.write('')  # Spacer
    run_analysis = st.button('Run Analysis', type='primary', use_container_width=True)

# Run analysis when button is clicked
if run_analysis and custom_ticker:
    with st.spinner(f'Fetching data and calculating correlations for {custom_ticker}...'):
        corr_type_param = 'return' if correlation_type == 'Daily Returns' else 'price'

        correlations, stock_data = calculate_custom_ticker_correlations(
            custom_ticker, df, all_indexes, regional_indexes, correlation_type=corr_type_param
        )

        if correlations and stock_data is not None:
            st.success(f'Analysis complete for {custom_ticker}!')

            st.subheader(f'{custom_ticker} - {correlation_type} Correlations')

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

            # Stock price chart
            st.divider()
            st.subheader(f'{custom_ticker} Stock Price (Since {GLOBAL_START_DATE})')

            stock_plot = stock_data.copy()
            stock_plot['Date'] = pd.to_datetime(stock_plot['Date']).dt.tz_localize(None)
            stock_plot = stock_plot.sort_values('Date')
            stock_plot['Normalized'] = (stock_plot['Price'] / stock_plot['Price'].iloc[0]) * 100

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=stock_plot['Date'],
                y=stock_plot['Normalized'],
                mode='lines',
                name=custom_ticker,
                line=dict(color='black', width=2)
            ))

            fig.update_layout(
                xaxis_title='Date',
                yaxis_title='Normalized Price (Base = 100)',
                hovermode='x unified',
                template='plotly_white',
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)

            # Detailed breakdown - all regional indexes
            st.divider()
            st.subheader('All Regional Index Correlations')

            st.dataframe(corr_df.style.format({'Correlation': '{:.3f}'}).background_gradient(
                subset=['Correlation'], cmap='RdYlGn', vmin=-1, vmax=1
            ), hide_index=True, use_container_width=True)

        elif stock_data is None:
            st.error(f'❌ Could not fetch stock price data for **{custom_ticker}**. Please check the ticker symbol and try again.')
        else:
            st.warning(f'⚠️ No correlations calculated for {custom_ticker}. The stock may not have overlapping data with our commodity indexes.')

elif run_analysis and not custom_ticker:
    st.warning('Please enter a stock ticker symbol.')

else:
    st.info('👆 Enter a stock ticker above and click **Run Analysis** to get started.')
