# Commodity Dashboard - Technical Summary

## Overview
Commodity price tracking and analysis system with Vietnamese stock ticker integration. Tracks commodity prices, creates equal-weighted indexes, maps to stock tickers, and analyzes correlations with stock performance.

---

## Project Structure

```
Commo Dash/
├── data/
│   └── cleaned_data.csv           # Backup (data now from SQL Server)
├── pages/                          # Streamlit pages
│   ├── 1_Price_Chart.py           # Individual commodity price viewer
│   ├── 2_Group_Analysis.py        # Commodity group deep dive
│   ├── 3_Ticker_Analysis.py       # Stock ticker analysis
│   ├── 4_Reports_Summary.py       # Research reports browser
│   ├── 5_Reports_Upload_Admin.py  # Upload PDFs to MongoDB
│   ├── 6_Ticker_Mapping_Admin.py  # Ticker mapping editor (MongoDB)
│   └── 7_Commodity_List_Admin.py  # Commodity classification editor (MongoDB)
├── news/
│   ├── reports/                   # PDF storage
│   └── pdf_processor.py           # PDF processing script
├── Dashboard.py                    # Main dashboard (homepage)
├── sql_connection.py              # SQL Server connection & data loading
├── mongodb_utils.py               # MongoDB connection & CRUD operations
├── commo_dashboard.py             # Index creation functions
├── classification_loader.py       # Dynamic classification loading (MongoDB)
├── ssi_api.py                     # Stock price API integration
└── migrate_commo_list_to_mongodb.py  # One-time migration script
```

---

## MongoDB Integration (Latest Update)

### Purpose
Enable dynamic data management on Streamlit Cloud by storing ticker mappings and commodity classifications in MongoDB instead of local files (JSON/Excel).

### Database Structure
- **Database**: `commodity_dashboard`
- **Collections**:
  - `ticker_mappings` - Stock ticker input/output mappings (57 documents)
  - `commodity_classification` - Commodity classification data (~100 items)

### Collection 1: Ticker Mappings
**Document Schema**:
```json
{
  "ticker": "HPG",
  "inputs": [
    {
      "group": "Iron Ore",
      "region": "Global",
      "item": "Ore 62",
      "sensitivity": 0.7
    }
  ],
  "outputs": [
    {
      "group": "HRC",
      "region": "Vietnam",
      "item": "HRC HPG",
      "sensitivity": null
    }
  ]
}
```

### Collection 2: Commodity Classifications
**Document Schema**:
```json
{
  "item": "Ore 62",
  "sector": "Steel Material",
  "group": "Iron Ore",
  "region": "China"
}
```
- **Unique Index**: `item` field
- **Purpose**: Maps commodity names to Sector/Group/Region hierarchy
- **Admin Page**: pages/7_Commodity_List_Admin.py

### Implementation (`mongodb_utils.py`)

**Key Functions**:
- `load_ticker_mappings()` - Read ticker mappings (cached 5 min)
- `save_ticker_mappings()` - Write ticker mappings (with cache clear)
- `load_commodity_classifications()` - Read classifications (cached 60 seconds)
- `save_commodity_classifications()` - Write classifications (with cache clear)
- `get_mongo_client()` - Connection management

**Configuration**:
- Local: `.streamlit/secrets.toml` with `MONGODB_URI`
- Cloud: Streamlit Cloud secrets with `MONGODB_URI`
- Fallback: Warns if connection string not found

**Files Using MongoDB**:
- `Dashboard.py` - Loads ticker mappings + classifications
- `pages/1_Price_Chart.py` - Loads classifications
- `pages/2_Group_Analysis.py` - Loads classifications
- `pages/3_Ticker_Analysis.py` - Loads ticker mappings + classifications
- `pages/6_Ticker_Mapping_Admin.py` - CRUD for ticker mappings
- `pages/7_Commodity_List_Admin.py` - CRUD for classifications
- `classification_loader.py` - Central classification loading
- `news/pdf_processor.py` - Loads commodity groups

### Workflow
**Before (File-based)**:
1. Edit Excel/JSON locally → Commit → Push → Redeploy

**After (MongoDB)**:
1. Edit on Admin page → Save to MongoDB → Changes live in ~60 seconds ✅

