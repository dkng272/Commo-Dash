import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
from datetime import datetime
from commo_dashboard import create_equal_weight_index, create_weighted_index, create_regional_indexes, create_sector_indexes, load_latest_news
from classification_loader import load_data_with_classification

st.set_page_config(layout="wide", initial_sidebar_state="expanded", menu_items=None)

# Force light theme
st.markdown("""
    <style>
        [data-testid="stAppViewContainer"] {
            background-color: white;
            color: black;
        }
        [data-testid="stSidebar"] {
            background-color: #f0f2f6;
        }
    </style>
""", unsafe_allow_html=True)

# Load data with dynamic classification
@st.cache_data
def load_data():
    df = load_data_with_classification('data/cleaned_data.csv')
    return df

@st.cache_data
def build_indexes(df):
    # Exclude NaN groups (unclassified tickers used for ticker-specific input/output)
    all_groups = df['Group'].dropna().unique()
    all_indexes = {}

    for group in all_groups:
        if group != 'Crack Spread':
            all_indexes[group] = create_equal_weight_index(df, group)

    # Handle Crack Spread separately
    crack_spread_df = df[df['Group'] == 'Crack Spread'].copy()
    crack_spread_df = crack_spread_df.drop_duplicates(subset=['Date', 'Ticker'], keep='last')
    crack_pivot = crack_spread_df.pivot(index='Date', columns='Ticker', values='Price')
    crack_avg = crack_pivot.abs().mean(axis=1)
    all_indexes['Crack Spread'] = pd.DataFrame({
        'Date': crack_avg.index,
        'Index_Value': crack_avg.values
    })

    # Combine all indexes
    first_group = list(all_indexes.keys())[0]
    combined_df = all_indexes[first_group].copy()
    combined_df.rename(columns={'Index_Value': first_group}, inplace=True)

    for group in list(all_indexes.keys())[1:]:
        temp_df = all_indexes[group].copy()
        temp_df.rename(columns={'Index_Value': group}, inplace=True)
        combined_df = combined_df.merge(temp_df, on='Date', how='outer')

    combined_df = combined_df.sort_values('Date')
    combined_df = combined_df.ffill()

    # Regional indexes
    regional_indexes = create_regional_indexes(df)

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

    # Sector indexes
    sector_indexes = create_sector_indexes(df)

    if len(sector_indexes) > 0:
        first_sector = list(sector_indexes.keys())[0]
        sector_combined_df = sector_indexes[first_sector].copy()
        sector_combined_df.rename(columns={'Index_Value': first_sector}, inplace=True)

        for sector in list(sector_indexes.keys())[1:]:
            temp_df = sector_indexes[sector].copy()
            temp_df.rename(columns={'Index_Value': sector}, inplace=True)
            sector_combined_df = sector_combined_df.merge(temp_df, on='Date', how='outer')

        sector_combined_df = sector_combined_df.sort_values('Date')
        sector_combined_df = sector_combined_df.ffill()
    else:
        sector_combined_df = pd.DataFrame()

    return all_indexes, combined_df, regional_indexes, regional_combined_df, sector_indexes, sector_combined_df

def get_index_data(item, group, region, df, all_indexes, regional_indexes):
    """Get price data for an item with fallback to regional/group index"""
    if item and item.strip():
        item_data = df[df['Ticker'] == item].copy()
        if not item_data.empty:
            return item_data[['Date', 'Price']].sort_values('Date')

    if region and region.strip() and region.lower() != 'nan' and region.lower() != 'none':
        key = f"{group} - {region}"
        if key in regional_indexes:
            index_df = regional_indexes[key].copy()
            index_df.rename(columns={'Index_Value': 'Price'}, inplace=True)
            return index_df

    if group and group in all_indexes:
        index_df = all_indexes[group].copy()
        index_df.rename(columns={'Index_Value': 'Price'}, inplace=True)
        return index_df

    return None

