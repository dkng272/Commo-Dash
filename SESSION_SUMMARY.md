# Commodity Dashboard - Session Summary

## Overview
Comprehensive commodity price tracking and analysis system with Vietnamese stock ticker integration. The system tracks commodity prices, creates equal-weighted indexes, maps them to stock tickers, and analyzes correlations with stock performance.

---

## Project Structure

```
Commo Dash/
├── data/                           # Data files
│   ├── cleaned_data.csv           # Main commodity price data (Date, Ticker, Price, Group, Region)
│   ├── BBG_data.csv               # Bloomberg data
│   ├── steel_prices.csv           # Steel price data
│   ├── heo.csv                    # Hog data
│   └── fish_prices.csv            # Fish price data
├── pages/                          # Streamlit pages
│   ├── Ticker_Analysis.py         # Stock ticker commodity analysis (main)
│   ├── Correlation_Matrix.py      # Stock vs commodity correlation explorer
│   └── _Custom_Ticker_Correlation.py  # Custom ticker correlation (hidden)
├── commo_dashboard.py              # Core index creation functions (group, regional, sector)
├── dashboard_app.py                # Main Streamlit dashboard (wide layout, sector chart)
├── ssi_api.py                      # SSI/TCBS API integration for stock prices
├── data_cleaning.py                # Data cleaning and consolidation
├── commo_list.xlsx                 # Commodity classification (Group, Region mapping)
└── ticker_mappings_final.json      # Stock ticker to commodity mappings
```

---

## Global Settings

### Start Date Filter
- **Global start date**: `2024-01-01`
- Applied to all data in `Ticker_Analysis.py`
- Ensures alignment between commodity and stock price data
- Defined in: `GLOBAL_START_DATE = '2024-01-01'`

---

## Key Components

### 1. Index Creation (`commo_dashboard.py`)

**Core Functions**:

#### `create_equal_weight_index(df, group_name, base_value=100)`
- Equal-weighted index for commodity groups
- Daily returns methodology
- Normalized to base 100

#### `create_regional_indexes(df, base_value=100)`
- Creates indexes for each Group-Region combination
- Format: "Steel - China", "Oil - Global"
- Special handling for Crack Spread (absolute value averaging)

#### `create_sector_indexes(df, base_value=100)`
- Creates equal-weighted indexes for each Sector (highest classification level)
- Aggregates all tickers within a sector regardless of group/region
- Available sectors: Energy, Fertilizers, Chemicals, Metals, Steel, Steel Material, Shipping, Agri, Industrials Vietnam
- Uses same methodology as group indexes with `skipna=True` for NA handling

**Important**:
- Only excludes "Crack Spread" group (special absolute value handling)
- Pangaseus is now included in all index calculations
- Uses `pct_change(fill_method=None)` and `.ffill()` (deprecation fixes)

---

### 2. Stock Price Integration (`ssi_api.py`)

**Purpose**: Fetch Vietnamese stock prices from TCBS API

**Function**: `fetch_historical_price(ticker, start_date=None)`
- Returns DataFrame with columns: `Date`, `open`, `high`, `low`, `close`, `volume`, `Price`
- Automatically handles timezone conversion
- Default lookback: 1 year if no start_date provided

**Usage**:
```python
from ssi_api import fetch_historical_price
stock_df = fetch_historical_price('HPG', '2024-01-01')
```

---

### 3. Ticker Analysis Page (`pages/Ticker_Analysis.py`)

**Main Features**:

#### Summary Metrics Table
- Shows 5D, 10D, 50D, 150D percentage changes
- **Always uses aggregated indexes** for multiple inputs/outputs
- **Sensitivity-Based Weighting**: Uses sensitivity values from ticker_mappings_final.json if provided
  - If sensitivities are null → Equal-weight (default)
  - If sensitivities have values → Weighted by sensitivity (must sum to 1.0)
  - Validation: Warns if sensitivities don't sum to 1.0 (±0.01 tolerance)
- Inputs: Negative changes marked (rising input = margin pressure)
  - Color coding: Negative = green (cost down, good), Positive = red (cost up, bad)
