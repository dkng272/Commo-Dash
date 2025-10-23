import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from classification_loader import load_sql_data_raw, apply_classification, get_classification_df

st.set_page_config(layout="wide", initial_sidebar_state="expanded", page_title="Individual Item Viewer")

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
# Page title
st.title("📊 Commodity Viewer")


# Load data from SQL
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

    # Filter out items without classification (internal calculated fields)
    df = df_classified.dropna(subset=['Group', 'Region', 'Sector'])

    return df

@st.cache_data(ttl=3600)
def load_classification_data():
    """Load classification structure for dropdown filters (cached 1 hour)."""
    return get_classification_df()

df_all = load_data()
classification_df = load_classification_data()

# Time period aggregation function
def aggregate_by_period(df, period='Daily'):
    """
    Aggregate price data by time period
    df: DataFrame with Date and Price columns
    period: 'Daily', 'Weekly', 'Monthly', 'Quarterly'
    """
    if period == 'Daily':
        return df

    df = df.copy()
    df['Date'] = pd.to_datetime(df['Date'])

    if period == 'Weekly':
        # Group by week (W = week ending Sunday)
        df['Period'] = df['Date'].dt.to_period('W')
        agg_df = df.groupby('Period')['Price'].mean().reset_index()
        agg_df['Date'] = agg_df['Period'].dt.start_time

    elif period == 'Monthly':
        df['Period'] = df['Date'].dt.to_period('M')
        agg_df = df.groupby('Period')['Price'].mean().reset_index()
        agg_df['Date'] = agg_df['Period'].dt.start_time

    elif period == 'Quarterly':
        df['Period'] = df['Date'].dt.to_period('Q')
        agg_df = df.groupby('Period')['Price'].mean().reset_index()
        agg_df['Date'] = agg_df['Period'].dt.start_time

    return agg_df[['Date', 'Price']]

# Calculate percentage change
def calculate_pct_change(df, days):
    """Calculate percentage change over specified days"""
    if len(df) < days + 1:
        return None
    old_price = df.iloc[-(days+1)]['Price']
    new_price = df.iloc[-1]['Price']
    return ((new_price / old_price) - 1) * 100

# Gradient header style
def gradient_header(text):
    st.markdown(f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 1px 12px; border-radius: 8px; margin-bottom: 12px; margin-top: 12px;">
            <h3 style="color: white; margin: 0; font-size: 18px;">{text}</h3>
        </div>
    """, unsafe_allow_html=True)

# ============ SIDEBAR FILTERS ============
st.sidebar.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 8px 12px; border-radius: 8px; margin-bottom: 16px;">
        <h3 style="color: white; margin: 0; font-size: 16px;">Filters</h3>
    </div>
""", unsafe_allow_html=True)

# Get unique sectors
sectors = sorted(classification_df['Sector'].dropna().unique().tolist())
selected_sector = st.sidebar.selectbox(
    "Sector",
    options=['All'] + sectors,
    index=0
)

# Filter by sector
if selected_sector != 'All':
    filtered_df = classification_df[classification_df['Sector'] == selected_sector]
else:
    filtered_df = classification_df

# Get unique groups based on sector filter
groups = sorted(filtered_df['Group'].dropna().unique().tolist())
selected_group = st.sidebar.selectbox(
    "Group",
    options=['All'] + groups,
    index=0
)

# Filter by group
if selected_group != 'All':
    filtered_df = filtered_df[filtered_df['Group'] == selected_group]

# Get unique regions based on group filter
regions = sorted(filtered_df['Region'].dropna().unique().tolist())
selected_region = st.sidebar.selectbox(
    "Region",
    options=['All'] + regions,
    index=0
)

# Filter by region
if selected_region != 'All':
    filtered_df = filtered_df[filtered_df['Region'] == selected_region]

# Get available items
available_items = sorted(filtered_df['Item'].dropna().unique().tolist())

st.sidebar.divider()

# ============ ITEM SELECTION IN SIDEBAR ============
# Initialize session state for selected items
if 'selected_items_chart' not in st.session_state:
    st.session_state.selected_items_chart = []

