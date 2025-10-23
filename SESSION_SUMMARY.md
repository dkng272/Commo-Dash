# Commodity Dashboard - Technical Summary

## Overview

Commodity price tracking and analysis system with Vietnamese stock ticker integration. Tracks commodity prices from SQL Server, creates equal-weighted indexes, maps to stock tickers, and analyzes correlations with stock performance.

**Tech Stack**: Streamlit + SQL Server + MongoDB + Plotly

---

## Project Structure

```
Commo Dash/
├── Dashboard.py                    # Homepage (market movers, quick views)
├── pages/
│   ├── 1_Price_Chart.py           # Individual commodity viewer (with st.fragment)
│   ├── 2_Group_Analysis.py        # Commodity group deep dive
│   ├── 3_Ticker_Analysis.py       # Stock ticker analysis
│   ├── 4_Reports_Summary.py       # Research reports browser
│   ├── 5_Reports_Upload_Admin.py  # Upload PDFs to MongoDB
│   ├── 6_Ticker_Mapping_Admin.py  # Ticker mapping editor (MongoDB)
│   └── 7_Commodity_List_Admin.py  # Commodity classification editor (MongoDB)
├── sql_connection.py              # SQL Server connection & data loading
├── mongodb_utils.py               # MongoDB CRUD operations
├── classification_loader.py       # Dynamic classification loading (MongoDB)
├── commo_dashboard.py             # Index creation functions
├── ssi_api.py                     # Stock price API integration
├── rename_group.py                # Batch group rename script (MongoDB)
├── check_groups.py                # List all groups and items (utility)
└── news/
    ├── reports/                   # PDF storage
    ├── pdf_processor.py           # PDF processing script
    └── prompts/                   # AI prompt templates
        ├── commodity_prompts.py   # Multi-sector report prompts
        └── sector_prompts.py      # Sector-focused report prompts
```

---

## Current Session Updates (2025-10-23)

### 1. Flexible Timeframe Selection

**Data Loading Changes**:
- Modified `classification_loader.py` to fetch ALL available data by default
- `load_sql_data_raw(start_date=None)` - Removed hardcoded `'2024-01-01'`
- Enables flexible timeframe filtering in-memory (no SQL re-query needed)

**Analysis Pages (Price Chart, Group Analysis, Ticker Analysis)**:
- Added timeframe selector: YTD, 1Y, 3Y, All Time
- Location: Sidebar (top section, purple gradient header)
- Behavior: Filters cached data in-memory (instant switching)

**Dashboard (Quick View Page)**:
- Uses date picker widget (not preset timeframes)
- Default: `2024-01-01` (ensures 150D calculations work)
- Max date: 150 days before today (guarantees 151+ days)
- Shows data range feedback: "📅 Data range: X days (150D metrics available)"
- Rationale: Dashboard needs consistent data for all metrics (5D/10D/50D/150D)

**YTD Column Added**:
- Price Chart summary table now shows Year-to-Date performance
- Positioned between 1M and 3M columns
- Same color coding: green (positive), red (negative), gray (N/A)

### 2. Performance Optimization with st.fragment

**Price Chart Page**:
- Implemented `@st.fragment` decorator for timeframe + table + chart section
- Only fragment re-runs on timeframe change (~100-200ms vs ~1-2s full page reload)
- Sidebar filters remain stable (no flickering)

**150D Lookback Window Architecture**:

```python
# User selects: YTD (2025-01-01)
display_start_date = '2025-01-01'          # User's choice
calc_start_date = '2024-08-04'             # Auto: display - 150 days

# Two filtered datasets
df_calc = df_all[Date >= calc_start_date]   # For calculations (with lookback)
df_display = df_calc[Date >= display_start_date]  # For chart display
```