- Outputs: Positive changes marked (rising output = margin expansion)
  - Color coding: Positive = green (revenue up, good), Negative = red (revenue down, bad)
- **Spread Row**: Bold with color coding (red if negative, green if positive)
  - Treats None values as 0 in calculation
  - Formula: Spread = (Output % or 0) - (Input % or 0)
- Caption explains sensitivity-weighted or equal-weighted aggregation methodology

#### Input/Output Charts
- **Aggregation Toggle**: Sidebar checkbox controls these charts
- Normalized to base 100 for comparison
- Line widths: All set to `width=2` for consistency
- Shows data source names in tables (5D/10D/50D/150D % changes)
- Number formatting: 2 decimal places
- **Legend Position**: Horizontal at top (yanchor='bottom', y=1.02) for better space utilization

#### Combined View (3-Panel Subplot)
- **Panel 1 (45%)**: Commodity Inputs vs Outputs
  - Always uses aggregated indexes (ignores toggle)
  - Dotted lines for inputs, solid for outputs
  - Shaded area between input/output lines

- **Panel 2 (25%)**: Output-Input Spread (Margin Indicator)
  - Calculates: `Spread = Output - Input`
  - Shows daily spread (light green, transparent)
  - Shows MA20 spread (bold green with fill)
  - Zero reference line (gray dashed)
  - Rising spread = expanding margins

- **Panel 3 (30%)**: Stock Price
  - Normalized to base 100
  - Black line, width 2
  - Fetched from TCBS API

#### Correlation Analysis
**Commodity Correlations**:
- Price level correlations (absolute prices)
- Daily return correlations (% changes)
- Displayed in two sections with 3 decimal precision

**Spread Correlations**:
- Stock price vs Spread MA20 (price level)
- Stock returns vs Spread changes (returns)
- Displayed in separate success box below chart

#### Data Fallback Hierarchy
```
Specific Item → Regional Index → Group Index → None
```

---

### 4. Correlation Matrix Page (`pages/Correlation_Matrix.py`)

**Purpose**: Browse correlations for all mapped tickers

**Features**:
- Dropdown to select from mapped tickers
- Radio button: Price Level vs Daily Returns correlation
- **Only uses regional indexes** (not group-level)
- Top 5 positive/negative correlations
- Color-coded table (red = negative, green = positive)
- Full regional index correlation table

---

### 5. Custom Ticker Correlation (Hidden: `_Custom_Ticker_Correlation.py`)

**Purpose**: Test any ticker against commodity indexes

**Features**:
- Text input for any stock ticker
- Run button to execute analysis
- Same correlation analysis as Correlation Matrix
- Stock price chart (normalized to base 100)
- Error handling for invalid tickers

**Note**: Hidden by underscore prefix (not shown in Streamlit sidebar)

---

### 6. Main Dashboard (`dashboard_app.py`)

**Layout**: Wide mode (`st.set_page_config(layout="wide")`)

**Features**:

#### Best Benefited/Worst Hit Stocks Table (Top of Page)
- Vectorized calculation of spreads across all 57 tickers
- Toggle checkbox to switch between "Best Benefited" (default) and "Worst Hit" stocks
- 4 columns showing top 10 stocks: 5D, 10D, 50D, 150D spreads
- Color-coded: Green (positive spread), Red (negative spread)
- Cached for performance using `@st.cache_data`
- Spread = Output % - Input % (treating None as 0)

#### Largest Index Swings Tables
- 4 columns: 5D, 10D, 50D, 150D
- Top 10 groups by absolute swing magnitude
- Color-coded: Green (positive), Red (negative), Black (zero)
- 2 decimal precision

#### Group-Level Analysis
- Dropdown to select commodity group
- Shows component tickers
- Group index chart
- Performance metrics (Current, 1D, 5D, 15D)
- Regional breakdowns with tabs (if applicable)

---

## Data Schema

