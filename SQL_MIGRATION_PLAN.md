# SQL Migration Plan - Commodity Dashboard

## Overview

This document outlines the phased approach to migrate from CSV files to SQL Server as the primary data source.

**Total Data Size**: ~14MB (all commodity prices, all tickers, all dates)
**Performance Impact**: Negligible with proper caching

---

## Phase 0: Prerequisites ✓

- [x] Create `sql_connection.py` utility module
- [x] Add `DB_AILAB_CONN` to `.streamlit/secrets.toml`
- [x] Add `pymssql>=2.2.0` to `requirements.txt`
- [x] Create test page (`pages/7_SQL_Data_Test.py`)

---

## Phase 1: SQL Schema Setup (TODO)

### 1.1 Identify SQL Tables

You need to identify the actual table names in your SQL Server database. Based on your current CSV structure:

**Current CSV**: `data/cleaned_data.csv`
- Columns: Date, Ticker, Price, Group, Region, Sector

**Expected SQL Table** (to be confirmed):
```sql
-- Example table structure
dbo.Commodity_Prices
    Date        DATETIME
    Ticker      VARCHAR(50)
    Price       FLOAT
    [Group]     VARCHAR(100)  -- Note: "Group" is a reserved word, may need brackets
    Region      VARCHAR(100)
    Sector      VARCHAR(100)
```

### 1.2 Update `sql_connection.py`

Once you identify the correct table name, update the `fetch_commodity_prices()` function:

```python
def fetch_commodity_prices(...):
    # Line 119: Update table name
    qualified_table = "YOUR_ACTUAL_TABLE_NAME"  # e.g., "Commodity_Prices"

    # Line 125: Update column names to match SQL schema
    clauses = [
        "SELECT Date, Ticker, Price, [Group], Region, Sector",  # Match exact column names
        ...
    ]
```

### 1.3 Test Connection

Run the test page to verify:
```bash
streamlit run pages/7_SQL_Data_Test.py
```

1. Click "Test SQL Connection" - should show ✓
2. Click "Load Data from SQL" - should load data successfully
3. Verify data structure matches CSV structure
4. Run "Cache Test" - should see significant speedup on cached queries

---

## Phase 2: Create Data Loader Module

Create a centralized data loading module that can switch between CSV and SQL.

**File**: `data_loader.py`

```python
import streamlit as st
import pandas as pd
from sql_connection import fetch_commodity_prices

# Configuration flag
USE_SQL = False  # Toggle this to switch between CSV and SQL

@st.cache_data(ttl=300)  # 5 minute cache
def load_commodity_data(start_date='2024-01-01'):
    """Load commodity price data from SQL or CSV.

    Args:
        start_date: Filter data from this date onwards

    Returns:
        DataFrame with columns: Date, Ticker, Price, Group, Region, Sector
    """
    if USE_SQL:
        # Load from SQL Server
        df = fetch_commodity_prices(start_date=start_date)
        # Ensure Date column is datetime
        df['Date'] = pd.to_datetime(df['Date'])
    else:
        # Load from CSV (fallback)
        df = pd.read_csv('data/cleaned_data.csv')
        df['Date'] = pd.to_datetime(df['Date'])
        df = df[df['Date'] >= start_date]

    return df

@st.cache_data(ttl=300)
def load_classification_data():
    """Load commodity classification from SQL or Excel."""
    if USE_SQL:
        # TODO: Implement SQL version
        from sql_connection import fetch_commodity_classification
        return fetch_commodity_classification()
    else:
        # Load from Excel (fallback)
        import openpyxl
        return pd.read_excel('commo_list.xlsx')
```

**Benefits**:
- Single toggle to switch between CSV/SQL
- Consistent caching strategy
- Easy rollback if SQL has issues
- Keeps existing code structure intact

---

## Phase 3: Page-by-Page Migration

Migrate pages one at a time, testing thoroughly after each migration.

### Priority Order:

