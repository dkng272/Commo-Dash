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

**Problem**: Combined SQL + classifications cached together → classification changes invisible until SQL cache expires (6 hours)

**Solution**:

```python
# Layer 1: Raw SQL data (expensive - GLOBAL cache 6 hours)
# Located in classification_loader.py
@st.cache_data(ttl=21600)  # 6 hours - shared across ALL pages
def load_raw_sql_data_cached(start_date=None):
    df = fetch_all_commodity_data(start_date=start_date, parallel=True)
    return df  # Returns: Ticker, Date, Price, Name (NO classifications)

# Layer 2: Fresh classification (cheap - NOT cached at page level)
def load_data():
    # Get globally cached raw SQL data
    df_raw = load_raw_sql_data_cached(start_date=None)

    # Apply FRESH classification (uses 60s cached MongoDB data)
    df_classified = apply_classification(df_raw)

    # Filter out unclassified items
    df = df_classified.dropna(subset=['Group', 'Region', 'Sector'])
    return df
```

**Implementation Details**:
- **ALL pages** call `load_raw_sql_data_cached()` from `classification_loader.py`
- This function is cached **ONCE** with `@st.cache_data(ttl=21600)` (6 hours)
- Cache is **GLOBAL** - shared across Dashboard, Price Chart, Group Analysis, Ticker Analysis
- Each page has its own `load_data()` wrapper that:
  1. Calls globally cached `load_raw_sql_data_cached(start_date=None)`
  2. Applies fresh classification via `apply_classification(df_raw)`
  3. Filters by date in-memory (if needed)
- `apply_classification()` uses `load_classification()` which internally calls MongoDB (60s cache)

**Benefits**:
- SQL query runs ONCE every 6 hours across entire app (expensive operation shared)
- Classifications refreshed every 60 seconds (cheap MongoDB lookup)
- Classification changes visible in ~60 seconds without re-querying SQL
- Date filtering happens in-memory (instant, no cache invalidation)
- No duplicate SQL queries even when switching between pages

**Pages Using Two-Layer Cache**: Dashboard, Price Chart, Group Analysis, Ticker Analysis (all 4 main pages)

### Complete Caching Architecture

**3-Tier Cache Hierarchy**:

```
┌─────────────────────────────────────────────────────────────┐
│ Level 1: GLOBAL SQL Cache (6 hours)                         │
│ • classification_loader.load_raw_sql_data_cached()          │
│ • Cached ONCE, shared across ALL pages                      │
│ • Decorator: @st.cache_data(ttl=21600)                      │
│ • Returns: Ticker, Date, Price, Name (raw SQL data)         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Level 2: MongoDB Caches (60s and 5min)                      │
│ • load_commodity_classifications() - 60s cache              │
│ • load_ticker_mappings() - 5min cache                       │
│ • Decorator: @st.cache_data(ttl=60/300)                     │
│ • Returns: Classification/mapping dictionaries              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Level 3: Per-Page Processing (NOT cached)                   │
│ • Each page's load_data() function                          │
│ • Calls apply_classification(df_raw)                        │
│ • Filters by date in-memory                                 │
│ • Drops unclassified items                                  │
│ • Fresh on every page load                                  │
└─────────────────────────────────────────────────────────────┘
```

**Cache Invalidation Flow**:
1. **SQL data changes** → Wait 6 hours OR manually clear cache (affects all pages)
2. **Classification changes in MongoDB** → Visible in ~60 seconds (no SQL re-query)
3. **Ticker mappings change in MongoDB** → Visible in ~5 minutes (no SQL re-query)
4. **Page switch** → Instant (reuses GLOBAL SQL cache, re-applies fresh classification)
5. **Timeframe change** → Instant (in-memory date filtering, no cache invalidation)

**Why This Works**:
- SQL data rarely changes (daily updates) → 6 hour cache is safe
- Classifications change frequently during setup/admin → 60s cache enables quick iteration
- Ticker mappings moderately stable → 5min cache balances freshness and performance
- Each page independently applies fresh classification → MongoDB changes propagate quickly
- Date filtering in-memory → No cache thrashing from timeframe changes

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
# GLOBAL cached function (classification_loader.py)
@st.cache_data(ttl=21600)  # 6 hours
load_raw_sql_data_cached(start_date=None)
# Returns: DataFrame with Ticker, Date, Price, Name (NO classifications)
# Shared across ALL pages - single SQL query for entire app