### cleaned_data.csv
```
Date       | Ticker                      | Price  | Group      | Region | Sector
2024-01-01 | Ore 62                      | 142.0  | Iron Ore   | China  | Steel Material
2024-01-01 | Yellow phosphorus - China   | 25000  | Yellow P4  | China  | Chemicals
2024-01-01 | HRC - VN                    | 550    | HRC        | VN     | Steel
```

**Classification Hierarchy**: Sector (highest) → Group → Region → Item (most specific)

### ticker_mappings_final.json
```json
{
  "ticker": "DGC",
  "inputs": [
    {
      "item": "Phosphate rock",
      "group": "P4 Rock",
      "region": "China",
      "sensitivity": null
    }
  ],
  "outputs": [
    {
      "item": "Yellow phosphorus - DGC",
      "group": "Yellow P4",
      "region": "Vietnam",
      "sensitivity": null
    }
  ]
}
```

---

## Technical Decisions

### 1. Index Methodology
- **Weighting Methods**:
  - **Sensitivity-weighted** (Ticker Analysis only): Uses sensitivity values from ticker_mappings_final.json
  - **Equal-weighted** (Group/Regional/Sector indexes, or when sensitivities are null): Average of daily returns
- **Base value**: 100 (normalized for comparison)
- **Missing data handling**: Robust NA handling at multiple levels
- **Aggregation**: Always used in Combined View for consistent spread calculation

#### Sensitivity-Weighted Index Calculation (Ticker Analysis):
1. **Get component prices**: Load price data for each input/output item
2. **Calculate daily returns**: `pct_change(fill_method=None)` for each ticker
3. **Extract sensitivity weights**: Read from ticker_mappings_final.json
4. **Validate weights**: Check if `sum(weights) ≈ 1.0` (±0.01 tolerance), warn if not
5. **Weighted averaging**: `(returns * weights).sum(axis=1, skipna=True)`
6. **Build cumulative index**: `(1 + avg_returns).cumprod() * base_value`
7. **Set starting value**: `first_valid_price = base_value`

**Example**: HPG with inputs [Iron Ore: 0.6, Coking Coal: 0.3, Scrap: 0.1]
- If Iron Ore +10%, Coking Coal +5%, Scrap +2%
- Weighted return = 0.6×10% + 0.3×5% + 0.1×2% = 7.7%

#### Equal-Weight Index Calculation (Group/Regional/Sector):
1. **Get component prices**: Pivot data into matrix (dates × tickers)
2. **Calculate daily returns**: `pct_change(fill_method=None)` for each ticker
3. **Equal-weight averaging**: `mean(axis=1, skipna=True)` across all available tickers
4. **Build cumulative index**: `(1 + avg_returns).cumprod() * base_value`
5. **Set starting value**: `first_valid_price = base_value`

#### NA Handling Strategy:
**Problem Type 1: Different Starting Dates**
- Ticker A starts Jan 2024, Ticker B starts Mar 2024
- Solution: `skipna=True` in mean calculation
- Jan-Feb: Uses only Ticker A's returns
- Mar onward: Averages both A & B's returns
- No manual intervention needed

**Problem Type 2: Sporadic Missing Data**
- Occasional gaps in price updates for specific tickers
- Solution: `mean(axis=1, skipna=True)` automatically excludes NaN values
- Only uses available tickers for each day's average
- Example: If 3 tickers but 1 is missing → averages the 2 available

**Problem Type 3: Empty Groups After Filtering**
- When date filtering removes all data for a group
- Solution: Early exit with empty DataFrame if `len(group_df) == 0` or `len(pivot_df) == 0`
- Prevents `IndexError: iloc cannot enlarge its target object`

**Forward-Fill Usage**:
- Applied to final combined index DataFrame: `combined_df.ffill()`
- Propagates last valid index value forward when entire day has no updates
- Maintains continuous time series for visualization

### 2. Correlation Approach
- **Regional indexes only**: More granular than group-level
- **Two types**: Price level and daily returns
- **Spread correlation**: Uses MA20 for smoothing

#### Correlation Calculation:
**Formula**: `merged['Stock_Price'].corr(merged['Commodity_Price'])`
- Pearson correlation between aligned time series
- **NA Handling**: `pd.merge(on='Date', how='inner')` ensures only matching dates are used
- Missing dates in either series are automatically excluded
- No NaN values in correlation calculation

