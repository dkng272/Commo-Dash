#%%
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import sys
import os

# Get the parent directory path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)
from commo_dashboard import create_equal_weight_index, create_regional_indexes

# Load data
@st.cache_data
def load_data():
    data_path = os.path.join(parent_dir, 'data', 'cleaned_data.csv')
    df = pd.read_csv(data_path)
    df['Date'] = pd.to_datetime(df['Date'])
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
    Get price data for an item. If item is None/empty, use group or group-region index.

    Returns: DataFrame with Date and Price columns, or None
    """
    if item and item.strip():
        # Use specific item data
        item_data = df[df['Ticker'] == item].copy()
        if not item_data.empty:
            return item_data[['Date', 'Price']].sort_values('Date')

    # Fall back to index
    if region and region.strip() and region.lower() != 'nan':
        # Try group-region index
        key = f"{group} - {region}"
        if key in regional_indexes:
            index_df = regional_indexes[key].copy()
            index_df.rename(columns={'Index_Value': 'Price'}, inplace=True)
            return index_df

    # Fall back to group index
    if group and group in all_indexes:
        index_df = all_indexes[group].copy()
        index_df.rename(columns={'Index_Value': 'Price'}, inplace=True)
        return index_df

    return None

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

# Get ticker data
ticker_data = next((item for item in ticker_mapping if item['ticker'] == selected_ticker), None)

if ticker_data:
    st.header(f'{selected_ticker} - Commodity Relationships')

    # Display inputs
    st.subheader('Input Commodities (Costs)')
    if ticker_data['inputs']:
        input_items = []
        for inp in ticker_data['inputs']:
            display_name = inp['item'] if inp['item'] else f"{inp['group']} Index"
            if inp['region'] and inp['region'].lower() != 'nan' and not inp['item']:
                display_name = f"{inp['group']} - {inp['region']} Index"

            input_items.append({
                'Item': display_name,
                'Group': inp['group'],
                'Region': inp['region'] if inp['region'] else 'N/A'
            })

        st.dataframe(pd.DataFrame(input_items), hide_index=True)

        # Plot input commodities
        st.write("**Input Commodity Prices**")
        fig_inputs = go.Figure()

        for inp in ticker_data['inputs']:
            item_data = get_index_data(inp['item'], inp['group'], inp['region'], df, all_indexes, regional_indexes)
            if item_data is not None and not item_data.empty:
                # Normalize to base 100
                item_data['Normalized'] = (item_data['Price'] / item_data['Price'].iloc[0]) * 100

                display_name = inp['item'] if inp['item'] else f"{inp['group']} Index"
                if inp['region'] and inp['region'].lower() != 'nan' and not inp['item']:
                    display_name = f"{inp['group']}-{inp['region']}"

                fig_inputs.add_trace(go.Scatter(
                    x=item_data['Date'],
                    y=item_data['Normalized'],
                    mode='lines',
                    name=display_name
                ))

        fig_inputs.update_layout(
            xaxis_title='Date',
            yaxis_title='Normalized Price (Base = 100)',
            hovermode='x unified',
            template='plotly_white',
            height=400
        )
        st.plotly_chart(fig_inputs, use_container_width=True)
    else:
        st.info('No input commodities mapped')

    st.divider()

    # Display outputs
    st.subheader('Output Commodities (Products)')
    if ticker_data['outputs']:
        output_items = []
        for out in ticker_data['outputs']:
            display_name = out['item'] if out['item'] else f"{out['group']} Index"
            if out['region'] and out['region'].lower() != 'nan' and not out['item']:
                display_name = f"{out['group']} - {out['region']} Index"

            output_items.append({
                'Item': display_name,
                'Group': out['group'],
                'Region': out['region'] if out['region'] else 'N/A'
            })

        st.dataframe(pd.DataFrame(output_items), hide_index=True)

        # Plot output commodities
        st.write("**Output Commodity Prices**")
        fig_outputs = go.Figure()

        for out in ticker_data['outputs']:
            item_data = get_index_data(out['item'], out['group'], out['region'], df, all_indexes, regional_indexes)
            if item_data is not None and not item_data.empty:
                # Normalize to base 100
                item_data['Normalized'] = (item_data['Price'] / item_data['Price'].iloc[0]) * 100

                display_name = out['item'] if out['item'] else f"{out['group']} Index"
                if out['region'] and out['region'].lower() != 'nan' and not out['item']:
                    display_name = f"{out['group']}-{out['region']}"

                fig_outputs.add_trace(go.Scatter(
                    x=item_data['Date'],
                    y=item_data['Normalized'],
                    mode='lines',
                    name=display_name
                ))

        fig_outputs.update_layout(
            xaxis_title='Date',
            yaxis_title='Normalized Price (Base = 100)',
            hovermode='x unified',
            template='plotly_white',
            height=400
        )
        st.plotly_chart(fig_outputs, use_container_width=True)
    else:
        st.info('No output commodities mapped')

    # Combined view
    if ticker_data['inputs'] or ticker_data['outputs']:
        st.divider()
        st.subheader('Combined View: Inputs vs Outputs')

        fig_combined = go.Figure()

        # Add inputs
        for inp in ticker_data['inputs']:
            item_data = get_index_data(inp['item'], inp['group'], inp['region'], df, all_indexes, regional_indexes)
            if item_data is not None and not item_data.empty:
                item_data['Normalized'] = (item_data['Price'] / item_data['Price'].iloc[0]) * 100

                display_name = inp['item'] if inp['item'] else f"{inp['group']} Index"
                if inp['region'] and inp['region'].lower() != 'nan' and not inp['item']:
                    display_name = f"{inp['group']}-{inp['region']}"

                fig_combined.add_trace(go.Scatter(
                    x=item_data['Date'],
                    y=item_data['Normalized'],
                    mode='lines',
                    name=f"[IN] {display_name}",
                    line=dict(dash='dot')
                ))

        # Add outputs
        for out in ticker_data['outputs']:
            item_data = get_index_data(out['item'], out['group'], out['region'], df, all_indexes, regional_indexes)
            if item_data is not None and not item_data.empty:
                item_data['Normalized'] = (item_data['Price'] / item_data['Price'].iloc[0]) * 100

                display_name = out['item'] if out['item'] else f"{out['group']} Index"
                if out['region'] and out['region'].lower() != 'nan' and not out['item']:
                    display_name = f"{out['group']}-{out['region']}"

                fig_combined.add_trace(go.Scatter(
                    x=item_data['Date'],
                    y=item_data['Normalized'],
                    mode='lines',
                    name=f"[OUT] {display_name}",
                    line=dict(width=2)
                ))

        fig_combined.update_layout(
            xaxis_title='Date',
            yaxis_title='Normalized Price (Base = 100)',
            hovermode='x unified',
            template='plotly_white',
            height=500
        )
        st.plotly_chart(fig_combined, use_container_width=True)

else:
    st.error(f'No data found for ticker {selected_ticker}')