1. **Dashboard.py** (Homepage) - Most critical, highest traffic
2. **pages/1_Price_Chart.py** - Simple data requirements
3. **pages/2_Group_Analysis.py** - Medium complexity
4. **pages/3_Ticker_Analysis.py** - Most complex, test last

### Migration Pattern for Each Page:

**Before**:
```python
# Old approach - direct CSV loading
df = pd.read_csv('data/cleaned_data.csv')
df['Date'] = pd.to_datetime(df['Date'])
```

**After**:
```python
# New approach - use data_loader
from data_loader import load_commodity_data

df = load_commodity_data(start_date='2024-01-01')
```

### Testing Checklist (per page):

- [ ] Data loads successfully
- [ ] All charts render correctly
- [ ] Filters work as expected
- [ ] Cache hit rate is high (test with cache test)
- [ ] No performance degradation
- [ ] Error handling works (try disconnecting from SQL)

---

## Phase 4: Dashboard Migration Example

### Dashboard.py Changes

**Step 1**: Add import at top
```python
from data_loader import load_commodity_data, load_classification_data
```

**Step 2**: Replace data loading function

**OLD** (Lines ~30-40):
```python
@st.cache_data
def load_data():
    df = pd.read_csv('data/cleaned_data.csv')
    df['Date'] = pd.to_datetime(df['Date'])
    classification = pd.read_excel('commo_list.xlsx')
    return df, classification
```

**NEW**:
```python
@st.cache_data
def load_data():
    df = load_commodity_data(start_date='2024-01-01')
    classification = load_classification_data()
    return df, classification
```

**Step 3**: Test thoroughly

```bash
# Test locally first
streamlit run Dashboard.py

# Verify:
# - Latest news loads
# - Market movers display
# - Commodity swings calculate correctly
# - Quick viewers work
```

**Step 4**: Deploy incrementally

```bash
# Option A: Toggle in production
# Set USE_SQL = True in data_loader.py
# Git commit and push
# Monitor for 24 hours

# Option B: Gradual rollout
# Keep CSV as default (USE_SQL = False)
# Only enable SQL for testing phase
```

---

## Phase 5: Performance Optimization

### 5.1 Caching Strategy

**Current CSV approach** (inefficient):
- Loads entire CSV every time
- No TTL, cached until app restart

**SQL approach** (optimized):
```python
@st.cache_data(ttl=300)  # 5 min cache
def load_commodity_data(start_date):
    # Only load data after start_date
    return fetch_commodity_prices(start_date=start_date)

# Usage:
# Page 1: load_commodity_data('2024-01-01')  -> Cache miss, load from SQL
# Page 2: load_commodity_data('2024-01-01')  -> Cache hit! Instant
# Page 3: load_commodity_data('2023-01-01')  -> Cache miss (different params)
```

### 5.2 Data Filtering Best Practices

**❌ Bad** - Load everything then filter in pandas:
```python
df = fetch_commodity_prices()  # Loads all data (14MB)
df = df[df['Date'] >= '2024-01-01']  # Filter in memory
```

**✓ Good** - Filter at SQL level:
```python
df = fetch_commodity_prices(start_date='2024-01-01')  # Only loads what's needed
```

**✓ Better** - Use specific ticker filters when possible:
```python
# Ticker Analysis page - only needs specific tickers
df = fetch_commodity_prices(
    start_date='2024-01-01',
    tickers=['HPG_Input', 'HPG_Output']  # Much smaller dataset
)
```

### 5.3 Expected Performance

| Scenario | Load Time | Memory | Cacheable |
|----------|-----------|--------|-----------|
| CSV (current) | 0.3-0.5s | 14MB | Yes (forever) |
| SQL (first load) | 1-2s | 14MB | Yes (5 min TTL) |
| SQL (cached) | <0.1s | 14MB | Yes |
| SQL (filtered) | 0.5-1s | 2-5MB | Yes |

