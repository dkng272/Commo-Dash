import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from classification_loader import load_data_with_classification, load_classification

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


# Load data
@st.cache_data(ttl=300)
def load_data():
    df = load_data_with_classification()
    # Filter out items without classification (internal calculated fields)
    df = df.dropna(subset=['Group', 'Region', 'Sector'])
    return df

@st.cache_data(ttl=300)
def load_classification_data():
    classification = pd.read_excel('commo_list.xlsx')
    classification['Item'] = classification['Item'].str.strip()
    return classification

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
# st.sidebar.markdown("""
#     <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
#                 padding: 12px 16px; border-radius: 8px; margin-bottom: 16px;">
#         <h3 style="color: white; margin: 0; font-size: 18px;">Filters</h3>
#     </div>
# """, unsafe_allow_html=True)

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

# ============ SUMMARY STATISTICS TABLE ============
# Always show table for available items (filtered by sidebar filters)
if len(available_items) > 0:
    gradient_header("Summary Statistics")

    # Calculate statistics for each item in available_items
    summary_rows = []

    for item in available_items:
        item_df = df_all[df_all['Ticker'] == item][['Date', 'Price']].copy()
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
    for col in ['1D', '1W', '1M', '3M', '6M', '1Y']:
        display_df[col] = display_df[col].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A")

    # Apply styling
    styled_df = summary_df.style.format({
        'Latest': '{:.2f}',
        '1D': lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A",
        '1W': lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A",
        '1M': lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A",
        '3M': lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A",
        '6M': lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A",
        '1Y': lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A"
    }).map(color_pct, subset=['1D', '1W', '1M', '3M', '6M', '1Y'])

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

        # Chart settings
        col_period, col_display = st.columns(2)

        with col_period:
            period = st.radio(
                "Time Period",
                options=['Daily', 'Weekly', 'Monthly', 'Quarterly'],
                index=0,
                horizontal=True
            )

        with col_display:
            display_mode = st.radio(
                "Display Mode",
                options=['Normalized (Base 100)', 'Absolute Prices'],
                index=0,
                horizontal=True
            )

        # Prepare data for selected items
        chart_data = []
        for item in selected_items:
            item_df = df_all[df_all['Ticker'] == item][['Date', 'Price']].copy()
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