### Two-Layer Caching Architecture
**Problem**: Combined SQL data + classifications cached together → classification changes not visible until SQL cache expires (1 hour)

**Solution**: Split caching into two layers
```python
# Layer 1: Raw SQL data (expensive - cached 1 hour)
@st.cache_data(ttl=3600)
def load_raw_sql_data():
    return load_sql_data_raw(start_date='2024-01-01')

# Layer 2: Fresh classification (cheap - NOT cached)
def load_data():
    df_raw = load_raw_sql_data()  # From cache
    df = apply_classification(df_raw)  # Fresh, uses 60s cached classifications
    return df
```

**Benefits**:
- SQL queries cached 1 hour (expensive operation)
- Classifications cached 60 seconds (cheap operation)
- Combination re-applied fresh → classification changes visible in ~60 seconds
- No need to re-fetch SQL data when classifications change

**Pages Implementing Two-Layer Cache**:
- `Dashboard.py`
- `pages/1_Price_Chart.py`
- `pages/2_Group_Analysis.py`
- `pages/3_Ticker_Analysis.py`

---

## Key Components

### 1. Dashboard (Homepage)
- **Market Movers**: Top 5 stocks by spread (5D/10D/50D/150D)
- **Commodity Index Swings**: Top 5 groups by absolute change
- **Latest Market News**: 20 most recent items across all commodities
- **UI**: Gradient headers, tabbed interface, news cards

### 2. Group Analysis Page
- **Features**:
  - View mode toggle: Index vs Components
  - Component ticker multiselect
  - Regional breakdown tabs
  - Latest news (scrollable, shows all items)
- **Charts**: Plotly line charts with normalized prices

### 3. Ticker Analysis Page
- **Summary Metrics**: Input/Output/Spread changes (5D/10D/50D/150D)
- **Charts**: Input prices, Output prices, normalized to base 100
- **Combined View**: 3-panel subplot (Commodities, Spread, Stock Price)
- **Correlations**: Price level & returns correlations with commodities

### 4. Reports Summary Page
- **Features**:
  - Hierarchical filtering (Source → Series)
  - Multiple sources: JPM, HSBC, etc.
  - Markdown rendering with proper escaping
- **Data Source**: `news/all_reports.json`

### 5. Ticker Mapping Admin Page
- **Features**:
  - Edit ticker input/output mappings
  - Dynamic dropdown filtering (Group → Region → Item)
  - Add/delete tickers
  - Preview JSON before saving
- **Storage**: MongoDB (works on cloud deployment)

### 6. Commodity List Admin Page
- **Features**:
  - View all commodity classifications
  - Edit existing items (Sector/Group/Region)
  - Add new items (manual or from unmapped SQL items)
  - Rename items to fix typos
  - Radio toggle: Select existing or Type new
  - Shows 22 unmapped SQL items for classification
- **Storage**: MongoDB `commodity_classification` collection
- **Refresh Key System**: Prevents state issues during edits
- **UI**: Three-tab interface with session state management

---

## Index Creation Logic

### Equal-Weight Index (`commo_dashboard.py`)
```python
def create_equal_weight_index(df, group_name, base_value=100):
    # 1. Filter by group
    # 2. Pivot to matrix (dates × tickers)
    # 3. Calculate daily returns: pct_change(fill_method=None)
    # 4. Equal-weight average: mean(axis=1, skipna=True)
    # 5. Cumulative product: (1 + returns).cumprod() * base_value
```

### Sensitivity-Weighted Index (Ticker Analysis only)
```python
# Uses sensitivity values from ticker_mappings_final.json
# If sensitivities provided: (returns * weights).sum(axis=1)
# If sensitivities null: Equal-weight (default)
# Validation: Warns if sum(weights) ≠ 1.0 (±0.01 tolerance)
```

### Regional & Sector Indexes
- Regional: `create_regional_indexes()` - Group-Region combinations
- Sector: `create_sector_indexes()` - Highest classification level

---

## Data Schema

### SQL Server Raw Data
```
Ticker  | Date       | Price  | Name
ORE62   | 2024-01-01 | 142.0  | Ore 62
HRCVN   | 2024-01-01 | 550    | HRC HPG
```
- **Source**: SQL Server commodity price tables
- **No classifications**: Sector/Group/Region added by `classification_loader.py`
- **Mapping Key**: `Name` column (NOT `Ticker`)

