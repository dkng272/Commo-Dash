import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from commo_dashboard import create_equal_weight_index, create_regional_indexes, load_latest_news
from classification_loader import load_sql_data_raw, apply_classification

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
@st.cache_data(ttl=3600)
def load_raw_sql_data():
    """Load RAW commodity price data from SQL Server (cached 1 hour - expensive operation)."""
    return load_sql_data_raw()  # Fetch ALL available data, filter later

def load_data():
    """
    Load commodity price data with FRESH classification.

    Two-layer caching:
    1. SQL data cached for 1 hour (expensive)
    2. Classification applied fresh each time (uses 60s cached classifications from MongoDB)

    This allows classification changes to appear within ~60 seconds without re-querying SQL.
    """
    # Get cached raw SQL data (1 hour cache)
    df_raw = load_raw_sql_data()

    # Apply FRESH classification (MongoDB cached 60s, re-applied every page load)
    df_classified = apply_classification(df_raw)

    # Filter out items without classification
    df = df_classified.dropna(subset=['Group', 'Region', 'Sector'])
    return df

@st.cache_data
def build_indexes(df):
    # Exclude NaN groups
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

    return all_indexes, combined_df, regional_indexes, regional_combined_df

# Load data
df = load_data()

# ============ TIMEFRAME SELECTOR (SIDEBAR) ============
st.sidebar.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 8px 12px; border-radius: 8px; margin-bottom: 16px;">
        <h3 style="color: white; margin: 0; font-size: 16px;">Timeframe</h3>
    </div>
""", unsafe_allow_html=True)

# Preset timeframe options
timeframe_options = {
    'YTD': f'{pd.Timestamp.now().year}-01-01',
    '1Y': (pd.Timestamp.now() - pd.DateOffset(years=1)).strftime('%Y-%m-%d'),
    '3Y': (pd.Timestamp.now() - pd.DateOffset(years=3)).strftime('%Y-%m-%d'),
    'All Time': df['Date'].min().strftime('%Y-%m-%d') if not df.empty else '2020-01-01'
}

selected_timeframe = st.sidebar.radio(
    "Select Timeframe",
    options=list(timeframe_options.keys()),
    index=0,
    horizontal=False
)

# Filter data by selected timeframe
start_date = pd.to_datetime(timeframe_options[selected_timeframe])
df = df[df['Date'] >= start_date].copy()

st.sidebar.caption(f"Data from: {start_date.strftime('%Y-%m-%d')}")
st.sidebar.divider()

# Build indexes after filtering
all_indexes, combined_df, regional_indexes, regional_combined_df = build_indexes(df)

# Sidebar for group selection
selected_group = st.sidebar.selectbox(
    'Select Commodity Group',
    options=sorted(list(all_indexes.keys()))
)

# Page Title with selected group
st.title(f'{selected_group}')
index_data = combined_df[selected_group].dropna()

# Helper function for color coding
def get_color(value):
    return '#22c55e' if value > 0 else '#ef4444' if value < 0 else '#6b7280'

col1, col2, col3 = st.columns(3)

with col1:
    change_5d = ((index_data.iloc[-1] / index_data.iloc[-6]) - 1) * 100 if len(index_data) >= 6 else 0
    color = get_color(change_5d)
    st.markdown(f"""
        <div style="text-align: center; padding: 10px; background: white; border-radius: 8px; border: 1px solid #e5e7eb;">
            <div style="color: #6b7280; font-size: 13px; font-weight: 500;">5D Change</div>
            <div style="color: {color}; font-size: 24px; font-weight: 600; margin-top: 5px;">{change_5d:.2f}%</div>
        </div>
    """, unsafe_allow_html=True)

with col2:
    change_10d = ((index_data.iloc[-1] / index_data.iloc[-11]) - 1) * 100 if len(index_data) >= 11 else 0
    color = get_color(change_10d)
    st.markdown(f"""
        <div style="text-align: center; padding: 10px; background: white; border-radius: 8px; border: 1px solid #e5e7eb;">
            <div style="color: #6b7280; font-size: 13px; font-weight: 500;">10D Change</div>
            <div style="color: {color}; font-size: 24px; font-weight: 600; margin-top: 5px;">{change_10d:.2f}%</div>
        </div>
    """, unsafe_allow_html=True)

with col3:
    change_50d = ((index_data.iloc[-1] / index_data.iloc[-51]) - 1) * 100 if len(index_data) >= 51 else 0
    color = get_color(change_50d)
    st.markdown(f"""
        <div style="text-align: center; padding: 10px; background: white; border-radius: 8px; border: 1px solid #e5e7eb;">
            <div style="color: #6b7280; font-size: 13px; font-weight: 500;">50D Change</div>
            <div style="color: {color}; font-size: 24px; font-weight: 600; margin-top: 5px;">{change_50d:.2f}%</div>
        </div>
    """, unsafe_allow_html=True)

# View selection: Index or Components
view_mode = st.radio(
    'View Mode',
    options=['Index', 'Components'],
    horizontal=True
)

fig = go.Figure()

if view_mode == 'Index':
    # Plot the index
    plot_df = combined_df[['Date', selected_group]].dropna()

    fig.add_trace(go.Scatter(
        x=plot_df['Date'],
        y=plot_df[selected_group],
        mode='lines',
        name=selected_group,
        line=dict(width=2)
    ))
else:
    # Get component names
    names = sorted(df[df['Group'] == selected_group]['Name'].unique())

    # Multi-select for components
    selected_names = st.multiselect(
        'Select Components to Display',
        options=names,
        default=names[:3] if len(names) > 3 else names
    )

    if selected_names:
        # Plot each selected commodity name
        for name in selected_names:
            item_data = df[df['Name'] == name][['Date', 'Price']].sort_values('Date')

            fig.add_trace(go.Scatter(
                x=item_data['Date'],
                y=item_data['Price'],
                mode='lines',
                name=name,
                line=dict(width=2)
            ))
    else:
        st.info('Please select at least one component to display.')

fig.update_layout(
    xaxis_title='Date',
    yaxis_title='Index Value' if selected_group != 'Crack Spread' else 'Average Absolute Value',
    hovermode='x unified',
    template='plotly_white',
    height=500
)

st.plotly_chart(fig, use_container_width=True)

# Display commodity components below chart
names = df[df['Group'] == selected_group]['Name'].unique()
st.caption(f"**Components:** {', '.join(sorted(names))}")

# Market News for Selected Group
st.divider()
st.markdown(f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 1px 12px; border-radius: 8px; margin-bottom: 12px;">
        <h3 style="color: white; margin: 0; font-size: 18px;">Latest News - {selected_group}</h3>
    </div>
""", unsafe_allow_html=True)

