#!/usr/bin/env python3
"""
Helper script to process PDF reports and consolidate summaries

Usage:
    python process_reports.py                    # Process all PDFs in reports/
    python process_reports.py --file report.pdf  # Process specific file
    python process_reports.py --consolidate      # Only consolidate existing summaries
"""

import sys
import os
import glob
import argparse

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pdf_to_markdown_summarizer import process_pdf, consolidate_summaries, OPENAI_API_KEY, DEFAULT_MODEL

def process_all_reports(reports_dir='reports'):
    """Process all PDF files in the reports directory"""
    pdf_files = glob.glob(os.path.join(reports_dir, '*.pdf'))

    if not pdf_files:
        print(f"⚠ No PDF files found in {reports_dir}/")
        return

    print(f"Found {len(pdf_files)} PDF files to process\n")

    for pdf_file in pdf_files:
        print(f"\n{'='*70}")
        print(f"Processing: {os.path.basename(pdf_file)}")
        print(f"{'='*70}")

        try:
            result = process_pdf(pdf_file, api_key=OPENAI_API_KEY, model=DEFAULT_MODEL)

            if result and result.get('summary'):
                print(f"✓ Successfully processed {os.path.basename(pdf_file)}")
            else:
                print(f"⚠ Failed to process {os.path.basename(pdf_file)}")

        except Exception as e:
            print(f"✗ Error processing {os.path.basename(pdf_file)}: {e}")
            continue

def main():
    parser = argparse.ArgumentParser(description='Process PDF reports and consolidate summaries')
    parser.add_argument('--file', type=str, help='Specific PDF file to process')
    parser.add_argument('--consolidate', action='store_true', help='Only consolidate existing summaries')
    parser.add_argument('--reports-dir', type=str, default='reports', help='Directory containing PDF reports')

    args = parser.parse_args()

    # Change to news directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    if args.consolidate:
        # Only consolidate
        print("Consolidating all summaries...")
        consolidate_summaries(news_dir='.', output_file='all_reports.json')

    elif args.file:
        # Process specific file
        pdf_path = os.path.join(args.reports_dir, args.file) if not os.path.isabs(args.file) else args.file

        if not os.path.exists(pdf_path):
            print(f"✗ File not found: {pdf_path}")
            return

        print(f"Processing: {pdf_path}")
        result = process_pdf(pdf_path, api_key=OPENAI_API_KEY, model=DEFAULT_MODEL)

        if result and result.get('summary'):
            print("\n✓ Processing complete! Now consolidating...")
            consolidate_summaries(news_dir='.', output_file='all_reports.json')

    else:
        # Process all PDFs
        process_all_reports(args.reports_dir)

        print("\n\n" + "="*70)
        print("Consolidating all summaries...")
        print("="*70)
        consolidate_summaries(news_dir='.', output_file='all_reports.json')

    print("\n✓ All done!")

if __name__ == "__main__":
    main()
