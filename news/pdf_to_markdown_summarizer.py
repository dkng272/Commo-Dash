#%% [markdown]
# # PDF to Markdown Converter & ChatGPT Summarizer
# Converts PDF to markdown and summarizes key news/information using OpenAI API
# Uses PyMuPDF (fitz) for automatic PDF text extraction

#%% Imports and Configuration
import os
import sys
import fitz  # PyMuPDF
from openai import OpenAI
import json
import pandas as pd

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Default settings
DEFAULT_MAX_PAGES = 4
DEFAULT_MODEL = "gpt-5-mini" 
DEFAULT_TEMPERATURE = 1.0

OPENAI_API_KEY = "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"  # Fill in your OpenAI API key


#%% PDF Extraction Function
def extract_pdf_text(pdf_path, max_pages=None):
    """
    Extract text from PDF using PyMuPDF

    Args:
        pdf_path: Path to PDF file
        max_pages: Maximum number of pages to extract (default: 4)

    Returns:
        str: Extracted text content
    """
    if max_pages is None:
        max_pages = DEFAULT_MAX_PAGES

    print(f"📖 Opening PDF: {os.path.basename(pdf_path)}")

    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        pages_to_extract = min(max_pages, total_pages)

        text_content = []

        print(f"📄 Extracting first {pages_to_extract} of {total_pages} pages...")

        for page_num in range(pages_to_extract):
            page = doc[page_num]
            text = page.get_text()
            if text.strip():
                text_content.append(f"--- Page {page_num + 1} ---\n{text}")

        doc.close()

        full_text = "\n\n".join(text_content)
        print(f"✓ Extracted {len(full_text):,} characters from {pages_to_extract} pages")

        return full_text

    except Exception as e:
        print(f"✗ Error extracting PDF: {e}")
        return None

#%% Markdown Conversion Function
def convert_to_markdown(raw_text):
    """
    Convert raw PDF text to structured markdown

    Args:
        raw_text: Raw text from PDF

    Returns:
        str: Formatted markdown content
    """
    lines = raw_text.split('\n')
    markdown_lines = ["# PDF Content\n"]

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Detect headings (all caps or specific patterns)
        if line.isupper() and len(line) < 100 and len(line) > 3:
            markdown_lines.append(f"\n## {line}\n")
        # Detect page markers
        elif line.startswith("--- Page"):
            markdown_lines.append(f"\n---\n{line}\n")
        # Detect bullet points
        elif line.startswith('•') or line.startswith('-'):
            markdown_lines.append(line)
        else:
            markdown_lines.append(line)

    return "\n".join(markdown_lines)

#%% Save Markdown Function
def save_markdown(content, output_path):
    """
    Save markdown content to file

    Args:
        content: Markdown content to save
        output_path: Output file path
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Markdown saved to: {output_path}")

#%% Load Commodity Groups
def load_commodity_groups():
    """Load unique commodity groups from commo_list.xlsx"""
    try:
        # Try to load from parent directory
        commo_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'commo_list.xlsx')
        df = pd.read_excel(commo_file)
        groups = df['Group'].dropna().unique().tolist()
        return groups
    except Exception as e:
        print(f"⚠ Could not load commodity groups: {e}")
        # Fallback to common groups
        return [
            "Crude Oil", "Natural Gas", "Gasoline", "Diesel", "Heating Oil",
            "Coal", "Uranium", "Corn", "Wheat", "Soybeans", "Sugar", "Coffee",
            "Cotton", "Gold", "Silver", "Copper", "Aluminum", "Iron Ore",
            "Steel", "Nickel", "Zinc", "Platinum", "Palladium",
            "Fertilizers", "Chemicals", "Plastics"
        ]

#%% ChatGPT Summary Function
def summarize_with_chatgpt(markdown_content, api_key=None, model=None, temperature=None, return_json=True):
    """
    Summarize the markdown content using ChatGPT API

    Args:
        markdown_content: Markdown text to summarize
        api_key: OpenAI API key (if None, uses OPENAI_API_KEY env variable)
        model: Model to use (default: gpt-4o-mini)
        temperature: Temperature setting (default: 1.0)
        return_json: If True, return structured JSON by commodity group

    Returns:
        dict or str: JSON dict if return_json=True, otherwise text summary
    """
    if api_key is None:
        api_key = os.environ.get('OPENAI_API_KEY')

    if not api_key:
        print("⚠ No API key provided. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
        return None

    if model is None:
        model = DEFAULT_MODEL
    if temperature is None:
        temperature = DEFAULT_TEMPERATURE

    client = OpenAI(api_key=api_key)

    if return_json:
        groups = load_commodity_groups()
        groups_str = ", ".join(groups)

        prompt = f"""You are a financial analyst analyzing a chemical and agricultural markets report.

