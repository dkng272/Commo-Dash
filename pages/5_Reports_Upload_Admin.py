import streamlit as st
import os
import sys
import tempfile
import pandas as pd

st.set_page_config(layout="wide", initial_sidebar_state="expanded", page_title="Reports Upload Admin")

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

st.title('📤 Reports Upload Admin')

st.markdown("""
Upload new PDF reports to be processed and added to the database.

**Filename Format**: `Source_Series_Date.pdf`
**Example**: `JPM_ChemAgri_2025-10-15.pdf`

The system will:
1. Extract text from the PDF
2. Summarize using ChatGPT
3. Save to MongoDB
""")

st.divider()

# File upload
uploaded_file = st.file_uploader(
    "Choose a PDF file",
    type=['pdf'],
    help="Upload a PDF report with the correct filename format"
)

if uploaded_file is not None:
    # Display file info
    st.info(f"**Filename**: {uploaded_file.name}")

    # Validate filename format
    import re
    pattern = r'^([^_]+)_([^_]+)_(\d{4}-\d{2}-\d{2})\.pdf$'
    match = re.match(pattern, uploaded_file.name)

    if not match:
        st.error("""
        ❌ **Invalid filename format!**

        Expected format: `Source_Series_Date.pdf`

        Examples:
        - `JPM_ChemAgri_2025-10-15.pdf`
        - `HSBC_GlobalFreight_2025-10-15.pdf`
        - `JPM_ChinaMetals_2025-10-15.pdf`
        """)
    else:
        source = match.group(1)
        series = match.group(2)
        date = match.group(3)

        # File renaming section
        st.subheader("📝 File Metadata")
        st.caption("You can edit the filename components below if needed")

        col1, col2, col3 = st.columns(3)
        with col1:
            edited_source = st.text_input("Source", value=source, help="Report publisher (e.g., JPM, HSBC)")
        with col2:
            edited_series = st.text_input("Series", value=series, help="Report series name")
        with col3:
            edited_date = st.date_input("Date", value=pd.to_datetime(date), help="Report date")
            edited_date_str = edited_date.strftime('%Y-%m-%d')

        # Generate new filename
        new_filename = f"{edited_source}_{edited_series}_{edited_date_str}.pdf"

        # Show if filename changed
        if new_filename != uploaded_file.name:
            st.info(f"""
            📝 **Filename will be changed**:
            - Original: `{uploaded_file.name}`
            - New: `{new_filename}`
            """)
        else:
            st.success(f"✅ **Filename**: `{new_filename}`")

        # Check for duplicates in MongoDB (using new filename)
        try:
            from mongodb_utils import load_reports
            existing_reports = load_reports()

            is_duplicate = False
            existing_report = None

            if existing_reports:
                for report in existing_reports:
                    if report.get('report_file') == new_filename:
                        is_duplicate = True
                        existing_report = report
                        break

            if is_duplicate:
                st.warning(f"""
                ⚠️ **Duplicate Report Detected**

                A report with this filename already exists in the database:
                - **Source**: {existing_report.get('report_source', 'Unknown')}
                - **Series**: {existing_report.get('report_series', 'Unknown')}
                - **Date**: {existing_report.get('report_date', 'Unknown')}
                - **Type**: {existing_report.get('report_type', 'Unknown')}

                If you proceed, the existing report will be **replaced** with the new one.
                """)

                # Show preview of existing report
                with st.expander("👁️ Preview Existing Report"):
                    commodity_news = existing_report.get('commodity_news', {})
                    non_empty = {k: v for k, v in commodity_news.items() if v and v.strip()}
                    st.metric("Commodities Covered", f"{len(non_empty)}/{len(commodity_news)}")

                    for commodity, news in commodity_news.items():
                        if news and news.strip():
                            st.markdown(f"**{commodity}**")
                            st.markdown(news[:200] + "..." if len(news) > 200 else news)
                            st.markdown("---")
            else:
                st.success("✅ **New Report** - No duplicate found")

        except Exception as e:
            st.error(f"Error checking for duplicates: {e}")

        st.divider()

        # Processing options
        st.subheader("Processing Options")

        col1, col2 = st.columns(2)
        with col1:
            model = st.selectbox(
                "AI Model",
                ["gpt-5-mini", "gpt-4o", "gpt-4o-mini"],
                index=0,
                help="Model to use for summarization"
            )
        with col2:
            temperature = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=2.0,
                value=1.0,
                step=0.1,
                help="Higher values = more creative, lower = more focused"
            )

        st.divider()

        # Process button
        if st.button("🚀 Process and Upload to MongoDB", type="primary"):
            with st.spinner("Processing PDF..."):
                # Save uploaded file to temp location
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_path = tmp_file.name

                try:
                    # Add news directory to path
                    news_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'news')
                    sys.path.insert(0, news_dir)

                    # Import processor
                    from pdf_processor_mongodb import process_pdf_to_mongodb

                    # Process PDF (use new filename)
                    result = process_pdf_to_mongodb(
                        tmp_path,
                        filename=new_filename,
                        model=model,
                        temperature=temperature
                    )

                    if result:
                        st.success("✅ Report processed and uploaded successfully!")

                        # Show summary
                        st.subheader("Report Summary")
                        commodity_news = result.get('commodity_news', {})
                        non_empty = {k: v for k, v in commodity_news.items() if v and v.strip()}

                        st.metric("Commodities Covered", f"{len(non_empty)}/{len(commodity_news)}")

                        with st.expander("View Full Report"):
                            for commodity, news in commodity_news.items():
                                if news and news.strip():
                                    st.markdown(f"**{commodity}**")
                                    st.markdown(news)
                                    st.markdown("---")
                    else:
                        st.error("❌ Failed to process report. Check the logs for details.")

                except Exception as e:
                    st.error(f"❌ Error processing report: {e}")
                    import traceback
                    with st.expander("Error Details"):
                        st.code(traceback.format_exc())

                finally:
                    # Clean up temp file
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

st.divider()

# Instructions
with st.expander("📋 Naming Convention Guide"):
    st.markdown("""
    ### Filename Format

    `{Source}_{Series}_{Date}.pdf`

    ### Components

    1. **Source**: Report publisher (e.g., JPM, HSBC, MS)
    2. **Series**: Report series name (e.g., ChemAgri, GlobalCommodities, ChinaMetals)
    3. **Date**: Report date in YYYY-MM-DD format

    ### Examples

    - `JPM_ChemAgri_2025-10-15.pdf` → J.P. Morgan Chemical & Agriculture report
    - `HSBC_GlobalFreight_2025-10-15.pdf` → HSBC Global Freight report
    - `JPM_ChinaMetals_2025-10-15.pdf` → J.P. Morgan China Metals report
    - `JPM_GlobalCommodities_2025-10-15.pdf` → J.P. Morgan Global Commodities report

    ### Supported Series

    - **JPM**: ChemAgri, GlobalCommodities, ChinaMetals, ContainerShipping
    - **HSBC**: GlobalFreight
    - Others can be added by updating the prompt router
    """)