**Returns Correlation**:
```python
merged['Stock_Return'] = merged['Stock_Price'].pct_change(fill_method=None)
merged['Commodity_Return'] = merged['Price'].pct_change(fill_method=None)
return_corr = merged['Stock_Return'].corr(merged['Commodity_Return'])
```
- First row will have NaN returns (no previous data)
- `.corr()` automatically ignores NaN pairs
- Correlation calculated on available return pairs only

### 3. Spread Analysis
- **Formula**: `Spread = Output - Input` (both normalized to base 100)
- **MA20 smoothing**: Reduces noise, shows trend
- **Interpretation**: Rising = expanding margins = bullish for stock
- **Correlation**: Helps validate if margin expansion drives stock price

#### Spread Calculation with NA Handling:
```python
merged_spread = pd.merge(
    input_normalized.rename(columns={'Normalized': 'Input'}),
    output_normalized.rename(columns={'Normalized': 'Output'}),
    on='Date', how='inner'
)
merged_spread['Spread'] = merged_spread['Output'] - merged_spread['Input']
merged_spread['Spread_MA20'] = merged_spread['Spread'].rolling(window=20, min_periods=1).mean()
```
- **Inner join**: Only uses dates where both input and output exist
- **Rolling MA20**: `min_periods=1` allows calculation even with <20 data points
- First 19 points use available data (MA1, MA2, ..., MA19)
- From point 20 onward: proper 20-period moving average
- No NaN values in spread calculation (but MA20 may have NaN if spread itself is NaN)

### 4. Stock Price Integration
- **Source**: TCBS API (Vietnamese market data)
- **Timezone handling**: Converts UTC to timezone-naive for pandas merge
- **Normalization**: All charts use base 100 for easy comparison

### 5. UI/UX Patterns
- Consistent line widths (2px)
- Color coding: Green = positive, Red = negative
- Number formatting: 2-3 decimals
- Separate note boxes for different information types

---

## Key Functions

### `calculate_ticker_summary(ticker, ticker_data, df, all_indexes, regional_indexes, aggregate_items)`
**Returns**: Dictionary with Input/Output percentage changes (5D, 10D, 50D, 150D)
- Always aggregates multiple inputs/outputs
- Reusable for future all-tickers summary table

### `create_aggregated_index(items_list, df, all_indexes, regional_indexes, base_value=100)`
**Purpose**: Combine multiple commodities into single equal-weighted index
**Process**:
1. Get price series for each item (or fallback to regional/group index)
2. Concatenate all price series: `pd.concat(all_prices, axis=1)`
3. Calculate returns for each: `pct_change(fill_method=None)`
4. Equal-weight average: `returns.mean(axis=1, skipna=True)`
5. Build cumulative index: `(1 + avg_returns).cumprod() * base_value`

**NA Handling**:
- `concat(axis=1)` creates matrix with potential NaNs where dates don't align
- `mean(axis=1, skipna=True)` averages only available items each day
- Handles different date ranges automatically
- Example: Input A (Jan-Dec) + Input B (Mar-Dec) → Jan-Feb uses only A, Mar-Dec uses both

### `calculate_correlations(ticker, ticker_data, df, all_indexes, regional_indexes, stock_data)`
**Returns**: Tuple of `(price_correlations, return_correlations)`
- Correlates stock with each input/output commodity
- Handles timezone mismatches
- Both price level and returns correlations

### `calculate_stock_vs_indexes_correlation(ticker, df, all_indexes, regional_indexes, correlation_type)`
**Returns**: Dictionary of correlations with all regional indexes
- Used in Correlation Matrix and Custom Ticker pages
- Only regional indexes (not group-level)

---

## Common Workflows

### 1. Adding New Stock Ticker Mapping
```json
// Edit ticker_mappings_final.json
{
  "ticker": "HPG",
  "inputs": [
    {"item": "Ore 62", "group": "Iron Ore", "region": "China"}
  ],
  "outputs": [
    {"item": "HRC - VN", "group": "HRC", "region": "VN"}
  ]
}
```
Ticker Analysis page auto-updates on next load.