news_items = load_latest_news(selected_group)

if news_items:
    # Merge all news items into one text box with scrollable container (using HTML)
    merged_news = []
    for item in news_items:  # Show all news items
        # Escape special characters for HTML display
        news_text = item['news'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        # Add date header and news (using HTML for bold)
        merged_news.append(f"<strong>{item['date']}</strong><br><br>{news_text}")

    # Display all merged news in a scrollable container with max height
    news_content = "<hr>".join(merged_news)
    st.markdown(
        f'<div style="max-height: 400px; overflow-y: auto; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">{news_content}</div>',
        unsafe_allow_html=True
    )
else:
    st.info(f"No recent news found for {selected_group}")

# Regional Sub-Indexes
regional_keys = [key for key in regional_indexes.keys() if key.startswith(selected_group + ' - ')]

if len(regional_keys) > 0:
    st.divider()
    st.subheader(f'{selected_group} - Regional Breakdown')

    # Create tabs for each region
    tabs = st.tabs([key.split(' - ')[1] for key in regional_keys])

    for i, (tab, regional_key) in enumerate(zip(tabs, regional_keys)):
        with tab:
            region_name = regional_key.split(' - ')[1]

            # Plot regional index
            plot_df_regional = regional_combined_df[['Date', regional_key]].dropna()

            fig_regional = go.Figure()
            fig_regional.add_trace(go.Scatter(
                x=plot_df_regional['Date'],
                y=plot_df_regional[regional_key],
                mode='lines',
                name=regional_key,
                line=dict(width=2)
            ))

            fig_regional.update_layout(
                xaxis_title='Date',
                yaxis_title='Index Value' if selected_group != 'Crack Spread' else 'Average Absolute Value',
                hovermode='x unified',
                template='plotly_white',
                height=400
            )

            st.plotly_chart(fig_regional, use_container_width=True)

            # Show commodity names in this region below chart
            regional_names = df[(df['Group'] == selected_group) & (df['Region'] == region_name)]['Name'].unique()
            st.caption(f"**Components ({region_name}):** {', '.join(sorted(regional_names))}")

            # Regional metrics
            regional_data = regional_combined_df[regional_key].dropna()
            col1r, col2r, col3r = st.columns(3)

            with col1r:
                change_5d_r = ((regional_data.iloc[-1] / regional_data.iloc[-6]) - 1) * 100 if len(regional_data) >= 6 else 0
                color = get_color(change_5d_r)
                st.markdown(f"""
                    <div style="text-align: center; padding: 10px; background: white; border-radius: 8px; border: 1px solid #e5e7eb;">
                        <div style="color: #6b7280; font-size: 13px; font-weight: 500;">5D Change</div>
                        <div style="color: {color}; font-size: 24px; font-weight: 600; margin-top: 5px;">{change_5d_r:.2f}%</div>
                    </div>
                """, unsafe_allow_html=True)

            with col2r:
                change_10d_r = ((regional_data.iloc[-1] / regional_data.iloc[-11]) - 1) * 100 if len(regional_data) >= 11 else 0
                color = get_color(change_10d_r)
                st.markdown(f"""
                    <div style="text-align: center; padding: 10px; background: white; border-radius: 8px; border: 1px solid #e5e7eb;">
                        <div style="color: #6b7280; font-size: 13px; font-weight: 500;">10D Change</div>
                        <div style="color: {color}; font-size: 24px; font-weight: 600; margin-top: 5px;">{change_10d_r:.2f}%</div>
                    </div>
                """, unsafe_allow_html=True)

            with col3r:
                change_50d_r = ((regional_data.iloc[-1] / regional_data.iloc[-51]) - 1) * 100 if len(regional_data) >= 51 else 0
                color = get_color(change_50d_r)
                st.markdown(f"""
                    <div style="text-align: center; padding: 10px; background: white; border-radius: 8px; border: 1px solid #e5e7eb;">
                        <div style="color: #6b7280; font-size: 13px; font-weight: 500;">50D Change</div>
                        <div style="color: {color}; font-size: 24px; font-weight: 600; margin-top: 5px;">{change_50d_r:.2f}%</div>
                    </div>
                """, unsafe_allow_html=True)
