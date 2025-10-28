"""
MongoDB utility functions for Commodity Dashboard
"""
from pymongo import MongoClient
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

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

# ==================== Catalyst Functions ====================

def load_catalysts() -> List[Dict[str, Any]]:
    """
    Load all catalysts from MongoDB
    Returns list of catalyst dictionaries sorted by date_created (newest first)

    Schema: {
        "commodity_group": "Iron Ore",
        "summary": "...",
        "timeline": [{"date": "YYYY-MM-DD", "event": "..."}],
        "search_date": "YYYY-MM-DD",
        "date_created": "ISO8601 timestamp",
        "search_trigger": "auto" or "manual",
        "cooldown_until": "ISO8601 timestamp"
    }
    """
    db = get_database()
    collection = db["catalysts"]

    # Fetch all catalysts, sorted by date_created (newest first)
    catalysts = list(collection.find({}, {'_id': 0}).sort("date_created", -1))

    return catalysts

# Cache the function only if Streamlit is available (60s TTL like classifications)
if HAS_STREAMLIT:
    load_catalysts = st.cache_data(ttl=60)(load_catalysts)

def get_catalyst(commodity_group: str) -> Optional[Dict[str, Any]]:
    """
    Get LATEST catalyst for a specific commodity group (by date_created)

    Parameters:
    - commodity_group: Name of the commodity group (e.g., "Iron Ore")

    Returns:
    - Latest catalyst document if found, None otherwise
    """
    db = get_database()
    collection = db["catalysts"]

    # Get the latest catalyst by date_created
    catalyst = collection.find_one(
        {"commodity_group": commodity_group},
        {'_id': 0},
        sort=[("date_created", -1)]
    )

    return catalyst

def get_catalyst_history(commodity_group: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get catalyst history for a specific commodity group

    Parameters:
    - commodity_group: Name of the commodity group
    - limit: Maximum number of historical entries to return (default: 10)

    Returns:
    - List of catalyst documents, sorted newest first
    """
    db = get_database()
    collection = db["catalysts"]

    catalysts = list(collection.find(
        {"commodity_group": commodity_group},
        {'_id': 0}
    ).sort("date_created", -1).limit(limit))

    return catalysts

def save_catalyst(
    commodity_group: str,
    summary: str,
    timeline: List[Dict[str, str]],
    search_trigger: str = "manual",
    direction: Optional[str] = None
) -> bool:
    """
    Save new catalyst for a commodity group (creates new document)

    Parameters:
    - commodity_group: Name of the commodity group
    - summary: 1-2 sentence summary of catalysts
    - timeline: List of {"date": "YYYY-MM-DD", "event": "..."} dicts
    - search_trigger: "auto" or "manual"
    - direction: "bullish", "bearish", or "both" (optional)

    Returns:
    - bool: True if successful, False otherwise
    """
    try:
        db = get_database()
        collection = db["catalysts"]

        now = datetime.utcnow()
        search_date = now.strftime("%Y-%m-%d")
        cooldown_until = now + timedelta(days=5)

        # Create new catalyst document
        new_catalyst = {
            "commodity_group": commodity_group,
            "summary": summary,
            "timeline": timeline,
            "search_date": search_date,
            "date_created": now.isoformat(),
            "search_trigger": search_trigger,
            "cooldown_until": cooldown_until.isoformat()
        }

        # Add direction if provided
        if direction:
            new_catalyst["direction"] = direction

        # Insert new document
        collection.insert_one(new_catalyst)

        # Create indexes for faster queries
        collection.create_index([("commodity_group", 1), ("date_created", -1)])
        collection.create_index("date_created")

        # Clear the cache so new data is loaded (only if using Streamlit)
        if HAS_STREAMLIT and hasattr(load_catalysts, 'clear'):
            load_catalysts.clear()

        return True

    except Exception as e:
        msg = f"Error saving catalyst to MongoDB: {e}"
        if HAS_STREAMLIT:
            st.error(msg)
        else:
            print(msg)
        return False

def can_auto_trigger(commodity_group: str) -> Tuple[bool, str]:
    """
    Check if auto-trigger is allowed for a commodity (5-day cooldown)
    Manual searches always allowed - this is only for auto-trigger

    Parameters:
    - commodity_group: Name of the commodity group

    Returns:
    - Tuple[bool, str]: (can_trigger, message)
    """
    # Get latest catalyst
    latest_catalyst = get_catalyst(commodity_group)

    if not latest_catalyst:
        return True, "No previous search found"

    cooldown_until_str = latest_catalyst.get("cooldown_until")
    if not cooldown_until_str:
        return True, "No cooldown set"

    try:
        cooldown_until = datetime.fromisoformat(cooldown_until_str)
        now = datetime.utcnow()

        if now < cooldown_until:
            days_remaining = (cooldown_until - now).days
            hours_remaining = ((cooldown_until - now).seconds // 3600)
            return False, f"Cooldown active: {days_remaining}d {hours_remaining}h remaining"

        return True, "Cooldown expired, ready to search"

    except Exception as e:
        # If error parsing date, allow trigger
        return True, f"Cooldown check error: {e}"

def update_catalyst_direction(commodity_group: str, direction: str) -> bool:
    """
    Update the direction field for the LATEST catalyst of a commodity group

    Parameters:
    - commodity_group: Name of the commodity group
    - direction: "bullish", "bearish", or "both"

    Returns:
    - bool: True if successful, False otherwise
    """
    try:
        db = get_database()
        collection = db["catalysts"]

        # Find the latest catalyst for this group
        latest_catalyst = collection.find_one(
            {"commodity_group": commodity_group},
            sort=[("date_created", -1)]
        )

        if not latest_catalyst:
            msg = f"No catalyst found for {commodity_group}"
            if HAS_STREAMLIT:
                st.warning(msg)
            else:
                print(msg)
            return False

        # Update the direction field
        result = collection.update_one(
            {"_id": latest_catalyst["_id"]},
            {"$set": {"direction": direction}}
        )

        # Clear the cache so updated data is loaded
        if HAS_STREAMLIT and hasattr(load_catalysts, 'clear'):
            load_catalysts.clear()

        return result.modified_count > 0

    except Exception as e:
        msg = f"Error updating catalyst direction: {e}"
        if HAS_STREAMLIT:
            st.error(msg)
        else:
            print(msg)
        return False