### 2. Running the Dashboard
```bash
cd "Commo Dash"
streamlit run dashboard_app.py
```

### 3. Testing Custom Ticker Correlation
1. Unhide: Rename `_Custom_Ticker_Correlation.py` → `Custom_Ticker_Correlation.py`
2. Refresh Streamlit
3. Enter ticker and click "Run Analysis"

---

## Known Behaviors

### 1. Aggregation Logic
- **Summary table**: Always aggregates
- **Combined View**: Always aggregates
- **Individual charts**: Respects toggle setting

### 2. Spread Calculation
- Only appears when both inputs AND outputs exist
- Uses aggregated data (multiple items → sensitivity-weighted or equal-weighted index)
- Single input/output → uses that item directly
- Sensitivity weighting only applies in Ticker Analysis page, not dashboard

### 3. Correlation Display
- **Regional only**: Group-level indexes excluded
- **Color gradient**: Applied to all correlation tables
- **Spread correlation**: Separate from commodity correlations

---

## Recent Updates (Latest Session)

### 1. Pangaseus Inclusion
- **Changed**: Removed Pangaseus exclusion from all index calculations
- **Files Updated**:
  - `dashboard_app.py`: Changed from `if group not in ['Pangaseus', 'Crack Spread']` to `if group != 'Crack Spread'`
  - `pages/Ticker_Analysis.py`: Same change
  - `pages/Correlation_Matrix.py`: Same change
  - `pages/_Custom_Ticker_Correlation.py.disabled`: Same change
  - `commo_dashboard.py`: Removed Pangaseus skip in `create_regional_indexes()`
- **Result**: Pangaseus now included normally in all indexes; only Crack Spread has special handling

### 2. Spread Row in Summary Metrics
- **Added**: Spread calculation row to Ticker Analysis summary table
- **Features**: Bold text, color-coded (green for positive, red for negative)
- **Calculation**: Treats None values as 0, calculates (Output % or 0) - (Input % or 0)

### 3. Best Benefited/Worst Hit Stocks Table
- **Added**: Vectorized stock spread analysis on dashboard front page
- **Features**:
  - Toggle between Best Benefited (default) and Worst Hit stocks
  - 4 columns: 5D, 10D, 50D, 150D periods
  - Top 10 stocks per period
  - Color-coded spreads
  - Cached for performance

### 4. Sensitivity-Based Weighting in Ticker Analysis
- **Added**: Support for sensitivity-weighted aggregation in ticker_mappings_final.json
- **Features**:
  - Uses `sensitivity` field from input/output items
  - If sensitivities are null → Equal-weight (default behavior)
  - If sensitivities provided → Weighted by sensitivity value
  - **Validation**: Warns if sensitivities don't sum to 1.0 (±0.01 tolerance)
  - Only applies to Ticker Analysis page, not dashboard or group indexes
- **Example**: HPG inputs with Iron Ore (0.6), Coking Coal (0.3), Scrap (0.1)
  - Index movement = 60% Iron Ore + 30% Coal + 10% Scrap
- **Files Updated**: `pages/Ticker_Analysis.py`

### 5. Dynamic Classification Loading
- **Added**: `classification_loader.py` module for instant classification updates
- **Features**:
  - Edit `commo_list.xlsx` and refresh app (no data regeneration needed)
  - Classification loaded at runtime from Excel file
  - Price data stays separate in `cleaned_data.csv`
- **Files Updated**: All pages now use `load_data_with_classification()`

### 6. NaN Price Handling
- **Fixed**: Items with NaN prices at start (e.g., DAP_DinhVu_61) now display correctly
- **Solution**: Use `dropna().iloc[0]` to get first valid price for normalization
- **Impact**: Charts show data from when valid prices exist, instead of failing

---

## Future Enhancements

### Phase 1: Lead-Lag Analysis
- Does commodity movement lead stock by N days?
- Cross-correlation with lags
- Optimal lag period identification