# Quick action buttons
col_btn1, col_btn2 = st.sidebar.columns(2)
with col_btn1:
    if st.button("Select All", use_container_width=True):
        st.session_state.selected_items_chart = available_items.copy()

with col_btn2:
    if st.button("Clear", use_container_width=True):
        st.session_state.selected_items_chart = []

# Filter to only include available items
default_items = [item for item in st.session_state.selected_items_chart if item in available_items]

selected_items = st.sidebar.multiselect(
    "Items",
    options=available_items,
    default=default_items,
    help="Select one or more items to view their price movements"
)

# Update session state with current selection
st.session_state.selected_items_chart = selected_items

st.sidebar.divider()
st.sidebar.caption(f"📊 {len(available_items)} items available")
st.sidebar.caption(f"📈 {len(selected_items)} items selected for chart")

# ============ FRAGMENT: TIMEFRAME + TABLE + CHART ============
@st.fragment
def display_analysis(df_all, available_items, selected_items, classification_df):
    """
    Fragment for timeframe selection and data display.
    Only this section re-runs when timeframe changes (not sidebar filters).
    """

    # ============ CHART CONTROLS ============
    st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 8px 12px; border-radius: 8px; margin-bottom: 16px;">
            <h3 style="color: white; margin: 0; font-size: 16px;">Chart Controls</h3>
        </div>
    """, unsafe_allow_html=True)

    # Preset timeframe options
    timeframe_options = {
        'YTD': f'{pd.Timestamp.now().year}-01-01',
        '1Y': (pd.Timestamp.now() - pd.DateOffset(years=1)).strftime('%Y-%m-%d'),
        '3Y': (pd.Timestamp.now() - pd.DateOffset(years=3)).strftime('%Y-%m-%d'),
        'All Time': df_all['Date'].min().strftime('%Y-%m-%d') if not df_all.empty else '2020-01-01'
    }

    # Three columns for all chart controls
    col_timeframe, col_period, col_display = st.columns(3)

    with col_timeframe:
        selected_timeframe = st.radio(
            "Timeframe",
            options=list(timeframe_options.keys()),
            index=0,
            horizontal=False
        )

    with col_period:
        period = st.radio(
            "Time Period",
            options=['Daily', 'Weekly', 'Monthly', 'Quarterly'],
            index=0,
            horizontal=False
        )

    with col_display:
        display_mode = st.radio(
            "Display Mode",
            options=['Normalized (Base 100)', 'Absolute Prices'],
            index=0,
            horizontal=False
        )

    # Calculate start date and lookback date (150 days before for calculations)
    display_start_date = pd.to_datetime(timeframe_options[selected_timeframe])
    calc_start_date = display_start_date - pd.DateOffset(days=150)

    st.caption(f"📅 Display from: {display_start_date.strftime('%Y-%m-%d')} | 📊 Calculations from: {calc_start_date.strftime('%Y-%m-%d')}")
    st.divider()

    # Filter data with 150D lookback for calculations
    df_calc = df_all[df_all['Date'] >= calc_start_date].copy()

    # ============ SUMMARY STATISTICS TABLE ============
    # Always show table for available items (filtered by sidebar filters)
    if len(available_items) > 0:
        gradient_header("Summary Statistics")

        # Calculate statistics for each item in available_items
        summary_rows = []

        for item in available_items:
            # Filter by Name column (not Ticker) since item comes from commo_list Item
            # Use df_calc (with 150D lookback) for calculations
            item_df = df_calc[df_calc['Name'] == item][['Date', 'Price']].copy()
            item_df = item_df.sort_values('Date')

            if len(item_df) == 0:
                continue

            # Get latest value
            latest_price = item_df.iloc[-1]['Price']

            # Calculate % changes
            changes = {}
            for days, label in [(1, '1D'), (5, '1W'), (20, '1M'), (60, '3M'), (125, '6M'), (250, '1Y')]:
                pct = calculate_pct_change(item_df, days)
                changes[label] = pct

            # Calculate YTD change
            current_year = pd.Timestamp.now().year
            year_start = pd.Timestamp(f'{current_year}-01-01')
            ytd_data = item_df[item_df['Date'] >= year_start]
            if len(ytd_data) > 1:
                ytd_start_price = ytd_data.iloc[0]['Price']
                ytd_latest_price = ytd_data.iloc[-1]['Price']
                changes['YTD'] = ((ytd_latest_price / ytd_start_price) - 1) * 100
            else:
                changes['YTD'] = None

            # Get group/region info
            item_info = classification_df[classification_df['Item'] == item].iloc[0]

            summary_rows.append({
                'Item': item,
                'Group': item_info['Group'],
                'Region': item_info['Region'],
                'Latest': latest_price,
                '1D': changes['1D'],
                '1W': changes['1W'],
                '1M': changes['1M'],
                'YTD': changes['YTD'],
                '3M': changes['3M'],
                '6M': changes['6M'],
                '1Y': changes['1Y']
            })

        summary_df = pd.DataFrame(summary_rows)

        # Format the dataframe for display
        display_df = summary_df.copy()

        # Format Latest column
        display_df['Latest'] = display_df['Latest'].apply(lambda x: f"{x:.2f}")

        # Format percentage columns with color coding
        def color_pct(val):
            """Apply color to percentage values"""
            if pd.isna(val) or val is None:
                return 'color: #6b7280'
            elif val > 0:
                return 'color: #22c55e; font-weight: 600'
            elif val < 0:
                return 'color: #ef4444; font-weight: 600'
            else:
                return 'color: #6b7280; font-weight: 600'

        # Format percentage columns
        for col in ['1D', '1W', '1M', 'YTD', '3M', '6M', '1Y']:
            display_df[col] = display_df[col].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A")

        # Apply styling
        styled_df = summary_df.style.format({
            'Latest': '{:.2f}',
            '1D': lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A",
            '1W': lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A",
            '1M': lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A",
            'YTD': lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A",
            '3M': lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A",
            '6M': lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A",
            '1Y': lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A"
        }).map(color_pct, subset=['1D', '1W', '1M', 'YTD', '3M', '6M', '1Y'])

        # Display using st.dataframe for better rendering
        st.dataframe(
            styled_df,
            use_container_width=True,
            height=min(350, 40 + len(summary_df) * 30),
            hide_index=True
        )

        # ============ CHART SECTION ============
        # Only show chart if items are selected
        if len(selected_items) > 0:
            gradient_header("Price Chart")

            # Prepare data for selected items
            # Filter for display timeframe only (not calc window)
            df_display = df_calc[df_calc['Date'] >= display_start_date].copy()

            chart_data = []
            for item in selected_items:
                # Filter by Name column (not Ticker) since item comes from commo_list Item
                item_df = df_display[df_display['Name'] == item][['Date', 'Price']].copy()
                item_df = item_df.sort_values('Date')

                # Aggregate by period
                item_df_agg = aggregate_by_period(item_df, period)

                # Normalize if needed
                if display_mode == 'Normalized (Base 100)' and len(item_df_agg) > 0:
                    base_price = item_df_agg.iloc[0]['Price']
                    item_df_agg['Price'] = (item_df_agg['Price'] / base_price) * 100

                chart_data.append((item, item_df_agg))

            # Create chart
            fig = go.Figure()

            for item, item_df_agg in chart_data:
                fig.add_trace(go.Scatter(
                    x=item_df_agg['Date'],
                    y=item_df_agg['Price'],
                    name=item,
                    mode='lines',
                    line=dict(width=2),
                    hovertemplate='<b>%{fullData.name}</b><br>Date: %{x}<br>Price: %{y:.2f}<extra></extra>'
                ))

            y_axis_title = 'Index (Base 100)' if display_mode == 'Normalized (Base 100)' else 'Price'

            fig.update_layout(
                title=f"{period} Price Movements - {len(selected_items)} Items",
                xaxis_title="Date",
                yaxis_title=y_axis_title,
                hovermode='x unified',
                height=500,
                showlegend=True,
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=1,
                    xanchor="left",
                    x=1.02
                ),
                margin=dict(l=50, r=150, t=50, b=50)
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("💡 Select items from the sidebar to view price comparison chart")

    else:
        st.info("👆 Use sidebar filters to narrow down items, or view all items in the table")

# Call the fragment
display_analysis(df_all, available_items, selected_items, classification_df)
