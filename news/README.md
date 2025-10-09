# News Processing System - User Guide

## 📋 Overview

This system automatically extracts commodity market news from PDF reports, classifies them by commodity group, and makes them available to the dashboard.

---

## 🔄 Processing Flow

```
PDF Report → Extract Text → Convert to Markdown → Send to OpenAI → Get JSON by Commodity → Save Files → Consolidate
```

### Detailed Process

1. **PDF Text Extraction** (`extract_pdf_text()`)
   - Opens PDF using PyMuPDF (fitz library)
   - Extracts first 4 pages by default (configurable with `max_pages`)
   - Returns raw text content

2. **Markdown Conversion** (`convert_to_markdown()`)
   - Formats raw text into structured markdown
   - Detects headings (ALL CAPS text)
   - Preserves bullet points and page markers

3. **ChatGPT Summarization** (`summarize_with_chatgpt()`)
   - Loads commodity groups from `commo_list.xlsx`
   - Sends markdown + prompt to OpenAI API
   - Prompt asks AI to extract news for each commodity group
   - Returns JSON: `{"Group Name": "news summary", ...}`

4. **Save Outputs** (`process_pdf()`)
   - Extracts date from filename (e.g., `JPM_2025-09-05.pdf` → `2025-09-05`)
   - Saves **JSON file** with metadata
   - Saves **Markdown file** for human-readable display

5. **Consolidation** (`consolidate_summaries()`)
   - Combines all individual JSONs into simple array
   - Sorted by date (newest first)
   - Dashboard reads from this consolidated file

---

## 🚀 How to Process Reports

### Simple Workflow (Most Common)

**Process all new reports at once:**
```bash
cd news
python process_reports.py
```

This **automatically**:
- ✅ Processes **ALL** PDFs in `news/reports/` folder
- ✅ Creates individual JSON files for each report
- ✅ Consolidates everything into `all_reports.json` at the end

**No manual consolidation step needed!**

---

## 📝 Command Options

| Command | Use Case | What It Does |
|---------|----------|--------------|
| `python process_reports.py` | **New batch of reports** | Processes all PDFs + auto-consolidates |
| `python process_reports.py --file report.pdf` | **One new report** | Processes single PDF + consolidates |
| `python process_reports.py --consolidate` | **Rebuild consolidated file** | Skips processing, just rebuilds `all_reports.json` |

### Examples

**Process specific report:**
```bash
python process_reports.py --file JPM_2025-09-12.pdf
```

**Only rebuild consolidated file (no PDF processing):**
```bash
python process_reports.py --consolidate
```

**Process PDFs from custom directory:**
```bash
python process_reports.py --reports-dir custom_folder
```

---

## 📁 File Structure

### Before Processing
```
news/
├── reports/
│   ├── JPM_2025-09-05.pdf
│   ├── JPM_2025-09-12.pdf
│   └── JPM_2025-09-19.pdf
├── process_reports.py
└── pdf_to_markdown_summarizer.py
```

### After Processing
```
news/
├── reports/
│   └── [PDF files]
├── JPM_2025-09-05_summary.json      ← Individual report (metadata + news)
├── JPM_2025-09-05_summary.md        ← Human-readable version
├── JPM_2025-09-12_summary.json      ← Individual report
├── JPM_2025-09-12_summary.md        ← Human-readable version
├── JPM_2025-09-19_summary.json      ← Individual report
├── JPM_2025-09-19_summary.md        ← Human-readable version
└── all_reports.json                 ← CONSOLIDATED FILE (dashboard uses this)
```

---

## 📊 JSON Structure

### Individual Report JSON
```json
{
  "report_date": "2025-09-05",
  "report_file": "JPM_2025-09-05.pdf",
  "commodity_news": {
    "Oil": "WTI prices rose 3% on supply concerns...",
    "Gas/LNG": "Henry Hub prices declined...",
    "Urea": "India tendered 2.1mt at $460-465/t...",
    "Grain": "USDA cut corn stocks-to-use..."
  }
}
```

### Consolidated JSON (`all_reports.json`)
Simple array of all reports, sorted by date (newest first):

```json
[
  {
    "report_date": "2025-09-12",
    "report_file": "JPM_2025-09-12.pdf",
    "commodity_news": {
      "Oil": "Brent rose to $66.99/bbl...",
      "Gas/LNG": "Natural gas fell to $2.94/mmBTU...",
      ...
    }
  },
  {
    "report_date": "2025-09-05",
    "report_file": "JPM_2025-09-05.pdf",
    "commodity_news": {
      "Oil": "Supply concerns...",
      "Gas/LNG": "Prices declined...",
      ...
    }
  }
]
```

---

## 🎯 Typical Workflow

1. **Add new PDF(s)** to `news/reports/` folder
2. **Run processing**: `cd news && python process_reports.py`
3. **Done!** Dashboard automatically shows updated news

---

## ⚙️ Configuration

### OpenAI API Settings
Edit `pdf_to_markdown_summarizer.py`:

```python
# Line 18-20
DEFAULT_MAX_PAGES = 4                # How many pages to extract
DEFAULT_MODEL = "gpt-5-mini"         # OpenAI model to use
DEFAULT_TEMPERATURE = 1.0            # Temperature for AI generation

# Line 22
OPENAI_API_KEY = "sk-proj-..."       # Your API key
```

### Commodity Groups
The system loads commodity groups from `../commo_list.xlsx` (Group column).

If file not found, falls back to hardcoded list in `load_commodity_groups()` function.

---

## 🔍 How Dashboard Uses This

The dashboard reads from `all_reports.json` (simple array):

1. **Commodity Page** (`dashboard_app.py`):
   - User selects a commodity group (e.g., "Oil")
   - Dashboard calls `load_latest_news(group_name)`
   - Function loops through all reports and extracts news for that group
   - Displays latest 3 news items

2. **News Browser Page** (`pages/JPM_News_Summary.py`):
   - Displays all markdown summary files
   - Shows reports sorted by date

---

## 🐛 Troubleshooting

### No PDFs found
```
⚠ No PDF files found in reports/
```
**Solution**: Make sure PDFs are in `news/reports/` folder

### No summary files found
```
⚠ No summary files found
```
**Solution**: Run `python process_reports.py` first to create summaries

### API key error
```
⚠ No API key provided
```
**Solution**: Set `OPENAI_API_KEY` in `pdf_to_markdown_summarizer.py` (line 22)

### Failed to parse JSON
```
⚠ Failed to parse JSON response
```
**Solution**: AI response was not valid JSON. Check model name and try again.

---

## 📌 Important Notes

- **Filename Format**: PDFs should contain date in format `YYYY-MM-DD` (e.g., `JPM_2025-09-05.pdf`)
- **Simple Structure**: `all_reports.json` is just a flat array - easy to read and extend
- **Consolidation**: Automatically runs after batch processing - no manual step needed
- **Dashboard Integration**: Dashboard loops through array to find news by commodity
- **API Costs**: Each report costs ~$0.01-0.05 depending on model and length

---

## 🔗 Related Files

- `pdf_to_markdown_summarizer.py` - Core processing engine
- `process_reports.py` - Batch processing helper script
- `../commo_dashboard.py` - Dashboard data loading functions
- `../dashboard_app.py` - Main dashboard with news display
- `../commo_list.xlsx` - Commodity group definitions