Extract relevant news for each commodity group and return ONLY a valid JSON object in this exact format:

{{
  "Group Name": "news summary for this group (or empty string if no relevant news)",
  "Another Group": "news summary..."
}}

Commodity Groups to check: {groups_str}

Instructions:
- For each group, extract ONLY news about: price movements, supply/demand dynamics, market fundamentals
- IGNORE: company-specific news (unless directly affects commodity prices), stock performances, general corporate announcements
- If no relevant news for a group, use empty string ""
- Return ONLY the JSON object, no additional text
- Keep each summary to 1-2 concise sentences maximum

REPORT:
"""
    else:
        prompt = """You are a financial analyst summarizing a chemical and agricultural markets report.

Analyze the following report and provide a concise summary focusing on:
- Commodity price movements and trends
- Supply and demand dynamics
- Market fundamentals affecting commodities

IGNORE the following:
- Company-specific news UNLESS it has direct implications for commodity prices or supply/demand
- Stock price performances of individual companies
- General corporate announcements without commodity market impact

NOTE
- PVC: Refers to all plastic products (PE, PP, etc.). Any news about plastics should be included under PVC.

Keep the summary concise but capture all critical commodity market information.

REPORT:
"""

    try:
        print(f"\n🤖 Calling ChatGPT API...")
        print(f"   Model: {model}")
        print(f"   Content length: {len(markdown_content):,} characters")
        print(f"   Format: {'JSON by group' if return_json else 'Text summary'}")

        response = client.responses.create(
            model=model,
            input=prompt + markdown_content,
            temperature=temperature
        )

        result = response.output_text

        if return_json:
            try:
                # Parse JSON response
                summary_json = json.loads(result)
                print("✓ Summary generated successfully (JSON format)")
                return summary_json
            except json.JSONDecodeError as e:
                print(f"⚠ Failed to parse JSON response: {e}")
                print(f"Raw response: {result[:200]}...")
                return None
        else:
            print("✓ Summary generated successfully")
            return result

    except Exception as e:
        print(f"✗ Error calling ChatGPT API: {e}")
        return None

#%% Main Processing Function
def process_pdf(pdf_path, api_key=None, max_pages=None, save_files=True, model=None):
    """
    Complete workflow: Extract PDF -> Convert to Markdown -> Summarize with ChatGPT

    Args:
        pdf_path: Path to PDF file
        api_key: OpenAI API key (optional, uses env variable if None)
        max_pages: Max pages to extract (default: 4)
        save_files: Whether to save markdown and summary to files (default: True)
        model: ChatGPT model to use (default: gpt-4o-mini)

    Returns:
        dict: Dictionary with 'markdown' and 'summary' keys
    """
    if max_pages is None:
        max_pages = DEFAULT_MAX_PAGES

    print("=" * 70)
    print("PDF to Markdown Converter & ChatGPT Summarizer")
    print("=" * 70)
    print(f"Settings: Max pages = {max_pages}, Model = {model or DEFAULT_MODEL}")
    print()

    # Step 1: Extract PDF
    print("[1/3] Extracting PDF content...")
    raw_text = extract_pdf_text(pdf_path, max_pages=max_pages)

    if not raw_text:
        print("✗ Failed to extract PDF content")
        return None

    # Step 2: Convert to markdown
    print("\n[2/3] Converting to Markdown...")
    markdown_content = convert_to_markdown(raw_text)

    # Step 3: Summarize with ChatGPT
    print("\n[3/3] Generating Summary with ChatGPT...")
    summary = summarize_with_chatgpt(markdown_content, api_key=api_key, model=model)

    if summary and save_files:
        # Extract date from filename (e.g., JPM_2025-09-12.pdf -> 2025-09-12)
        import re
        filename = os.path.basename(pdf_path)
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
        report_date = date_match.group(1) if date_match else "Unknown"

        # Save JSON version with metadata
        json_output = pdf_path.replace('.pdf', '_summary.json')
        json_data = {
            "report_date": report_date,
            "report_file": os.path.basename(pdf_path),
            "commodity_news": summary
        }
        with open(json_output, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        print(f"✓ JSON saved to: {json_output}")

        # Save markdown version for display
        summary_output = pdf_path.replace('.pdf', '_summary.md')

        # Convert JSON to readable markdown
        markdown_sections = []
        for group, news in summary.items():
            if news and news.strip():  # Only include groups with news
                markdown_sections.append(f"### {group}\n{news}\n")

        summary_text = "\n".join(markdown_sections) if markdown_sections else "No significant commodity news found."

        summary_full = f"""# Chemical & Agriculture Report Summary
