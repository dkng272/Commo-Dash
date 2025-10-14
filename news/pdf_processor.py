#%% [markdown]
# # PDF Report Processor - MongoDB Version
# Processes PDF reports and saves directly to MongoDB
# Supports series-based prompt routing and metadata tracking

#%% Imports and Configuration
import os
import sys
import re
import json
import fitz  # PyMuPDF
from openai import OpenAI
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import prompt system
from prompts import get_prompt_for_series, get_commodity_prompt, get_sector_prompt
from prompts.prompt_router import get_max_pages_for_prompt

# Add parent directory to path for mongodb_utils import
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Default settings
DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_TEMPERATURE = 1.0
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


#%% Helper Functions
def load_commodity_groups():
    """Load unique commodity groups from commo_list.xlsx"""
    try:
        commo_file = os.path.join(parent_dir, 'commo_list.xlsx')
        df = pd.read_excel(commo_file)
        groups = df['Group'].dropna().unique().tolist()
        return groups
    except Exception as e:
        print(f"⚠ Could not load commodity groups: {e}")
        return [
            "Oil", "Crack Spread", "Gas/LNG", "Coal",
            "Urea", "NPK", "DAP", "Caustic Soda", "Yellow P4", "P4 Rock",
            "PVC", "Aluminum", "Tungsten", "Long Steel", "HRC", "Iron Ore",
            "Met Coal", "Scrap", "Bulk Shipping", "Liquids Shipping",
            "Container Shipping", "Barley", "Milk", "Grain", "Sugar", "Hog", "Pangaseus"
        ]


def parse_filename(pdf_path):
    """
    Parse filename to extract metadata

    Expected format: {Source}_{Series}_{Date}.pdf
    Example: JPM_ChemAgri_2025-10-03.pdf

    Returns:
        dict: {'source': 'JPM', 'series': 'ChemAgri', 'date': '2025-10-03', 'filename': ...}
        None if parsing fails
    """
    filename = os.path.basename(pdf_path)

    # Pattern: Source_Series_Date.pdf
    pattern = r'^([^_]+)_([^_]+)_(\d{4}-\d{2}-\d{2})\.pdf$'
    match = re.match(pattern, filename)

    if match:
        return {
            'source': match.group(1),
            'series': match.group(2),
            'date': match.group(3),
            'filename': filename
        }
    else:
        print(f"⚠ Warning: Filename doesn't match expected format: {filename}")
        print(f"   Expected: Source_Series_Date.pdf (e.g., JPM_ChemAgri_2025-10-03.pdf)")
        return None


#%% PDF Processing Functions
def extract_pdf_text(pdf_path, max_pages=None):
    """Extract text from PDF using PyMuPDF"""
    if max_pages is None:
        max_pages = 4

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


def convert_to_markdown(raw_text):
    """Convert raw PDF text to structured markdown"""
    lines = raw_text.split('\n')
    markdown_lines = ["# PDF Content\n"]

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.isupper() and len(line) < 100 and len(line) > 3:
            markdown_lines.append(f"\n## {line}\n")
        elif line.startswith("--- Page"):
            markdown_lines.append(f"\n---\n{line}\n")
        elif line.startswith('•') or line.startswith('-'):
            markdown_lines.append(line)
        else:
            markdown_lines.append(line)

    return "\n".join(markdown_lines)


#%% ChatGPT Summarization
def summarize_with_chatgpt(markdown_content, prompt_type, api_key=None, model=None, temperature=None):
    """
    Summarize markdown content using ChatGPT with appropriate prompt

    Args:
        markdown_content: Markdown text to summarize
        prompt_type: Type of prompt ('commodity' or 'sector')
        api_key: OpenAI API key
        model: Model to use
        temperature: Temperature setting

    Returns:
        dict: JSON dict with commodity news
    """
    if api_key is None:
        api_key = os.environ.get('OPENAI_API_KEY')

    if not api_key:
        print("⚠ No API key provided. Set OPENAI_API_KEY environment variable.")
        return None

    if model is None:
        model = DEFAULT_MODEL
    if temperature is None:
        temperature = DEFAULT_TEMPERATURE

    client = OpenAI(api_key=api_key)

    # Get commodity groups
    groups = load_commodity_groups()
    groups_str = ", ".join(groups)

    # Select prompt based on type
    if prompt_type == 'sector':
        prompt = get_sector_prompt(groups_str)
    else:  # default to commodity
        prompt = get_commodity_prompt(groups_str)

    try:
        print(f"\n🤖 Calling ChatGPT API...")
        print(f"   Model: {model}")
        print(f"   Prompt type: {prompt_type}")
        print(f"   Content length: {len(markdown_content):,} characters")

        response = client.responses.create(
            model=model,
            input=prompt + markdown_content,
            temperature=temperature
        )

        result = response.output_text

        try:
            summary_json = json.loads(result)
            print("✓ Summary generated successfully (JSON format)")
            return summary_json
        except json.JSONDecodeError as e:
            print(f"⚠ Failed to parse JSON response: {e}")
            print(f"Raw response: {result[:200]}...")
            return None

    except Exception as e:
        print(f"✗ Error calling ChatGPT API: {e}")
        return None