**Data Usage Split**:
- **Summary Table**: Uses `df_calc` (150D lookback) for accurate metrics
- **Price Chart**: Uses `df_display` (user's selected timeframe)
- **Benefit**: All metrics (1D, 1W, 1M, YTD, 3M, 6M, 1Y) always accurate

**UI Changes**:
- Timeframe selector moved from sidebar to main content (above summary table)
- Horizontal radio buttons for compact layout
- Shows two captions:
  - "📅 Display from: [date]" - What chart shows
  - "📊 Calculations from: [date]" - What table uses

### Design Decisions - Timeframe Selectors

| Page | Selector Type | Rationale |
|------|--------------|-----------|
| Dashboard | Date picker (fixed default) | Quick view - needs consistent 150D metrics |
| Price Chart | Preset + st.fragment | Fast switching, accurate long-term metrics |
| Group Analysis | Preset (sidebar) | Standard analysis periods |
| Ticker Analysis | Preset (sidebar) | Stock correlation analysis |

**Key Benefits**:
1. No SQL re-queries - all timeframe changes filter in-memory
2. Accurate metrics - 150D lookback ensures sufficient data
3. Fast switching - st.fragment prevents sidebar flicker
4. User clarity - Dashboard picker shows 150D requirement

### 3. Group Name Optimization for AI Routing

**Problem**: Generic or ambiguous group names caused AI misclassification when routing news from PDF reports.

**Solution**: Renamed 12 commodity groups (out of 28 total) to improve AI routing accuracy.

**Phase 1 - Ambiguity Fixes** (High Priority):
1. Liquids Shipping → **Crude and Product Tankers**
2. Products → **Refined Petroleum Products**
3. PVC → **Plastics and Polymers**
4. Yellow P4 → **Phosphorus Products**
5. Pangaseus → **Pangasius Aquaculture** (typo fix)

**Phase 2 - Industry Alignment** (Medium Priority):
6. Bulk Shipping → **Dry Bulk Shipping**
7. Met Coal → **Metallurgical Coal**
8. Long Steel → **Construction Steel**
9. Grain → **Grains and Oilseeds**
10. Coal → **Thermal Coal**

**Phase 3 - Polish** (Low Priority):
11. Oil → **Crude Oil**
12. Gas/LNG → **Natural Gas and LNG**
13. Container Shipping → **Container Freight**

**Implementation**:
- Created `rename_group.py` script for batch MongoDB updates
- Updated 3 MongoDB collections:
  - `commodity_classification`: 49 items renamed
  - `ticker_mappings`: 28 documents updated (inputs + outputs)
  - `reports`: 410 report entries updated (nested key renames)
- Updated AI prompts in `news/prompts/`:
  - `commodity_prompts.py`: Removed confusing aliases like "(aka Tankers)"
  - `sector_prompts.py`: Updated mapping examples

**Key Improvements**:
- **Direct keyword matching**: "VLCC rates" → "Crude and Product Tankers" (no mental mapping)
- **Eliminated ambiguity**: "Refined Petroleum Products" vs "Crude and Product Tankers" (clear separation)
- **Industry terminology**: "Metallurgical Coal", "Dry Bulk Shipping" match Bloomberg/Reuters
- **Simplified prompts**: Removed explanatory text, let group names speak for themselves

**Benefits**:
1. Better AI precision - matches specific terms to correct groups
2. Reduced prompt engineering - less explanation needed
3. Clearer taxonomy - shipping types clearly distinguished
4. Self-explanatory names - "Phosphorus Products" > "Yellow P4"

---

## Architecture Overview

### Data Flow

**SQL Server → classification_loader → Pages**:

```
1. SQL returns: Ticker, Date, Price, Name (NO classifications)
2. classification_loader maps: Name → MongoDB item → adds Sector, Group, Region
3. Pages filter: df[df['Name'] == item]
```

**Critical Naming Rule**:
- **Ticker**: Short code (e.g., "ORE62") - internal SQL use only
- **Name**: Descriptive name (e.g., "Ore 62") - **Maps to MongoDB `item` field**
- **Mapping**: Always use `df['Name']` to filter commodities, NEVER `df['Ticker']`

### Two-Layer Caching System

**Problem**: Combined SQL + classifications cached together → classification changes invisible until SQL cache expires (1 hour)

**Solution**:

```python
# Layer 1: Raw SQL data (expensive - cached 1 hour)
@st.cache_data(ttl=3600)
def load_raw_sql_data():
    return load_sql_data_raw()

# Layer 2: Fresh classification (cheap - NOT cached)
def load_data():
    df_raw = load_raw_sql_data()  # From cache
    df = apply_classification(df_raw)  # Fresh, uses 60s cached MongoDB
    return df
```

**Benefits**:
- SQL queries: 1 hour cache (expensive)
- Classifications: 60 seconds cache (cheap)
- Classification changes visible in ~60 seconds without re-querying SQL

**Pages Using Two-Layer Cache**: Dashboard, Price Chart, Group Analysis, Ticker Analysis

### MongoDB Collections

**Database**: `commodity_dashboard`

**1. ticker_mappings** (57 documents):

```json
{
  "ticker": "HPG",
  "inputs": [{"group": "Iron Ore", "region": "Global", "item": "Ore 62", "sensitivity": 0.7}],
  "outputs": [{"group": "HRC", "region": "Vietnam", "item": "HRC HPG", "sensitivity": null}]
}
```

- Cache: 5 minutes
- Admin: pages/6_Ticker_Mapping_Admin.py

**2. commodity_classification** (~100 items):

```json
{
  "item": "Ore 62",
  "sector": "Steel Material",
  "group": "Iron Ore",
  "region": "China"
}
```

- Cache: 60 seconds
- Unique index: `item` field
- Hierarchy: Sector → Group → Region → Item
- Admin: pages/7_Commodity_List_Admin.py

---

## Page Summaries

### Dashboard (Homepage)
- Market movers: Top 5 stocks by spread (5D/10D/50D/150D)
- Commodity swings: Top 5 groups by absolute change
- Quick viewers: Dropdown navigation with isolated fragment reruns
- Latest news: 20 most recent items, collapsed by default
- Date picker: Fixed 2024-01-01 default (ensures 150D metrics)

### Price Chart (Individual Commodity Viewer)
- Cascading filters: Sector → Group → Region → Items
- Summary table: Shows all filtered items with performance metrics (1D/1W/1M/YTD/3M/6M/1Y)
- Chart section: Multi-select items, time period aggregation (Daily/Weekly/Monthly/Quarterly)
- Display modes: Normalized (Base 100) or Absolute Prices
- st.fragment: Fast timeframe switching without sidebar reload

### Group Analysis
- Group selector: View any commodity group
- View modes: Index or Components (individual tickers)
- Regional tabs: Compare price movements across regions
- Latest news: Group-specific news feed

### Ticker Analysis
- Stock ticker selector: Analyze commodity exposure for any ticker
- Summary metrics: Input/Output/Spread changes across timeframes
- Combined view: 3-panel subplot (Commodities, Spread, Stock Price)
- Correlations: Price level & returns correlations
- Aggregation: Sensitivity-weighted or equal-weighted indexes

### Admin Pages
- **Ticker Mapping Admin**: Edit stock ticker input/output mappings (MongoDB)
- **Commodity List Admin**: Add/edit/rename commodity classifications (MongoDB)
- **Reports Upload Admin**: Upload PDF reports, AI summarization, save to MongoDB

---

## Key Functions Reference

### Data Loading

```python
load_sql_data_raw(start_date=None)
# Returns: DataFrame with Ticker, Date, Price, Name (NO classifications)
# Cached: 1 hour (expensive SQL query)

apply_classification(df)
# Returns: DataFrame with Sector, Group, Region added
# NOT cached - re-applies fresh using 60s cached MongoDB data

load_ticker_mappings()
# Returns: List[Dict] of ticker mappings
# Cached: 5 minutes

load_commodity_classifications()
# Returns: List[Dict] of classifications
# Cached: 60 seconds
```

### Index Creation

```python
create_equal_weight_index(df, group, base_value=100)
# Returns: DataFrame with Date, Index_Value
# Method: Equal-weight daily returns, cumulative product

create_aggregated_index(items_list, df, all_indexes, regional_indexes)
# Returns: DataFrame with Date, Price
# Method: Sensitivity-weighted (if provided) or equal-weighted
```

### Stock Prices

```python
fetch_historical_price(ticker, start_date='2024-01-01')
# Returns: DataFrame with Date, Price
# Source: TCBS/SSI API
```

---

## Deployment

### Requirements

```txt
streamlit>=1.30.0
pandas>=2.0.0
plotly>=5.18.0
pymongo>=4.6.0      # MongoDB
pymssql>=2.2.0      # SQL Server
PyMuPDF>=1.23.0     # PDF processing
openai>=1.0.0       # AI summarization
openpyxl>=3.1.0
```

### Secrets Configuration

**Local**: `.streamlit/secrets.toml`

```toml
MONGODB_URI = "mongodb+srv://..."
DB_AILAB_CONN = "DRIVER={ODBC Driver 18 for SQL Server};SERVER=..."
```

**Streamlit Cloud**: Add both secrets to dashboard settings

---

## Common Workflows

### 1. Edit Ticker Mapping
1. Open Ticker Mapping Admin page
2. Select ticker or add new
3. Configure inputs/outputs with dropdowns
4. Save → Changes live immediately (no deployment)

### 2. Update Classification
1. Open Commodity List Admin page
2. Edit/Add/Rename item
3. Save → Changes live in ~60 seconds (classification cache TTL)

### 3. Add News Report
```bash
cd news
# Place PDF in reports/ folder
python pdf_processor.py
# Updates all_reports.json + uploads to MongoDB
```

### 4. Change Analysis Timeframe
- **Dashboard**: Select date from picker (max 150 days before today)
- **Other pages**: Choose preset (YTD/1Y/3Y/All Time)
- All changes filter in-memory (no SQL re-query)

### 5. Rename Commodity Group
1. Edit `rename_group.py` to specify old and new group names
2. Run script: `python rename_group.py`
3. Script updates all 3 MongoDB collections:
   - commodity_classification
   - ticker_mappings (inputs + outputs)
   - reports (commodity_news keys)
4. Restart Streamlit app or wait 60 seconds for cache refresh
5. Update AI prompts if needed (news/prompts/)

---

## Previous Major Updates Summary

### SQL Server Integration (Oct 2024)
- Migrated all 4 pages from CSV to SQL Server
- Parallel loading: 10-15s vs 30s sequential
- 1-hour shared cache across pages
- Test page for connection validation

### MongoDB Integration (Sep 2024)
- Migrated ticker mappings + classifications to MongoDB
- Real-time admin pages (no git commits needed)
- Two-layer caching architecture
- Excel file removal (single source of truth)

### UI/UX Improvements (Aug-Sep 2024)
- Purple gradient headers (consistent styling)
- Compact padding, removed emojis
- Tabbed interface for reduced scrolling
- Color-coded metrics (green/red/gray)
- Scrollable news sections

### Performance Optimization (Aug 2024)
- @st.fragment decorator for quick viewers
- Isolated reruns (no full page reload)
- Dropdown-only navigation (removed slow buttons)

---

## Key Lessons Learned

1. **Column Mapping**: Always use `df['Name']` (from SQL) to map to MongoDB `item` field
2. **Two-Layer Caching**: Split expensive (SQL) from cheap (classification) operations
3. **Timeframe Flexibility**: Load all data once, filter in-memory for instant switching
4. **st.fragment**: Use for sections that change independently (prevents sidebar flicker)
5. **150D Lookback**: Essential for accurate long-term metrics with short display periods
6. **Group Naming for AI**: Descriptive, self-explanatory names improve AI routing accuracy. Avoid generic terms ("Products", "PVC") and confusing aliases ("aka Tankers").

---

**Last Updated**: 2025-10-23

**Current State**:
- ✅ Flexible timeframe selection (in-memory filtering)
- ✅ st.fragment optimization (Price Chart page)
- ✅ 150D lookback window (accurate metrics)
- ✅ YTD performance column
- ✅ Dashboard quick view defaults (5D)
- ✅ Group name optimization (12 groups renamed for AI routing)
- ✅ AI prompt simplification (removed aliases, improved clarity)
- ✅ SQL Server integration (1-hour cache)
- ✅ MongoDB classifications (60s cache)
- ✅ Two-layer caching architecture