def create_aggregated_index(items_list, df, all_indexes, regional_indexes, base_value=100):
    """Create equal-weighted index from multiple items"""
    all_prices = []

    for item_info in items_list:
        item_data = get_index_data(
            item_info['item'], item_info['group'], item_info['region'],
            df, all_indexes, regional_indexes
        )

        if item_data is not None and not item_data.empty:
            item_data = item_data.copy()
            item_name = f"{item_info.get('item', item_info['group'])}_Price"
            item_data = item_data.rename(columns={'Price': item_name})
            all_prices.append(item_data.set_index('Date'))

    if not all_prices:
        return None

    combined = pd.concat(all_prices, axis=1)
    returns = combined.pct_change(fill_method=None)
    avg_returns = returns.mean(axis=1, skipna=True)
    index_values = (1 + avg_returns).cumprod() * base_value
    index_values.iloc[0] = base_value

    return pd.DataFrame({'Date': index_values.index, 'Price': index_values.values}).reset_index(drop=True)

@st.cache_data
def calculate_all_ticker_spreads(_df, _all_indexes, _regional_indexes, ticker_mapping):
    """Vectorized calculation of spreads for all tickers"""
    spread_data = []

    for ticker_info in ticker_mapping:
        ticker = ticker_info['ticker']

        # Get input data
        input_data = None
        if ticker_info.get('inputs'):
            if len(ticker_info['inputs']) > 1:
                input_data = create_aggregated_index(ticker_info['inputs'], _df, _all_indexes, _regional_indexes)
            else:
                input_data = get_index_data(
                    ticker_info['inputs'][0]['item'],
                    ticker_info['inputs'][0]['group'],
                    ticker_info['inputs'][0]['region'],
                    _df, _all_indexes, _regional_indexes
                )

        # Get output data
        output_data = None
        if ticker_info.get('outputs'):
            if len(ticker_info['outputs']) > 1:
                output_data = create_aggregated_index(ticker_info['outputs'], _df, _all_indexes, _regional_indexes)
            else:
                output_data = get_index_data(
                    ticker_info['outputs'][0]['item'],
                    ticker_info['outputs'][0]['group'],
                    ticker_info['outputs'][0]['region'],
                    _df, _all_indexes, _regional_indexes
                )

        # Calculate percentage changes
        input_5d = input_10d = input_50d = input_150d = 0
        output_5d = output_10d = output_50d = output_150d = 0

        if input_data is not None and not input_data.empty:
            input_data = input_data.sort_values('Date').reset_index(drop=True)
            latest = input_data['Price'].iloc[-1]
            input_5d = ((latest - input_data['Price'].iloc[-6]) / input_data['Price'].iloc[-6] * 100) if len(input_data) > 5 else 0
            input_10d = ((latest - input_data['Price'].iloc[-11]) / input_data['Price'].iloc[-11] * 100) if len(input_data) > 10 else 0
            input_50d = ((latest - input_data['Price'].iloc[-51]) / input_data['Price'].iloc[-51] * 100) if len(input_data) > 50 else 0
            input_150d = ((latest - input_data['Price'].iloc[-151]) / input_data['Price'].iloc[-151] * 100) if len(input_data) > 150 else 0

        if output_data is not None and not output_data.empty:
            output_data = output_data.sort_values('Date').reset_index(drop=True)
            latest = output_data['Price'].iloc[-1]
            output_5d = ((latest - output_data['Price'].iloc[-6]) / output_data['Price'].iloc[-6] * 100) if len(output_data) > 5 else 0
            output_10d = ((latest - output_data['Price'].iloc[-11]) / output_data['Price'].iloc[-11] * 100) if len(output_data) > 10 else 0
            output_50d = ((latest - output_data['Price'].iloc[-51]) / output_data['Price'].iloc[-51] * 100) if len(output_data) > 50 else 0
            output_150d = ((latest - output_data['Price'].iloc[-151]) / output_data['Price'].iloc[-151] * 100) if len(output_data) > 150 else 0

        # Calculate spreads
        spread_data.append({
            'Ticker': ticker,
            'Spread_5D': output_5d - input_5d,
            'Spread_10D': output_10d - input_10d,
            'Spread_50D': output_50d - input_50d,
            'Spread_150D': output_150d - input_150d
        })

    return pd.DataFrame(spread_data)

# Load data
df = load_data()
all_indexes, combined_df, regional_indexes, regional_combined_df, sector_indexes, sector_combined_df = build_indexes(df)

# Streamlit Dashboard
col_title, col_update = st.columns([3, 1])
with col_title:
    st.title('Commodity Index Dashboard')
