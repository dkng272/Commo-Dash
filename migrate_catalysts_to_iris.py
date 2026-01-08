"""
One-time migration script: Copy XAI catalysts from personal MongoDB to IRIS (ClaudeTrade)

Source: Duy_MongoDB_MCP → commodity_dashboard.catalysts
Target: DC_MongoDB_MCP → IRIS.commodity_news
"""
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

# Source: Personal MongoDB
SOURCE_URI = os.getenv("MONGODB_URI")
# Target: IRIS MongoDB (ClaudeTrade)
TARGET_URI = os.getenv("IRIS_MONGODB_URI")


def migrate():
    if not SOURCE_URI:
        print("ERROR: MONGODB_URI not found in environment")
        return
    if not TARGET_URI:
        print("ERROR: IRIS_MONGODB_URI not found in environment")
        return

    # Connect to source
    source_client = MongoClient(SOURCE_URI)
    source_collection = source_client["commodity_dashboard"]["catalysts"]

    # Connect to target
    target_client = MongoClient(TARGET_URI)
    target_collection = target_client["IRIS"]["commodity_news"]

    # Export all documents (exclude _id to let target generate new ones)
    docs = list(source_collection.find({}, {'_id': 0}))
    print(f"Found {len(docs)} documents to migrate")

    if not docs:
        print("No documents to migrate")
        return

    # Insert into target
    result = target_collection.insert_many(docs)
    print(f"Inserted {len(result.inserted_ids)} documents")

    # Create indexes
    target_collection.create_index([("commodity_group", 1), ("date_created", -1)])
    target_collection.create_index("date_created")
    print("Created indexes")

    print("Migration complete!")


if __name__ == "__main__":
    migrate()
