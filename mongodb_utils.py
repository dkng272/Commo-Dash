"""
MongoDB utility functions for Commodity Dashboard
"""
from pymongo import MongoClient
import os
from typing import List, Dict, Any

# Try to import streamlit, but make it optional for local usage
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

def get_mongo_client():
    """
    Get MongoDB client with connection from Streamlit secrets or environment variables
    """
    # Try Streamlit secrets first, then fall back to environment variable
    if HAS_STREAMLIT:
        try:
            mongo_uri = st.secrets["MONGODB_URI"]
        except:
            mongo_uri = os.getenv("MONGODB_URI")
    else:
        mongo_uri = os.getenv("MONGODB_URI")

    if not mongo_uri:
        raise ValueError("MONGODB_URI not found in secrets or environment variables")

    client = MongoClient(mongo_uri)
    return client

def get_database():
    """
    Get the commodity dashboard database
    """
    client = get_mongo_client()
    return client["commodity_dashboard"]

def load_ticker_mappings() -> List[Dict[str, Any]]:
    """
    Load ticker mappings from MongoDB
    Returns list of ticker mapping dictionaries
    """
    db = get_database()
    collection = db["ticker_mappings"]

    # Fetch all ticker mappings, exclude MongoDB's _id field
    ticker_mappings = list(collection.find({}, {'_id': 0}))

    if not ticker_mappings:
        msg = "⚠️ No ticker mappings found in MongoDB."
        if HAS_STREAMLIT:
            st.error(msg)
        else:
            print(msg)
        return []

    return ticker_mappings

# Cache the function only if Streamlit is available
if HAS_STREAMLIT:
    load_ticker_mappings = st.cache_data(ttl=300)(load_ticker_mappings)

def save_ticker_mappings(ticker_mappings: List[Dict[str, Any]]) -> bool:
    """
    Save ticker mappings to MongoDB (replaces all existing data)

    Parameters:
    - ticker_mappings: List of ticker mapping dictionaries

    Returns:
    - bool: True if successful, False otherwise
    """
    try:
        db = get_database()
        collection = db["ticker_mappings"]

        # Clear existing data
        collection.delete_many({})

        # Insert new data
        if ticker_mappings:
            collection.insert_many(ticker_mappings)

        # Clear the cache so new data is loaded (only if using Streamlit)
        if HAS_STREAMLIT and hasattr(load_ticker_mappings, 'clear'):
            load_ticker_mappings.clear()

        return True
    except Exception as e:
        msg = f"Error saving to MongoDB: {e}"
        if HAS_STREAMLIT:
            st.error(msg)
        else:
            print(msg)
        return False

# ==================== Reports Functions ====================

def load_reports() -> List[Dict[str, Any]]:
    """
    Load all reports from MongoDB
    Returns list of report dictionaries sorted by date (newest first)
    """
    db = get_database()
    collection = db["reports"]

    # Fetch all reports, exclude MongoDB's _id field
    reports = list(collection.find({}, {'_id': 0}).sort("report_date", -1))

    if not reports:
        msg = "⚠️ No reports found in MongoDB."
        if HAS_STREAMLIT:
            st.warning(msg)
        else:
            print(msg)
        return []

    return reports

# Cache the function only if Streamlit is available
if HAS_STREAMLIT:
    load_reports = st.cache_data(ttl=300)(load_reports)

def save_reports(reports: List[Dict[str, Any]]) -> bool:
    """
    Save reports to MongoDB (replaces all existing data)

    Parameters:
    - reports: List of report dictionaries

    Returns:
    - bool: True if successful, False otherwise
    """
    try:
        db = get_database()
        collection = db["reports"]

        # Clear existing data
        collection.delete_many({})

        # Insert new data
        if reports:
            collection.insert_many(reports)

        # Create index on report_date for faster queries
        collection.create_index("report_date")

        # Clear the cache so new data is loaded (only if using Streamlit)
        if HAS_STREAMLIT and hasattr(load_reports, 'clear'):
            load_reports.clear()

        return True
    except Exception as e:
        msg = f"Error saving reports to MongoDB: {e}"
        if HAS_STREAMLIT:
            st.error(msg)
        else:
            print(msg)
        return False

# ==================== Commodity Classification Functions ====================

def load_commodity_classifications() -> List[Dict[str, Any]]:
    """
    Load commodity classifications from MongoDB
    Returns list of classification dictionaries

    Schema: {"item": "Ore 62", "sector": "Steel Material", "group": "Iron Ore", "region": "China"}
    """
    db = get_database()
    collection = db["commodity_classification"]

    # Fetch all classifications, exclude MongoDB's _id field
    classifications = list(collection.find({}, {'_id': 0}))

    if not classifications:
        msg = "⚠️ No commodity classifications found in MongoDB. Please run the migration script: python migrate_commo_list_to_mongodb.py"
        if HAS_STREAMLIT:
            st.warning(msg)
        else:
            print(msg)
        return []

    return classifications

# Cache the function only if Streamlit is available
# Short TTL (60s) allows quick propagation of classification changes across pages
if HAS_STREAMLIT:
    load_commodity_classifications = st.cache_data(ttl=60)(load_commodity_classifications)

def save_commodity_classifications(classifications: List[Dict[str, Any]]) -> bool:
    """
    Save commodity classifications to MongoDB (replaces all existing data)

    Parameters:
    - classifications: List of classification dictionaries
      Each dict should have: {"item": str, "sector": str, "group": str, "region": str}

    Returns:
    - bool: True if successful, False otherwise
    """
    try:
        db = get_database()
        collection = db["commodity_classification"]

        # Clear existing data
        collection.delete_many({})

        # Insert new data
        if classifications:
            collection.insert_many(classifications)

        # Create index on item for faster lookups
        collection.create_index("item", unique=True)

        # Clear the cache so new data is loaded (only if using Streamlit)
        if HAS_STREAMLIT and hasattr(load_commodity_classifications, 'clear'):
            load_commodity_classifications.clear()

        return True
    except Exception as e:
        msg = f"Error saving commodity classifications to MongoDB: {e}"
        if HAS_STREAMLIT:
            st.error(msg)
        else:
            print(msg)
        return False
