"""
One-time migration script to move commo_list.xlsx to MongoDB

Run this script once to migrate your commodity classification from Excel to MongoDB:
    python migrate_commo_list_to_mongodb.py
"""

import pandas as pd
from mongodb_utils import save_commodity_classifications

def migrate_commo_list():
    """
    Load commo_list.xlsx and upload to MongoDB
    """
    print("Loading commo_list.xlsx...")
    df = pd.read_excel('commo_list.xlsx')

    # Strip whitespace
    df['Sector'] = df['Sector'].str.strip()
    df['Group'] = df['Group'].str.strip()
    df['Region'] = df['Region'].str.strip()
    df['Item'] = df['Item'].str.strip()

    print(f"Loaded {len(df)} classifications")
    print(f"Columns: {df.columns.tolist()}")
    print(f"\nFirst few rows:")
    print(df.head())

    # Convert to list of dictionaries
    classifications = []
    for _, row in df.iterrows():
        classifications.append({
            'item': row['Item'],
            'sector': row['Sector'],
            'group': row['Group'],
            'region': row['Region']
        })

    print(f"\nConverted to {len(classifications)} classification records")
    print(f"Sample record: {classifications[0]}")

    # Upload to MongoDB
    print("\nUploading to MongoDB...")
    success = save_commodity_classifications(classifications)

    if success:
        print("✅ Migration completed successfully!")
        print(f"   - Uploaded {len(classifications)} commodity classifications")
        print("   - MongoDB collection: commodity_dashboard.commodity_classification")
        print("\nYou can now use the Commodity List Admin page to manage classifications.")
    else:
        print("❌ Migration failed. Check error messages above.")
        return False

    return True

if __name__ == "__main__":
    migrate_commo_list()