**Report:** {os.path.basename(pdf_path)}
**Date:** {report_date}

---

{summary_text}

---
"""
        save_markdown(summary_full, summary_output)

    print("\n" + "=" * 70)
    if summary:
        print("✓ COMPLETED SUCCESSFULLY")
        print("=" * 70)
        if save_files:
            print(f"\n📋 Summary (JSON): {pdf_path.replace('.pdf', '_summary.json')}")
            print(f"📋 Summary (MD): {pdf_path.replace('.pdf', '_summary.md')}")
    else:
        print("⚠ Summary generation failed")
        print("=" * 70)

    return {
        'markdown': markdown_content,
        'summary': summary
    }

#%% Consolidate All Summaries
def consolidate_summaries(news_dir='news', output_file='news/all_reports.json'):
    """
    Consolidate all individual JSON summaries into one simple array

    Structure: Simple array of reports sorted by date (newest first)
    [
      {
        "report_date": "2025-09-12",
        "report_file": "JPM_2025-09-12.pdf",
        "commodity_news": {...}
      },
      ...
    ]
    """
    import glob

    try:
        # Get all individual summary JSONs (check both news_dir and reports subdirectory)
        json_files = glob.glob(os.path.join(news_dir, '*_summary.json'))
        json_files += glob.glob(os.path.join(news_dir, 'reports', '*_summary.json'))

        if not json_files:
            print("⚠ No summary files found")
            return None

        # Sort by date (newest first)
        json_files.sort(reverse=True)

        reports = []

        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                reports.append(data)
            except Exception as e:
                print(f"Error reading {json_file}: {e}")
                continue

        # Sort by report_date (newest first)
        reports.sort(key=lambda x: x.get('report_date', ''), reverse=True)

        # Save as simple array
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(reports, f, indent=2, ensure_ascii=False)

        print(f"✓ Consolidated {len(reports)} reports into {output_file}")

        return reports

    except Exception as e:
        print(f"✗ Error consolidating summaries: {e}")
        return None

#%% [markdown]
# ## Quick Start Examples

#%% Example: Process PDF from reports folder
pdf_path = "reports/JPM_2025-09-05.pdf"
result = process_pdf(pdf_path, api_key=OPENAI_API_KEY, model=DEFAULT_MODEL)

#%% Example: Consolidate all summaries into one file
consolidated = consolidate_summaries(news_dir='.')