### MongoDB Classification Data
**Collection**: `commodity_classification`
```json
{
  "item": "Ore 62",
  "sector": "Steel Material",
  "group": "Iron Ore",
  "region": "China"
}
```

**Classification Hierarchy**: Sector → Group → Region → Item

**Data Flow**:
1. SQL returns: `Ticker`, `Date`, `Price`, `Name` (no classifications)
2. `classification_loader.py` maps: `Name` → `item` in MongoDB → adds `Sector`, `Group`, `Region`
3. Pages filter by: `df[df['Name'] == item]` where item comes from MongoDB

---

## Stock Price Integration

### API: TCBS/SSI (`ssi_api.py`)
```python
fetch_historical_price(ticker, start_date='2024-01-01')
# Returns: DataFrame with Date, Price columns
# Timezone handling: Converts to timezone-naive
```

### Global Start Date
- **Default**: `2024-01-01`
- **Applied**: All pages filter data from this date
- **Purpose**: Alignment between commodity and stock data

---

## News System

### PDF Processing (`news/pdf_processor.py`)
- Extracts text from PDF reports (PyMuPDF)
- AI summarization (OpenAI API)
- Classifies by commodity groups
- Outputs: JSON + Markdown

### Consolidated Storage (`all_reports.json`)
```json
[
  {
    "report_date": "2025-10-13",
    "report_file": "JPM_ChinaMetals_2025-10-13.pdf",
    "report_source": "JPM",
    "report_series": "ChinaMetals",
    "report_type": "commodity",
    "commodity_news": {
      "Iron Ore": "Price movements...",
      "Aluminum": "Supply updates..."
    }
  }
]
```

### Dashboard Integration
- `load_latest_news(group)` - Loads news for specific commodity
- `get_all_news_summary()` - Aggregates across all groups
- HTML rendering with proper escaping ($, ~, bold text)

---

## UI/UX Design

### Visual Style
- **Colors**: Purple gradient (`#667eea → #764ba2`) for all section headers
- **Layout**: Wide mode, compact padding
- **Typography**: 18px headers, 13-14px body text
- **No emojis**: Removed from headers and dates

### Components
- **Gradient Headers**: Section dividers with subtle gradients
- **Tabs**: Reduce scrolling (Stock Spreads vs Index Swings)
- **News Cards**: White cards with left border accent, group badges
- **Scrollable Containers**: Max-height with auto-scroll
- **Last Updated**: Timestamp in top-right corner

### HTML Rendering Pattern
```python
# For scrollable sections
st.markdown(f'''
<div style="max-height: 400px; overflow-y: auto;">
  <strong>{date}</strong><br><br>
  {escaped_text}
</div>
''', unsafe_allow_html=True)
```

---

## Technical Decisions

### 1. Aggregation
- **Summary table**: Always aggregates multiple items
- **Combined view**: Always aggregates
- **Individual charts**: User toggle (Index vs Components)

### 2. Spread Calculation
```python
# Formula: Spread = Output - Input (both normalized to 100)
# None values treated as 0
# MA20 smoothing for trend analysis
```

### 3. Correlation Types
- **Price level**: Absolute price correlation
- **Returns**: Daily % change correlation
- **Spread**: Stock vs MA20 spread correlation

### 4. NA Handling
- `skipna=True` in all mean calculations
- Forward-fill for missing dates: `.ffill()`
- Inner join for correlation to ensure alignment

---

## Deployment

### Requirements
```
streamlit>=1.30.0
pandas>=2.0.0
plotly>=5.18.0
pymongo>=4.6.0      # MongoDB integration
pymssql>=2.2.0      # SQL Server integration (NEW)
PyMuPDF>=1.23.0     # PDF processing
openai>=1.0.0       # AI summarization
openpyxl>=3.1.0     # Excel reading
```

### Secrets Configuration
**Local**: `.streamlit/secrets.toml`
```toml
MONGODB_URI = "mongodb+srv://..."
DB_AILAB_CONN = "DRIVER={ODBC Driver 18 for SQL Server};SERVER=tcp:dcdwhprod.database.windows.net,1433;DATABASE=dclab;UID=dclab_readonly;PWD=DHS#@vGESADdf!;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
```

