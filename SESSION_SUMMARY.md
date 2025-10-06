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
- Excludes "Pangaseus" group
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
- Inputs: Negative changes marked (rising input = margin pressure)
- Outputs: Positive changes marked (rising output = margin expansion)
- Caption explains equal-weighted aggregation methodology

#### Input/Output Charts
- **Aggregation Toggle**: Sidebar checkbox controls these charts
- Normalized to base 100 for comparison
- Line widths: All set to `width=2` for consistency
- Shows data source names in tables (5D/10D/50D/150D % changes)
- Number formatting: 2 decimal places

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

#### Sector Performance Chart (Top of Page)
- Shows all 9 sectors on single chart
- Normalized to base 100 starting from 2025-01-01
- Horizontal legend at top for space efficiency
- Quick visual comparison of sector trends

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
- **Equal-weight**: Average of daily returns
- **Base value**: 100 (normalized for comparison)
- **Missing data handling**: Robust NA handling at multiple levels
- **Aggregation**: Always used in Combined View for consistent spread calculation

#### Equal-Weight Index Calculation Steps:
1. **Get component prices**: Pivot data into matrix (dates × tickers)
2. **Calculate daily returns**: `pct_change(fill_method=None)` for each ticker
3. **Equal-weight averaging**: `mean(axis=1, skipna=True)` across all available tickers
4. **Build cumulative index**: `(1 + avg_returns).cumprod() * base_value`
5. **Set starting value**: `index_values.iloc[0] = base_value`

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
- Uses aggregated data (multiple items → equal-weighted index)
- Single input/output → uses that item directly

### 3. Correlation Display
- **Regional only**: Group-level indexes excluded
- **Color gradient**: Applied to all correlation tables
- **Spread correlation**: Separate from commodity correlations

---

## Future Enhancements

### Phase 1: Summary Table for All Tickers
- Use `calculate_ticker_summary()` in a loop
- Display all tickers with their Input/Output changes
- Sortable/filterable table

### Phase 2: Lead-Lag Analysis
- Does commodity movement lead stock by N days?
- Cross-correlation with lags
- Optimal lag period identification

### Phase 3: Alert System
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

**Session completed successfully. All features integrated and working.**
