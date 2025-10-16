#%%
import streamlit as st
import sys
from pathlib import Path
import time

# Add parent directory to path to import sql_connection
sys.path.append(str(Path(__file__).parent.parent))
from sql_connection import (
    test_connection,
    fetch_ticker_reference,
    fetch_all_commodity_data
)

#%% Page Configuration
st.set_page_config(layout='wide', page_title="SQL Data Test")

st.title("SQL Connection Test")

st.markdown("""
Simple test page to verify SQL Server connection and data loading.
""")

#%% Test 1: Connection Test
st.header("1. Connection Test")

if st.button("Test SQL Connection", type="primary"):
    with st.spinner("Testing connection..."):
        start_time = time.time()
        success = test_connection()
        elapsed = time.time() - start_time

        if success:
            st.success(f"✓ Connection successful! ({elapsed:.2f}s)")
        else:
            st.error(f"✗ Connection failed! ({elapsed:.2f}s)")
            st.info("**Check:**")
            st.markdown("""
            - `.streamlit/secrets.toml` has DB_AILAB_CONN configured
            - SQL Server firewall allows Streamlit Cloud IPs
            - Credentials are correct
            """)

#%% Test 2: Ticker Reference
st.header("2. Ticker Reference")

if st.button("Load Ticker Reference"):
    with st.spinner("Loading ticker reference..."):
        try:
            start_time = time.time()
            ticker_ref = fetch_ticker_reference()
            elapsed = time.time() - start_time

            st.success(f"✓ Loaded {len(ticker_ref)} tickers in {elapsed:.2f}s")

            # Show sectors found
            sectors = ticker_ref['Sector'].unique()
            st.markdown(f"**Sectors found ({len(sectors)}):** {', '.join(sorted(sectors))}")

            # Show counts per sector
            sector_counts = ticker_ref['Sector'].value_counts()
            st.markdown("**Tickers per sector:**")
            for sector, count in sector_counts.items():
                st.text(f"  {sector}: {count} tickers")

            # Display table
            st.dataframe(ticker_ref, use_container_width=True, height=400)

        except Exception as e:
            st.error(f"Failed to load ticker reference: {e}")
            st.code(str(e))

#%% Test 3: Load All Data
st.header("3. Load All Commodity Data")

st.markdown("""
Test loading all commodity data with parallel processing.
""")

col1, col2 = st.columns(2)
with col1:
    use_parallel = st.checkbox("Use Parallel Loading", value=True, help="Faster loading (10-15s vs 30s)")
with col2:
    exclude_textile = st.checkbox("Exclude Textile", value=True)

if st.button("Load All Data", type="primary"):
    exclude_sectors = ['Textile'] if exclude_textile else None

    with st.spinner("Loading all commodity data..."):
        try:
            start_time = time.time()

            df = fetch_all_commodity_data(
                exclude_sectors=exclude_sectors,
                parallel=use_parallel
            )

            elapsed = time.time() - start_time

            # Success metrics
            st.success(f"✓ Loaded {len(df):,} records in {elapsed:.2f}s")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Rows", f"{len(df):,}")
            with col2:
                st.metric("Unique Tickers", df['Ticker'].nunique())
            with col3:
                st.metric("Sectors", df['Sector'].nunique())
            with col4:
                data_size_mb = df.memory_usage(deep=True).sum() / 1024**2
                st.metric("Memory", f"{data_size_mb:.2f} MB")

            # Date range
            st.markdown(f"**Date Range:** {df['Date'].min()} to {df['Date'].max()}")

            # Sector breakdown
            st.subheader("Data by Sector")
            sector_summary = df.groupby('Sector').agg({
                'Ticker': 'nunique',
                'Date': ['min', 'max'],
                'Price': 'count'
            }).round(2)
            sector_summary.columns = ['Unique Tickers', 'First Date', 'Last Date', 'Total Records']
            st.dataframe(sector_summary, use_container_width=True)

            # Sample data
            st.subheader("Sample Data (First 50 rows)")
            st.dataframe(df.head(50), use_container_width=True, height=300)

        except Exception as e:
            st.error(f"Failed to load data: {e}")
            import traceback
            st.code(traceback.format_exc())

#%% Summary
st.header("4. Summary")

st.markdown("""
### ✓ Tests Complete

If all tests passed, you're ready to integrate SQL into your production pages!

**Next Steps:**
1. Update existing pages to use `fetch_all_commodity_data()` instead of CSV
2. Add caching: `@st.cache_data(ttl=300)`
3. Test each page individually
4. Keep CSV files as backup for 1-2 weeks

**Performance Tips:**
- Use `parallel=True` for faster loading (default)
- Use `start_date` filter to reduce data size
- Cache TTL of 5 minutes balances freshness and performance
""")

st.info("💡 **Tip:** Delete this test page after migration is complete!")
