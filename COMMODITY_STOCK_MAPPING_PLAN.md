# Commodity-to-Stock Mapping Plan

## Overview
This document outlines functions and algorithms needed to track commodity performance and map it to stock performance for investment analysis.

---

## 1. Stock Data Integration

### Functions Needed:
- **`load_stock_data(tickers=None, start_date=None, end_date=None)`**
  - Load stock price data from `DAILY DATA/PRICE_VOLUME.csv`
  - Filter by ticker list and date range
  - Return normalized DataFrame with columns: [Date, Ticker, Close, Volume]

- **`calculate_stock_returns(stock_df, periods=[1, 5, 15])`**
  - Calculate daily and period returns for stocks
  - Return DataFrame with return columns for each period

- **`load_commodity_stock_mapping()`**
  - Load mapping configuration from `commodity_stock_mapping.xlsx`
  - Schema: [Commodity_Group, Stock_Ticker, Relationship_Type, Weight, Region]
  - Relationship types:
    - `Direct`: Producers (e.g., HPG, HSG for Steel)
    - `Indirect`: Users/Consumers (e.g., automotive for Steel)
    - `Regional`: Geographic exposure

### Algorithm:
```python
# Merge stock data with commodity indexes on Date
# Forward-fill missing dates to align with commodity data
# Normalize both to base 100 for comparison
```

---

## 2. Correlation Analysis

### Functions Needed:
- **`calculate_correlation(commodity_index, stock_ticker, window=30, method='pearson')`**
  - Rolling correlation between commodity index and stock price
  - Methods: pearson (linear), spearman (rank-based)
  - Return time series of correlation coefficients

- **`find_top_correlated_stocks(commodity_group, top_n=10, min_correlation=0.3)`**
  - Identify stocks most correlated with commodity group
  - Return ranked DataFrame: [Stock_Ticker, Correlation, P_Value, Beta]

- **`correlation_heatmap(commodity_groups, stock_list)`**
  - Create correlation matrix between all commodity groups and stocks
  - Visualize with plotly heatmap

### Algorithm:
```python
# Pearson Correlation
corr = stock_returns.corr(commodity_returns)

# Rolling Correlation (30-day window)
rolling_corr = stock_returns.rolling(30).corr(commodity_returns)

# Significance Testing
from scipy.stats import pearsonr
corr, p_value = pearsonr(stock_returns, commodity_returns)
```

---

## 3. Comparative Performance Analysis

### Functions Needed:
- **`overlay_stock_performance(commodity_index, stock_tickers, normalize=True)`**
  - Normalize commodity index and stock prices to base 100
  - Plot on same chart with dual y-axis option
  - Return plotly figure

- **`relative_strength_comparison(commodity_group, stock_tickers, periods=[30, 90, 180])`**
  - Compare percentage changes over multiple timeframes
  - Show which outperformed: commodity index vs stocks
  - Return comparison DataFrame

- **`calculate_beta(commodity_index, stock_ticker, window=90)`**
  - Measure stock sensitivity to commodity movements
  - Beta = Cov(stock, commodity) / Var(commodity)
  - Return rolling beta time series

### Algorithm:
```python
# Normalization for overlay
normalized_commodity = (commodity_index / commodity_index.iloc[0]) * 100
normalized_stock = (stock_price / stock_price.iloc[0]) * 100

# Beta Calculation
returns_commodity = commodity_index.pct_change()
returns_stock = stock_price.pct_change()
covariance = returns_stock.rolling(90).cov(returns_commodity)
variance = returns_commodity.rolling(90).var()
beta = covariance / variance

# Interpretation:
# Beta > 1: Stock is more volatile than commodity
# Beta = 1: Stock moves in line with commodity
# Beta < 1: Stock is less volatile
# Beta < 0: Stock moves opposite to commodity
```

---

## 4. Lead-Lag Analysis

### Functions Needed:
- **`calculate_lead_lag_correlation(commodity_index, stock_ticker, max_lag=10)`**
  - Test correlation at different time lags (-10 to +10 days)
  - Identify if commodity leads or lags stock price
  - Return DataFrame: [Lag_Days, Correlation]

- **`predict_stock_direction(commodity_index, forecast_days=5)`**
  - Use commodity index changes to predict stock direction
  - Simple signal: if commodity up X% over Y days → stock likely follows
  - Return prediction DataFrame with confidence scores

- **`granger_causality_test(commodity_index, stock_ticker, max_lag=5)`**
  - Statistical test: does commodity index help predict stock price?
  - Return test statistics and p-values

### Algorithm:
```python
# Cross-Correlation with Lags
from scipy.signal import correlate
for lag in range(-10, 11):
    if lag < 0:
        corr = stock_returns[:-lag].corr(commodity_returns[lag:])
    elif lag > 0:
        corr = stock_returns[lag:].corr(commodity_returns[:-lag])
    else:
        corr = stock_returns.corr(commodity_returns)

# Granger Causality (using statsmodels)
from statsmodels.tsa.stattools import grangercausalitytests
data = pd.DataFrame({
    'stock': stock_returns,
    'commodity': commodity_returns
})
result = grangercausalitytests(data[['stock', 'commodity']], maxlag=5)

# Interpretation:
# Positive lag: Commodity leads stock by X days
# Negative lag: Stock leads commodity by X days
```

---

## 5. Dashboard Enhancements

### New Features:
1. **Stock Selector Section**
   - Multi-select dropdown for stock tickers
   - Auto-suggest stocks based on selected commodity group
   - Show stock company names alongside tickers

