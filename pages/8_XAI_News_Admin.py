import streamlit as st
import sys
import os

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# Add xai_api directory to path
xai_api_dir = os.path.join(parent_dir, "xai_api")
sys.path.append(xai_api_dir)

# Import utilities
from mongodb_utils import get_catalyst, get_catalyst_history, save_catalyst, can_auto_trigger, load_commodity_classifications
from catalyst_search import search_catalysts, MODEL

# Import batch search functions
try:
    from intelligent_batch_search import load_commodity_data, calculate_group_movements, determine_search_params
    BATCH_SEARCH_AVAILABLE = True
except ImportError:
    BATCH_SEARCH_AVAILABLE = False

st.set_page_config(layout="wide", page_title="Catalyst Search Admin")

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

st.title('Catalyst Search Admin')
st.markdown("*View and manage commodity price catalysts from X (Twitter)*")
st.caption(f"Model: {MODEL}")

# ===== Load Commodity Groups =====

@st.cache_data(ttl=60)
def load_commodity_groups():
    """Load all commodity groups from MongoDB classifications"""
    try:
        classifications = load_commodity_classifications()
        if classifications:
            groups = [c.get('group') for c in classifications if c.get('group')]
            return sorted(set(groups))
        return []
    except Exception as e:
        st.error(f"Error loading commodity groups: {e}")
        return []

commodity_groups = load_commodity_groups()

# ===== Shared Configuration =====

st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 1px 12px; border-radius: 8px; margin-bottom: 12px;">
        <h3 style="color: white; margin: 0; font-size: 16px;">Configuration</h3>
    </div>
