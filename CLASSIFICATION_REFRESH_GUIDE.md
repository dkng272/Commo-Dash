# Classification Refresh Architecture

## Problem Solved

Previously, when you updated commodity classifications in the Admin page, other pages wouldn't see the changes for up to 1 hour because:
- SQL data + classifications were cached together
- Changing classifications in MongoDB didn't invalidate the combined cache

## New Two-Layer Caching Architecture

### Layer 1: Raw SQL Data (Expensive - Cache 1 hour)
```python
@st.cache_data(ttl=3600)
def load_raw_sql_data():
    return load_sql_data_raw(start_date='2024-01-01')
```

### Layer 2: Fresh Classification (Cheap - Cache 60 seconds)
```python
def load_data():
    df_raw = load_raw_sql_data()  # Cached 1 hour
    df = apply_classification(df_raw)  # Re-applied every page load using 60s cached classifications
    return df
```

## How It Works

1. **SQL fetch** happens once per hour (expensive operation)
2. **Classification fetch** from MongoDB happens every 60 seconds (cheap operation)
3. **Classification application** (mapping) happens every page load (instant operation)

**Result:** Classification changes appear within ~60 seconds without re-fetching SQL data!

## Pages Already Updated

✅ **Dashboard.py** - Updated with two-layer caching
✅ **mongodb_utils.py** - Classification TTL reduced to 60 seconds
✅ **classification_loader.py** - Added `load_sql_data_raw()` function
✅ **pages/7_Commodity_List_Admin.py** - Updated save message

## Pages That Need Updating

The following pages use `load_sql_data_with_classification()` and need the same two-layer pattern:

### 🔧 To Update:

1. **pages/1_Price_Chart.py**
2. **pages/2_Group_Analysis.py**
3. **pages/3_Ticker_Analysis.py**

## Update Pattern for Each Page

### BEFORE (Old Pattern):
```python
from classification_loader import load_sql_data_with_classification

@st.cache_data(ttl=3600)
def load_data():
    df = load_sql_data_with_classification(start_date='2024-01-01')
    return df
```

### AFTER (New Pattern):
```python
from classification_loader import load_sql_data_raw, apply_classification

@st.cache_data(ttl=3600)
def load_raw_sql_data():
    """Load RAW SQL data (cached 1 hour)."""
    return load_sql_data_raw(start_date='2024-01-01')

def load_data():
    """
    Load data with FRESH classification.
    SQL cached 1 hour, classification re-applied every page load.
    """
    df_raw = load_raw_sql_data()  # Cached
    df = apply_classification(df_raw)  # Fresh
    return df
```

## Key Benefits

1. ✅ **Fast updates** - Classification changes visible in ~60 seconds
2. ✅ **Performance** - SQL queries still cached (expensive operation)
3. ✅ **No redundancy** - Classification mapping is cheap (just dictionary lookups)
4. ✅ **Clean architecture** - Separation of concerns (data fetch vs. enrichment)

## Testing

After making changes to commodity classifications:
1. Save in Admin page
2. Wait ~60 seconds
3. Refresh any dashboard page
4. Changes should appear (without re-querying SQL)