with col_update:
    # Last updated timestamp based on latest data date
    latest_data_date = df['Date'].max().strftime('%Y-%m-%d')
    st.markdown(f"""
        <div style="text-align: right; padding-top: 20px;">
            <span style="color: #666; font-size: 12px;">Last updated</span><br>
            <span style="color: #333; font-size: 13px; font-weight: 500;">{latest_data_date}</span>
        </div>
    """, unsafe_allow_html=True)

# Load ticker mappings from MongoDB
from mongodb_utils import load_ticker_mappings
ticker_mapping = load_ticker_mappings()

spreads_df = calculate_all_ticker_spreads(df, all_indexes, regional_indexes, ticker_mapping)

st.divider()

# Visual Section Container for Market Movers
st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 12px 16px; border-radius: 8px; margin-bottom: 16px;">
        <h3 style="color: white; margin: 0; font-size: 18px;">Market Movers</h3>
        <p style="color: rgba(255,255,255,0.9); margin: 4px 0 0 0; font-size: 13px;">
            Track stocks with the largest input-output spreads
        </p>
    </div>
""", unsafe_allow_html=True)

# Create tabs for Stock Spreads and Index Swings
tab1, tab2 = st.tabs(["Stock Spreads", "Commodity Index Swings"])

with tab1:
    # Toggle between best benefited and worst hit
    show_worst = st.checkbox('Show Worst Hit Stocks', value=False)

    st.caption("**Tip:** Visit the Ticker Analysis page for detailed stock analysis")

    # Create 4-column layout
    col1, col2, col3, col4 = st.columns(4)

    def color_spread(val):
        color = 'red' if val < 0 else 'green' if val > 0 else 'black'
        return f'color: {color}'

    with col1:
        st.write("**5D Spread**")
        if show_worst:
            top_5d = spreads_df.nsmallest(5, 'Spread_5D')[['Ticker', 'Spread_5D']]
        else:
            top_5d = spreads_df.nlargest(5, 'Spread_5D')[['Ticker', 'Spread_5D']]
        st.dataframe(
            top_5d.style.map(color_spread, subset=['Spread_5D']).format({'Spread_5D': '{:.2f}'}),
            hide_index=True
        )

    with col2:
        st.write("**10D Spread**")
        if show_worst:
            top_10d = spreads_df.nsmallest(5, 'Spread_10D')[['Ticker', 'Spread_10D']]
        else:
            top_10d = spreads_df.nlargest(5, 'Spread_10D')[['Ticker', 'Spread_10D']]
        st.dataframe(
            top_10d.style.map(color_spread, subset=['Spread_10D']).format({'Spread_10D': '{:.2f}'}),
            hide_index=True
        )

    with col3:
        st.write("**50D Spread**")
        if show_worst:
            top_50d = spreads_df.nsmallest(5, 'Spread_50D')[['Ticker', 'Spread_50D']]
        else:
            top_50d = spreads_df.nlargest(5, 'Spread_50D')[['Ticker', 'Spread_50D']]
        st.dataframe(
            top_50d.style.map(color_spread, subset=['Spread_50D']).format({'Spread_50D': '{:.2f}'}),
            hide_index=True
        )

    with col4:
        st.write("**150D Spread**")
        if show_worst:
            top_150d = spreads_df.nsmallest(5, 'Spread_150D')[['Ticker', 'Spread_150D']]
        else:
            top_150d = spreads_df.nlargest(5, 'Spread_150D')[['Ticker', 'Spread_150D']]
        st.dataframe(
            top_150d.style.map(color_spread, subset=['Spread_150D']).format({'Spread_150D': '{:.2f}'}),
            hide_index=True
        )

with tab2:
    # Summary Table - Largest Swings

    summary_data = []
    for group in all_indexes.keys():
        index_data = combined_df[group].dropna()

        change_5d = ((index_data.iloc[-1] / index_data.iloc[-6]) - 1) * 100 if len(index_data) >= 6 else 0
        change_10d = ((index_data.iloc[-1] / index_data.iloc[-11]) - 1) * 100 if len(index_data) >= 11 else 0
        change_50d = ((index_data.iloc[-1] / index_data.iloc[-51]) - 1) * 100 if len(index_data) >= 51 else 0
        change_150d = ((index_data.iloc[-1] / index_data.iloc[-151]) - 1) * 100 if len(index_data) >= 151 else 0

        summary_data.append({
            'Group': group,
            '5D Change (%)': round(change_5d, 2),
            '10D Change (%)': round(change_10d, 2),
            '50D Change (%)': round(change_50d, 2),
            '150D Change (%)': round(change_150d, 2),
            '5D Abs Swing': round(abs(change_5d), 2),
            '10D Abs Swing': round(abs(change_10d), 2),
            '50D Abs Swing': round(abs(change_50d), 2),
            '150D Abs Swing': round(abs(change_150d), 2)
        })

    summary_df = pd.DataFrame(summary_data)

    col1, col2, col3, col4 = st.columns(4)

    def color_negative_red(val):
        color = 'red' if val < 0 else 'green' if val > 0 else 'black'
        return f'color: {color}'

    with col1:
        st.write("**5D Swings**")
        top_5d = summary_df.sort_values('5D Abs Swing', ascending=False).head(5)
        st.dataframe(
            top_5d[['Group', '5D Change (%)']].style.map(color_negative_red, subset=['5D Change (%)']).format({'5D Change (%)': '{:.2f}'}),
            hide_index=True
        )

    with col2:
        st.write("**10D Swings**")
        top_10d = summary_df.sort_values('10D Abs Swing', ascending=False).head(5)
        st.dataframe(
            top_10d[['Group', '10D Change (%)']].style.map(color_negative_red, subset=['10D Change (%)']).format({'10D Change (%)': '{:.2f}'}),
            hide_index=True
        )

    with col3:
        st.write("**50D Swings**")
        top_50d = summary_df.sort_values('50D Abs Swing', ascending=False).head(5)
        st.dataframe(
            top_50d[['Group', '50D Change (%)']].style.map(color_negative_red, subset=['50D Change (%)']).format({'50D Change (%)': '{:.2f}'}),
            hide_index=True
        )

    with col4:
        st.write("**150D Swings**")
        top_150d = summary_df.sort_values('150D Abs Swing', ascending=False).head(5)
        st.dataframe(
            top_150d[['Group', '150D Change (%)']].style.map(color_negative_red, subset=['150D Change (%)']).format({'150D Change (%)': '{:.2f}'}),
            hide_index=True
        )

st.divider()

# Quick Chart Viewer Section
st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 12px 16px; border-radius: 8px; margin-bottom: 16px;">
        <h3 style="color: white; margin: 0; font-size: 18px;">📊 Quick Chart Viewer</h3>
        <p style="color: rgba(255,255,255,0.9); margin: 4px 0 0 0; font-size: 13px;">
            Visualize top movers without leaving the dashboard
        </p>
    </div>
""", unsafe_allow_html=True)

