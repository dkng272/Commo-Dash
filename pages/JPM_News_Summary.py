import streamlit as st
import os
from datetime import datetime
import glob

st.set_page_config(layout="wide", initial_sidebar_state="expanded", page_title="Market News Summary")

# Force light theme
st.markdown("""
    <style>
        [data-testid="stAppViewContainer"] {
            background-color: white;
            color: black;
        }
        [data-testid="stSidebar"] {
            background-color: #f0f2f6;
        }
    </style>
""", unsafe_allow_html=True)

st.title('📰 Chemical & Agriculture Market Reports')

# Get all summary files
news_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'news')
summary_files = glob.glob(os.path.join(news_dir, '*_summary.md'))

if not summary_files:
    st.warning('No summary files found in the news directory.')
    st.info('Run the PDF summarizer to generate summaries from market reports.')
else:
    # Sort files by date (newest first)
    summary_files.sort(reverse=True)

    # Extract dates from filenames for display
    file_info = []
    for file_path in summary_files:
        filename = os.path.basename(file_path)
        # Extract date from filename (JPM_2025-09-12_summary.md or other formats)
        date_str = filename.replace('JPM_', '').replace('_summary.md', '')
        file_info.append({
            'path': file_path,
            'filename': filename,
            'date': date_str,
            'display': f"Market Report - {date_str}"
        })

    # Sidebar for file selection
    st.sidebar.subheader('Select Report')
    selected_display = st.sidebar.radio(
        'Available Reports',
        options=[f['display'] for f in file_info],
        index=0
    )

    # Get selected file path
    selected_file = next(f for f in file_info if f['display'] == selected_display)

    # Display file info
    st.divider()

    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(f"📄 {selected_file['display']}")
    with col2:
        st.caption(f"Last modified: {datetime.fromtimestamp(os.path.getmtime(selected_file['path'])).strftime('%Y-%m-%d %H:%M')}")

    st.divider()

    # Read and display the summary
    try:
        with open(selected_file['path'], 'r', encoding='utf-8') as f:
            content = f.read()

        # Remove JPM references from content
        content_cleaned = content.replace('JPM Chemical & Agriculture Report Summary', 'Chemical & Agriculture Report Summary')
        content_cleaned = content_cleaned.replace('JPMorgan', 'Market')
        content_cleaned = content_cleaned.replace('JPM', '')
        content_cleaned = content_cleaned.replace('J.P. Morgan', 'Market')

        # Escape special markdown characters to prevent misrendering
        # Replace $ with \$ to prevent LaTeX rendering
        content_escaped = content_cleaned.replace('$', r'\$')
        # Escape ~ to prevent strikethrough (e.g., ~95% should not be strikethrough)
        content_escaped = content_escaped.replace('~', r'\~')

        # Display the markdown content with escaped characters
        st.markdown(content_escaped)

    except Exception as e:
        st.error(f"Error reading file: {e}")

    # Show total number of reports
    st.sidebar.divider()
    st.sidebar.caption(f"Total reports: {len(file_info)}")
