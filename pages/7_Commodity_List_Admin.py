import streamlit as st
import pandas as pd
import sys
import os

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# Import MongoDB and SQL utilities
from mongodb_utils import load_commodity_classifications, save_commodity_classifications
from sql_connection import fetch_all_commodity_data

st.set_page_config(layout="wide", page_title="Commodity List Admin")

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

st.title('Commodity Classification Management')
st.markdown("*Manage commodity classifications (Item → Sector/Group/Region)*")

# ===== Helper Functions =====

@st.cache_data
def load_sql_items():
    """Load all unique commodity names from SQL"""
    try:
        df = fetch_all_commodity_data(start_date='2024-01-01', parallel=True)
        if 'Name' in df.columns:
            # Filter out NaN and non-string values, then sort
            unique_names = df['Name'].dropna().unique()
            # Convert to string and filter out any remaining non-strings
            valid_names = [str(name) for name in unique_names if isinstance(name, str) or pd.notna(name)]
            return sorted(valid_names)
        return []
    except Exception as e:
        st.error(f"Error loading SQL items: {e}")
        return []

def load_classifications():
    """Load commodity classifications from MongoDB"""
    return load_commodity_classifications()

def save_classifications(classifications):
    """Save commodity classifications to MongoDB"""
    success = save_commodity_classifications(classifications)
    if success:
        st.success("✅ Classifications saved successfully to MongoDB!")
        # Clear cache
        load_sql_items.clear()
    else:
        st.error("❌ Failed to save classifications to MongoDB")

def find_classification_index(classifications, item):
    """Find index of item in classifications list"""
    for idx, classification in enumerate(classifications):
        if classification['item'] == item:
            return idx
    return -1

# ===== Load Data =====

classifications = load_classifications()
sql_items = load_sql_items()

# Convert to DataFrame for easier display
if classifications:
    df_classifications = pd.DataFrame(classifications)
    # Capitalize for display
    df_classifications.rename(columns={
        'item': 'Item',
        'sector': 'Sector',
        'group': 'Group',
        'region': 'Region'
    }, inplace=True)
else:
    df_classifications = pd.DataFrame(columns=['Item', 'Sector', 'Group', 'Region'])

# Get unique values for dropdowns
unique_sectors = sorted(df_classifications['Sector'].dropna().unique().tolist()) if not df_classifications.empty else []
unique_groups = sorted(df_classifications['Group'].dropna().unique().tolist()) if not df_classifications.empty else []
unique_regions = sorted(df_classifications['Region'].dropna().unique().tolist()) if not df_classifications.empty else []

# Find unmapped items
if sql_items:
    classified_items = set(df_classifications['Item'].tolist())
    unmapped_items = sorted([item for item in sql_items if item not in classified_items])
else:
    unmapped_items = []

# ===== Initialize Session State =====

if 'selected_item' not in st.session_state:
    st.session_state.selected_item = None
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = 'view'  # 'view', 'edit', 'new'
if 'working_classification' not in st.session_state:
    st.session_state.working_classification = None
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = 0  # 0 = View All, 1 = Edit/Add, 2 = Unmapped

# ===== Sidebar - Statistics & Unmapped Items =====

st.sidebar.header("📊 Statistics")
st.sidebar.metric("Total Classified Items", len(df_classifications))
st.sidebar.metric("Total SQL Items", len(sql_items))
st.sidebar.metric("Unmapped Items", len(unmapped_items))

st.sidebar.divider()

# Show unmapped items
if unmapped_items:
    st.sidebar.subheader("⚠️ Unmapped SQL Items")
    st.sidebar.caption(f"{len(unmapped_items)} items need classification:")
    with st.sidebar.expander(f"View {len(unmapped_items)} unmapped items", expanded=False):
        for item in unmapped_items[:20]:  # Show first 20
            st.sidebar.text(f"• {item}")
        if len(unmapped_items) > 20:
            st.sidebar.caption(f"... and {len(unmapped_items) - 20} more")

# ===== Main Content Tabs =====

# Use radio buttons for tab navigation (preserves state better than st.tabs)
tab_names = ["📋 View All", "✏️ Edit/Add Item", "🆕 Add Unmapped Items"]
selected_tab = st.radio("", tab_names, index=st.session_state.active_tab, horizontal=True, label_visibility="collapsed")

# Update active tab in session state
st.session_state.active_tab = tab_names.index(selected_tab)

st.divider()