2. **Correlation Panel**
   - Display correlation coefficient between commodity and selected stock
   - Show beta value and interpretation
   - Traffic light indicator: Green (high +corr), Yellow (low corr), Red (negative corr)

3. **Affected Stocks Table**
   - When commodity group selected, show table of related stocks
   - Columns: [Ticker, Name, Correlation, Beta, 1D%, 5D%, 15D%]
   - Sortable by correlation or performance

4. **Comparison Chart**
   - Dual-axis chart: Commodity index (left) + Stock price (right)
   - Both normalized to base 100 at chart start
   - Toggleable: show absolute values or normalized

5. **Lead-Lag Visualization**
   - Bar chart showing correlation at different lags
   - Highlight optimal lag period

### Layout:
```
[Top: Largest Swings Summary Table]
---
[Sidebar: Select Commodity Group + Select Stocks]
---
[Main Area]
  - Commodity Index Chart
  - Performance Metrics (1D, 5D, 15D)

  [NEW: Stock Comparison Section]
  - Correlation Metrics (correlation, beta, lead/lag)
  - Affected Stocks Table
  - Overlay Chart (Commodity + Stock)
  - Lead-Lag Chart

  [Regional Breakdown Tabs]
```

---

## 6. Data Requirements

### New Files Needed:
1. **`commodity_stock_mapping.xlsx`**
   - Columns: `Commodity_Group`, `Stock_Ticker`, `Relationship_Type`, `Weight`, `Region`, `Notes`
   - Example rows:
     ```
     Steel, HPG, Direct, 1.0, VN, Major steel producer
     Steel, HSG, Direct, 1.0, VN, Major steel producer
     Steel, NKG, Direct, 0.8, VN, Steel producer
     Oil, PVD, Direct, 1.0, VN, Oil & gas exploration
     Oil, GAS, Direct, 1.0, VN, Gas distribution
     Agriculture, HAG, Direct, 1.0, VN, Agriculture/rubber
     ```

2. **Stock Price Data** (already available)
   - Source: `DAILY DATA/PRICE_VOLUME.csv`
   - Use `CLOSEPRICEADJUSTED` column

---

## 7. Statistical Concepts & Formulas

### Correlation
- **Pearson Correlation**: Measures linear relationship
  ```
  ρ = Cov(X,Y) / (σ_X * σ_Y)
  Range: -1 to +1
  ```

### Beta
- **Stock Beta to Commodity**: Sensitivity measure
  ```
  β = Cov(R_stock, R_commodity) / Var(R_commodity)

  Interpretation:
  β = 1.5: Stock moves 1.5% for every 1% commodity move
  β = 0.5: Stock moves 0.5% for every 1% commodity move
  ```

### Lead-Lag Correlation
- **Cross-correlation at lag k**:
  ```
  ρ_k = Corr(X_t, Y_{t-k})

  If max ρ at k=3: X leads Y by 3 days
  If max ρ at k=-2: Y leads X by 2 days
  ```

### Granger Causality
- **Test**: Does past commodity data help predict future stock prices?
  ```
  H0: Commodity does NOT Granger-cause Stock
  If p-value < 0.05: Reject H0 (commodity helps predict stock)
  ```

---

## 8. Implementation Priority

### Phase 1: Basic Integration
1. Create `commodity_stock_mapping.xlsx` file
2. Implement `load_stock_data()` function
3. Implement `calculate_correlation()` function
4. Add stock selector to dashboard sidebar

### Phase 2: Visualization
1. Implement `overlay_stock_performance()` function
2. Add comparison chart to dashboard
3. Display correlation coefficient on dashboard

### Phase 3: Advanced Analytics
1. Implement `calculate_beta()` function
2. Implement `calculate_lead_lag_correlation()` function
3. Add affected stocks table
4. Add lead-lag visualization

### Phase 4: Predictive Features
1. Implement `granger_causality_test()` function
2. Implement `predict_stock_direction()` function
3. Add signal/alert system for high-correlation movements

---

## 9. Example Use Cases

### Use Case 1: Steel Price Surge
```
Scenario: Steel commodity index up 5% over 5 days
Expected: HPG, HSG stocks should show positive correlation
Action: Check correlation panel, review beta, look for entry points
```

### Use Case 2: Oil Price Drop
```
Scenario: Oil index down 10% over 15 days
Expected: PVD, GAS stocks likely to decline (high correlation)
Action: Monitor lead-lag to see if commodity leads stock by 2-3 days
Opportunity: Short stocks before they fully price in oil decline
```

### Use Case 3: Agriculture Seasonality
```
Scenario: Coffee prices rising (harvest season)
Expected: Coffee-related stocks (e.g., NKL) follow with lag
Action: Use lead-lag analysis to time stock entry
```

---

## 10. Next Steps

1. Review and approve this plan
2. Create `commodity_stock_mapping.xlsx` with initial mappings
3. Implement Phase 1 functions in `commo_dashboard.py`
4. Update `dashboard_app.py` with new UI components
5. Test with real data and iterate

ticker | company_name | sector_primary | geography | commodity_inputs | commodity_outputs | input_sensitivity | output_sensitivity | notes
-------|--------------|----------------|-----------|------------------|-------------------|-------------------|--------------------|---------
XOM    | Exxon Mobil  | Energy        | Global    | []               | [Oil, Gas/LNG]   | {}                | {Oil:0.7, Gas:0.3} | Integrated
DAL    | Delta        | Airlines      | US        | [Jet Fuel]       | []               | {Jet Fuel:0.8}    | {}                 | High fuel cost
FCX    | Freeport     | Metals        | Global    | []               | [Copper, Gold]   | {}                | {Copper:0.85, Gold:0.15} | Major producer