# Implementation Options - Calculated Series & Volume Data

## Feature 1: Calculated Series

### Background
Create derived commodities based on formulas (e.g., Iron Ore Spread = Output - Input, Aluminum Ratio = LME/China, Weighted Basket = 0.6*A + 0.4*B).

---

### Option 1A: MongoDB Formula Collection + On-the-Fly Calculation

**Architecture**:
```json
// Collection: calculated_series
{
  "item": "Iron Ore Spread China",
  "formula_type": "spread",  // spread, ratio, weighted_average, custom
  "components": [
    {"name": "Ore 62", "weight": -1},
    {"name": "Ore Fines", "weight": 1}
  ],
  "sector": "Steel Material",
  "group": "Iron Ore",
  "region": "China"
}
```

**Implementation**:
1. Admin page (e.g., `pages/8_Calculated_Series_Admin.py`) to define formulas
2. `classification_loader.py` loads both raw + calculated series
3. Calculate on page load: fetch components → apply formula → merge with raw data

**Pros**:
- ✅ Flexible - users can modify formulas without code changes
- ✅ Always fresh calculations (no stale data)
- ✅ Easy to add new formula types (ratios, spreads, custom)
- ✅ Consistent with current MongoDB architecture

**Cons**:
- ❌ Performance overhead - recalculates every page load (even with caching)
- ❌ Complex formula validation logic needed
- ❌ Requires alignment of dates across components

**Cache Strategy**: Cache calculated results for 60s, recalculate when formula changes

---

### Option 1B: Pre-Calculate and Store in SQL Server

**Architecture**:
- Create Python script `calculate_series_batch.py`
- Runs daily/weekly to calculate all derived series
- Stores results as new rows in SQL Server commodity tables
- Treated as regular commodities in all pages

**Implementation**:
1. Define formulas in Python config file or MongoDB
2. Batch script loads raw data → calculates → inserts into SQL
3. Add to `commodity_classification` collection with `calculated: true` flag
4. Pages load them like any other commodity

**Pros**:
- ✅ Best performance - no runtime calculation
- ✅ Simple page logic - calculated series are just regular tickers
- ✅ Works well with existing caching (1 hour SQL cache)

**Cons**:
- ❌ Not real-time - depends on batch schedule
- ❌ Formula changes require re-running batch job
- ❌ Needs write access to SQL Server (may not have)
- ❌ Data duplication (storage concern if many calculated series)

**Best For**: Production use with stable formulas, when performance is critical

---

### Option 1C: Hybrid - Admin Page + Streamlit Cache

**Architecture**:
```python
# Load raw data (1 hour cache)
@st.cache_data(ttl=3600)
def load_raw_sql_data():
    return fetch_all_commodity_data()

# Load formulas (60s cache)
@st.cache_data(ttl=60)
def load_calculated_formulas():
    return mongodb_utils.load_calculated_series()

# Calculate and cache (5 min cache)
@st.cache_data(ttl=300)
def get_calculated_series(formula_id, raw_df):
    formula = get_formula(formula_id)
    return apply_formula(formula, raw_df)
```

**Implementation**:
1. MongoDB collection stores formulas
2. Three-layer cache: raw data (1h) → formulas (60s) → calculated results (5min)
3. Admin page to add/edit formulas with preview
4. `classification_loader.py` merges calculated series with raw data

**Pros**:
- ✅ Good performance with multi-layer caching
- ✅ Formula changes propagate in 5 minutes
- ✅ No SQL Server write access needed
- ✅ Preview formulas before saving

**Cons**:
- ❌ Cache complexity (3 layers to manage)
- ❌ Recalculation on every cache miss
- ❌ Memory usage if many calculated series

**Best For**: Balanced approach - flexibility + performance

---

### Option 1D: Python Config File (Simple)

**Architecture**:
```python
# calculated_series_config.py
CALCULATED_SERIES = {
    "Iron Ore Spread China": {
        "type": "spread",
        "output": "Ore 62",
        "input": "Ore Fines",
        "group": "Iron Ore",
        "region": "China"
    },
    "LME/China Aluminum Ratio": {
        "type": "ratio",
        "numerator": "Aluminum LME",
        "denominator": "Aluminum SMM",
        "group": "Aluminum",
        "region": "Global"
    }
}
```

**Implementation**:
1. Simple Python file with formula definitions
2. `classification_loader.py` reads config and calculates
3. Add to commodity classification after calculation
4. Edit formulas by modifying Python file (requires redeploy on cloud)

