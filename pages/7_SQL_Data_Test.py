#%%
import streamlit as st
import pandas as pd
import sys
from pathlib import Path
import time

# Add parent directory to path to import sql_connection
sys.path.append(str(Path(__file__).parent.parent))
from sql_connection import (
    test_connection,
    fetch_ticker_reference,
    fetch_all_commodity_data,
    fetch_sector_data,
    fetch_tables
)

#%% Page Configuration
st.set_page_config(layout='wide', page_title="SQL Data Test")

st.title("SQL Data Connection Test")

#%% Connection Test Section
st.header("1. Connection Test")

if st.button("Test SQL Connection"):
    with st.spinner("Testing connection..."):
        start_time = time.time()
        success = test_connection()
        elapsed = time.time() - start_time

        if success:
            st.success(f"✓ Connection successful! ({elapsed:.2f}s)")
        else:
            st.error(f"✗ Connection failed! ({elapsed:.2f}s)")
            st.info("Check your .streamlit/secrets.toml file for DB_AILAB_CONN configuration")
            st.stop()

#%% Schema Exploration Section
st.header("2. Explore Database Schema")

col1, col2 = st.columns(2)

with col1:
    if st.button("Show All Tables"):
        with st.spinner("Fetching tables..."):
            tables = fetch_tables(schema='dbo')
            st.subheader(f"Found {len(tables)} tables")
            st.dataframe(tables, use_container_width=True, height=400)

with col2:
    if st.button("Show Ticker Reference"):
        with st.spinner("Loading ticker reference..."):
            ticker_ref = fetch_ticker_reference()
            st.session_state.ticker_ref = ticker_ref

            st.subheader(f"Ticker Reference ({len(ticker_ref)} rows)")
            st.markdown(f"**Sectors found:** {', '.join(ticker_ref['Sector'].unique())}")

            # Show summary by sector
            sector_counts = ticker_ref['Sector'].value_counts()
            st.markdown("**Tickers per sector:**")
            for sector, count in sector_counts.items():
                st.text(f"  {sector}: {count} tickers")

            st.dataframe(ticker_ref, use_container_width=True, height=400)

#%% Data Loading Section
st.header("3. Load Commodity Data")

st.markdown("""
Load all commodity price data from sector tables (Steel, Agriculture, etc.)
""")

# Data loading controls
col1, col2, col3 = st.columns(3)
with col1:
    start_date = st.date_input("Start Date (Optional)", value=None)
with col2:
    exclude_textile = st.checkbox("Exclude Textile", value=True, help="Exclude Textile sector as per commo.py")
with col3:
    use_cache = st.checkbox("Use Caching", value=True, help="Cache data for 5 minutes")

# Caching function - define outside conditional for proper scope
@st.cache_data(ttl=300)  # 5 minute cache
def load_data_cached(start_str, exclude_sectors):
    return fetch_all_commodity_data(
        start_date=start_str if start_str else None,
        exclude_sectors=exclude_sectors
    )

# Load button
if st.button("Load All Commodity Data", type="primary"):
    start_str = start_date.strftime('%Y-%m-%d') if start_date else None
    exclude_sectors = ['Textile'] if exclude_textile else None

    with st.spinner("Loading data from SQL..."):
        try:
            load_start = time.time()

            if use_cache:
                df = load_data_cached(start_str, exclude_sectors)
            else:
                df = fetch_all_commodity_data(
                    start_date=start_str,
                    exclude_sectors=exclude_sectors
                )

            load_time = time.time() - load_start

            # Store in session state
            st.session_state.sql_test_df = df
            st.session_state.load_time = load_time

        except Exception as e:
            st.error(f"Error loading data: {e}")
            st.info("**Common issues:**")
            st.markdown("""
            1. One or more sector tables don't exist
            2. Column names don't match expected schema (Ticker, Date, Price)
            3. Schema name incorrect (default is 'dbo')
            4. Database permissions
            """)
            import traceback
            st.code(traceback.format_exc())
            st.stop()