# Applied fresh on each page load (NOT cached)
apply_classification(df)
# Returns: DataFrame with Sector, Group, Region added
# Uses load_classification() which calls MongoDB (60s cache internally)

# MongoDB loaders (mongodb_utils.py)
@st.cache_data(ttl=300)  # 5 minutes
load_ticker_mappings()
# Returns: List[Dict] of ticker mappings

@st.cache_data(ttl=60)  # 60 seconds
load_commodity_classifications()
# Returns: List[Dict] of classifications
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

## Current Session Updates (2025-10-28)

### 1. XAI News Intelligent Batch Search

**Problem**: Manual individual searches for 28+ commodity groups time-consuming and inefficient.

**Solution**: Created automated batch search system that determines search parameters based on price movements.

**Logic**:
```
IF 5D movement > 3%   → Bullish direction, 7-day lookback
IF 5D movement < -3%  → Bearish direction, 7-day lookback
IF 5D within ±3%:
   IF 10D > 3%   → Bullish direction, 14-day lookback
   IF 10D < -3%  → Bearish direction, 14-day lookback
   ELSE          → Both directions, 14-day lookback
```

**Implementation**:

**A. Standalone Script** (`xai_api/intelligent_batch_search.py`):
- Command-line tool for scheduled/automated runs
- Uses GLOBAL 6-hour SQL cache for instant analysis
- Calculates equal-weighted group indexes for 5D/10D movements
- Respects 5-day cooldown periods
- Saves direction (bullish/bearish/both) to MongoDB

**Usage**:
```bash
# Dry run (preview only)
python intelligent_batch_search.py

# Run with MongoDB saving
python intelligent_batch_search.py --save-to-mongodb

# Test specific groups
python intelligent_batch_search.py --groups "Iron Ore,HRC" --save-to-mongodb

# Custom threshold
python intelligent_batch_search.py --threshold 5.0 --save-to-mongodb
```

**B. UI Integration** (`pages/8_XAI_News_Admin.py`):
- Added **"Batch Search" tab** to XAI News Admin page
- Two-step workflow:
  1. **Analyze All Groups**: Shows preview table with 5D/10D changes, determined direction/lookback, cooldown status
  2. **Run Batch Search**: Executes searches with real-time progress bar
- Color-coded table: Green (bullish), Red (bearish), Yellow (both)
- Configurable threshold and delay settings
- Stays on tab after execution (no page jump)

**Key Features**:
- ✅ Preview parameters before running (no surprises)
- ✅ Uses cached SQL data (instant analysis)
- ✅ Auto-saves to MongoDB with trigger type "auto"
- ✅ Respects cooldown periods (skips groups in cooldown)
- ✅ Progress tracking (shows current group being searched)
- ✅ Clears only catalyst cache (preserves SQL/classification caches)

### 2. Reports Summary Page Restructure

**Changes to `pages/4_Reports_Summary.py`**:

**New Tab Structure**:
- **Tab 1: 💡 Price Catalysts** (moved from page 8, now primary)
  - 3-column grid layout showing all commodity catalysts
  - Sidebar filters: Search box, Direction (bullish/bearish/both), Sort by (alphabetical/recent/has catalyst)
  - Color-coded cards based on direction
  - Expandable timeline for each catalyst

- **Tab 2: 📄 PDF Reports** (existing, now secondary)
  - Filters moved inside tab (left column: 25%, content: 75%)
  - Self-contained layout (no sidebar pollution)

