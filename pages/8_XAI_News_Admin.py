import streamlit as st
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# Add xai_api directory to path
xai_api_dir = os.path.join(parent_dir, "xai_api")
sys.path.append(xai_api_dir)

# Import utilities
from mongodb_utils import get_catalyst, get_catalyst_history, save_catalyst, can_auto_trigger, load_commodity_classifications
from catalyst_search import search_catalysts

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

# ===== Load Commodity Groups =====

@st.cache_data(ttl=60)
def load_commodity_groups():
    """Load all commodity groups from MongoDB classifications"""
    try:
        classifications = load_commodity_classifications()
        if classifications:
            groups = set(c.get('group') for c in classifications if c.get('group'))
            return sorted(groups)
        return []
    except Exception as e:
        st.error(f"Error loading commodity groups: {e}")
        return []

commodity_groups = load_commodity_groups()

# ===== Step 1: Select Commodity Group =====

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
        st.text(summary)  # Use st.text() to avoid markdown interpretation

        st.divider()

        # Timeline
        timeline = results.get("timeline", [])
        if timeline:
            st.markdown(f"**Catalyst Timeline ({len(timeline)} events):**")

            for entry in timeline:
                date = entry.get("date", "Unknown")
                event = entry.get("event", "No description")

                with st.expander(f"📅 {date}", expanded=False):
                    st.text(event)  # Use st.text() to avoid markdown interpretation
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