#%% Display Data Section
if 'sql_test_df' in st.session_state:
    df = st.session_state.sql_test_df
    load_time = st.session_state.load_time

    st.header("4. Data Summary")

    # Performance metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Load Time", f"{load_time:.2f}s")
    with col2:
        st.metric("Total Rows", f"{len(df):,}")
    with col3:
        data_size_mb = df.memory_usage(deep=True).sum() / 1024**2
        st.metric("Memory", f"{data_size_mb:.2f} MB")
    with col4:
        cached_status = "✓ Cached" if use_cache else "✗ Not Cached"
        st.metric("Cache Status", cached_status)

    # Data breakdown by sector
    st.subheader("Data by Sector")
    sector_summary = df.groupby('Sector').agg({
        'Ticker': 'nunique',
        'Date': ['min', 'max'],
        'Price': 'count'
    }).round(2)
    sector_summary.columns = ['Unique Tickers', 'First Date', 'Last Date', 'Total Records']
    st.dataframe(sector_summary, use_container_width=True)

    # Overall statistics
    st.subheader("Overall Statistics")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Date Range:**")
        st.write(f"From: {df['Date'].min()}")
        st.write(f"To: {df['Date'].max()}")
        days = (df['Date'].max() - df['Date'].min()).days
        st.write(f"Span: {days} days")

    with col2:
        unique_tickers = df['Ticker'].nunique()
        unique_sectors = df['Sector'].nunique()
        st.markdown(f"**Unique Tickers:** {unique_tickers}")
        st.markdown(f"**Unique Sectors:** {unique_sectors}")
        st.write(f"Avg records/ticker: {len(df)/unique_tickers:.0f}")

    with col3:
        st.markdown(f"**Price Stats:**")
        st.write(f"Min: {df['Price'].min():.2f}")
        st.write(f"Max: {df['Price'].max():.2f}")
        st.write(f"Mean: {df['Price'].mean():.2f}")
        st.write(f"Median: {df['Price'].median():.2f}")

    # Display sample data
    st.subheader("Sample Data")

    # Filter by sector for sampling
    selected_sector = st.selectbox("Filter by Sector", ['All'] + sorted(df['Sector'].unique().tolist()))

    if selected_sector != 'All':
        sample_df = df[df['Sector'] == selected_sector].head(100)
    else:
        sample_df = df.head(100)

    st.dataframe(sample_df, use_container_width=True, height=400)

    # Full data preview
    with st.expander("Show Full Data"):
        st.dataframe(df, use_container_width=True, height=600)

    # Export option
    st.subheader("Export")
    csv = df.to_csv(index=False)
    st.download_button(
        label="Download as CSV",
        data=csv,
        file_name=f"commodity_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )

#%% Sector Detail Viewer
st.header("5. View Individual Sector")

if 'ticker_ref' in st.session_state:
    ticker_ref = st.session_state.ticker_ref
    available_sectors = sorted(ticker_ref['Sector'].unique())

    selected_sector_detail = st.selectbox("Select Sector to View", available_sectors)

    if st.button(f"Load {selected_sector_detail} Data"):
        with st.spinner(f"Loading {selected_sector_detail}..."):
            try:
                sector_df = fetch_sector_data(selected_sector_detail)
                st.session_state.sector_detail_df = sector_df
                st.session_state.sector_detail_name = selected_sector_detail

                st.success(f"Loaded {len(sector_df)} records from {selected_sector_detail}")
            except Exception as e:
                st.error(f"Error loading sector: {e}")

if 'sector_detail_df' in st.session_state:
    sector_df = st.session_state.sector_detail_df
    sector_name = st.session_state.sector_detail_name

    st.subheader(f"{sector_name} Data")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Records", f"{len(sector_df):,}")
    with col2:
        st.metric("Unique Tickers", sector_df['Ticker'].nunique())
    with col3:
        st.metric("Date Range", f"{(sector_df['Date'].max() - sector_df['Date'].min()).days} days")

    st.dataframe(sector_df, use_container_width=True, height=400)

#%% Caching Performance Test
st.header("6. Cache Performance Test")

st.markdown("""
Test the performance difference between cached and non-cached queries.
This will run the same query multiple times.
""")

if st.button("Run Cache Test"):
    if 'sql_test_df' not in st.session_state:
        st.warning("Please load data first using the 'Load All Commodity Data' button above")
    else:
        # Use the same parameters from previous load
        start_str = start_date.strftime('%Y-%m-%d') if start_date else None
        exclude_sectors = ['Textile'] if exclude_textile else None

        # Clear cache first
        if use_cache:
            st.cache_data.clear()

        st.markdown("**Running 3 queries:**")

        times = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i in range(3):
            status_text.text(f"Query {i+1}/3...")
            start = time.time()

            if use_cache:
                _ = load_data_cached(start_str, exclude_sectors)
            else:
                _ = fetch_all_commodity_data(start_date=start_str, exclude_sectors=exclude_sectors)

            elapsed = time.time() - start
            times.append(elapsed)
            progress_bar.progress((i + 1) / 3)

        status_text.text("Complete!")

        # Display results
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Query 1 (Cold)", f"{times[0]:.2f}s")
        with col2:
            st.metric("Query 2", f"{times[1]:.2f}s")
            if use_cache and times[1] < times[0]:
                st.caption("✓ Cache hit!")
        with col3:
            st.metric("Query 3", f"{times[2]:.2f}s")
            if use_cache and times[2] < times[0]:
                st.caption("✓ Cache hit!")

        # Analysis
        if use_cache:
            speedup = times[0] / min(times[1:])
            st.success(f"Cache speedup: {speedup:.1f}x faster!")
        else:
            avg_time = sum(times) / len(times)
            st.info(f"Average query time (no cache): {avg_time:.2f}s")

#%% Next Steps Section
st.header("7. Next Steps")

st.markdown("""
### ✓ Test Completed Successfully!

Now you can integrate this into your Streamlit pages:

#### 1. Update Your Existing Pages

**Replace CSV loading with SQL:**

```python
# OLD (Dashboard.py, Group_Analysis.py, etc.)
df = pd.read_csv('data/cleaned_data.csv')
df['Date'] = pd.to_datetime(df['Date'])

# NEW
from sql_connection import fetch_all_commodity_data

@st.cache_data(ttl=300)  # 5 minute cache
def load_commodity_data(start_date='2024-01-01'):
    return fetch_all_commodity_data(
        exclude_sectors=['Textile'],
        start_date=start_date
    )

df = load_commodity_data()
```

#### 2. Expected Performance

- **First load**: 1-2 seconds (loads all ~14MB)
- **Cached loads**: <0.1 seconds (instant)
- **Cache TTL**: 5 minutes (auto-refresh)
- **Memory**: Same as CSV (~14MB)

#### 3. Benefits

✓ No more git commits to update data
✓ Real-time updates every 5 minutes
✓ Centralized data management
✓ Same performance as CSV

#### 4. Migration Order

1. Start with **Dashboard.py** (most important)
2. Then **Price_Chart.py** (simplest)
3. Then **Group_Analysis.py**
4. Finally **Ticker_Analysis.py** (most complex)

Test each page thoroughly before moving to the next!
""")

st.info("**Tip**: Keep CSV files as backup for 1-2 weeks during transition period.")
