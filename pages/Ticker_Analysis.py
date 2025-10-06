#%%
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import sys
import os

# Get the parent directory path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)
from commo_dashboard import create_equal_weight_index, create_regional_indexes
from ssi_api import fetch_historical_price

# Global start date for all data on this page
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

def get_index_data(item, group, region, df, all_indexes, regional_indexes):
    """
    Get price data for an item. If item is None/empty or not found, use group or group-region index.

    Returns: tuple of (DataFrame with Date and Price columns, display_name) or (None, None)
    """
    # Try to use specific item data first
    if item and item.strip():
        item_data = df[df['Ticker'] == item].copy()
        if not item_data.empty:
            return item_data[['Date', 'Price']].sort_values('Date'), item
        # If item specified but not found, continue to fallback

    # Fall back to regional index
    if region and region.strip() and region.lower() != 'nan' and region.lower() != 'none':
        key = f"{group} - {region}"
        if key in regional_indexes:
            index_df = regional_indexes[key].copy()
            index_df.rename(columns={'Index_Value': 'Price'}, inplace=True)
            return index_df, f"{group} - {region} Index"
        # If regional index not found, continue to group fallback

    # Fall back to group index
    if group and group in all_indexes:
        index_df = all_indexes[group].copy()
        index_df.rename(columns={'Index_Value': 'Price'}, inplace=True)
        return index_df, f"{group} Index"

    return None, None

def create_aggregated_index(items_list, df, all_indexes, regional_indexes, base_value=100):
    """
    Create an equal-weighted index from multiple items.

    Parameters:
    - items_list: List of item dictionaries with 'item', 'group', 'region'
    - df: Main dataframe
    - all_indexes: Group-level indexes
    - regional_indexes: Regional indexes
    - base_value: Starting value for the index

    Returns: DataFrame with Date and Price columns
    """
    all_prices = []

    for item_info in items_list:
        item_data, display_name = get_index_data(
            item_info['item'],
            item_info['group'],
            item_info['region'],
            df,
            all_indexes,
            regional_indexes
        )

        if item_data is not None and not item_data.empty:
            item_data = item_data.copy()
            item_name = display_name.replace(' Index', '_Index').replace(' - ', '_')
            item_data = item_data.rename(columns={'Price': item_name})
            all_prices.append(item_data.set_index('Date'))

    if not all_prices:
        return None

    # Combine all price series
    combined = pd.concat(all_prices, axis=1)

    # Calculate returns
    returns = combined.pct_change(fill_method=None)

    # Equal-weight average returns
    avg_returns = returns.mean(axis=1, skipna=True)

    # Build index
    index_values = (1 + avg_returns).cumprod() * base_value
    index_values.iloc[0] = base_value

    result = pd.DataFrame({
        'Date': index_values.index,
        'Price': index_values.values
    }).reset_index(drop=True)

    return result