### Phase 2: Alert System
- Monitor spread divergence from MA20
- Notify when correlation breaks down
- Flag unusual margin compression/expansion

---

## Debugging Tips

### 1. Check Timezone Issues
```python
# If merge fails on Date
df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
```

### 2. Verify Spread Calculation
```python
# In Combined View
print(merged_spread[['Date', 'Input', 'Output', 'Spread', 'Spread_MA20']].tail())
```

### 3. Test Correlation Functions
```python
from pages.Ticker_Analysis import calculate_correlations
price_corr, return_corr = calculate_correlations(
    'HPG', ticker_data, df, all_indexes, regional_indexes, stock_data
)
print(f"Price correlations: {price_corr}")
print(f"Return correlations: {return_corr}")
```

---

## Code Quality Standards

### Followed User Preferences:
1. **Vectorized operations**: Pandas/numpy, no loops
2. **Direct calculations**: Minimal error handling
3. **Clear variable names**: `df`, `input_normalized`, `spread_data`
4. **Consistent formatting**: 2-3 decimal places for percentages/correlations

### Best Practices:
- Use `.copy()` when creating DataFrames from filtered data
- Always specify `fill_method=None` in `.pct_change()`
- Use `.ffill()` instead of `.fillna(method='ffill')`
- Handle timezone mismatches explicitly

---

## News Processing System (Latest Session)

### 1. PDF to Markdown Converter (`news/pdf_to_markdown_summarizer.py`)
**Features**:
- Extracts text from PDF reports (PyMuPDF)
- AI-powered summarization via OpenAI API
- Classifies news by commodity groups from `commo_list.xlsx`
- **Output Formats**:
  - Individual JSON: `{report_date, report_file, commodity_news}`
  - Markdown: Human-readable summaries organized by commodity
  - Consolidated JSON: `all_reports.json` - single file with all reports

**Consolidated JSON Structure**:
```json
{
  "last_updated": "2025-10-09T15:30:00",
  "total_reports": 2,
  "reports": [...],  // Full report data
  "by_commodity": {  // Organized for quick lookup
    "Oil": [{"date": "2025-09-12", "news": "..."}],
    "Urea": [{"date": "2025-09-12", "news": "..."}]
  }
}
```

### 2. News Integration in Dashboard
**Files Updated**:
- `commo_dashboard.py`: Added `load_latest_news()` and `get_all_news_summary()`
- `dashboard_app.py`: Shows latest 3 news items per commodity group
- `pages/JPM_News_Summary.py`: Dedicated news browsing page

**Features**:
- News displayed on commodity group pages (after performance metrics)
- Expandable sections with date and report file
- Markdown rendering with $ and ~ escaping (prevents LaTeX/strikethrough)
- Automatically loads from `all_reports.json` (falls back to individual files)

### 3. Workflow
**Structure**:
```
news/
├── reports/              # Store PDF files here
├── process_reports.py    # Helper script
├── pdf_to_markdown_summarizer.py
├── all_reports.json      # Consolidated (used by dashboard)
├── JPM_*_summary.json    # Individual reports
└── JPM_*_summary.md      # Markdown versions
```

**Usage**:
```bash
# Process all PDFs in reports/ folder
cd news
python process_reports.py

# Process specific file
python process_reports.py --file reports/JPM_2025-09-12.pdf

# Consolidate existing summaries
python process_reports.py --consolidate
```

### 4. AI Processing
**Prompt Strategy**:
- Focused on commodity fundamentals (price, supply/demand)
- Ignores company-specific news (unless affects commodities)
- Removes bank/source names from public display
- Returns structured JSON by commodity group
- 1-2 sentence summaries per commodity

**API Configuration**:
- Uses simple `client.responses.create()` pattern
- No conversation history (single request/response)
- Temperature: 1.0 for varied phrasing

### 5. Deployment Preparation
**Files Created**:
- `requirements.txt`: All Python dependencies
- `.streamlit/config.toml`: Theme and server settings
- `.gitignore`: Protects API keys and sensitive data
- `README.md`: Installation and usage instructions