# ===== TAB 1: View All Classifications =====
if selected_tab == "📋 View All":
    st.subheader("All Commodity Classifications")

    if not df_classifications.empty:
        # Add search filter
        search_term = st.text_input("🔍 Search items", placeholder="Type to filter...")

        if search_term:
            filtered_df = df_classifications[
                df_classifications['Item'].str.contains(search_term, case=False, na=False) |
                df_classifications['Group'].str.contains(search_term, case=False, na=False) |
                df_classifications['Sector'].str.contains(search_term, case=False, na=False)
            ]
        else:
            filtered_df = df_classifications

        st.caption(f"Showing {len(filtered_df)} of {len(df_classifications)} items")
        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True,
            height=500
        )

        # Download button
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name="commodity_classifications.csv",
            mime="text/csv"
        )
    else:
        st.info("No classifications found. Please run the migration script first:\n\n`python migrate_commo_list_to_mongodb.py`")

# ===== TAB 2: Edit/Add Individual Item =====
elif selected_tab == "✏️ Edit/Add Item":
    st.subheader("Edit or Add Individual Item")

    mode = st.radio("Mode", ["Edit Existing Item", "Add New Item"], horizontal=True)

    if mode == "Edit Existing Item":
        existing_items = sorted(df_classifications['Item'].tolist())

        if existing_items:
            selected_item = st.selectbox(
                "Select Item to Edit",
                options=[""] + existing_items
            )

            if selected_item:
                st.session_state.edit_mode = 'edit'
                st.session_state.selected_item = selected_item

                # Load current classification
                idx = find_classification_index(classifications, selected_item)
                if idx >= 0:
                    current = classifications[idx]
                else:
                    st.error(f"Item {selected_item} not found in classifications")
                    st.stop()

                st.divider()

                col1, col2 = st.columns(2)

                with col1:
                    st.markdown(f"**Editing:** `{selected_item}`")

                    # Rename item option
                    st.markdown("**Rename Item (optional)**")
                    rename_item = st.checkbox("Rename this item to match SQL name", key="rename_checkbox")

                    if rename_item:
                        new_item_name_selected = st.selectbox(
                            "Select SQL item name",
                            options=[""] + sql_items,
                            help="Choose the correct name from SQL database"
                        )
                        if new_item_name_selected:
                            st.info(f"Will rename '{selected_item}' → '{new_item_name_selected}'")
                            new_item_name = new_item_name_selected
                        else:
                            new_item_name = selected_item
                    else:
                        new_item_name = selected_item

                    st.divider()

                    # Sector selector
                    current_sector = current.get('sector', '')

                    new_sector_input = st.text_input(
                        "Sector (type new or select below)",
                        value=current_sector,
                        key="sector_text"
                    )

                    if unique_sectors:
                        sector_options = [""] + unique_sectors
                        sector_idx = sector_options.index(current_sector) if current_sector in sector_options else 0
                        selected_existing_sector = st.selectbox(
                            "Or select existing sector",
                            options=sector_options,
                            index=sector_idx,
                            key="sector_select"
                        )
                        # Use selectbox value only if explicitly selected (not empty and different from current)
                        if selected_existing_sector and selected_existing_sector != current_sector:
                            new_sector = selected_existing_sector
                        else:
                            new_sector = new_sector_input
                    else:
                        new_sector = new_sector_input

                    # Group selector
                    current_group = current.get('group', '')

                    new_group_input = st.text_input(
                        "Group (type new or select below)",
                        value=current_group,
                        key="group_text"
                    )

                    if unique_groups:
                        group_options = [""] + unique_groups
                        group_idx = group_options.index(current_group) if current_group in group_options else 0
                        selected_existing_group = st.selectbox(
                            "Or select existing group",
                            options=group_options,
                            index=group_idx,
                            key="group_select"
                        )
                        # Use selectbox value only if explicitly selected (not empty and different from current)
                        if selected_existing_group and selected_existing_group != current_group:
                            new_group = selected_existing_group
                        else:
                            new_group = new_group_input
                    else:
                        new_group = new_group_input

                with col2:
                    st.write("")
                    st.write("")

                    # Region selector
                    current_region = current.get('region', '')

                    new_region_input = st.text_input(
                        "Region (type new or select below)",
                        value=current_region,
                        key="region_text"
                    )

                    if unique_regions:
                        region_options = [""] + unique_regions
                        region_idx = region_options.index(current_region) if current_region in region_options else 0
                        selected_existing_region = st.selectbox(
                            "Or select existing region",
                            options=region_options,
                            index=region_idx,
                            key="region_select"
                        )
                        # Use selectbox value only if explicitly selected (not empty and different from current)
                        if selected_existing_region and selected_existing_region != current_region:
                            new_region = selected_existing_region
                        else:
                            new_region = new_region_input
                    else:
                        new_region = new_region_input

                st.divider()

                col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])

                with col_btn1:
                    if st.button("💾 Save Changes", type="primary", use_container_width=True):
                        # Check if new name already exists (when renaming)
                        if new_item_name != selected_item and new_item_name in [c['item'] for c in classifications]:
                            st.error(f"❌ Item '{new_item_name}' already exists! Choose a different name.")
                        else:
                            # Update classification (with possible rename)
                            classifications[idx] = {
                                'item': new_item_name,
                                'sector': new_sector,
                                'group': new_group,
                                'region': new_region
                            }
                            st.session_state.active_tab = 1  # Stay on Edit/Add tab
                            save_classifications(classifications)
                            st.rerun()

                with col_btn2:
                    if st.button("🗑️ Delete Item", type="secondary", use_container_width=True):
                        classifications.pop(idx)
                        st.session_state.active_tab = 1  # Stay on Edit/Add tab
                        save_classifications(classifications)
                        st.session_state.selected_item = None
                        st.rerun()

        else:
            st.info("No items to edit. Add new items first.")

    else:  # Add New Item
        st.markdown("**Add New Commodity Classification**")

        new_item = st.text_input("Item Name", placeholder="e.g., Urea Vietnam")

        if new_item:
            # Check if already exists
            if new_item in df_classifications['Item'].tolist():
                st.error(f"❌ Item '{new_item}' already exists! Please edit it instead.")
            else:
                col1, col2 = st.columns(2)

                with col1:
                    # Sector
                    new_sector_input = st.text_input("Sector (type new or select below)", key="new_sector_text")
                    if unique_sectors:
                        selected_sector = st.selectbox("Or select existing sector", [""] + unique_sectors, key="new_sector_select")
                        new_sector = selected_sector if selected_sector else new_sector_input
                    else:
                        new_sector = new_sector_input

                    # Group
                    new_group_input = st.text_input("Group (type new or select below)", key="new_group_text")
                    if unique_groups:
                        selected_group = st.selectbox("Or select existing group", [""] + unique_groups, key="new_group_select")
                        new_group = selected_group if selected_group else new_group_input
                    else:
                        new_group = new_group_input

                with col2:
                    # Region
                    new_region_input = st.text_input("Region (type new or select below)", key="new_region_text")
                    if unique_regions:
                        selected_region = st.selectbox("Or select existing region", [""] + unique_regions, key="new_region_select")
                        new_region = selected_region if selected_region else new_region_input
                    else:
                        new_region = new_region_input

                st.divider()

                if st.button("➕ Add Classification", type="primary"):
                    if not new_sector or not new_group or not new_region:
                        st.error("Please fill in all fields (Sector, Group, Region)")
                    else:
                        # Add new classification
                        classifications.append({
                            'item': new_item,
                            'sector': new_sector,
                            'group': new_group,
                            'region': new_region
                        })
                        st.session_state.active_tab = 1  # Stay on Edit/Add tab
                        save_classifications(classifications)
                        st.rerun()