def calculate_correlations(ticker, ticker_data, df, all_indexes, regional_indexes, stock_data):
    """
    Calculate correlations between stock price and commodity inputs/outputs.
    Returns both price-level and returns-based correlations.

    Parameters:
    - ticker: Stock ticker symbol
    - ticker_data: Ticker mapping data with inputs/outputs
    - df: Main dataframe
    - all_indexes: Group-level indexes
    - regional_indexes: Regional indexes
    - stock_data: Stock price DataFrame with Date and Price columns

    Returns: Tuple of (price_correlations, return_correlations) dictionaries
    """
    if stock_data is None or stock_data.empty:
        return {}, {}

    price_correlations = {}
    return_correlations = {}

    stock_df = stock_data[['Date', 'Price']].copy()
    stock_df['Date'] = pd.to_datetime(stock_df['Date']).dt.tz_localize(None)
    stock_df = stock_df.rename(columns={'Price': 'Stock_Price'})

    # Calculate correlations for inputs
    for idx, inp in enumerate(ticker_data.get('inputs', [])):
        item_data, display_name = get_index_data(
            inp['item'], inp['group'], inp['region'],
            df, all_indexes, regional_indexes
        )

        if item_data is not None and not item_data.empty:
            item_data = item_data.copy()
            item_data['Date'] = pd.to_datetime(item_data['Date']).dt.tz_localize(None)
            # Merge on Date
            merged = pd.merge(stock_df, item_data[['Date', 'Price']], on='Date', how='inner')
            if len(merged) > 1:
                # Price level correlation
                price_corr = merged['Stock_Price'].corr(merged['Price'])
                price_correlations[f'Input_{idx}_{display_name}'] = price_corr

                # Returns correlation
                merged['Stock_Return'] = merged['Stock_Price'].pct_change(fill_method=None)
                merged['Commodity_Return'] = merged['Price'].pct_change(fill_method=None)
                return_corr = merged['Stock_Return'].corr(merged['Commodity_Return'])
                return_correlations[f'Input_{idx}_{display_name}'] = return_corr

    # Calculate correlations for outputs
    for idx, out in enumerate(ticker_data.get('outputs', [])):
        item_data, display_name = get_index_data(
            out['item'], out['group'], out['region'],
            df, all_indexes, regional_indexes
        )

        if item_data is not None and not item_data.empty:
            item_data = item_data.copy()
            item_data['Date'] = pd.to_datetime(item_data['Date']).dt.tz_localize(None)
            # Merge on Date
            merged = pd.merge(stock_df, item_data[['Date', 'Price']], on='Date', how='inner')
            if len(merged) > 1:
                # Price level correlation
                price_corr = merged['Stock_Price'].corr(merged['Price'])
                price_correlations[f'Output_{idx}_{display_name}'] = price_corr

                # Returns correlation
                merged['Stock_Return'] = merged['Stock_Price'].pct_change(fill_method=None)
                merged['Commodity_Return'] = merged['Price'].pct_change(fill_method=None)
                return_corr = merged['Stock_Return'].corr(merged['Commodity_Return'])
                return_correlations[f'Output_{idx}_{display_name}'] = return_corr

    return price_correlations, return_correlations

def calculate_ticker_summary(ticker, ticker_data, df, all_indexes, regional_indexes, aggregate_items=False):
    """
    Calculate summary metrics for a ticker's inputs and outputs.

    Parameters:
    - ticker: Stock ticker symbol
    - ticker_data: Ticker mapping data with inputs/outputs
    - df: Main dataframe
    - all_indexes: Group-level indexes
    - regional_indexes: Regional indexes
    - aggregate_items: Whether to aggregate multiple items into index

    Returns: Dictionary with ticker summary metrics
    """
    summary = {'Ticker': ticker}

    # Calculate input metrics - always use aggregated index for multiple inputs
    if ticker_data['inputs']:
        if len(ticker_data['inputs']) > 1:
            input_data = create_aggregated_index(ticker_data['inputs'], df, all_indexes, regional_indexes)
        else:
            # Single input - use directly
            input_data, _ = get_index_data(
                ticker_data['inputs'][0]['item'],
                ticker_data['inputs'][0]['group'],
                ticker_data['inputs'][0]['region'],
                df, all_indexes, regional_indexes
            )

        if input_data is not None and not input_data.empty:
            input_data = input_data.sort_values('Date').reset_index(drop=True)
            latest = input_data['Price'].iloc[-1]
            summary['Input_5D'] = ((latest - input_data['Price'].iloc[-6]) / input_data['Price'].iloc[-6] * 100) if len(input_data) > 5 else None
            summary['Input_10D'] = ((latest - input_data['Price'].iloc[-11]) / input_data['Price'].iloc[-11] * 100) if len(input_data) > 10 else None
            summary['Input_50D'] = ((latest - input_data['Price'].iloc[-51]) / input_data['Price'].iloc[-51] * 100) if len(input_data) > 50 else None
            summary['Input_150D'] = ((latest - input_data['Price'].iloc[-151]) / input_data['Price'].iloc[-151] * 100) if len(input_data) > 150 else None
        else:
            summary['Input_5D'] = summary['Input_10D'] = summary['Input_50D'] = summary['Input_150D'] = None
    else:
        summary['Input_5D'] = summary['Input_10D'] = summary['Input_50D'] = summary['Input_150D'] = None

    # Calculate output metrics - always use aggregated index for multiple outputs
    if ticker_data['outputs']:
        if len(ticker_data['outputs']) > 1:
            output_data = create_aggregated_index(ticker_data['outputs'], df, all_indexes, regional_indexes)
        else:
            # Single output - use directly
            output_data, _ = get_index_data(
                ticker_data['outputs'][0]['item'],
                ticker_data['outputs'][0]['group'],
                ticker_data['outputs'][0]['region'],
                df, all_indexes, regional_indexes
            )

        if output_data is not None and not output_data.empty:
            output_data = output_data.sort_values('Date').reset_index(drop=True)
            latest = output_data['Price'].iloc[-1]
            summary['Output_5D'] = ((latest - output_data['Price'].iloc[-6]) / output_data['Price'].iloc[-6] * 100) if len(output_data) > 5 else None
            summary['Output_10D'] = ((latest - output_data['Price'].iloc[-11]) / output_data['Price'].iloc[-11] * 100) if len(output_data) > 10 else None
            summary['Output_50D'] = ((latest - output_data['Price'].iloc[-51]) / output_data['Price'].iloc[-51] * 100) if len(output_data) > 50 else None
            summary['Output_150D'] = ((latest - output_data['Price'].iloc[-151]) / output_data['Price'].iloc[-151] * 100) if len(output_data) > 150 else None
        else:
            summary['Output_5D'] = summary['Output_10D'] = summary['Output_50D'] = summary['Output_150D'] = None
    else:
        summary['Output_5D'] = summary['Output_10D'] = summary['Output_50D'] = summary['Output_150D'] = None

    return summary