**Streamlit Cloud**: Add both secrets to Secrets section in dashboard

### Git Ignore
```
.streamlit/secrets.toml
__pycache__/
*.pyc
.DS_Store
```

---

## Recent Updates Summary

### Dynamic Commodity Classification System - Phase 1 (Latest Session)
- ✅ **MongoDB Migration**: Migrated `commo_list.xlsx` to MongoDB `commodity_classification` collection
- ✅ **Admin Page**: Created `pages/7_Commodity_List_Admin.py` with three-tab interface
  - View All: Display all classifications in sortable table
  - Edit/Add Item: Edit existing or add new items with radio toggle (Select/Type)
  - Add Unmapped: Shows 22 unmapped SQL items for classification
- ✅ **Rename Feature**: Allows renaming items to fix typos by selecting from SQL list
- ✅ **Two-Layer Caching**: Split SQL data (1 hour cache) from classifications (60s cache)
  - `load_raw_sql_data()` - Caches expensive SQL queries
  - `apply_classification()` - Re-applies fresh classifications using 60s cached MongoDB data
  - Classification changes visible in ~60 seconds without re-querying SQL
- ✅ **Caching Updates**: Implemented two-layer caching in 4 main pages:
  - `Dashboard.py`, `pages/1_Price_Chart.py`, `pages/2_Group_Analysis.py`, `pages/3_Ticker_Analysis.py`
- ✅ **Excel Removal**: Removed all `commo_list.xlsx` references across codebase
  - Updated `classification_loader.py` to load exclusively from MongoDB
  - Removed Excel fallback per user request
  - Updated `news/pdf_processor.py`, `news/pdf_processor_mongodb.py`, `data/data_cleaning.py`
- ✅ **Ticker Mapping Sync**: Updated `pages/6_Ticker_Mapping_Admin.py` to load from MongoDB
  - Changed from `pd.read_excel('commo_list.xlsx')` to `get_classification_df()`
  - Ensures ticker mappings stay in sync with latest classifications
- ✅ **UI/UX Improvements**:
  - Radio button navigation to prevent tab jumping
  - Refresh key system for proper state management (similar to Ticker Mapping Admin)
  - Single input method: Either select existing OR type new (not both)
- ✅ **Migration Script**: Created `migrate_commo_list_to_mongodb.py` for one-time data migration
- ✅ **Documentation**: Created `CLASSIFICATION_REFRESH_GUIDE.md` documenting caching architecture

**Phase 2 Deferred**: Calculated commodities (spreads, ratios, weighted baskets) - to be implemented later

### SQL Server Integration (Previous Session)
- ✅ **SQL Connection Module**: Created `sql_connection.py` for live data loading from SQL Server
- ✅ **Data Source Migration**: Transitioning from CSV files to SQL Server as primary data source
- ✅ **Parallel Loading**: Implemented ThreadPoolExecutor for concurrent sector loading (10-15s vs 30s)
- ✅ **Test Page**: Created `pages/7_SQL_Data_Test.py` for connection validation
- ✅ **Schema Adaptation**: Adapted from pyodbc (work computer) to pymssql (Streamlit Cloud)
- ✅ **Duplicate Chart Fix**: Fixed Streamlit duplicate element ID error in Ticker Analysis page
- ✅ **Requirements Update**: Added `pymssql>=2.2.0` to requirements.txt
- ✅ **Secrets Configuration**: Added `DB_AILAB_CONN` to `.streamlit/secrets.toml`
- ✅ **Price Chart Migration**: Migrated `pages/1_Price_Chart.py` to use SQL data via `load_sql_data_with_classification()`
- ✅ **Classification Fix**: Fixed mapping to use `Name` column (not `Ticker`) to match MongoDB Item field
- ✅ **Caching Strategy**: Implemented 1-hour cache (3600s) for daily data updates, shared across all pages

#### SQL Data Architecture
**Schema Structure**:
- `Ticker_Reference` table: Maps tickers to sectors (Ticker, Name, Sector, Data_Source, Active)
- Sector tables: One table per sector (Steel, Agriculture, Energy, etc.)
- Each sector table: Ticker, Date, Price columns
- Data loading: Fetch Ticker_Reference → Loop through sectors → Concatenate all data