**Deployment-Ready Features**:
- API keys externalized (use Streamlit secrets in production)
- Consolidated JSON reduces file I/O
- Fallback to individual files if consolidated missing
- Clean separation of reports folder

---

## Current Session Updates (2025-10-13)

### 1. Enhanced News System with Metadata Filtering

#### `all_reports.json` Structure Update
- **Added metadata fields**:
  - `report_source`: Source of the report (JPM, HSBC, etc.)
  - `report_series`: Report series name (ChemAgri, GlobalCommodities, GlobalFreight, ChinaMetals, ContainerShipping)
  - `report_type`: Type of report (commodity, sector)
- **Multi-source support**: Now includes JPM and HSBC reports
- **Array structure**: Changed from object with metadata to direct array of reports

**New Structure**:
```json
[
  {
    "report_date": "2025-10-13",
    "report_file": "JPM_ChinaMetals_2025-10-13.pdf",
    "report_source": "JPM",
    "report_series": "ChinaMetals",
    "report_type": "commodity",
    "commodity_news": {...}
  }
]
```

#### JPM News Summary Page Updates (`pages/JPM_News_Summary.py`)
- **Removed markdown file reading**: No longer reads from `reports/*.md` files
- **Direct JSON integration**: Reads directly from `all_reports.json`
- **Added filtering UI**:
  - Multiselect for `Report Source` (JPM, HSBC, etc.)
  - Multiselect for `Report Series` (ChemAgri, GlobalCommodities, etc.)
  - Both filters default to showing all options
- **Improved display**:
  - Changed from expandable sections to direct display with headers
  - Shows metadata in header: Source, Series, Date, Type
  - Each commodity displayed with `### {Commodity}` header
  - Horizontal dividers between commodities
- **Markdown escaping**: Prevents $ (LaTeX) and ~ (strikethrough) rendering issues
- **Removed unused imports**: Cleaned up `datetime` and `pandas` imports

### 2. Group Analysis Page Enhancements (`pages/Group_Analysis.py`)

#### UI Cleanup
- **Dynamic title**: Shows selected group name instead of generic "Commodity Group Analysis"
  - Example: "📊 Aluminum" instead of "📊 Commodity Group Analysis"
- **Removed fluff headers**:
  - Removed "Performance Metrics" subheader
  - Removed "{Group} Index" subheader
- **Component tickers repositioned**: Moved from top section to caption below charts

#### View Mode Toggle
- **Added radio button**: Switch between "Index" and "Components" view
- **Index mode** (default): Shows equal-weighted group index
- **Components mode**:
  - Multiselect to choose specific tickers
  - Defaults to first 3 tickers (or all if ≤3 tickers)
  - Plots multiple component tickers on same chart
  - Allows single or multiple selection for comparison

#### News Display Enhancement
- **Removed limit**: Previously capped at 3 news items, now shows all
- **Scrollable container**:
  - Max height: 400px
  - Auto-scroll when content exceeds height
  - Bordered container with padding
- **Markdown escaping**: $ and ~ characters properly escaped

#### Regional Breakdown
- **Component tickers moved**: Now displayed as captions below regional charts
- **Cleaner layout**: Less visual clutter, more focus on data

### 3. Main Dashboard Updates (`Dashboard.py`)

#### Top Rankings Scaled Down
- **Changed Top 10 → Top 5**:
  - Stock spread tables: Now show top 5 instead of 10
  - Index swing tables: Now show top 5 instead of 10
  - Applies to all time periods: 5D, 10D, 50D, 150D
- **Rationale**: More compact view, focuses on most significant movers

#### Latest Market News Section
- **New section added**: "📰 Latest Market News" at bottom of dashboard
- **Features**:
  - Aggregates news from all commodity groups
  - Sorts by date (newest first)
  - Limits to 20 most recent news items
  - Scrollable container (max-height: 500px)
  - Shows group label with each news item
  - Format: "📅 {date} | {group}"
- **Markdown escaping**: Prevents $ and ~ rendering issues
- **Integration**: Uses `load_latest_news()` from `commo_dashboard.py`

### 4. Project Structure Updates