with st.expander("🔍 View Charts", expanded=False):
    # Get top 5 tickers based on current selection
    available_tickers = spreads_df.nlargest(5, 'Spread_50D')['Ticker'].tolist() if not show_worst else spreads_df.nsmallest(5, 'Spread_50D')['Ticker'].tolist()

    if available_tickers:
        # Ticker selection controls
        col1, col2 = st.columns([3, 1])

        with col1:
            selected_chart_ticker = st.selectbox(
                "Select Ticker",
                options=available_tickers,
                index=0,
                key="chart_ticker_selector",
                help="Choose from top 5 movers"
            )

        with col2:
            st.metric("Current Spread (50D)",
                     f"{spreads_df[spreads_df['Ticker'] == selected_chart_ticker]['Spread_50D'].values[0]:.2f}%",
                     delta=None)

        # Quick switch buttons for top 3
        st.caption("**Quick Switch:**")
        col_btn1, col_btn2, col_btn3, col_btn_spacer = st.columns([1, 1, 1, 6])

        for idx, ticker in enumerate(available_tickers[:3]):
            with [col_btn1, col_btn2, col_btn3][idx]:
                spread_val = spreads_df[spreads_df['Ticker'] == ticker]['Spread_50D'].values[0]
                button_label = f"#{idx+1} {ticker} ({spread_val:+.1f}%)"
                if st.button(button_label, key=f"quick_btn_{idx}", use_container_width=True):
                    selected_chart_ticker = ticker
                    st.rerun()

        st.divider()

        # Get ticker data
        ticker_data = next((item for item in ticker_mapping if item['ticker'] == selected_chart_ticker), None)

        if ticker_data:
            # Fetch stock data
            from ssi_api import fetch_historical_price
            stock_data = fetch_historical_price(selected_chart_ticker, start_date='2024-01-01')

            # Create 2x2 grid
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1:
                # Input commodities chart
                st.markdown("**Input Commodities (Costs)**")
                fig_inputs = go.Figure()

                if ticker_data.get('inputs'):
                    if len(ticker_data['inputs']) > 1:
                        input_data = create_aggregated_index(ticker_data['inputs'], df, all_indexes, regional_indexes)
                        label = 'Aggregated Input Index'
                    else:
                        input_data = get_index_data(
                            ticker_data['inputs'][0]['item'],
                            ticker_data['inputs'][0]['group'],
                            ticker_data['inputs'][0]['region'],
                            df, all_indexes, regional_indexes
                        )
                        label = ticker_data['inputs'][0]['group']

                    if input_data is not None and not input_data.empty:
                        first_price = input_data['Price'].dropna().iloc[0]
                        if first_price:
                            input_data['Normalized'] = (input_data['Price'] / first_price) * 100
                            fig_inputs.add_trace(go.Scatter(
                                x=input_data['Date'],
                                y=input_data['Normalized'],
                                mode='lines',
                                name=label,
                                line=dict(color='#ff6b6b', width=2)
                            ))

                fig_inputs.update_layout(
                    xaxis_title='', yaxis_title='Index (Base=100)',
                    hovermode='x', template='plotly_white', height=300,
                    showlegend=False, margin=dict(l=10, r=10, t=10, b=30)
                )
                st.plotly_chart(fig_inputs, use_container_width=True, key="input_chart")

            with chart_col2:
                # Output commodities chart
                st.markdown("**Output Commodities (Products)**")
                fig_outputs = go.Figure()

                if ticker_data.get('outputs'):
                    if len(ticker_data['outputs']) > 1:
                        output_data = create_aggregated_index(ticker_data['outputs'], df, all_indexes, regional_indexes)
                        label = 'Aggregated Output Index'
                    else:
                        output_data = get_index_data(
                            ticker_data['outputs'][0]['item'],
                            ticker_data['outputs'][0]['group'],
                            ticker_data['outputs'][0]['region'],
                            df, all_indexes, regional_indexes
                        )
                        label = ticker_data['outputs'][0]['group']

                    if output_data is not None and not output_data.empty:
                        first_price = output_data['Price'].dropna().iloc[0]
                        if first_price:
                            output_data['Normalized'] = (output_data['Price'] / first_price) * 100
                            fig_outputs.add_trace(go.Scatter(
                                x=output_data['Date'],
                                y=output_data['Normalized'],
                                mode='lines',
                                name=label,
                                line=dict(color='#4ecdc4', width=2)
                            ))

                fig_outputs.update_layout(
                    xaxis_title='', yaxis_title='Index (Base=100)',
                    hovermode='x', template='plotly_white', height=300,
                    showlegend=False, margin=dict(l=10, r=10, t=10, b=30)
                )
                st.plotly_chart(fig_outputs, use_container_width=True, key="output_chart")

            chart_col3, chart_col4 = st.columns(2)

            with chart_col3:
                # Stock price chart
                st.markdown(f"**{selected_chart_ticker} Stock Price**")
                fig_stock = go.Figure()

                if stock_data is not None and not stock_data.empty:
                    stock_data = stock_data.sort_values('Date')
                    first_price = stock_data['Price'].iloc[0]
                    stock_data['Normalized'] = (stock_data['Price'] / first_price) * 100

                    fig_stock.add_trace(go.Scatter(
                        x=stock_data['Date'],
                        y=stock_data['Normalized'],
                        mode='lines',
                        name=selected_chart_ticker,
                        line=dict(color='#95a5a6', width=2)
                    ))

                fig_stock.update_layout(
                    xaxis_title='', yaxis_title='Index (Base=100)',
                    hovermode='x', template='plotly_white', height=300,
                    showlegend=False, margin=dict(l=10, r=10, t=10, b=30)
                )
                st.plotly_chart(fig_stock, use_container_width=True, key="stock_chart")

            with chart_col4:
                # Spread chart
                st.markdown("**Spread (Output - Input)**")
                fig_spread = go.Figure()

                # Calculate spread
                if ticker_data.get('inputs') and ticker_data.get('outputs'):
                    if len(ticker_data['inputs']) > 1:
                        input_data = create_aggregated_index(ticker_data['inputs'], df, all_indexes, regional_indexes)
                    else:
                        input_data = get_index_data(
                            ticker_data['inputs'][0]['item'],
                            ticker_data['inputs'][0]['group'],
                            ticker_data['inputs'][0]['region'],
                            df, all_indexes, regional_indexes
                        )

                    if len(ticker_data['outputs']) > 1:
                        output_data = create_aggregated_index(ticker_data['outputs'], df, all_indexes, regional_indexes)
                    else:
                        output_data = get_index_data(
                            ticker_data['outputs'][0]['item'],
                            ticker_data['outputs'][0]['group'],
                            ticker_data['outputs'][0]['region'],
                            df, all_indexes, regional_indexes
                        )

                    if input_data is not None and output_data is not None:
                        # Normalize both
                        input_first = input_data['Price'].dropna().iloc[0]
                        output_first = output_data['Price'].dropna().iloc[0]

                        if input_first and output_first:
                            input_norm = input_data.copy()
                            output_norm = output_data.copy()
                            input_norm['Normalized'] = (input_norm['Price'] / input_first) * 100
                            output_norm['Normalized'] = (output_norm['Price'] / output_first) * 100

                            # Merge and calculate spread
                            merged = pd.merge(
                                input_norm[['Date', 'Normalized']].rename(columns={'Normalized': 'Input'}),
                                output_norm[['Date', 'Normalized']].rename(columns={'Normalized': 'Output'}),
                                on='Date', how='inner'
                            )

                            if not merged.empty:
                                merged['Spread'] = merged['Output'] - merged['Input']
                                merged['MA20'] = merged['Spread'].rolling(20, min_periods=1).mean()

                                fig_spread.add_trace(go.Scatter(
                                    x=merged['Date'],
                                    y=merged['MA20'],
                                    mode='lines',
                                    name='Spread MA20',
                                    line=dict(color='#2ecc71', width=2),
                                    fill='tozeroy',
                                    fillcolor='rgba(46, 204, 113, 0.2)'
                                ))
                                fig_spread.add_hline(y=0, line=dict(color='gray', dash='dash', width=1))

                fig_spread.update_layout(
                    xaxis_title='', yaxis_title='Spread Points',
                    hovermode='x', template='plotly_white', height=300,
                    showlegend=False, margin=dict(l=10, r=10, t=10, b=30)
                )
                st.plotly_chart(fig_spread, use_container_width=True, key="spread_chart")

            # Link to full analysis
            st.markdown(f"[🔍 View Full Analysis for {selected_chart_ticker}](Ticker_Analysis?ticker={selected_chart_ticker})")
        else:
            st.warning(f"No commodity mapping found for {selected_chart_ticker}")
    else:
        st.info("No tickers available to display")