**IMPORTANT - Column Naming Convention**:
- **Ticker**: Short code from SQL (e.g., "ORE62", "HRCVN") - used internally
- **Name**: Descriptive name from SQL (e.g., "Ore 62", "HRC HPG") - **THIS MAPS TO MongoDB Item field**
- **Item**: Field in MongoDB `commodity_classification` collection
- **Mapping Rule**: Always use `df['Name']` (from SQL) to map to MongoDB `item` field, NEVER use `df['Ticker']`

**Data Flow**:
1. SQL returns: Ticker, Date, Price, Name (no Sector/Group/Region yet)
2. classification_loader maps: Name → Item in MongoDB → adds Sector, Group, Region
3. Pages filter: `df[df['Name'] == item]` where item comes from MongoDB

**Key Functions** (`sql_connection.py`):
```python
fetch_ticker_reference()           # Load ticker-to-sector mapping
fetch_sector_data(sector_name)     # Load specific sector table
fetch_all_commodity_data()         # Load all sectors (with parallel option)
                                   # Returns: Ticker, Date, Price, Name (NO Sector column)
fetch_specific_sectors()           # Load only selected sectors (faster)
```

**Performance**:
- Sequential loading: ~30 seconds for all sectors
- Parallel loading (default): ~10-15 seconds for all sectors
- With caching (@st.cache_data, TTL=300): <0.1s on cache hits
- Total data size: ~14MB for all commodity prices

**Test Page Features**:
1. Connection test - Verify SQL Server connectivity
2. Ticker Reference test - Load and display sector mapping
3. Full data load test - Load all commodity data with parallel option
4. Performance comparison - Sequential vs parallel loading

**Migration Status** (COMPLETE ✅):
- ✅ SQL connection module ready with 1-hour caching
- ✅ Test page validates connection and data loading
- ✅ **Price Chart migrated to SQL** (pages/1_Price_Chart.py)
- ✅ **Dashboard migrated to SQL** (Dashboard.py)
- ✅ **Group Analysis migrated to SQL** (pages/2_Group_Analysis.py)
- ✅ **Ticker Analysis migrated to SQL** (pages/3_Ticker_Analysis.py)

**Migration Summary**:
All 4 main pages now use SQL Server as primary data source with shared 1-hour cache:
- Dashboard.py: Changed import, updated load_data(), modified get_index_data() and component charts
- pages/1_Price_Chart.py: Changed import, updated load_data(), changed filtering to use Name column
- pages/2_Group_Analysis.py: Changed import, updated load_data(), updated multiselect and captions
- pages/3_Ticker_Analysis.py: Changed import, updated load_data(), modified get_index_data()

**Key Changes Across All Pages**:
1. Import: `load_data_with_classification` → `load_sql_data_with_classification`
2. Caching: Added `@st.cache_data(ttl=3600)` for 1-hour cache
3. Commodity filtering: Changed from `df['Ticker']` to `df['Name']` (matches MongoDB Item field)
4. Stock tickers: Remain unchanged (ticker, selected_ticker for HPG, VNM, etc.)
5. Data source: Removed CSV file path logic, now using `load_sql_data_with_classification(start_date='2024-01-01')`

**Next Steps**:
1. ✅ ~~Update all 4 main pages~~ (COMPLETE)
2. Monitor performance and cache hit rates in production
3. Keep CSV files as backup for 1-2 weeks
4. Optionally delete test page (pages/7_SQL_Data_Test.py) after verification
5. Consider migrating commo_dashboard.py functions to use Name column consistently

**Key Lessons Learned**:
1. **Column Mapping Rule**: Always use `df['Name']` (from SQL) to map to MongoDB `item` field, NEVER use `df['Ticker']`
2. **Stock vs Commodity**: Stock tickers (HPG, VNM) use 'ticker'/'Ticker', commodity series use 'Name'
3. **Data Flow**: SQL returns NO Sector/Group/Region - these are added by classification_loader from MongoDB
4. **Test Data Confusion**: Test page excluded Textile by default - can cause confusion with row counts
5. **Shared Cache**: Cache is shared across all pages - clear cache after code changes
6. **MongoDB Integration**: Both ticker mappings and classifications use commodity Names (not Ticker codes)
7. **Two-Layer Caching**: Split expensive operations (SQL) from cheap operations (classification) for faster updates