#### Updated File Locations
```
pages/
├── JPM_News_Summary.py         # JSON-based news browser with filtering
├── Group_Analysis.py            # Enhanced with view toggle and cleanup
├── Ticker_Analysis.py           # (Unchanged)
└── Correlation_Matrix.py        # (Unchanged)

news/
├── all_reports.json             # Multi-source with metadata
├── reports/                     # PDF storage
└── pdf_processor.py             # Processor script
```

### 5. Key Technical Changes

#### News Loading Pattern
**Before**:
```python
# Read markdown files
summary_files = glob.glob('reports/*_summary.md')
with open(file, 'r') as f:
    content = f.read()
```

**After**:
```python
# Read JSON with metadata filtering
with open('all_reports.json', 'r') as f:
    reports_data = json.load(f)

filtered_reports = [
    r for r in reports_data
    if r.get('report_source') in selected_sources
    and r.get('report_series') in selected_series
]
```

#### Scrollable Container Pattern
```python
st.markdown(
    f'<div style="max-height: 400px; overflow-y: auto; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">{content}</div>',
    unsafe_allow_html=True
)
```

#### Component View Implementation
```python
# View mode toggle
view_mode = st.radio('View Mode', options=['Index', 'Components'], horizontal=True)

if view_mode == 'Components':
    selected_tickers = st.multiselect(
        'Select Components to Display',
        options=tickers,
        default=tickers[:3] if len(tickers) > 3 else tickers
    )
    # Plot each selected ticker
    for ticker in selected_tickers:
        fig.add_trace(go.Scatter(...))
```

### 6. UI/UX Improvements

#### Consistent Patterns
- **Scrollable sections**: All news sections use consistent max-height and styling
- **Metadata display**: Consistent format across all pages (Source, Series, Date, Type)
- **Component captions**: Moved to bottom of charts for cleaner layout
- **Horizontal radio buttons**: More compact than vertical stacking

#### User Experience
- **Faster filtering**: Multiselect filters are instant, no page reload
- **Better scannability**: Direct display of news without clicking expandable sections
- **Flexible comparison**: Components mode allows custom ticker selection
- **Reduced clutter**: Removed unnecessary headers and moved metadata to captions

### 7. Reports Summary Page (`pages/Reports_Summary.py`)

#### Hierarchical Filtering
- **Changed filtering structure**: Report Source → Report Name (series)
- **Dynamic cascading**: Report name options update based on selected sources
- **Renamed field**: "Report Series" → "Report Name" for clarity
- **Example flow**: Select JPM → See only JPM series (ChemAgri, ChinaMetals, etc.)

### 8. UI/UX Design Improvements

#### Dashboard Visual Enhancements
- **Section Headers with Gradients**:
  - Market Movers: Purple gradient (`#667eea → #764ba2`)
  - Latest News: Pink-red gradient (`#f093fb → #f5576c`)
  - Includes descriptive subtitles

- **Tabbed Interface**:
  - Tab 1: 📊 Stock Spreads
  - Tab 2: 🔄 Commodity Index Swings
  - Reduces scrolling, cleaner organization

- **Enhanced News Cards**:
  - White cards with subtle shadows
  - 4px left border accent (blue)
  - Date badge + commodity group pill (gradient)
  - Better spacing and typography
  - HTML-based for consistent rendering

- **Last Updated Timestamp**:
  - Top-right corner of dashboard
  - Shows current date/time on load
  - Indicates data freshness

- **Navigation Hints**:
  - Added caption: "💡 **Tip:** Visit the Ticker Analysis page for detailed stock analysis"
  - Guides users to detailed views

#### HTML Rendering Fixes
- **News displays**: Changed from markdown to HTML in scrollable containers
- **Bold text**: `**text**` → `<strong>text</strong>`
- **Line breaks**: `\n\n` → `<br><br>`
- **Separators**: `---` → `<hr>`
- **Character escaping**: Proper HTML entities (`&amp;`, `&lt;`, `&gt;`)
- **Rationale**: Markdown doesn't render inside HTML `<div>` tags

---

**Session completed: News system enhanced, UI modernized, hierarchical filtering implemented.**
