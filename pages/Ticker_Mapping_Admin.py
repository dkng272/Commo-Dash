import streamlit as st
import pandas as pd
import json
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

st.set_page_config(layout="wide", page_title="Ticker Mapping Admin")

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

st.title('Ticker Mapping Administration')
st.markdown("*Edit ticker input/output mappings with validated commodity data*")

# File paths
COMMO_LIST_PATH = 'commo_list.xlsx'
MAPPING_JSON_PATH = 'ticker_mappings_final.json'

# ===== Helper Functions =====

@st.cache_data
def load_commo_list():
    """Load commodity list as reference data"""
    df = pd.read_excel(COMMO_LIST_PATH)
    # Strip whitespace from all columns (consistency with data_cleaning.py)
    df['Sector'] = df['Sector'].str.strip()
    df['Group'] = df['Group'].str.strip()
    df['Region'] = df['Region'].str.strip()
    df['Item'] = df['Item'].str.strip()
    return df

@st.cache_data
def get_unique_values(df):
    """Extract unique values for dropdowns"""
    return {
        'sectors': sorted(df['Sector'].dropna().unique().tolist()),
        'groups': sorted(df['Group'].dropna().unique().tolist()),
        'regions': sorted(df['Region'].dropna().unique().tolist()),
        'items': sorted(df['Item'].dropna().unique().tolist())
    }

def get_filtered_options(commo_df, group=None, region=None):
    """Get filtered regions and items based on group selection"""
    filtered = commo_df.copy()

    if group:
        filtered = filtered[filtered['Group'] == group]

    regions = sorted(filtered['Region'].dropna().unique().tolist())

    if region:
        filtered = filtered[filtered['Region'] == region]

    items = sorted(filtered['Item'].dropna().unique().tolist())

    return regions, items

def load_mappings():
    """Load ticker mappings from MongoDB"""
    from mongodb_utils import load_ticker_mappings
    return load_ticker_mappings()

def save_mappings(mappings):
    """Save ticker mappings to MongoDB"""
    from mongodb_utils import save_ticker_mappings

    success = save_ticker_mappings(mappings)
    if success:
        st.success("✅ Mappings saved successfully to MongoDB!")
    else:
        st.error("❌ Failed to save mappings to MongoDB")

def find_ticker_index(mappings, ticker):
    """Find index of ticker in mappings list"""
    for idx, mapping in enumerate(mappings):
        if mapping['ticker'] == ticker:
            return idx
    return -1

# ===== Load Data =====

commo_df = load_commo_list()
unique_vals = get_unique_values(commo_df)
mappings = load_mappings()
existing_tickers = sorted([m['ticker'] for m in mappings])

# ===== Initialize Session State =====

if 'selected_ticker' not in st.session_state:
    st.session_state.selected_ticker = None
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = 'view'  # 'view', 'edit', 'new'
if 'working_mapping' not in st.session_state:
    st.session_state.working_mapping = None
if 'refresh_key' not in st.session_state:
    st.session_state.refresh_key = 0

# ===== Sidebar - Ticker Selection =====

st.sidebar.header("Ticker Selection")

# Mode selection (no refresh_key here to keep it stable)
mode = st.sidebar.radio("Mode", ["Edit Existing Ticker", "Add New Ticker"])

if mode == "Edit Existing Ticker":
    # Determine default index from session state
    default_index = 0
    if st.session_state.selected_ticker and st.session_state.selected_ticker in existing_tickers and st.session_state.edit_mode == 'edit':
        default_index = existing_tickers.index(st.session_state.selected_ticker) + 1  # +1 for empty option

    selected = st.sidebar.selectbox(
        "Select Ticker",
        options=[""] + existing_tickers,
        index=default_index
    )

    if selected:
        st.session_state.edit_mode = 'edit'
        st.session_state.selected_ticker = selected
        # Only reload from JSON if ticker changed or working_mapping is None
        if st.session_state.working_mapping is None or st.session_state.working_mapping.get('ticker') != selected:
            idx = find_ticker_index(mappings, selected)
            st.session_state.working_mapping = mappings[idx].copy()
    else:
        st.session_state.selected_ticker = None
        st.session_state.working_mapping = None