# ===== TAB 3: Bulk Add Unmapped Items =====
elif selected_tab == "🆕 Add Unmapped Items":
    st.subheader("Add Unmapped SQL Items")

    if unmapped_items:
        st.info(f"Found {len(unmapped_items)} items in SQL that need classification")

        # Batch classification mode
        st.markdown("**Quick Classification Mode**")
        st.caption("Select an unmapped item and assign Sector/Group/Region")

        selected_unmapped = st.selectbox(
            "Select Unmapped Item",
            options=[""] + unmapped_items
        )

        if selected_unmapped:
            st.markdown(f"**Classifying:** `{selected_unmapped}`")

            col1, col2 = st.columns(2)

            with col1:
                # Sector
                batch_sector_input = st.text_input("Sector (type new or select below)", key="batch_sector")
                if unique_sectors:
                    sel_sector = st.selectbox("Or select existing sector", [""] + unique_sectors, key="batch_sel_sector")
                    batch_sector = sel_sector if sel_sector else batch_sector_input
                else:
                    batch_sector = batch_sector_input

                # Group
                batch_group_input = st.text_input("Group (type new or select below)", key="batch_group")
                if unique_groups:
                    sel_group = st.selectbox("Or select existing group", [""] + unique_groups, key="batch_sel_group")
                    batch_group = sel_group if sel_group else batch_group_input
                else:
                    batch_group = batch_group_input

            with col2:
                # Region
                batch_region_input = st.text_input("Region (type new or select below)", key="batch_region")
                if unique_regions:
                    sel_region = st.selectbox("Or select existing region", [""] + unique_regions, key="batch_sel_region")
                    batch_region = sel_region if sel_region else batch_region_input
                else:
                    batch_region = batch_region_input

            if st.button("✅ Add This Classification", type="primary"):
                if not batch_sector or not batch_group or not batch_region:
                    st.error("Please fill in all fields")
                else:
                    classifications.append({
                        'item': selected_unmapped,
                        'sector': batch_sector,
                        'group': batch_group,
                        'region': batch_region
                    })
                    st.session_state.active_tab = 2  # Stay on Add Unmapped Items tab
                    save_classifications(classifications)
                    st.success(f"✅ Added classification for '{selected_unmapped}'")
                    st.rerun()

    else:
        st.success("🎉 All SQL items are classified! No unmapped items found.")
