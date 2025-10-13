# PDF Report Processing System

## Overview

Automated system for processing PDF reports from multiple sources and generating structured summaries. Reports are processed based on series-specific prompts and all summaries are consolidated into `all_reports.json`.

## Features

✅ **Series-based prompt routing** - Automatic prompt selection based on report series
✅ **Metadata tracking** - Source, series, date, and type metadata for each report
✅ **Direct JSON writing** - No intermediate files, writes directly to `all_reports.json`
✅ **Batch processing** - Process entire folders at once
✅ **Portal-ready architecture** - Designed for future web upload interface

## System Architecture

```
news/
├── prompts/                          # Prompt system
│   ├── __init__.py
│   ├── prompt_router.py             # Series → Prompt mapping
│   ├── commodity_prompts.py         # Multi-sector prompts
│   └── sector_prompts.py            # Sector-specific prompts
├── reports/                          # All PDF files (single folder)
│   ├── JPM_ChemAgri_2025-10-03.pdf
│   ├── JPM_GlobalCommodities_2025-10-06.pdf
│   └── JPM_ContainerShipping_2025-08-10.pdf
├── pdf_processor.py                  # Main processing script ⭐️
├── all_reports.json                  # Consolidated output
└── README.md                         # This file
```

---

## 📝 Naming Convention

**Required Format:**
```
{Source}_{Series}_{Date}.pdf
```

**Examples:**
- `JPM_ChemAgri_2025-10-03.pdf` → JPM source, ChemAgri series
- `CITI_Steel_2025-08-15.pdf` → CITI source, Steel series
- `GS_GlobalCommodities_2025-09-01.pdf` → GS source, GlobalCommodities series

**Rules:**
- Source: Firm name (JPM, CITI, GS, etc.)
- Series: Report series name (ChemAgri, Steel, etc.)
- Date: YYYY-MM-DD format
- Underscores separate components

---

## 📊 JSON Output Structure

Each report in `all_reports.json` contains:

```json
{
  "report_date": "2025-10-03",
  "report_file": "JPM_ChemAgri_2025-10-03.pdf",
  "report_source": "JPM",
  "report_series": "ChemAgri",
  "report_type": "commodity",
  "commodity_news": {
    "Oil": "Brent fell to $64.53/bbl...",
    "Gas/LNG": "U.S. natural gas rose...",
    ...
  }
}
```

---

## 🎯 Series → Prompt Mapping

Configured in `prompts/prompt_router.py`:

### Commodity Reports (Multi-sector, 4 pages)
- `ChemAgri` - Chemicals & Agriculture
- `GlobalCommodities` - Global commodities overview
- `WeeklyMarkets`, `DailyMarkets` - Market updates

### Sector Reports (Focused, 10 pages)
- `ContainerShipping` - Container shipping industry
- `Steel`, `Oil`, `Banking` - Specific sectors

**Adding New Series:**
Edit `prompts/prompt_router.py` → `SERIES_PROMPT_MAP`

---

## 🚀 Usage

### Process Single PDF

```python
from pdf_processor import process_pdf, OPENAI_API_KEY, DEFAULT_MODEL

result = process_pdf(
    pdf_path="reports/JPM_ChemAgri_2025-10-03.pdf",
    api_key=OPENAI_API_KEY,
    model=DEFAULT_MODEL
)
```

### Batch Process Folder

```python
from pdf_processor import process_folder, OPENAI_API_KEY, DEFAULT_MODEL

results = process_folder(
    folder_path='reports/',
    api_key=OPENAI_API_KEY,
    model=DEFAULT_MODEL
)
```

### Add New Report

1. Name PDF: `Source_Series_Date.pdf`
2. Place in `reports/` folder
3. Run: `process_pdf("reports/JPM_ChemAgri_2025-10-11.pdf", api_key=OPENAI_API_KEY)`
4. Report auto-added to `all_reports.json` ✅

---

## 🔄 Processing Flow

```
1. Upload PDF to reports/
2. Parse filename → Extract metadata
3. Lookup series → Get prompt type
4. Extract text (4 or 10 pages)
5. Convert to markdown
6. Send to ChatGPT
7. Parse JSON response
8. Add/update in all_reports.json
9. Done! (No intermediate files)
```

---

## 🌐 Portal Integration (Future)

### Upload Flow
1. User uploads PDF
2. Portal validates filename
3. Extracts source/series/date
4. Shows preview
5. Calls `process_pdf()`
6. Returns summary
7. Displays to user

### Portal Features
- Source/Series dropdowns
- Auto-generate filename
- Real-time processing status
- Bulk upload support

---

## 🛠️ Maintenance

### Add New Series
```python
# prompts/prompt_router.py
SERIES_PROMPT_MAP = {
    'NewSeries': 'commodity',  # or 'sector'
}
```

### Update Prompts
Edit `prompts/commodity_prompts.py` or `prompts/sector_prompts.py`

### Troubleshooting
- **Invalid filename**: Check `Source_Series_Date.pdf` format
- **Series not recognized**: Add to `SERIES_PROMPT_MAP`
- **API error**: Verify OpenAI API key

---

## ✅ Migration Complete

**Old System:**
- Keyword-based detection
- Multiple folders
- Individual summary files
- Manual consolidation

**New System:**
- Series-based mapping ✅
- Single reports/ folder ✅
- Direct JSON writes ✅
- No intermediate files ✅

**All old reports renamed to include series name ✅**


# Quick Start Guide

## 🚀 Getting Started in 3 Steps

### 1. Name Your PDF
```
{Source}_{Series}_{Date}.pdf
```
Example: `JPM_ChemAgri_2025-10-11.pdf`

### 2. Place in reports/ Folder
```
news/reports/JPM_ChemAgri_2025-10-11.pdf
```

### 3. Run Processor
```python
from pdf_processor import process_pdf, OPENAI_API_KEY, DEFAULT_MODEL

process_pdf("reports/JPM_ChemAgri_2025-10-11.pdf",
            api_key=OPENAI_API_KEY,
            model=DEFAULT_MODEL)
```

**Done!** Check `all_reports.json` for the new report.

---

## 📁 Available Report Series

### Multi-Sector (4 pages extracted)
- `ChemAgri` - Chemicals & Agriculture
- `GlobalCommodities` - Global overview
- `WeeklyMarkets` - Weekly updates
- `DailyMarkets` - Daily updates

### Sector-Specific (10 pages extracted)
- `ContainerShipping`
- `Steel`
- `Oil`
- `Banking`

---

## 🔧 Add New Series

Edit `prompts/prompt_router.py`:

```python
SERIES_PROMPT_MAP = {
    'MyNewSeries': 'commodity',  # or 'sector'
}
```

---

## 📝 Batch Processing

```python
from pdf_processor import process_folder

# Process all PDFs in reports/ folder
results = process_folder('reports/',
                         api_key=OPENAI_API_KEY,
                         model=DEFAULT_MODEL)
```

---

## ✅ What Changed

### Before
- Keyword detection
- Multiple folders
- Individual summary files
- Manual consolidation

### After
- Series-based mapping
- Single reports/ folder
- Direct JSON writes
- Auto-consolidation

---

## 📞 Need Help?

See `README.md` for detailed documentation.