**Pros**:
- ✅ Simplest to implement
- ✅ Version controlled (tracked in git)
- ✅ No new admin page needed
- ✅ Good for small number of stable formulas

**Cons**:
- ❌ Requires code deployment to change formulas
- ❌ Not user-friendly for non-technical users
- ❌ Limited formula types (need to code new types)

**Best For**: MVP/prototyping, small team with technical users

---

## Feature 2: Volume Data Upload

### Background
Tickers have input/output prices but need production/sales volume data. Data can be irregular: monthly, quarterly, yearly, or weekly.

---

### Option 2A: MongoDB Volume Collection + Interpolation

**Architecture**:
```json
// Collection: ticker_volumes
{
  "ticker": "HPG",
  "data_type": "production",  // or "sales"
  "frequency": "quarterly",   // monthly, quarterly, yearly, weekly
  "unit": "million tonnes",
  "data": [
    {"date": "2024-Q1", "value": 1.2},
    {"date": "2024-Q2", "value": 1.5}
  ],
  "uploaded_by": "user@email.com",
  "uploaded_at": "2025-10-22 10:30:00"
}
```

**Implementation**:
1. Admin page: `pages/9_Volume_Upload_Admin.py`
2. Upload options: Manual entry, CSV upload, Excel upload
3. Backend interpolates to daily for charting (forward-fill or linear)
4. Ticker Analysis page loads volume data alongside prices

**Pros**:
- ✅ Handles irregular frequencies naturally
- ✅ Flexible - can store any frequency without schema changes
- ✅ Works on Streamlit Cloud (no local files)
- ✅ Audit trail (uploaded_by, uploaded_at)
- ✅ Can store multiple data types (production, sales, inventory)

**Cons**:
- ❌ Interpolation introduces assumptions (forward-fill vs linear)
- ❌ Need to handle frequency conversions (Q1 2024 → date range)
- ❌ Complex querying for mixed frequencies

**Best For**: Production use, flexible data sources, non-technical users

---

### Option 2B: Extend SQL Server Tables (If Write Access)

**Architecture**:
- Add volume columns to existing commodity price tables
- Store volume as separate "ticker" entries (e.g., "HPG_VOLUME")
- Use same date structure as price data

**Implementation**:
1. Create volume tickers in SQL Server (HPG_PRODUCTION, HPG_SALES)
2. Users upload CSV → Python script inserts into SQL
3. Load volume data same way as prices (via `sql_connection.py`)
4. Join volume with price data in pages

**Pros**:
- ✅ Reuses existing SQL infrastructure
- ✅ Consistent with current data flow
- ✅ Fast queries (indexed, cached)
- ✅ No new MongoDB collection needed

**Cons**:
- ❌ Requires SQL Server write access (may not have)
- ❌ Less flexible for irregular frequencies
- ❌ Need to interpolate quarterly → daily before upload
- ❌ Harder to manage on Streamlit Cloud

**Best For**: If you control SQL Server and want centralized data

---

### Option 2C: CSV Files in MongoDB GridFS

**Architecture**:
```json
// Collection: volume_files
{
  "ticker": "HPG",
  "file_name": "HPG_quarterly_production_2024.csv",
  "frequency": "quarterly",
  "data_type": "production",
  "file_id": ObjectId("..."),  // GridFS reference
  "uploaded_at": "2025-10-22 10:30:00"
}
```

**Implementation**:
1. Upload CSV files to MongoDB GridFS
2. Parse on-the-fly when ticker page is loaded
3. Cache parsed results (5 min TTL)
4. Admin page to upload/delete files

**Pros**:
- ✅ Simple file management
- ✅ Users can download original files for audit
- ✅ No schema constraints - any CSV format accepted
- ✅ Easy to version (multiple files per ticker)

**Cons**:
- ❌ Parsing overhead on every load
- ❌ Need to validate CSV format
- ❌ File management UI needed (list, delete, reupload)
- ❌ Harder to query/aggregate across tickers

**Best For**: Ad-hoc uploads, keeping original data files

---

### Option 2D: Admin Page with Manual Entry + Excel Upload

**Architecture**:
```python
# Admin page UI
- Ticker selector
- Data type: Production / Sales / Inventory
- Frequency: Monthly / Quarterly / Yearly / Weekly
- Input method:
  [Tab 1] Manual entry table (add rows one by one)
  [Tab 2] Excel upload (template download available)
```