#%% MongoDB Reports Management
def save_report_to_mongodb(report_data):
    """
    Save report to MongoDB

    Args:
        report_data: Dict with report metadata and commodity_news

    Returns:
        bool: Success status
    """
    try:
        from mongodb_utils import load_reports, save_reports

        # Load existing reports
        reports = load_reports()
        if reports is None:
            reports = []

        # Check if report already exists (by filename)
        existing_idx = None
        for i, report in enumerate(reports):
            if report.get('report_file') == report_data['report_file']:
                existing_idx = i
                break

        if existing_idx is not None:
            print(f"📝 Updating existing report: {report_data['report_file']}")
            reports[existing_idx] = report_data
        else:
            print(f"📝 Adding new report: {report_data['report_file']}")
            reports.append(report_data)

        # Save to MongoDB
        success = save_reports(reports)

        if success:
            print(f"✓ Report saved to MongoDB")
        else:
            print(f"✗ Failed to save report to MongoDB")

        return success

    except Exception as e:
        print(f"✗ Error saving to MongoDB: {e}")
        return False


#%% Main Processing Function
def process_pdf(pdf_path, api_key=None, model=None):
    """
    Complete workflow: Parse metadata → Extract → Summarize → Save to MongoDB

    Args:
        pdf_path: Path to PDF file
        api_key: OpenAI API key
        model: ChatGPT model to use

    Returns:
        dict: Report data that was added to MongoDB
    """
    print("=" * 70)
    print("PDF Report Processor (MongoDB)")
    print("=" * 70)
    print()

    # Step 1: Parse filename to get metadata
    print("[1/4] Parsing filename...")
    metadata = parse_filename(pdf_path)

    if not metadata:
        print("✗ Failed to parse filename. Please check naming convention.")
        return None

    source = metadata['source']
    series = metadata['series']
    date = metadata['date']
    filename = metadata['filename']

    print(f"   Source: {source}")
    print(f"   Series: {series}")
    print(f"   Date: {date}")

    # Get prompt type from series mapping
    prompt_type = get_prompt_for_series(series)
    max_pages = get_max_pages_for_prompt(prompt_type)

    print(f"   Prompt type: {prompt_type}")
    print(f"   Max pages: {max_pages}")
    print()

    # Step 2: Extract PDF
    print("[2/4] Extracting PDF content...")
    raw_text = extract_pdf_text(pdf_path, max_pages=max_pages)

    if not raw_text:
        print("✗ Failed to extract PDF content")
        return None

    # Step 3: Convert to markdown
    print("\n[3/4] Converting to Markdown...")
    markdown_content = convert_to_markdown(raw_text)

    # Step 4: Summarize with ChatGPT
    print("\n[4/4] Generating Summary with ChatGPT...")
    summary = summarize_with_chatgpt(markdown_content, prompt_type, api_key=api_key, model=model)

    if not summary:
        print("✗ Failed to generate summary")
        return None

    # Create report data with metadata
    report_data = {
        "report_date": date,
        "report_file": filename,
        "report_source": source,
        "report_series": series,
        "report_type": prompt_type,
        "commodity_news": summary
    }

    # Save to MongoDB
    print()
    success = save_report_to_mongodb(report_data)

    if not success:
        print("✗ Failed to save to MongoDB")
        return None

    print("\n" + "=" * 70)
    print("✓ COMPLETED SUCCESSFULLY")
    print("=" * 70)
    print(f"\n📊 Report saved to MongoDB")

    return report_data


#%% Batch Processing
def process_folder(folder_path, api_key=None, model=None):
    """
    Batch process all PDF files in a folder

    Args:
        folder_path: Path to folder containing PDF files
        api_key: OpenAI API key
        model: ChatGPT model to use

    Returns:
        list: List of processing results
    """
    import glob

    pdf_files = glob.glob(os.path.join(folder_path, '*.pdf'))

    if not pdf_files:
        print(f"⚠ No PDF files found in {folder_path}")
        return []

    print(f"\n{'=' * 70}")
    print(f"Batch Processing: {len(pdf_files)} PDF files")
    print(f"{'=' * 70}\n")

    results = []

    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] Processing: {os.path.basename(pdf_path)}")
        print("-" * 70)

        try:
            result = process_pdf(pdf_path, api_key=api_key, model=model)
            results.append({
                'file': os.path.basename(pdf_path),
                'status': 'success' if result else 'failed',
                'result': result
            })
        except Exception as e:
            print(f"✗ Error processing {os.path.basename(pdf_path)}: {e}")
            results.append({
                'file': os.path.basename(pdf_path),
                'status': 'error',
                'error': str(e)
            })

        print()

    # Summary
    print(f"\n{'=' * 70}")
    print("Batch Processing Complete")
    print(f"{'=' * 70}")
    success_count = sum(1 for r in results if r['status'] == 'success')
    print(f"✓ Successful: {success_count}/{len(pdf_files)}")
    print(f"✗ Failed: {len(pdf_files) - success_count}/{len(pdf_files)}")

    return results


#%% [markdown]
# ## Quick Start Examples

#%% Example: Process single PDF
name = "JPM_GlobalCommodities_2025-09-29"
pdf_path = f"reports/{name}.pdf"
result = process_pdf(pdf_path, api_key=OPENAI_API_KEY, model=DEFAULT_MODEL)

#%% Example: Batch process all PDFs in reports folder
results = process_folder('reports/', api_key=OPENAI_API_KEY, model=DEFAULT_MODEL)
