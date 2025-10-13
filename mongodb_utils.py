"""
MongoDB utility functions for Commodity Dashboard
"""
from pymongo import MongoClient
import streamlit as st
import json
from typing import List, Dict, Any

def get_mongo_client():
    """
    Get MongoDB client with connection from Streamlit secrets
    """
    try:
        # Try to get from Streamlit secrets first (for cloud deployment)
        mongo_uri = st.secrets["MONGODB_URI"]
    except (FileNotFoundError, KeyError):
        # Fallback to local connection for development
        mongo_uri = "mongodb://localhost:27017/"
        st.warning("⚠️ Using local MongoDB. Add MONGODB_URI to .streamlit/secrets.toml for cloud deployment.")

    client = MongoClient(mongo_uri)
    return client

def get_database():
    """
    Get the commodity dashboard database
    """
    client = get_mongo_client()
    return client["commodity_dashboard"]

@st.cache_data(ttl=300)  # Cache for 5 minutes
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
        st.error("⚠️ No ticker mappings found in MongoDB. Please run the migration script.")
        return []

    return ticker_mappings

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

        # Clear the cache so new data is loaded
        load_ticker_mappings.clear()

        return True
    except Exception as e:
        st.error(f"Error saving to MongoDB: {e}")
        return False

def migrate_json_to_mongodb(json_file_path: str) -> bool:
    """
    Migrate ticker mappings from JSON file to MongoDB

    Parameters:
    - json_file_path: Path to the JSON file

    Returns:
    - bool: True if successful, False otherwise
    """
    try:
        # Load from JSON
        with open(json_file_path, 'r') as f:
            ticker_mappings = json.load(f)

        # Save to MongoDB
        success = save_ticker_mappings(ticker_mappings)

        if success:
            print(f"✅ Successfully migrated {len(ticker_mappings)} ticker mappings to MongoDB")
        else:
            print("❌ Failed to migrate ticker mappings")

        return success
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        return False

def test_connection() -> bool:
    """
    Test MongoDB connection

    Returns:
    - bool: True if connection successful, False otherwise
    """
    try:
        client = get_mongo_client()
        # Ping the database
        client.admin.command('ping')
        print("✅ MongoDB connection successful")
        return True
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        return False