### Individual Commodity Price Viewer (Previous Session)
- ✅ **New Page**: Created pages/1_Price_Chart.py (formerly 6_Individual_Item_Viewer.py)
- ✅ **Sidebar Filters**: Cascading filters (Sector → Group → Region → Items)
- ✅ **Summary Statistics Table**: Shows all filtered items with 1D/1W/1M/3M/6M/1Y changes
- ✅ **Color-Coded Metrics**: Green (positive), red (negative), gray (zero/N/A)
- ✅ **Chart Section**: Only displays when items are selected
- ✅ **Time Period Aggregation**: Daily/Weekly/Monthly/Quarterly averaging
- ✅ **Display Modes**: Normalized (Base 100) or Absolute Prices
- ✅ **Session State Management**: Persists selections across reruns
- ✅ **Select All/Clear Buttons**: Quick selection controls
- ✅ **Table-First Design**: Browse all items in table, select specific ones to chart

### UI/UX Improvements (Latest Session)
- ✅ **Compact Gradient Headers**: Reduced padding (1px 12px) and margins (12px) across all pages
- ✅ **Consistent Styling**: Applied compact headers to Dashboard, Group Analysis, Ticker Analysis, Price Chart
- ✅ **Hide Index Column**: Removed row numbers from summary statistics table
- ✅ **Page Title Simplification**: Changed to simple st.title() instead of large HTML headers

### Reports System Enhancements (Latest Session)
- ✅ **Upload Timestamp**: Added `date_uploaded` field to track when reports are processed
- ✅ **Reports Upload Admin**: Displays both report date and upload timestamp
- ✅ **Reports Summary Page**: Shows report date, type, and upload date (or N/A if blank)
- ✅ **Timestamp Format**: YYYY-MM-DD HH:MM:SS for precise tracking

### Dashboard Quick Viewer Features (Previous Session)
- ✅ **Quick Viewer for Commodity Swings**: View top 5 movers with 2-chart layout (Group Index + Component Tickers)
- ✅ **Quick Viewer for Stock Spreads**: View top 5 movers with 4-chart grid (Input/Output/Stock/Spread)
- ✅ **Group-Specific News**: Each commodity quick viewer shows news for selected group
- ✅ **Dropdown Navigation**: Type or select from top 5 movers, no page reloads
- ✅ **Spread Logic Fix**: Missing input/output data treated as flat line at 100
- ✅ **Tab Reordering**: Commodity Swings first (default landing), Stock Spreads second
- ✅ **Collapsible General News**: Latest Market News collapsed by default

### Performance Optimization
- ✅ **@st.fragment Decorator**: Quick viewers use fragments for isolated reruns
- ✅ **No Full Page Reloads**: Switching tickers only reloads quick viewer section
- ✅ **Removed st.expander**: Quick viewers displayed normally for smooth scrolling
- ✅ **Removed Buttons**: Dropdown-only navigation (buttons were causing slow reruns)

### Color-Coded Metrics
- ✅ **Dashboard Metrics**: 5D/10D/50D/150D changes colored (green/red/gray)
- ✅ **Group Analysis Metrics**: Main and regional metrics color-coded
- ✅ **Consistent Styling**: HTML-based colored boxes with borders

### MongoDB Integration - Reports (Latest Session)
- ✅ **Reports Collection**: Added `reports` collection to MongoDB
- ✅ **Reports Upload Admin**: Web interface to upload PDFs and save to MongoDB
- ✅ **Error Logging**: Enhanced with captured stdout/stderr for debugging
- ✅ **pdf_processor.py**: Updated to save to MongoDB (local batch processing)
- ✅ **pdf_processor_mongodb.py**: Streamlit version for web uploads
- ✅ **Dual Processing**: Both local and web uploads save to same MongoDB collection

### Local Development Setup (Latest Session)
- ✅ **mongodb_utils.py**: Works for both Streamlit Cloud and local Python scripts
- ✅ **Environment Variable Support**: Reads `MONGODB_URI` from `.env` file
- ✅ **python-dotenv Integration**: pdf_processor.py loads .env automatically
- ✅ **Conditional Caching**: Only caches in Streamlit, not in local scripts
- ✅ **Optional Streamlit**: mongodb_utils works without Streamlit installed