# Load data
df = load_data()
ticker_mapping = load_ticker_mapping()
all_indexes, regional_indexes = build_indexes(df)

# Get all tickers
all_tickers = [item['ticker'] for item in ticker_mapping]

st.title('Ticker Commodity Analysis')

# Sidebar for ticker selection
selected_ticker = st.sidebar.selectbox(
    'Select Stock Ticker',
    options=sorted(all_tickers)
)

# Sidebar option to aggregate multiple items
st.sidebar.divider()
aggregate_items = st.sidebar.checkbox(
    'Aggregate Multiple Items into Index',
    value=False,
    help='When enabled, combines multiple input/output items into an equal-weighted index'
)

# Get ticker data
ticker_data = next((item for item in ticker_mapping if item['ticker'] == selected_ticker), None)

if ticker_data:
    st.header(f'{selected_ticker} - Commodity Relationships')

    # Display summary table at the top
    summary = calculate_ticker_summary(selected_ticker, ticker_data, df, all_indexes, regional_indexes, aggregate_items)

    summary_display = pd.DataFrame({
        'Metric': ['Input', 'Output'],
        '5D %': [summary['Input_5D'], summary['Output_5D']],
        '10D %': [summary['Input_10D'], summary['Output_10D']],
        '50D %': [summary['Input_50D'], summary['Output_50D']],
        '150D %': [summary['Input_150D'], summary['Output_150D']]
    })

    st.subheader('Summary Metrics')
    st.dataframe(summary_display.style.format({
        '5D %': '{:.2f}',
        '10D %': '{:.2f}',
        '50D %': '{:.2f}',
        '150D %': '{:.2f}'
    }, na_rep='-'), hide_index=True)
    st.caption('*Note: For multiple inputs/outputs, metrics are calculated using equal-weighted aggregated index*')
    st.divider()

    # Display inputs
    st.subheader('Input Commodities (Costs)')
    if ticker_data['inputs']:
        input_items = []

        # Check if aggregation is enabled and multiple inputs exist
        if aggregate_items and len(ticker_data['inputs']) > 1:
            aggregated_data = create_aggregated_index(ticker_data['inputs'], df, all_indexes, regional_indexes)
            if aggregated_data is not None and not aggregated_data.empty:
                aggregated_data = aggregated_data.sort_values('Date').reset_index(drop=True)
                latest_price = aggregated_data['Price'].iloc[-1]

                pct_5d = ((latest_price - aggregated_data['Price'].iloc[-6]) / aggregated_data['Price'].iloc[-6] * 100) if len(aggregated_data) > 5 else None
                pct_10d = ((latest_price - aggregated_data['Price'].iloc[-11]) / aggregated_data['Price'].iloc[-11] * 100) if len(aggregated_data) > 10 else None
                pct_50d = ((latest_price - aggregated_data['Price'].iloc[-51]) / aggregated_data['Price'].iloc[-51] * 100) if len(aggregated_data) > 50 else None
                pct_150d = ((latest_price - aggregated_data['Price'].iloc[-151]) / aggregated_data['Price'].iloc[-151] * 100) if len(aggregated_data) > 150 else None

                input_items.append({
                    'Data Source': 'Aggregated Input Index',
                    '5D %': pct_5d,
                    '10D %': pct_10d,
                    '50D %': pct_50d,
                    '150D %': pct_150d
                })
        else:
            for inp in ticker_data['inputs']:
                item_data, actual_name = get_index_data(inp['item'], inp['group'], inp['region'], df, all_indexes, regional_indexes)

                if item_data is not None and not item_data.empty:
                    item_data = item_data.sort_values('Date').reset_index(drop=True)
                    latest_price = item_data['Price'].iloc[-1]

                    pct_5d = ((latest_price - item_data['Price'].iloc[-6]) / item_data['Price'].iloc[-6] * 100) if len(item_data) > 5 else None
                    pct_10d = ((latest_price - item_data['Price'].iloc[-11]) / item_data['Price'].iloc[-11] * 100) if len(item_data) > 10 else None
                    pct_50d = ((latest_price - item_data['Price'].iloc[-51]) / item_data['Price'].iloc[-51] * 100) if len(item_data) > 50 else None
                    pct_150d = ((latest_price - item_data['Price'].iloc[-151]) / item_data['Price'].iloc[-151] * 100) if len(item_data) > 150 else None
                else:
                    pct_5d = pct_10d = pct_50d = pct_150d = None

                input_items.append({
                    'Data Source': actual_name if actual_name else 'N/A',
                    '5D %': pct_5d,
                    '10D %': pct_10d,
                    '50D %': pct_50d,
                    '150D %': pct_150d
                })

        input_df = pd.DataFrame(input_items)
        st.dataframe(input_df.style.format({
            '5D %': '{:.2f}',
            '10D %': '{:.2f}',
            '50D %': '{:.2f}',
            '150D %': '{:.2f}'
        }, na_rep='-'), hide_index=True)

        # Plot input commodities
        st.write("**Input Commodity Prices**")
        fig_inputs = go.Figure()

        if aggregate_items and len(ticker_data['inputs']) > 1:
            # Create aggregated index for all inputs
            aggregated_data = create_aggregated_index(ticker_data['inputs'], df, all_indexes, regional_indexes)
            if aggregated_data is not None and not aggregated_data.empty:
                aggregated_data['Normalized'] = (aggregated_data['Price'] / aggregated_data['Price'].iloc[0]) * 100

                fig_inputs.add_trace(go.Scatter(
                    x=aggregated_data['Date'],
                    y=aggregated_data['Normalized'],
                    mode='lines',
                    name='Aggregated Input Index',
                    line=dict(width=2)
                ))
        else:
            # Show individual items
            for inp in ticker_data['inputs']:
                item_data, display_name = get_index_data(inp['item'], inp['group'], inp['region'], df, all_indexes, regional_indexes)
                if item_data is not None and not item_data.empty:
                    # Normalize to base 100
                    item_data['Normalized'] = (item_data['Price'] / item_data['Price'].iloc[0]) * 100

                    fig_inputs.add_trace(go.Scatter(
                        x=item_data['Date'],
                        y=item_data['Normalized'],
                        mode='lines',
                        name=display_name,
                        line=dict(width=2)
                    ))

        fig_inputs.update_layout(
            xaxis_title='Date',
            yaxis_title='Normalized Price (Base = 100)',
            hovermode='x unified',
            template='plotly_white',
            height=400,
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='center',
                x=0.5,
                font=dict(size=12)
            )
        )
        st.plotly_chart(fig_inputs, use_container_width=True)
    else:
        st.info('No input commodities mapped')

    st.divider()

    # Display outputs
    st.subheader('Output Commodities (Products)')
    if ticker_data['outputs']:
        output_items = []

        # Check if aggregation is enabled and multiple outputs exist
        if aggregate_items and len(ticker_data['outputs']) > 1:
            aggregated_data = create_aggregated_index(ticker_data['outputs'], df, all_indexes, regional_indexes)
            if aggregated_data is not None and not aggregated_data.empty:
                aggregated_data = aggregated_data.sort_values('Date').reset_index(drop=True)
                latest_price = aggregated_data['Price'].iloc[-1]

                pct_5d = ((latest_price - aggregated_data['Price'].iloc[-6]) / aggregated_data['Price'].iloc[-6] * 100) if len(aggregated_data) > 5 else None
                pct_10d = ((latest_price - aggregated_data['Price'].iloc[-11]) / aggregated_data['Price'].iloc[-11] * 100) if len(aggregated_data) > 10 else None
                pct_50d = ((latest_price - aggregated_data['Price'].iloc[-51]) / aggregated_data['Price'].iloc[-51] * 100) if len(aggregated_data) > 50 else None
                pct_150d = ((latest_price - aggregated_data['Price'].iloc[-151]) / aggregated_data['Price'].iloc[-151] * 100) if len(aggregated_data) > 150 else None

                output_items.append({
                    'Data Source': 'Aggregated Output Index',
                    '5D %': pct_5d,
                    '10D %': pct_10d,
                    '50D %': pct_50d,
                    '150D %': pct_150d
                })
        else:
            for out in ticker_data['outputs']:
                item_data, actual_name = get_index_data(out['item'], out['group'], out['region'], df, all_indexes, regional_indexes)

                if item_data is not None and not item_data.empty:
                    item_data = item_data.sort_values('Date').reset_index(drop=True)
                    latest_price = item_data['Price'].iloc[-1]

                    pct_5d = ((latest_price - item_data['Price'].iloc[-6]) / item_data['Price'].iloc[-6] * 100) if len(item_data) > 5 else None
                    pct_10d = ((latest_price - item_data['Price'].iloc[-11]) / item_data['Price'].iloc[-11] * 100) if len(item_data) > 10 else None
                    pct_50d = ((latest_price - item_data['Price'].iloc[-51]) / item_data['Price'].iloc[-51] * 100) if len(item_data) > 50 else None
                    pct_150d = ((latest_price - item_data['Price'].iloc[-151]) / item_data['Price'].iloc[-151] * 100) if len(item_data) > 150 else None
                else:
                    pct_5d = pct_10d = pct_50d = pct_150d = None

                output_items.append({
                    'Data Source': actual_name if actual_name else 'N/A',
                    '5D %': pct_5d,
                    '10D %': pct_10d,
                    '50D %': pct_50d,
                    '150D %': pct_150d
                })

        output_df = pd.DataFrame(output_items)
        st.dataframe(output_df.style.format({
            '5D %': '{:.2f}',
            '10D %': '{:.2f}',
            '50D %': '{:.2f}',
            '150D %': '{:.2f}'
        }, na_rep='-'), hide_index=True)

        # Plot output commodities
        st.write("**Output Commodity Prices**")
        fig_outputs = go.Figure()

        if aggregate_items and len(ticker_data['outputs']) > 1:
            # Create aggregated index for all outputs
            aggregated_data = create_aggregated_index(ticker_data['outputs'], df, all_indexes, regional_indexes)
            if aggregated_data is not None and not aggregated_data.empty:
                aggregated_data['Normalized'] = (aggregated_data['Price'] / aggregated_data['Price'].iloc[0]) * 100

                fig_outputs.add_trace(go.Scatter(
                    x=aggregated_data['Date'],
                    y=aggregated_data['Normalized'],
                    mode='lines',
                    name='Aggregated Output Index',
                    line=dict(width=2)
                ))
        else:
            # Show individual items
            for out in ticker_data['outputs']:
                item_data, display_name = get_index_data(out['item'], out['group'], out['region'], df, all_indexes, regional_indexes)
                if item_data is not None and not item_data.empty:
                    # Normalize to base 100
                    item_data['Normalized'] = (item_data['Price'] / item_data['Price'].iloc[0]) * 100

                    fig_outputs.add_trace(go.Scatter(
                        x=item_data['Date'],
                        y=item_data['Normalized'],
                        mode='lines',
                        name=display_name,
                        line=dict(width=2)
                    ))

        fig_outputs.update_layout(
            xaxis_title='Date',
            yaxis_title='Normalized Price (Base = 100)',
            hovermode='x unified',
            template='plotly_white',
            height=400,
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='center',
                x=0.5,
                font=dict(size=12)
            )
        )
        st.plotly_chart(fig_outputs, use_container_width=True)
    else:
        st.info('No output commodities mapped')

    # Combined view with stock price subplot
    if ticker_data['inputs'] or ticker_data['outputs']:
        st.divider()
        st.subheader('Combined View: Inputs vs Outputs vs Stock Price')

        # Create subplots - 3 rows, shared x-axis
        fig_combined = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            row_heights=[0.45, 0.25, 0.3],
            subplot_titles=['Commodity Inputs/Outputs', 'Output-Input Spread (Margin Indicator)', f'{selected_ticker} Stock Price']
        )

        # Prepare input and output data for spread calculation
        # Always use aggregated indexes in combined view for consistent spread calculation
        input_normalized = None
        output_normalized = None

        # Add inputs to top subplot - always aggregate
        if ticker_data['inputs']:
            if len(ticker_data['inputs']) > 1:
                aggregated_data = create_aggregated_index(ticker_data['inputs'], df, all_indexes, regional_indexes)
                input_label = '[IN] Aggregated Input Index'
            else:
                # Single input - use directly
                inp = ticker_data['inputs'][0]
                aggregated_data, display_name = get_index_data(inp['item'], inp['group'], inp['region'], df, all_indexes, regional_indexes)
                input_label = f"[IN] {display_name}"

            if aggregated_data is not None and not aggregated_data.empty:
                if 'Index_Value' in aggregated_data.columns:
                    aggregated_data = aggregated_data.rename(columns={'Index_Value': 'Price'})
                aggregated_data['Normalized'] = (aggregated_data['Price'] / aggregated_data['Price'].iloc[0]) * 100
                input_normalized = aggregated_data[['Date', 'Normalized']].copy()

                fig_combined.add_trace(go.Scatter(
                    x=aggregated_data['Date'],
                    y=aggregated_data['Normalized'],
                    mode='lines',
                    name=input_label,
                    line=dict(dash='dot', width=2)
                ), row=1, col=1)

        # Add outputs to top subplot - always aggregate
        if ticker_data['outputs']:
            if len(ticker_data['outputs']) > 1:
                aggregated_data = create_aggregated_index(ticker_data['outputs'], df, all_indexes, regional_indexes)
                output_label = '[OUT] Aggregated Output Index'
            else:
                # Single output - use directly
                out = ticker_data['outputs'][0]
                aggregated_data, display_name = get_index_data(out['item'], out['group'], out['region'], df, all_indexes, regional_indexes)
                output_label = f"[OUT] {display_name}"

            if aggregated_data is not None and not aggregated_data.empty:
                if 'Index_Value' in aggregated_data.columns:
                    aggregated_data = aggregated_data.rename(columns={'Index_Value': 'Price'})
                aggregated_data['Normalized'] = (aggregated_data['Price'] / aggregated_data['Price'].iloc[0]) * 100
                output_normalized = aggregated_data[['Date', 'Normalized']].copy()

                fig_combined.add_trace(go.Scatter(
                    x=aggregated_data['Date'],
                    y=aggregated_data['Normalized'],
                    mode='lines',
                    name=output_label,
                    line=dict(width=2)
                ), row=1, col=1)

        # Add shaded area between input and output
        if input_normalized is not None and output_normalized is not None:
            # Merge on date
            merged_spread = pd.merge(
                input_normalized.rename(columns={'Normalized': 'Input'}),
                output_normalized.rename(columns={'Normalized': 'Output'}),
                on='Date', how='inner'
            )

            if not merged_spread.empty:
                # Split into positive and negative spread segments
                merged_spread['Spread'] = merged_spread['Output'] - merged_spread['Input']
                merged_spread['Sign'] = (merged_spread['Spread'] >= 0).astype(int)
                merged_spread['Group'] = (merged_spread['Sign'] != merged_spread['Sign'].shift()).cumsum()

                # Plot each continuous segment
                for group_id in merged_spread['Group'].unique():
                    segment = merged_spread[merged_spread['Group'] == group_id].copy()

                    if segment['Spread'].iloc[0] >= 0:
                        # Positive spread - blue
                        fig_combined.add_trace(go.Scatter(
                            x=segment['Date'],
                            y=segment['Output'],
                            mode='lines',
                            line=dict(width=0),
                            showlegend=False,
                            hoverinfo='skip'
                        ), row=1, col=1)

                        fig_combined.add_trace(go.Scatter(
                            x=segment['Date'],
                            y=segment['Input'],
                            mode='lines',
                            line=dict(width=0),
                            fill='tonexty',
                            fillcolor='rgba(0, 176, 246, 0.2)',
                            showlegend=False,
                            hoverinfo='skip'
                        ), row=1, col=1)
                    else:
                        # Negative spread - red
                        fig_combined.add_trace(go.Scatter(
                            x=segment['Date'],
                            y=segment['Input'],
                            mode='lines',
                            line=dict(width=0),
                            showlegend=False,
                            hoverinfo='skip'
                        ), row=1, col=1)

                        fig_combined.add_trace(go.Scatter(
                            x=segment['Date'],
                            y=segment['Output'],
                            mode='lines',
                            line=dict(width=0),
                            fill='tonexty',
                            fillcolor='rgba(255, 0, 0, 0.2)',
                            showlegend=False,
                            hoverinfo='skip'
                        ), row=1, col=1)

        # Add spread line to 2nd subplot
        spread_data = None
        if input_normalized is not None and output_normalized is not None:
            if not merged_spread.empty:
                merged_spread['Spread'] = merged_spread['Output'] - merged_spread['Input']
                merged_spread['Spread_MA20'] = merged_spread['Spread'].rolling(window=20, min_periods=1).mean()

                # Save for correlation calculation
                spread_data = merged_spread[['Date', 'Spread', 'Spread_MA20']].copy()

                # Add raw spread line (thin, transparent)
                fig_combined.add_trace(go.Scatter(
                    x=merged_spread['Date'],
                    y=merged_spread['Spread'],
                    mode='lines',
                    name='Spread (Daily)',
                    line=dict(color='lightgreen', width=1),
                    opacity=0.3
                ), row=2, col=1)

                # Add MA20 spread line (main)
                fig_combined.add_trace(go.Scatter(
                    x=merged_spread['Date'],
                    y=merged_spread['Spread_MA20'],
                    mode='lines',
                    name='Spread MA20',
                    line=dict(color='green', width=2),
                    fill='tozeroy',
                    fillcolor='rgba(0, 255, 0, 0.1)'
                ), row=2, col=1)

                # Add zero line for reference
                fig_combined.add_hline(y=0, line=dict(color='gray', dash='dash', width=1), row=2, col=1)

        # Add stock price to 3rd subplot
        stock_data = fetch_historical_price(selected_ticker, start_date=GLOBAL_START_DATE)
        if stock_data is not None and not stock_data.empty:
            stock_data = stock_data.sort_values('Date').reset_index(drop=True)
            stock_data['Normalized'] = (stock_data['Price'] / stock_data['Price'].iloc[0]) * 100

            fig_combined.add_trace(go.Scatter(
                x=stock_data['Date'],
                y=stock_data['Normalized'],
                mode='lines',
                name=f'[STOCK] {selected_ticker}',
                line=dict(color='black', width=2)
            ), row=3, col=1)

            # Calculate correlations
            price_correlations, return_correlations = calculate_correlations(selected_ticker, ticker_data, df, all_indexes, regional_indexes, stock_data)

        # Calculate spread correlation with stock price
        spread_correlation = None
        spread_return_correlation = None
        if stock_data is not None and spread_data is not None:
            stock_df = stock_data[['Date', 'Price']].copy()
            stock_df['Date'] = pd.to_datetime(stock_df['Date']).dt.tz_localize(None)
            spread_data['Date'] = pd.to_datetime(spread_data['Date']).dt.tz_localize(None)

            merged_corr = pd.merge(stock_df, spread_data, on='Date', how='inner')
            if len(merged_corr) > 1:
                # Price level correlation (stock price vs spread MA20)
                spread_correlation = merged_corr['Price'].corr(merged_corr['Spread_MA20'])

                # Returns correlation
                merged_corr['Stock_Return'] = merged_corr['Price'].pct_change(fill_method=None)
                merged_corr['Spread_Change'] = merged_corr['Spread_MA20'].pct_change(fill_method=None)
                spread_return_correlation = merged_corr['Stock_Return'].corr(merged_corr['Spread_Change'])

        # Update layout
        fig_combined.update_xaxes(title_text='Date', row=3, col=1)
        fig_combined.update_yaxes(title_text='Normalized Price (Base = 100)', row=1, col=1)
        fig_combined.update_yaxes(title_text='Spread (Output - Input)', row=2, col=1)
        fig_combined.update_yaxes(title_text='Normalized Price (Base = 100)', row=3, col=1)

        fig_combined.update_layout(
            hovermode='x unified',
            template='plotly_white',
            height=900,
            showlegend=True,
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.05,
                xanchor='center',
                x=0.5,
                font=dict(size=12)
            )
        )
        st.plotly_chart(fig_combined, use_container_width=True)

        # Add interpretation notes
        if input_normalized is not None and output_normalized is not None:
            if spread_correlation is not None:
                st.success(f'📊 **Spread-Stock Correlation**: Price Level = {spread_correlation:.3f} | Returns = {spread_return_correlation:.3f}')

        # Display correlation results
        if stock_data is not None and not stock_data.empty and (price_correlations or return_correlations):
            st.subheader('Correlation Analysis')

            # Separate inputs and outputs for price correlations
            input_price_corrs = []
            output_price_corrs = []
            input_return_corrs = []
            output_return_corrs = []

            for key, value in price_correlations.items():
                if key.startswith('Input_'):
                    name = key.split('_', 2)[2]
                    input_price_corrs.append({'Commodity': name, 'Price Corr': value})
                elif key.startswith('Output_'):
                    name = key.split('_', 2)[2]
                    output_price_corrs.append({'Commodity': name, 'Price Corr': value})

            for key, value in return_correlations.items():
                if key.startswith('Input_'):
                    name = key.split('_', 2)[2]
                    input_return_corrs.append({'Commodity': name, 'Return Corr': value})
                elif key.startswith('Output_'):
                    name = key.split('_', 2)[2]
                    output_return_corrs.append({'Commodity': name, 'Return Corr': value})

            # Display price correlations
            st.write('**Price Level Correlations**')
            col1, col2 = st.columns(2)

            with col1:
                if input_price_corrs:
                    st.write('*Inputs*')
                    input_df = pd.DataFrame(input_price_corrs)
                    st.dataframe(input_df.style.format({'Price Corr': '{:.3f}'}), hide_index=True)

            with col2:
                if output_price_corrs:
                    st.write('*Outputs*')
                    output_df = pd.DataFrame(output_price_corrs)
                    st.dataframe(output_df.style.format({'Price Corr': '{:.3f}'}), hide_index=True)

            # Display return correlations
            st.write('**Daily Return Correlations**')
            col3, col4 = st.columns(2)

            with col3:
                if input_return_corrs:
                    st.write('*Inputs*')
                    input_ret_df = pd.DataFrame(input_return_corrs)
                    st.dataframe(input_ret_df.style.format({'Return Corr': '{:.3f}'}), hide_index=True)

            with col4:
                if output_return_corrs:
                    st.write('*Outputs*')
                    output_ret_df = pd.DataFrame(output_return_corrs)
                    st.dataframe(output_ret_df.style.format({'Return Corr': '{:.3f}'}), hide_index=True)

else:
    st.error(f'No data found for ticker {selected_ticker}')