**MongoDB Schema** (same as Option 2A):
```json
{
  "ticker": "HPG",
  "data_type": "production",
  "frequency": "quarterly",
  "data": [
    {"period": "2024-Q1", "value": 1.2},
    {"period": "2024-Q2", "value": 1.5}
  ]
}
```

**Implementation**:
1. Admin page with two input methods
2. Excel template generator (download empty template)
3. Validation: Check date formats, numeric values, no gaps
4. Preview before saving
5. Edit/delete existing entries

**Pros**:
- ✅ User-friendly for both quick edits and bulk uploads
- ✅ Template ensures consistent format
- ✅ Validation prevents bad data
- ✅ No file storage needed (data goes directly to MongoDB)

**Cons**:
- ❌ More complex admin page UI
- ❌ Need to parse Excel files (openpyxl)
- ❌ Template maintenance

**Best For**: Best UX for end users, recommended for production

---

### Option 2E: Quarterly-Only Simplification

**Architecture**:
- Assume all volume data is quarterly (simplify the problem)
- Store in MongoDB with fixed quarterly structure
- Display quarterly bars on charts (no interpolation)

**Implementation**:
```json
{
  "ticker": "HPG",
  "data_type": "production",
  "quarters": [
    {"year": 2024, "quarter": 1, "value": 1.2},
    {"year": 2024, "quarter": 2, "value": 1.5}
  ]
}
```

**Display Strategy**:
- Price chart: Daily line
- Volume chart: Quarterly bars (side-by-side)
- No interpolation needed

**Pros**:
- ✅ Simplest implementation
- ✅ No frequency conversion logic
- ✅ Matches typical financial reporting
- ✅ Clear visual distinction (line vs bars)

**Cons**:
- ❌ Inflexible if monthly/yearly data available
- ❌ Need separate solution for weekly data
- ❌ Limited use cases

**Best For**: MVP if volume data is primarily quarterly

---

## Recommended Approach

### For Calculated Series:
**Recommendation**: **Option 1C (Hybrid)** or **Option 1D (Config File)** for MVP

**Rationale**:
- Start with Option 1D (config file) for quick prototyping
- Migrate to Option 1C when you have >10 calculated series
- Option 1A is over-engineered unless you need daily formula changes
- Option 1B requires SQL write access (may not have)

**Implementation Order**:
1. Create `calculated_series_config.py` with 2-3 example formulas
2. Update `classification_loader.py` to calculate and merge
3. Test on Price Chart page
4. If successful, build admin page (Option 1C)

---

### For Volume Data:
**Recommendation**: **Option 2D (Admin Page with Manual + Excel Upload)**

**Rationale**:
- Best user experience (manual for quick fixes, Excel for bulk)
- MongoDB flexible enough for any frequency
- No SQL Server changes needed
- Works on Streamlit Cloud

**Implementation Order**:
1. Create MongoDB collection `ticker_volumes`
2. Build admin page `pages/9_Volume_Upload_Admin.py`
   - Tab 1: Ticker selector + manual table entry
   - Tab 2: Excel upload with template download
3. Add volume loading to `mongodb_utils.py`
4. Update Ticker Analysis page to display volume chart
5. Add interpolation logic for daily alignment (forward-fill default)

**Display Strategy**:
```python
# In Ticker Analysis page
fig = make_subplots(rows=2, cols=1, specs=[[{"secondary_y": False}], [{"secondary_y": False}]])

# Row 1: Price (line chart, daily)
fig.add_trace(go.Scatter(x=dates, y=prices, name="Stock Price"), row=1, col=1)

# Row 2: Volume (bar chart, quarterly/monthly)
fig.add_trace(go.Bar(x=volume_dates, y=volumes, name="Production Volume"), row=2, col=1)
```

---

## Next Steps Discussion Points

### Questions for You:

1. **Calculated Series**:
   - How many calculated series do you anticipate? (5? 20? 100?)
   - Will formulas change frequently or mostly static?
   - Who will define formulas - just you or end users too?

2. **Volume Data**:
   - What's the typical frequency for your volume data? (quarterly most common?)
   - Do you need to support all 4 frequencies or can we start with quarterly?
   - Should volume be displayed as bars (quarterly points) or interpolated line?
   - Do you need multiple volume types per ticker (production + sales + inventory)?

3. **Priority**:
   - Which feature should be implemented first?
   - MVP scope for initial version?

4. **Integration**:
   - Should calculated series appear in Price Chart page?
   - Should volume appear in Ticker Analysis page or separate page?
   - Do you want correlation analysis with volume (price vs volume)?

---

**Document Created**: 2025-10-22
