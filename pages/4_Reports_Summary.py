import streamlit as st

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

# Load reports from MongoDB
try:
    from mongodb_utils import load_reports
    reports_data = load_reports()

    if not reports_data:
        st.warning('No reports found in the data file.')
        st.info('Run the PDF processor to generate reports.')
    else:
        # Extract unique sources
        all_sources = sorted(list(set(report.get('report_source', 'Unknown') for report in reports_data)))

        # Sidebar filters
        st.sidebar.subheader('Filters')

        # Source filter
        selected_sources = st.sidebar.multiselect(
            'Report Source',
            options=all_sources,
            default=all_sources,
            help='Filter by report source (e.g., JPM, HSBC, etc.)'
        )

        # Get series that belong to selected sources
        available_series = sorted(list(set(
            report.get('report_series', 'Unknown')
            for report in reports_data
            if report.get('report_source', 'Unknown') in selected_sources
        )))

        # Series filter (only show series from selected sources)
        selected_series = st.sidebar.multiselect(
            'Report Name',
            options=available_series,
            default=available_series,
            help='Filter by report name/series (e.g., GlobalCommodities, ChemAgri, etc.)'
        )

        st.sidebar.divider()

        # Filter reports
        filtered_reports = [
            report for report in reports_data
            if report.get('report_source', 'Unknown') in selected_sources
            and report.get('report_series', 'Unknown') in selected_series
        ]

        if not filtered_reports:
            st.warning('No reports match the selected filters.')
            st.info('Try adjusting your filter selections.')
        else:
            # Sort by date (newest first)
            filtered_reports.sort(key=lambda x: x.get('report_date', ''), reverse=True)

            # Create display list
            report_options = []
            for report in filtered_reports:
                date = report.get('report_date', 'Unknown')
                source = report.get('report_source', 'Unknown')
                series = report.get('report_series', 'Unknown')
                display_text = f"{source} - {series} - {date}"
                report_options.append(display_text)

            # Report selection
            st.sidebar.subheader('Select Report')
            selected_display = st.sidebar.radio(
                'Available Reports',
                options=report_options,
                index=0
            )

            # Get selected report
            selected_idx = report_options.index(selected_display)
            selected_report = filtered_reports[selected_idx]

            # Display report metadata
            st.divider()

            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            with col1:
                st.subheader(f"📄 {selected_report.get('report_source', 'Unknown')} - {selected_report.get('report_series', 'Unknown')}")
            with col2:
                st.caption(f"Report Date: {selected_report.get('report_date', 'Unknown')}")
            with col3:
                st.caption(f"Type: {selected_report.get('report_type', 'Unknown')}")
            with col4:
                upload_date = selected_report.get('date_uploaded', 'N/A')
                st.caption(f"Uploaded: {upload_date}")

            st.divider()

            # Display commodity news
            commodity_news = selected_report.get('commodity_news', {})

            if commodity_news:
                # Count non-empty entries
                non_empty = {k: v for k, v in commodity_news.items() if v.strip()}

                st.markdown(f"**{len(non_empty)} commodities** covered in this report")
                st.divider()

                # Display each commodity with news
                for commodity, news in commodity_news.items():
                    if news.strip():
                        st.markdown(f"### {commodity}")
                        # Escape markdown special characters
                        # Replace $ with \$ to prevent LaTeX rendering
                        news_escaped = news.replace('$', r'\$')
                        # Escape ~ to prevent strikethrough (e.g., ~95% should not be strikethrough)
                        news_escaped = news_escaped.replace('~', r'\~')
                        st.markdown(news_escaped)
                        st.markdown("---")
            else:
                st.info('No commodity news available for this report.')

            # Show statistics in sidebar
            st.sidebar.divider()
            st.sidebar.caption(f"Filtered reports: {len(filtered_reports)}")
            st.sidebar.caption(f"Total reports: {len(reports_data)}")

except Exception as e:
    st.error(f"Error loading reports from MongoDB: {e}")
    st.info('Please ensure MongoDB is running and the reports collection has been migrated.')
