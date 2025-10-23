# Catalyst Search - Simple Guide

Search X (Twitter) for commodity price catalysts using xAI Grok.

## Setup

```bash
# 1. Install
pip install xai-sdk

# 2. Set API key (already done in .env)
# XAI_API_KEY is in .env file
```

## Usage

### Single Search
```bash
# Basic search
python catalyst_search.py --commodity "Tungsten" --days 7

# With direction filter (bullish/bearish)
python catalyst_search.py --commodity "Iron Ore" --days 7 --direction bullish
```

### Batch Search (Multiple Commodities)
```bash
# Quick batch
python batch_search.py --commodities "Iron Ore,HRC,Coal,Copper" --days 7

# Using config file
python batch_search.py --config batch_config.json
```

**batch_config.json example:**
```json
{
  "commodities": ["Iron Ore", "HRC", "Coal"],
  "lookback_days": 7,
  "direction": "both",
  "output_dir": "output"
}
```

## Output

Results saved to: `output/catalyst_{commodity}_{timestamp}.json`

**JSON structure:**
```json
{
  "_meta": {
    "search_timestamp": "2025-10-23T17:30:00Z",
    "commodity_group": "Tungsten"
  },
  "summary": "1-2 sentences explaining why prices moved",
  "timeline": [
    {"date": "2025-10-22", "event": "what happened"},
    {"date": "2025-10-21", "event": "what happened"}
  ]
}
```

## Common Use Cases

**1. Explain price spike:** Dashboard shows "Iron Ore +8%"
```bash
python catalyst_search.py --commodity "Iron Ore" --days 7 --direction bullish
```

**2. Weekly market scan:** Every Monday
```bash
python batch_search.py --commodities "Iron Ore,HRC,Coal,Copper,Tungsten" --days 7
```

**3. Investigate drop:**
```bash
python catalyst_search.py --commodity "Coal" --days 5 --direction bearish
```

## Tips

- **Search period**: 5-7 days is best, 14 days max
- **Direction filter**: Use when you know price direction
- **Commodity names**: Match your dashboard groups exactly
- **Batch delay**: Default 5s between searches (avoid rate limits)

## Integration (Future)

**MongoDB schema:**
```python
# catalysts collection
{
  "date": "2025-10-23",
  "commodity_group": "Iron Ore",
  "summary": "Prices rose due to supply disruption",
  "timeline": [
    {"date": "2025-10-22", "event": "Vale mine closure"}
  ]
}
```

**Dashboard display:**
- Widget: Show summary + timeline per group
- Chart: Mark catalyst dates when hovered

---

That's it! Start testing with your Tungsten example:
```bash
python catalyst_search.py --commodity "Tungsten" --days 14 --direction bullish
```
