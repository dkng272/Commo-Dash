# Commodity Dashboard - Technical Summary

## Overview
Commodity price tracking and analysis system with Vietnamese stock ticker integration. Tracks commodity prices, creates equal-weighted indexes, maps to stock tickers, and analyzes correlations with stock performance.

---

## Project Structure

```
Commo Dash/
├── data/
│   ├── cleaned_data.csv           # Main commodity price data
│   └── commo_list.xlsx            # Commodity classification
├── pages/                          # Streamlit pages
│   ├── Group_Analysis.py          # Commodity group deep dive
│   ├── Ticker_Analysis.py         # Stock ticker analysis
│   ├── Reports_Summary.py         # Research reports browser
│   └── Ticker_Mapping_Admin.py    # Ticker mapping editor (MongoDB)
├── news/
│   ├── all_reports.json           # Consolidated research reports
│   ├── reports/                   # PDF storage
│   └── pdf_processor.py           # PDF processing script
├── Dashboard.py                    # Main dashboard (homepage)
├── mongodb_utils.py               # MongoDB connection & CRUD (NEW)
├── commo_dashboard.py             # Index creation functions
├── classification_loader.py       # Dynamic classification loading
├── ssi_api.py                     # Stock price API integration
└── ticker_mappings_final.json     # Backup (data now in MongoDB)
```

---

## MongoDB Integration (Latest Update)

### Purpose
Enable Ticker Mapping Admin page to work on Streamlit Cloud deployment by storing mappings in MongoDB instead of local JSON files.

### Database Structure
- **Database**: `commodity_dashboard`
- **Collection**: `ticker_mappings`
- **Documents**: 57 ticker mappings

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

### Implementation (`mongodb_utils.py`)

**Key Functions**:
- `load_ticker_mappings()` - Read from MongoDB (cached 5 min)
- `save_ticker_mappings()` - Write to MongoDB (with cache clear)
- `get_mongo_client()` - Connection management

**Configuration**:
- Local: `.streamlit/secrets.toml` with `MONGODB_URI`
- Cloud: Streamlit Cloud secrets with `MONGODB_URI`
- Fallback: Warns if connection string not found

**Files Updated**:
- `Dashboard.py` - Loads from MongoDB
- `pages/Ticker_Analysis.py` - Loads from MongoDB
- `pages/Ticker_Mapping_Admin.py` - Read/write to MongoDB
- `requirements.txt` - Added `pymongo>=4.6.0`

### Workflow
**Before (JSON file)**:
1. Edit locally → Save to JSON → Commit → Push → Redeploy

**After (MongoDB)**:
1. Edit on Admin page → Save to MongoDB → Changes live immediately ✅

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

### cleaned_data.csv
```
Date       | Ticker       | Price  | Group     | Region | Sector
2024-01-01 | Ore 62       | 142.0  | Iron Ore  | China  | Steel Material
2024-01-01 | HRC HPG      | 550    | HRC       | Vietnam| Steel
```

**Classification Hierarchy**: Sector → Group → Region → Item

### commo_list.xlsx
```
Sector          | Group      | Region  | Item
Steel Material  | Iron Ore   | China   | Ore 62
Steel           | HRC        | Vietnam | HRC HPG
```

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
PyMuPDF>=1.23.0     # PDF processing
openai>=1.0.0       # AI summarization
openpyxl>=3.1.0     # Excel reading
```

### Secrets Configuration
**Local**: `.streamlit/secrets.toml`
```toml
MONGODB_URI = "mongodb+srv://..."
```

**Streamlit Cloud**: Add to Secrets section in dashboard

### Git Ignore
```
.streamlit/secrets.toml
__pycache__/
*.pyc
.DS_Store
```

---

## Recent Updates Summary

### MongoDB Integration (Current Session)
- ✅ Created `mongodb_utils.py` for database operations
- ✅ Migrated 57 ticker mappings to MongoDB
- ✅ Updated all pages to use MongoDB
- ✅ Admin page now works on cloud deployment
- ✅ Real-time updates without git commits

### UI/UX Modernization
- ✅ Gradient section headers
- ✅ Tabbed interface for Market Movers
- ✅ Enhanced news cards with badges
- ✅ Last updated timestamp
- ✅ Removed emojis for cleaner look
- ✅ Consistent purple gradient theme

### News System Enhancement
- ✅ Multi-source support (JPM, HSBC, etc.)
- ✅ Hierarchical filtering (Source → Series)
- ✅ HTML rendering fixes
- ✅ Scrollable containers for long content

### Group Analysis Improvements
- ✅ Index vs Components view toggle
- ✅ Component ticker multiselect
- ✅ Moved tickers to captions
- ✅ Removed unnecessary headers

---

## Key Functions Reference

### `load_ticker_mappings()` - NEW
```python
# From mongodb_utils.py
# Returns: List[Dict] of ticker mappings
# Cached: 5 minutes (TTL)
# Used by: Dashboard, Ticker Analysis, Admin page
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
1. Edit `commo_list.xlsx`
2. Refresh Streamlit app (F5)
3. No data regeneration needed

---

**Last Updated**: 2025-10-14 - MongoDB integration complete, deployed on Streamlit Cloud