### Code Cleanup & Organization
- ✅ **Removed Migration Functions**: Cleaned up one-time migration code
- ✅ **Removed Unused Imports**: json, datetime, create_weighted_index
- ✅ **Removed Emojis**: Cleaner headers throughout
- ✅ **Gradient Headers**: Consistent purple gradient on all section headers
- ✅ **Duplicate Code Removal**: Fixed duplicate commodity swing tables

### MongoDB Integration - Ticker Mappings (Previous Session)
- ✅ Created `mongodb_utils.py` for database operations
- ✅ Migrated 57 ticker mappings to MongoDB
- ✅ Updated all pages to use MongoDB
- ✅ Admin page now works on cloud deployment
- ✅ Real-time updates without git commits

---

## Key Functions Reference

### `load_ticker_mappings()`
```python
# From mongodb_utils.py
# Returns: List[Dict] of ticker mappings
# Cached: 5 minutes (TTL)
# Used by: Dashboard, Ticker Analysis, Admin page
```

### `load_commodity_classifications()`
```python
# From mongodb_utils.py
# Returns: List[Dict] of commodity classifications
# Schema: {"item": "Ore 62", "sector": "Steel Material", "group": "Iron Ore", "region": "China"}
# Cached: 60 seconds (TTL)
# Used by: classification_loader, all data pages, pdf_processor
```

### `load_sql_data_raw()`
```python
# From classification_loader.py
# Returns: DataFrame with Ticker, Date, Price, Name (NO classifications)
# Cached: 1 hour (3600s) - expensive SQL query
# Used by: Dashboard, Price Chart, Group Analysis, Ticker Analysis
```

### `apply_classification(df)`
```python
# From classification_loader.py
# Returns: DataFrame with Sector, Group, Region added
# NOT cached - re-applies fresh classifications using 60s cached MongoDB data
# Enables classification changes to propagate in ~60 seconds
```

### `create_equal_weight_index(df, group, base_value=100)`
```python
# From commo_dashboard.py
# Returns: DataFrame with Date, Index_Value columns
# Method: Equal-weight daily returns
```

### `create_aggregated_index(items_list, df, all_indexes, regional_indexes)`
```python
# From Ticker Analysis
# Returns: DataFrame with Date, Price columns
# Method: Sensitivity-weighted or equal-weighted
```

### `load_latest_news(group)`
```python
# From commo_dashboard.py
# Returns: List[Dict] with date, news
# Source: all_reports.json filtered by commodity group
```

### `fetch_all_commodity_data()` - NEW
```python
# From sql_connection.py
# Returns: DataFrame with Ticker, Date, Price, Name, Sector columns
# Method: Parallel loading from SQL Server sector tables
# Parameters:
#   - exclude_sectors: List[str] (e.g., ['Textile'])
#   - start_date: str (YYYY-MM-DD format)
#   - parallel: bool (default True, 10-15s vs 30s sequential)
#   - max_workers: int (default 5 threads)
```

---

## Common Workflows

### 1. Edit Ticker Mapping
1. Open Ticker Mapping Admin page
2. Select ticker or add new
3. Configure inputs/outputs with dropdowns
4. Click "Save" → Saved to MongoDB
5. Changes live immediately (no deployment needed)

### 2. Add News Report
```bash
cd news
# Place PDF in reports/ folder
python pdf_processor.py
# Updates all_reports.json automatically
```

### 3. Update Classification
1. Open Commodity List Admin page (pages/7_Commodity_List_Admin.py)
2. Edit item: Select item → Update Sector/Group/Region → Save
3. Add new item: Select from unmapped SQL items or type manually → Save
4. Rename item: Check "Rename" → Select new name from SQL list → Save
5. Changes live in ~60 seconds (classification cache TTL)
6. No data regeneration or deployment needed

---

**Last Updated**: 2025-10-22
- ✅ **SQL Server Integration**: All 4 main pages using SQL Server with 1-hour shared cache
- ✅ **Dynamic Classification System (Phase 1)**: MongoDB-based commodity classifications with web admin interface
- ✅ **Two-Layer Caching**: Classification changes propagate in ~60 seconds without re-querying SQL
- ✅ **Excel Removal**: All `commo_list.xlsx` references removed, single source of truth in MongoDB