**Conclusion**: SQL with caching performs similarly to CSV, with benefits:
- ✓ Real-time data updates (no git commits needed)
- ✓ Better filtering capabilities
- ✓ Scalable to larger datasets
- ✓ Centralized data management

---

## Phase 6: MongoDB vs SQL Decision

You currently have:
- **MongoDB**: Ticker mappings, reports
- **SQL**: Commodity prices (to be added)

**Recommendation**: Keep both

| Data Type | Storage | Reason |
|-----------|---------|--------|
| Commodity Prices | SQL | Large timeseries, analytical queries |
| Ticker Mappings | MongoDB | Document structure, frequent updates via admin |
| Reports | MongoDB | Document structure, JSON metadata |
| Classification | Excel → SQL | Small reference table, rarely changes |

**Future consideration**: If SQL has classification/mapping tables, you could consolidate.

---

## Phase 7: Rollback Plan

If SQL migration causes issues:

### Immediate Rollback (1 minute):
```python
# In data_loader.py
USE_SQL = False  # Switch back to CSV

# Git commit and push
git add data_loader.py
git commit -m "Rollback to CSV data loading"
git push
```

### Keep CSV Files as Backup:
- Don't delete `data/cleaned_data.csv`
- Keep data update scripts functional
- Maintain dual-load capability for 1-2 months

---

## Phase 8: Cloud Deployment Checklist

### Streamlit Cloud Configuration:

1. **Add SQL connection to Secrets**:
   ```toml
   DB_AILAB_CONN = "DRIVER={ODBC Driver 18 for SQL Server};SERVER=tcp:dcdwhprod.database.windows.net,1433;DATABASE=dclab;UID=dclab_readonly;PWD=DHS#@vGESADdf!;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
   ```

2. **Verify SQL Server Firewall**:
   - Ensure Streamlit Cloud IPs are whitelisted
   - Test connection from cloud environment first

3. **Monitor Performance**:
   - Check app logs for SQL connection errors
   - Monitor cache hit rates
   - Watch for timeout issues

4. **Set Connection Timeout**:
   - Current: 30 seconds (good for initial load)
   - Consider 60s for large queries

---

## Phase 9: Next Steps Summary

### Immediate (This Session):
1. ✓ SQL connection utility created
2. ✓ Test page created
3. Run test page and verify connection works

### Short Term (Next Session):
1. Identify actual SQL table names
2. Update `sql_connection.py` with correct schema
3. Create `data_loader.py` module
4. Test with Dashboard.py first

### Medium Term:
1. Migrate remaining pages one by one
2. Monitor performance for 1 week
3. Set `USE_SQL = True` as default
4. Keep CSV as backup for 1 month

### Long Term:
1. Remove CSV files once confident
2. Add more SQL tables (classification, mappings)
3. Optimize queries with indexes
4. Consider materialized views for complex aggregations

---

## FAQ

### Q: Will 14MB slow down my app?
A: No. With `@st.cache_data(ttl=300)`, data loads once every 5 minutes and is shared across all users. Subsequent page loads are instant.

### Q: What if SQL Server goes down?
A: Keep `USE_SQL = False` as fallback. Your CSV files continue working. SQL downtime = 1 minute to rollback.

### Q: How often should I refresh the cache?
A: TTL=300 (5 minutes) is ideal balance:
- Fresh enough for near real-time updates
- Long enough to minimize SQL queries
- Adjust based on data update frequency

### Q: Should I migrate everything at once?
A: No. Start with test page, then Dashboard, then one page at a time. This minimizes risk and allows testing each migration.

### Q: What about the 14MB data transfer cost?
A: Azure SQL egress within same region is free. If Streamlit Cloud is in different region, 14MB every 5 minutes = negligible cost (~$0.01/day).

---

## Support

If you encounter issues:
1. Check test page first (`pages/7_SQL_Data_Test.py`)
2. Verify connection string in secrets.toml
3. Check SQL Server firewall rules
4. Review error messages in Streamlit logs
5. Rollback to CSV if needed (`USE_SQL = False`)