else:  # Add New Ticker
    # Preserve the new ticker value if in 'new' mode
    default_value = ""
    if st.session_state.edit_mode == 'new' and st.session_state.selected_ticker:
        default_value = st.session_state.selected_ticker

    new_ticker = st.sidebar.text_input("New Ticker Code", value=default_value)

    if new_ticker:
        if new_ticker in existing_tickers:
            st.sidebar.error(f"❌ Ticker {new_ticker} already exists!")
            st.session_state.selected_ticker = None
            st.session_state.working_mapping = None
        else:
            st.session_state.edit_mode = 'new'
            st.session_state.selected_ticker = new_ticker
            # Only create new mapping if ticker changed or working_mapping is None
            if st.session_state.working_mapping is None or st.session_state.working_mapping.get('ticker') != new_ticker:
                st.session_state.working_mapping = {
                    'ticker': new_ticker,
                    'inputs': [],
                    'outputs': []
                }
    else:
        st.session_state.selected_ticker = None
        st.session_state.working_mapping = None

# ===== Main Editor =====

if not st.session_state.selected_ticker:
    st.info("👈 Select a ticker from the sidebar to begin editing")

else:
    ticker = st.session_state.selected_ticker
    working = st.session_state.working_mapping

    st.header(f"Editing: {ticker}")

    # Create two columns for Inputs and Outputs
    col_input, col_output = st.columns(2)

    # ===== INPUTS EDITOR =====
    with col_input:
        st.subheader("📥 Inputs")

        if 'inputs' not in working:
            working['inputs'] = []

        # Display existing inputs
        for idx, inp in enumerate(working['inputs']):
            with st.expander(f"Input #{idx + 1}: {inp.get('group', 'Not set')}", expanded=True):
                col1, col2 = st.columns([4, 1])

                with col1:
                    # Group selection
                    current_group = inp.get('group', '')
                    group_idx = unique_vals['groups'].index(current_group) if current_group in unique_vals['groups'] else 0
                    selected_group = st.selectbox(
                        "Group",
                        options=unique_vals['groups'],
                        index=group_idx,
                        key=f"input_group_{ticker}_{idx}_{st.session_state.refresh_key}"
                    )

                    # Get filtered regions and items
                    regions, items = get_filtered_options(commo_df, group=selected_group)

                    # Region selection
                    current_region = inp.get('region', '')
                    if current_region and current_region in regions:
                        region_idx = regions.index(current_region)
                    else:
                        region_idx = 0

                    selected_region = st.selectbox(
                        "Region",
                        options=regions,
                        index=region_idx,
                        key=f"input_region_{ticker}_{idx}_{st.session_state.refresh_key}"
                    )

                    # Item selection (filtered by group and region)
                    _, items = get_filtered_options(commo_df, group=selected_group, region=selected_region)
                    items_with_none = [""] + items

                    current_item = inp.get('item', '')
                    if current_item and current_item in items_with_none:
                        item_idx = items_with_none.index(current_item)
                    else:
                        item_idx = 0

                    selected_item = st.selectbox(
                        "Item (optional)",
                        options=items_with_none,
                        index=item_idx,
                        key=f"input_item_{ticker}_{idx}_{st.session_state.refresh_key}"
                    )

                    # Sensitivity
                    current_sensitivity = inp.get('sensitivity')
                    sensitivity = st.number_input(
                        "Sensitivity (0-1, optional)",
                        min_value=0.0,
                        max_value=1.0,
                        value=current_sensitivity if current_sensitivity else 0.0,
                        step=0.1,
                        key=f"input_sensitivity_{ticker}_{idx}_{st.session_state.refresh_key}"
                    )

                    # Update working mapping
                    working['inputs'][idx] = {
                        'group': selected_group,
                        'region': selected_region,
                        'item': selected_item if selected_item else None,
                        'sensitivity': sensitivity if sensitivity > 0 else None
                    }

                with col2:
                    st.write("")
                    st.write("")
                    if st.button("🗑️", key=f"del_input_{ticker}_{idx}_{st.session_state.refresh_key}"):
                        working['inputs'].pop(idx)
                        st.session_state.refresh_key += 1
                        st.rerun()

        # Add new input button
        if st.button("➕ Add Input", key=f"add_input_{ticker}_{st.session_state.refresh_key}"):
            working['inputs'].append({
                'group': unique_vals['groups'][0],
                'region': None,
                'item': None,
                'sensitivity': None
            })
            st.session_state.refresh_key += 1
            st.rerun()

    # ===== OUTPUTS EDITOR =====
    with col_output:
        st.subheader("📤 Outputs")

        if 'outputs' not in working:
            working['outputs'] = []

        # Display existing outputs
        for idx, out in enumerate(working['outputs']):
            with st.expander(f"Output #{idx + 1}: {out.get('group', 'Not set')}", expanded=True):
                col1, col2 = st.columns([4, 1])

                with col1:
                    # Group selection
                    current_group = out.get('group', '')
                    group_idx = unique_vals['groups'].index(current_group) if current_group in unique_vals['groups'] else 0
                    selected_group = st.selectbox(
                        "Group",
                        options=unique_vals['groups'],
                        index=group_idx,
                        key=f"output_group_{ticker}_{idx}_{st.session_state.refresh_key}"
                    )

                    # Get filtered regions and items
                    regions, items = get_filtered_options(commo_df, group=selected_group)

                    # Region selection
                    current_region = out.get('region', '')
                    if current_region and current_region in regions:
                        region_idx = regions.index(current_region)
                    else:
                        region_idx = 0

                    selected_region = st.selectbox(
                        "Region",
                        options=regions,
                        index=region_idx,
                        key=f"output_region_{ticker}_{idx}_{st.session_state.refresh_key}"
                    )

                    # Item selection (filtered by group and region)
                    _, items = get_filtered_options(commo_df, group=selected_group, region=selected_region)
                    items_with_none = [""] + items

                    current_item = out.get('item', '')
                    if current_item and current_item in items_with_none:
                        item_idx = items_with_none.index(current_item)
                    else:
                        item_idx = 0

                    selected_item = st.selectbox(
                        "Item (optional)",
                        options=items_with_none,
                        index=item_idx,
                        key=f"output_item_{ticker}_{idx}_{st.session_state.refresh_key}"
                    )

                    # Sensitivity
                    current_sensitivity = out.get('sensitivity')
                    sensitivity = st.number_input(
                        "Sensitivity (0-1, optional)",
                        min_value=0.0,
                        max_value=1.0,
                        value=current_sensitivity if current_sensitivity else 0.0,
                        step=0.1,
                        key=f"output_sensitivity_{ticker}_{idx}_{st.session_state.refresh_key}"
                    )

                    # Update working mapping
                    working['outputs'][idx] = {
                        'group': selected_group,
                        'region': selected_region,
                        'item': selected_item if selected_item else None,
                        'sensitivity': sensitivity if sensitivity > 0 else None
                    }

                with col2:
                    st.write("")
                    st.write("")
                    if st.button("🗑️", key=f"del_output_{ticker}_{idx}_{st.session_state.refresh_key}"):
                        working['outputs'].pop(idx)
                        st.session_state.refresh_key += 1
                        st.rerun()

        # Add new output button
        if st.button("➕ Add Output", key=f"add_output_{ticker}_{st.session_state.refresh_key}"):
            working['outputs'].append({
                'group': unique_vals['groups'][0],
                'region': None,
                'item': None,
                'sensitivity': None
            })
            st.session_state.refresh_key += 1
            st.rerun()

    # ===== Preview and Save =====
    st.divider()

    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader("📋 Preview JSON")
        st.json(working)

    with col2:
        st.write("")
        st.write("")
        st.write("")

        # Save button
        if st.button("💾 Save Changes", type="primary", use_container_width=True):
            if st.session_state.edit_mode == 'new':
                # Add new ticker
                mappings.append(working)
                # Sort by ticker
                mappings = sorted(mappings, key=lambda x: x['ticker'])
            else:
                # Update existing ticker
                idx = find_ticker_index(mappings, ticker)
                if idx >= 0:
                    mappings[idx] = working

            save_mappings(mappings)
            st.session_state.refresh_key += 1
            st.rerun()

        # Delete ticker button (only for existing tickers)
        if st.session_state.edit_mode == 'edit':
            if st.button("🗑️ Delete Ticker", type="secondary", use_container_width=True):
                idx = find_ticker_index(mappings, ticker)
                if idx >= 0:
                    mappings.pop(idx)
                    save_mappings(mappings)
                    st.session_state.selected_ticker = None
                    st.session_state.working_mapping = None
                    st.session_state.refresh_key += 1
                    st.rerun()

# ===== Data Validation Summary =====
st.sidebar.divider()
st.sidebar.subheader("📊 Data Summary")
st.sidebar.metric("Total Tickers", len(existing_tickers))
st.sidebar.metric("Total Groups", len(unique_vals['groups']))
st.sidebar.metric("Total Regions", len(unique_vals['regions']))
st.sidebar.metric("Total Items", len(unique_vals['items']))