""", unsafe_allow_html=True)

threshold = st.number_input(
    "Movement Threshold (%) - Used by Batch Search",
    min_value=1.0,
    max_value=10.0,
    value=3.0,
    step=0.5,
    help="Percentage threshold for significant movement (used to determine bullish/bearish direction)"
)

st.divider()

# ===== TABS =====

tab1, tab2 = st.tabs(["🔍 Individual Search", "🚀 Batch Search"])

# ===== TAB 1: Individual Search =====

with tab1:
    st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 1px 12px; border-radius: 8px; margin-bottom: 12px;">
            <h3 style="color: white; margin: 0; font-size: 18px;">Step 1: Select Commodity</h3>
        </div>
    """, unsafe_allow_html=True)

    selected_commodity = st.selectbox(
        "Commodity Group",
        commodity_groups,
        help="Select commodity to view or search catalysts"
    )

    st.divider()

    # ===== Step 2: View Saved Catalyst =====

    st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 1px 12px; border-radius: 8px; margin-bottom: 12px;">
            <h3 style="color: white; margin: 0; font-size: 18px;">Step 2: Saved Catalyst (from Database)</h3>
        </div>
    """, unsafe_allow_html=True)

    if selected_commodity:
        # Get latest catalyst
        latest_catalyst = get_catalyst(selected_commodity)

        if latest_catalyst:
            col_meta1, col_meta2 = st.columns(2)
            with col_meta1:
                st.metric("Search Date", latest_catalyst.get('search_date', 'N/A'))
            with col_meta2:
                st.metric("Trigger Type", latest_catalyst.get('search_trigger', 'N/A'))

            st.markdown("**Summary:**")
            st.text(latest_catalyst.get('summary', 'No summary'))

            timeline = latest_catalyst.get('timeline', [])
            if timeline:
                st.markdown(f"**Timeline ({len(timeline)} events):**")
                for entry in timeline:
                    date = entry.get("date", "Unknown")
                    event = entry.get("event", "No description")
                    st.markdown(f"• **{date}**:")
                    st.text(event)

            # Show history if available
            history = get_catalyst_history(selected_commodity, limit=10)
            if len(history) > 1:
                with st.expander(f"📜 View History ({len(history) - 1} previous searches)"):
                    for catalyst in history[1:]:
                        st.markdown(f"**{catalyst.get('search_date', 'Unknown')}** "
                                  f"({catalyst.get('search_trigger', 'Unknown')})")
                        st.text(catalyst.get('summary', 'No summary'))
                        st.divider()
        else:
            st.info(f"No saved catalyst found for {selected_commodity}. Run a search below to create one.")
    else:
        st.info("Select a commodity group to view saved catalysts")

    st.divider()

    # ===== Step 3: Run New Search =====

    st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 1px 12px; border-radius: 8px; margin-bottom: 12px;">
            <h3 style="color: white; margin: 0; font-size: 18px;">Step 3: Run New Search (X API)</h3>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("⚠️ **This will query X (Twitter) via API** (~30 seconds)")

    col1, col2 = st.columns(2)

    with col1:
        lookback_days = st.number_input(
            "Lookback Days",
            min_value=3,
            max_value=30,
            value=7,
            help="Number of days to search back (3-30)"
        )

    with col2:
        direction = st.selectbox(
            "Direction",
            ["both", "bullish", "bearish"],
            help="Filter by price direction"
        )

    # Check cooldown status
    if selected_commodity:
        can_trigger, cooldown_msg = can_auto_trigger(selected_commodity)

        if not can_trigger:
            st.warning(f"⏳ Auto-trigger cooldown: {cooldown_msg} (Manual search still allowed)")
        else:
            st.success("✅ Ready to search")

    # Initialize session state for search results
    if 'search_results' not in st.session_state:
        st.session_state.search_results = None
    if 'search_commodity' not in st.session_state:
        st.session_state.search_commodity = None

    # Search button
    search_clicked = st.button("🚀 Run Search on X", type="primary", use_container_width=True)

    # ===== Search Results =====

    if search_clicked:
        with st.spinner(f"🔍 Searching X for {selected_commodity} catalysts..."):
            try:
                # Run search
                direction_param = None if direction == "both" else direction
                results = search_catalysts(
                    commodity_group=selected_commodity,
                    lookback_days=lookback_days,
                    direction=direction_param
                )

                # Store results in session state
                st.session_state.search_results = results
                st.session_state.search_commodity = selected_commodity

            except Exception as e:
                st.error(f"❌ Error during search: {e}")
                st.exception(e)
                st.session_state.search_results = None

    # Display results if they exist in session state
    if st.session_state.search_results is not None:
        results = st.session_state.search_results

        # Check if valid results
        if "_meta" in results and results["_meta"].get("parse_error"):
            st.error("⚠️ Grok returned invalid JSON. Check raw response below.")
            st.code(results.get("raw_response", "No response"), language="text")
        else:
            # Display results
            st.markdown("""
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            padding: 1px 12px; border-radius: 8px; margin-bottom: 12px;">
                    <h3 style="color: white; margin: 0; font-size: 18px;">Search Results</h3>
                </div>
            """, unsafe_allow_html=True)

            # Summary
            summary = results.get("summary", "No summary available")
            st.markdown("**Summary:**")
            st.text(summary)

            st.divider()

            # Timeline
            timeline = results.get("timeline", [])
            if timeline:
                st.markdown(f"**Catalyst Timeline ({len(timeline)} events):**")

                for entry in timeline:
                    date = entry.get("date", "Unknown")
                    event = entry.get("event", "No description")

                    with st.expander(f"📅 {date}", expanded=False):
                        st.text(event)
            else:
                st.info("No catalyst timeline found")

            st.divider()

            # Save to MongoDB button
            save_clicked = st.button("💾 Save to MongoDB", type="secondary", use_container_width=True)

            if save_clicked:
                success = save_catalyst(
                    commodity_group=st.session_state.search_commodity,
                    summary=summary,
                    timeline=timeline,
                    search_trigger="manual"
                )

                if success:
                    st.success(f"✅ Catalyst saved for {st.session_state.search_commodity}!\n\nℹ️ Changes will appear on Dashboard within ~60 seconds.")
                    # Clear cache to force refresh
                    st.cache_data.clear()
                    # Clear search results after successful save
                    st.session_state.search_results = None
                    st.rerun()
                else:
                    st.error("❌ Failed to save catalyst to MongoDB")

# ===== TAB 2: Batch Search =====

with tab2:
    if not BATCH_SEARCH_AVAILABLE:
        st.error("❌ Batch search module not available. Check intelligent_batch_search.py")
    else:
        st.markdown("""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        padding: 1px 12px; border-radius: 8px; margin-bottom: 12px;">
                <h3 style="color: white; margin: 0; font-size: 18px;">Intelligent Batch Search</h3>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("**Automatically determines search parameters based on price movements:**")
        st.markdown("""
        - **5D > 3%**: Bullish, 7-day lookback
        - **5D < -3%**: Bearish, 7-day lookback
        - **5D within ±3%**:
            - 10D > 3%: Bullish, 14-day lookback
            - 10D < -3%: Bearish, 14-day lookback
            - Otherwise: Both directions, 14-day lookback
        """)

        st.divider()

        # Configuration
        st.markdown("**Batch Search Settings:**")
        delay_seconds = st.number_input(
            "Delay Between Searches (seconds)",
            min_value=3,
            max_value=30,
            value=5,
            help="Delay between API calls to avoid rate limits"
        )

        check_cooldown = st.checkbox("Check cooldown periods (skip groups in cooldown)", value=True)

        st.divider()

        # Initialize session state for batch data
        if 'batch_movements' not in st.session_state:
            st.session_state.batch_movements = None
        if 'batch_search_running' not in st.session_state:
            st.session_state.batch_search_running = False

        # Load and analyze button
        if st.button("📊 Analyze All Groups", type="secondary", use_container_width=True):
            with st.spinner("Loading commodity data and calculating movements..."):
                try:
                    # Load data
                    df = load_commodity_data()

                    # Calculate movements
                    movements = calculate_group_movements(df)

                    # Determine search parameters
                    movements['Direction'], movements['Lookback_Days'], movements['Reason'] = zip(
                        *movements.apply(lambda row: determine_search_params(row, threshold), axis=1)
                    )

                    # Check cooldown status for each group
                    if check_cooldown:
                        cooldown_status = []
                        for group in movements['Group']:
                            can_trigger, msg = can_auto_trigger(group)
                            cooldown_status.append("✅ Ready" if can_trigger else f"⏳ {msg}")
                        movements['Cooldown_Status'] = cooldown_status

                    # Store in session state
                    st.session_state.batch_movements = movements
                    st.success(f"✅ Analyzed {len(movements)} commodity groups")

                except Exception as e:
                    st.error(f"❌ Error analyzing groups: {e}")
                    st.exception(e)

        # Display analysis results
        if st.session_state.batch_movements is not None:
            movements = st.session_state.batch_movements

            st.markdown("---")
            st.markdown(f"**Analysis Results ({len(movements)} groups):**")

            # Format display dataframe
            display_df = movements[['Group', '5D_Change', '10D_Change', 'Direction', 'Lookback_Days'] +
                                    (['Cooldown_Status'] if 'Cooldown_Status' in movements.columns else [])].copy()

            # Rename columns for display
            display_df = display_df.rename(columns={
                '5D_Change': '5D Change (%)',
                '10D_Change': '10D Change (%)',
                'Lookback_Days': 'Lookback (Days)',
                'Cooldown_Status': 'Status'
            })

            # Format percentages
            display_df['5D Change (%)'] = display_df['5D Change (%)'].apply(lambda x: f"{x:+.1f}")
            display_df['10D Change (%)'] = display_df['10D Change (%)'].apply(lambda x: f"{x:+.1f}")

            # Color code by direction
            def highlight_direction(row):
                if row['Direction'] == 'bullish':
                    return ['background-color: #d4edda'] * len(row)
                elif row['Direction'] == 'bearish':
                    return ['background-color: #f8d7da'] * len(row)
                else:
                    return ['background-color: #fff3cd'] * len(row)

            # Display table
            st.dataframe(
                display_df.style.apply(highlight_direction, axis=1),
                use_container_width=True,
                height=400
            )

            # Summary stats
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                bullish_count = len(movements[movements['Direction'] == 'bullish'])
                st.metric("Bullish", bullish_count)
            with col2:
                bearish_count = len(movements[movements['Direction'] == 'bearish'])
                st.metric("Bearish", bearish_count)
            with col3:
                both_count = len(movements[movements['Direction'] == 'both'])
                st.metric("Both", both_count)
            with col4:
                if 'Cooldown_Status' in movements.columns:
                    ready_count = len([s for s in movements['Cooldown_Status'] if s.startswith('✅')])
                    st.metric("Ready", ready_count)

            st.markdown("---")

            # Run batch search button
            groups_to_search = movements
            if check_cooldown and 'Cooldown_Status' in movements.columns:
                groups_to_search = movements[movements['Cooldown_Status'].str.startswith('✅')]
                if len(groups_to_search) < len(movements):
                    st.info(f"ℹ️ {len(movements) - len(groups_to_search)} groups will be skipped due to cooldown")

            if len(groups_to_search) == 0:
                st.warning("⚠️ No groups available to search (all in cooldown)")
            else:
                st.markdown(f"**Ready to run {len(groups_to_search)} searches**")

                if st.button(f"🚀 Run Batch Search ({len(groups_to_search)} groups)", type="primary", use_container_width=True):
                    st.session_state.batch_search_running = True

                    # Progress tracking
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    results = []

                    for idx, (_, row) in enumerate(groups_to_search.iterrows()):
                        group = row['Group']
                        direction_val = None if row['Direction'] == 'both' else row['Direction']
                        lookback_days = int(row['Lookback_Days'])

                        # Update progress
                        progress = (idx + 1) / len(groups_to_search)
                        progress_bar.progress(progress)
                        status_text.text(f"[{idx+1}/{len(groups_to_search)}] Searching {group}...")

                        try:
                            # Run search
                            search_result = search_catalysts(
                                commodity_group=group,
                                lookback_days=lookback_days,
                                direction=direction_val
                            )

                            # Save to MongoDB
                            if "_meta" in search_result and search_result["_meta"].get("parse_error"):
                                results.append({
                                    "group": group,
                                    "success": False,
                                    "error": "Parse error"
                                })
                            else:
                                summary = search_result.get("summary", "")
                                timeline = search_result.get("timeline", [])

                                # Save with direction from analysis
                                success = save_catalyst(
                                    commodity_group=group,
                                    summary=summary,
                                    timeline=timeline,
                                    search_trigger="auto",
                                    direction=row['Direction']
                                )

                                results.append({
                                    "group": group,
                                    "success": success,
                                    "direction": row['Direction'],
                                    "lookback_days": lookback_days
                                })

                            # Delay between searches (except for last one)
                            if idx < len(groups_to_search) - 1:
                                import time
                                time.sleep(delay_seconds)

                        except Exception as e:
                            results.append({
                                "group": group,
                                "success": False,
                                "error": str(e)
                            })

                    # Clear progress
                    progress_bar.empty()
                    status_text.empty()

                    # Show summary
                    successful = [r for r in results if r.get("success")]
                    failed = [r for r in results if not r.get("success")]

                    st.success(f"✅ Batch search completed: {len(successful)}/{len(results)} successful")

                    if failed:
                        with st.expander(f"⚠️ Failed searches ({len(failed)})"):
                            for r in failed:
                                st.text(f"• {r['group']}: {r.get('error', 'Unknown error')}")

                    # Clear only catalyst cache so new results appear on Dashboard
                    # Keep SQL price cache (6h) and other caches intact
                    from mongodb_utils import load_catalysts
                    if hasattr(load_catalysts, 'clear'):
                        load_catalysts.clear()

                    # Keep batch_movements visible so user can review results
                    # Don't reset state or trigger rerun
                    st.session_state.batch_search_running = False

                    st.info("💡 New catalysts will appear on Dashboard within ~60 seconds.")
