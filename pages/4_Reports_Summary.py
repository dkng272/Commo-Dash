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

st.title('📰 Market News & Catalysts')

# Load data
try:
    from mongodb_utils import load_reports, load_catalysts, load_commodity_classifications
    reports_data = load_reports()
    catalysts_data = load_catalysts()
    classifications = load_commodity_classifications()
except Exception as e:
    st.error(f"Error loading data from MongoDB: {e}")
    st.stop()

# ===== TABS =====
tab1, tab2 = st.tabs(["💡 Price Catalysts", "📄 PDF Reports"])

# ===== TAB 1: PRICE CATALYSTS =====

with tab1:
    # Get all commodity groups
    all_groups = sorted(list(set(c.get('group') for c in classifications if c.get('group'))))

    # Create catalyst lookup by group
    catalyst_by_group = {}
    for catalyst in catalysts_data:
        group = catalyst.get('commodity_group')
        if group:
            # Keep only the latest catalyst per group (catalysts_data is already sorted newest first)
            if group not in catalyst_by_group:
                catalyst_by_group[group] = catalyst

    # Sidebar filters
    st.sidebar.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 1px 12px; border-radius: 8px; margin-bottom: 12px;">
            <h3 style="color: white; margin: 0; font-size: 16px;">Catalyst Filters</h3>
        </div>
    """, unsafe_allow_html=True)

    # Search box
    search_query = st.sidebar.text_input("🔍 Search commodity", placeholder="e.g., Iron Ore")

    # Direction filter
    direction_filter = st.sidebar.radio(
        "Filter by Direction",
        options=["All", "Bullish 📈", "Bearish 📉", "Both ↔️"],
        index=0
    )

    # Sort options
    sort_by = st.sidebar.radio(
        "Sort by",
        options=["Alphabetical", "Most Recent", "Has Catalyst"],
        index=0
    )

    st.sidebar.divider()

    # Filter groups by search query
    if search_query:
        filtered_groups = [g for g in all_groups if search_query.lower() in g.lower()]
    else:
        filtered_groups = all_groups

    # Sort groups
    if sort_by == "Alphabetical":
        filtered_groups.sort()
    elif sort_by == "Most Recent":
        # Sort by catalyst date (newest first), groups without catalysts go to end
        filtered_groups.sort(
            key=lambda g: catalyst_by_group.get(g, {}).get('search_date', '0000-00-00'),
            reverse=True
        )
    elif sort_by == "Has Catalyst":
        # Groups with catalysts first, then alphabetical
        filtered_groups.sort(key=lambda g: (g not in catalyst_by_group, g))

    # Display stats
    groups_with_catalyst = len([g for g in filtered_groups if g in catalyst_by_group])
    st.sidebar.caption(f"Showing: {len(filtered_groups)} groups")
    st.sidebar.caption(f"With catalyst: {groups_with_catalyst}")
    st.sidebar.caption(f"Total tracked: {len(all_groups)}")

    # Main area: Display catalyst cards in grid
    st.markdown("---")

    if len(filtered_groups) == 0:
        st.info("No commodities match your search.")
    else:
        # Create 3-column grid
        cols_per_row = 3
        rows = (len(filtered_groups) + cols_per_row - 1) // cols_per_row

        for row_idx in range(rows):
            cols = st.columns(cols_per_row)

            for col_idx in range(cols_per_row):
                group_idx = row_idx * cols_per_row + col_idx

                if group_idx >= len(filtered_groups):
                    break

                group = filtered_groups[group_idx]
                catalyst = catalyst_by_group.get(group)

                with cols[col_idx]:
                    if catalyst:
                        # Has catalyst
                        summary = catalyst.get('summary', 'No summary')
                        search_date = catalyst.get('search_date', 'Unknown')
                        trigger_type = catalyst.get('search_trigger', 'Unknown')
                        timeline = catalyst.get('timeline', [])

                        # Determine direction from summary keywords (simple heuristic)
                        summary_lower = summary.lower()
                        if any(word in summary_lower for word in ['rally', 'surge', 'increase', 'bullish', 'gains', 'rise']):
                            direction_emoji = "📈"
                            border_color = "#d4edda"
                        elif any(word in summary_lower for word in ['decline', 'fall', 'bearish', 'drop', 'weaken', 'pressure']):
                            direction_emoji = "📉"
                            border_color = "#f8d7da"
                        else:
                            direction_emoji = "↔️"
                            border_color = "#fff3cd"

                        # Apply direction filter
                        if direction_filter != "All":
                            if direction_filter == "Bullish 📈" and direction_emoji != "📈":
                                continue
                            if direction_filter == "Bearish 📉" and direction_emoji != "📉":
                                continue
                            if direction_filter == "Both ↔️" and direction_emoji != "↔️":
                                continue

                        # Display card header
                        st.markdown(f"""
                            <div style="border: 2px solid {border_color}; border-radius: 8px;
                                        padding: 12px; background-color: {border_color}20; margin-bottom: 8px;">
                                <h4 style="margin: 0 0 4px 0;">{direction_emoji} {group}</h4>
                                <p style="margin: 0; font-size: 12px; color: #666;">
                                    {search_date} | {trigger_type.capitalize()}
                                </p>
                            </div>
                        """, unsafe_allow_html=True)

                        # Summary (show more text, no truncation or minimal truncation)
                        if len(summary) > 500:
                            summary_display = summary[:500] + "..."
                        else:
                            summary_display = summary

                        st.markdown(f"**Summary:**")
                        # Use markdown container with more space for summary
                        st.markdown(f"""<div style='padding: 8px; background-color: #f9f9f9; border-radius: 4px;
                                     min-height: 180px; margin-bottom: 12px; line-height: 1.6;'>
                            {summary_display}
                        </div>""", unsafe_allow_html=True)

                        # Timeline expander
                        if timeline:
                            with st.expander(f"📅 View Timeline ({len(timeline)} events)"):
                                for event in timeline:
                                    event_date = event.get('date', 'Unknown')
                                    event_desc = event.get('event', 'No description')
                                    st.markdown(f"**{event_date}**")
                                    st.text(event_desc)
                                    st.markdown("---")

                    else:
                        # No catalyst
                        st.markdown(f"""
                            <div style="border: 2px solid #e0e0e0; border-radius: 8px;
                                        padding: 12px; background-color: #f5f5f5; margin-bottom: 8px;">
                                <h4 style="margin: 0 0 4px 0; color: #666;">{group}</h4>
                                <p style="margin: 0; font-size: 12px; color: #999;">
                                    No catalyst available
                                </p>
                            </div>
                        """, unsafe_allow_html=True)
                        st.markdown("<div style='min-height: 180px;'></div>", unsafe_allow_html=True)


# ===== TAB 2: PDF REPORTS =====

with tab2:
    if not reports_data:
        st.warning('No reports found in the data file.')
        st.info('Run the PDF processor to generate reports.')
    else:
        # Create two-column layout: filters on left, content on right
        filter_col, content_col = st.columns([1, 3])

        with filter_col:
            st.markdown("""
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            padding: 1px 12px; border-radius: 8px; margin-bottom: 12px;">
                    <h3 style="color: white; margin: 0; font-size: 16px;">Filters</h3>
                </div>
            """, unsafe_allow_html=True)

            # Extract unique sources
            all_sources = sorted(list(set(report.get('report_source', 'Unknown') for report in reports_data)))

            # Source filter
            selected_sources = st.multiselect(
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
            selected_series = st.multiselect(
                'Report Name',
                options=available_series,
                default=available_series,
                help='Filter by report name/series (e.g., GlobalCommodities, ChemAgri, etc.)'
            )

            st.divider()

            # Filter reports
            filtered_reports = [
                report for report in reports_data
                if report.get('report_source', 'Unknown') in selected_sources
                and report.get('report_series', 'Unknown') in selected_series
            ]

            # Initialize variables
            report_options = []
            selected_display = None

            if filtered_reports:
                # Sort by date (newest first)
                filtered_reports.sort(key=lambda x: x.get('report_date', ''), reverse=True)

                # Create display list
                for report in filtered_reports:
                    date = report.get('report_date', 'Unknown')
                    source = report.get('report_source', 'Unknown')
                    series = report.get('report_series', 'Unknown')
                    display_text = f"{date} - {source}"
                    report_options.append(display_text)

                # Report selection
                st.markdown("**Select Report:**")
                selected_display = st.radio(
                    'Available Reports',
                    options=report_options,
                    index=0,
                    label_visibility="collapsed"
                )

                st.divider()

                # Show statistics
                st.caption(f"Filtered: {len(filtered_reports)}")
                st.caption(f"Total: {len(reports_data)}")

        with content_col:
            if not filtered_reports or not selected_display:
                st.warning('No reports match the selected filters.')
                st.info('Try adjusting your filter selections.')
            else:
                # Get selected report
                selected_idx = report_options.index(selected_display)
                selected_report = filtered_reports[selected_idx]

                # Display report metadata
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
                            news_escaped = news.replace('$', r'\$')
                            news_escaped = news_escaped.replace('~', r'\~')
                            st.markdown(news_escaped)
                            st.markdown("---")
                else:
                    st.info('No commodity news available for this report.')