**Catalyst Card Design**:
- **Header Box**: Compact (group name, emoji, date, trigger type)
- **Summary Area**: Large text box (180px min-height, 500 char limit)
  - Light gray background (#f9f9f9)
  - Better line spacing (1.6)
  - More readable
- **Timeline**: Collapsible expander with event details

**Direction Detection**:
- **Primary**: Uses `direction` field from MongoDB (accurate, from price data)
- **Fallback**: Keyword heuristic for old catalysts without direction field
- **Keywords**:
  - Bullish: rally, surge, increase, increased, bullish, gains, gain, rise, rising, up
  - Bearish: decline, declined, fall, falling, bearish, drop, dropped, weaken, pressure, decrease, decreased, down

### 3. MongoDB Schema Update

**Catalyst Collection** (`commodity_dashboard.catalysts`):

**New Field**: `direction` (optional)

```json
{
  "commodity_group": "Iron Ore",
  "summary": "Prices rallied on China stimulus...",
  "timeline": [{"date": "2025-10-28", "event": "..."}],
  "search_date": "2025-10-28",
  "date_created": "2025-10-28T10:30:00Z",
  "search_trigger": "auto",
  "cooldown_until": "2025-11-02T10:30:00Z",
  "direction": "bullish"  // NEW: "bullish", "bearish", or "both"
}
```

**Updated Functions** (`mongodb_utils.py`):
```python
save_catalyst(
    commodity_group: str,
    summary: str,
    timeline: List[Dict[str, str]],
    search_trigger: str = "manual",
    direction: Optional[str] = None  # NEW parameter
) -> bool
```

**Benefits**:
- Accurate direction based on actual price movements (not text interpretation)
- No recalculation needed on display
- Backward compatible (old catalysts work with keyword fallback)

### 4. Cache Optimization

**Updated `intelligent_batch_search.py`**:
```python
# Before: Direct SQL query every time
df_raw = fetch_all_commodity_data(start_date=None, parallel=True)

# After: Use GLOBAL 6-hour cache
df_raw = load_raw_sql_data_cached(start_date=None)
df = apply_classification(df_raw)
```

**Result**:
- "Analyze All Groups" button: Instant (uses cached data)
- No duplicate SQL queries when switching between pages
- Consistent with 3-tier caching architecture

### 5. UI/UX Improvements

**Git Configuration**:
- Fixed `.gitignore` to exclude `__pycache__/` folders everywhere (not just root)
- Pattern: `__pycache__/` and `**/__pycache__/`

**Summary**:
- Two ways to trigger batch search: UI (interactive preview) or CLI (scheduled automation)
- Price Catalysts now primary view on Reports Summary page
- Direction stored in MongoDB for future accuracy
- All changes backward compatible with existing catalysts

---

**Last Updated**: 2025-10-28

**Recent Documentation Updates** (2025-10-28):
- Added intelligent batch search implementation (UI + CLI)
- Documented XAI News Admin batch search tab workflow
- Updated Reports Summary page structure (Price Catalysts first)
- MongoDB catalyst schema updated with direction field
- Cache optimization for batch search (uses GLOBAL SQL cache)

**Recent Documentation Updates** (2025-10-25):
- Deep dive into actual caching implementation across all pages
- Documented GLOBAL SQL cache in `classification_loader.py` (6 hours, shared across all pages)
- Clarified cache TTL values: SQL (6h), MongoDB classifications (60s), ticker mappings (5min)
- Added 3-tier caching architecture diagram with cache invalidation flow
- Emphasized single SQL query pattern for entire app (no duplicate queries)

**Current State**:
- ✅ Intelligent batch search (automated parameter detection)
- ✅ XAI News Admin batch search tab (preview + execute)
- ✅ Price Catalysts primary view (Reports Summary page)
- ✅ Direction stored in MongoDB (bullish/bearish/both)
- ✅ Improved card layout (larger summary space)
- ✅ Flexible timeframe selection (in-memory filtering)
- ✅ st.fragment optimization (Price Chart page)
- ✅ 150D lookback window (accurate metrics)
- ✅ YTD performance column
- ✅ Dashboard quick view defaults (5D)
- ✅ Group name optimization (12 groups renamed for AI routing)
- ✅ AI prompt simplification (removed aliases, improved clarity)
- ✅ SQL Server integration (6-hour GLOBAL cache)
- ✅ MongoDB classifications (60s cache)
- ✅ Two-layer caching architecture
