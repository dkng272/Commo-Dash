import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from commo_dashboard import create_equal_weight_index, create_regional_indexes, load_latest_news
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
all_indexes, combined_df, regional_indexes, regional_combined_df = build_indexes(df)

# Sidebar for group selection
selected_group = st.sidebar.selectbox(
    'Select Commodity Group',
    options=sorted(list(all_indexes.keys()))
)

# Page Title with selected group
st.title(f'📊 {selected_group}')
index_data = combined_df[selected_group].dropna()
col1, col2, col3 = st.columns(3)

with col1:
    change_5d = ((index_data.iloc[-1] / index_data.iloc[-6]) - 1) * 100 if len(index_data) >= 6 else 0
    st.metric('5D Change', f'{change_5d:.2f}%', delta=f'{change_5d:.2f}%')
with col2:
    change_10d = ((index_data.iloc[-1] / index_data.iloc[-11]) - 1) * 100 if len(index_data) >= 11 else 0
    st.metric('10D Change', f'{change_10d:.2f}%', delta=f'{change_10d:.2f}%')
with col3:
    change_50d = ((index_data.iloc[-1] / index_data.iloc[-51]) - 1) * 100 if len(index_data) >= 51 else 0
    st.metric('50D Change', f'{change_50d:.2f}%', delta=f'{change_50d:.2f}%')

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
    # Get component tickers
    tickers = sorted(df[df['Group'] == selected_group]['Ticker'].unique())

    # Multi-select for components
    selected_tickers = st.multiselect(
        'Select Components to Display',
        options=tickers,
        default=tickers[:3] if len(tickers) > 3 else tickers
    )

    if selected_tickers:
        # Plot each selected ticker
        for ticker in selected_tickers:
            ticker_data = df[df['Ticker'] == ticker][['Date', 'Price']].sort_values('Date')

            fig.add_trace(go.Scatter(
                x=ticker_data['Date'],
                y=ticker_data['Price'],
                mode='lines',
                name=ticker,
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

# Display ticker components below chart
tickers = df[df['Group'] == selected_group]['Ticker'].unique()
st.caption(f"**Component Tickers:** {', '.join(sorted(tickers))}")

# Market News for Selected Group
st.divider()
st.subheader(f'📰 Latest News - {selected_group}')

news_items = load_latest_news(selected_group)

if news_items:
    # Merge all news items into one text box with scrollable container
    merged_news = []
    for item in news_items:  # Show all news items
        # Escape special markdown characters
        news_text = item['news']
        news_text = news_text.replace('$', r'\$')
        news_text = news_text.replace('~', r'\~')

        # Add date header and news
        merged_news.append(f"**📅 {item['date']}**\n\n{news_text}")

    # Display all merged news in a scrollable container with max height
    news_content = "\n\n---\n\n".join(merged_news)
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

            # Show tickers in this region below chart
            regional_tickers = df[(df['Group'] == selected_group) & (df['Region'] == region_name)]['Ticker'].unique()
            st.caption(f"**Component Tickers ({region_name}):** {', '.join(sorted(regional_tickers))}")

            # Regional metrics
            regional_data = regional_combined_df[regional_key].dropna()
            col1r, col2r, col3r = st.columns(3)

            with col1r:
                change_5d_r = ((regional_data.iloc[-1] / regional_data.iloc[-6]) - 1) * 100 if len(regional_data) >= 6 else 0
                st.metric('5D Change', f'{change_5d_r:.2f}%', delta=f'{change_5d_r:.2f}%')
            with col2r:
                change_10d_r = ((regional_data.iloc[-1] / regional_data.iloc[-11]) - 1) * 100 if len(regional_data) >= 11 else 0
                st.metric('10D Change', f'{change_10d_r:.2f}%', delta=f'{change_10d_r:.2f}%')
            with col3r:
                change_50d_r = ((regional_data.iloc[-1] / regional_data.iloc[-51]) - 1) * 100 if len(regional_data) >= 51 else 0
                st.metric('50D Change', f'{change_50d_r:.2f}%', delta=f'{change_50d_r:.2f}%')