st.divider()

# Visual Section Container for Latest News
st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 12px 16px; border-radius: 8px; margin-bottom: 16px;">
        <h3 style="color: white; margin: 0; font-size: 18px;">Latest Market News</h3>
        <p style="color: rgba(255,255,255,0.9); margin: 4px 0 0 0; font-size: 13px;">
            Recent commodity updates across all sectors
        </p>
    </div>
""", unsafe_allow_html=True)

# Collect all news from all groups
all_news = []
for group in all_indexes.keys():
    group_news = load_latest_news(group)
    if group_news:
        for item in group_news:
            all_news.append({
                'date': item['date'],
                'group': group,
                'news': item['news']
            })

# Sort by date (newest first) and limit to 20
all_news_sorted = sorted(all_news, key=lambda x: x['date'], reverse=True)[:20]

if all_news_sorted:
    # Build all news cards HTML
    all_cards_html = '<div style="max-height: 500px; overflow-y: auto; padding: 4px;">'

    for item in all_news_sorted:
        # Escape special characters for HTML display
        news_text = item['news'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        # Add each card to the HTML string
        all_cards_html += f'''<div style="background: white; border-left: 4px solid #667eea; padding: 16px; margin: 12px 0; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); transition: box-shadow 0.3s ease;">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
<strong style="font-size: 14px; color: #333;">{item['date']}</strong>
<span style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 4px 14px; border-radius: 16px; font-size: 12px; font-weight: 600;">{item['group']}</span>
</div>
<p style="margin: 0; color: #555; line-height: 1.6; font-size: 14px;">{news_text}</p>
</div>'''

    all_cards_html += '</div>'

    # Display the scrollable container with all cards
    st.markdown(all_cards_html, unsafe_allow_html=True)
else:
    st.info("No recent news available")

