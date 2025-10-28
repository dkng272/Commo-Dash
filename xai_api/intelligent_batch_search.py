"""
Intelligent Batch Catalyst Search

Automatically determines search parameters (direction, lookback days) based on
recent commodity price movements for each group.

Logic:
1. Calculate 5D and 10D price movements for each commodity group
2. If 5D movement > 3%: bullish direction, 7-day lookback
3. If 5D movement < -3%: bearish direction, 7-day lookback
4. If 5D movement between -3% and 3%:
   - If 10D > 3%: bullish direction, 14-day lookback
   - If 10D < -3%: bearish direction, 14-day lookback
   - Otherwise: both directions, 14-day lookback

Usage:
    python intelligent_batch_search.py
    python intelligent_batch_search.py --threshold 3.0 --delay 5
    python intelligent_batch_search.py --groups "Iron Ore,HRC,Coal" --save-to-mongodb
"""

import sys
import os
import time
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
sys.path.append(str(parent_dir))

# Import required modules
from mongodb_utils import load_commodity_classifications, save_catalyst, can_auto_trigger
from commo_dashboard import create_equal_weight_index
from catalyst_search import search_catalysts


def load_commodity_data():
    """
    Load commodity price data from SQL Server.

    Uses GLOBAL 6-hour cached data when running in Streamlit (shared across all pages).
    Falls back to direct SQL query for standalone command-line use.

    Returns DataFrame with columns: Ticker, Date, Price, Name, Group, Region, Sector
    """
    # Import here to avoid Streamlit dependency issues
    from classification_loader import load_raw_sql_data_cached, apply_classification

    print("📊 Loading commodity price data...")

    # Use GLOBAL cached SQL data (6 hours cache, shared across all pages)
    df_raw = load_raw_sql_data_cached(start_date=None)

    # Apply FRESH classification (60s MongoDB cache)
    df = apply_classification(df_raw)

    # Filter out unclassified items
    df = df.dropna(subset=['Group', 'Region', 'Sector'])

    print(f"✅ Loaded {len(df):,} rows for {df['Group'].nunique()} commodity groups")
    return df


def calculate_group_movements(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate 5D and 10D movements for each commodity group.

    Args:
        df: DataFrame with Date, Group, Price columns

    Returns:
        DataFrame with Group, 5D_Change, 10D_Change, Latest_Date columns
    """
    print("\n📈 Calculating group-level price movements...")

    groups = df['Group'].unique()
    results = []

    for group in groups:
        # Create equal-weighted index for the group
        group_index = create_equal_weight_index(df, group, base_value=100)

        if len(group_index) < 11:  # Need at least 11 days for 10D calculation
            print(f"⚠️  {group}: Insufficient data ({len(group_index)} days)")
            continue

        # Sort by date
        group_index = group_index.sort_values('Date')

        # Get latest values
        latest_value = group_index['Index_Value'].iloc[-1]
        value_5d_ago = group_index['Index_Value'].iloc[-6] if len(group_index) >= 6 else None
        value_10d_ago = group_index['Index_Value'].iloc[-11] if len(group_index) >= 11 else None
        latest_date = group_index['Date'].iloc[-1]

        # Calculate percentage changes
        change_5d = ((latest_value / value_5d_ago) - 1) * 100 if value_5d_ago else None
        change_10d = ((latest_value / value_10d_ago) - 1) * 100 if value_10d_ago else None

        results.append({
            'Group': group,
            '5D_Change': change_5d,
            '10D_Change': change_10d,
            'Latest_Date': latest_date,
            'Latest_Value': latest_value
        })

    results_df = pd.DataFrame(results)
    print(f"✅ Calculated movements for {len(results_df)} groups")

    return results_df


def determine_search_params(row: pd.Series, threshold: float = 3.0) -> Tuple[str, int, str]:
    """
    Determine search direction and lookback days based on price movements.

    Args:
        row: Series with 5D_Change and 10D_Change
        threshold: Percentage threshold for significant movement (default: 3.0)

    Returns:
        Tuple of (direction, lookback_days, reason)
    """
    change_5d = row['5D_Change']
    change_10d = row['10D_Change']

    # Check 5D movement first
    if change_5d is not None:
        if change_5d > threshold:
            return "bullish", 7, f"5D: +{change_5d:.1f}% (>{threshold}%)"
        elif change_5d < -threshold:
            return "bearish", 7, f"5D: {change_5d:.1f}% (<-{threshold}%)"

    # If 5D is within threshold, check 10D
    if change_10d is not None:
        if change_10d > threshold:
            return "bullish", 14, f"5D: {change_5d:.1f}%, 10D: +{change_10d:.1f}% (>{threshold}%)"
        elif change_10d < -threshold:
            return "bearish", 14, f"5D: {change_5d:.1f}%, 10D: {change_10d:.1f}% (<-{threshold}%)"

    # Default: both directions, 14-day lookback
    return "both", 14, f"5D: {change_5d:.1f}%, 10D: {change_10d:.1f}% (within ±{threshold}%)"


def run_intelligent_batch_search(
    df: pd.DataFrame,
    threshold: float = 3.0,
    delay_seconds: int = 5,
    save_to_mongodb: bool = False,
    check_cooldown: bool = True,
    output_dir: str = "output",
    groups_filter: List[str] = None
) -> List[Dict]:
    """
    Run intelligent batch search with automated parameter detection.

    Args:
        df: Commodity price DataFrame
        threshold: Percentage threshold for significant movement
        delay_seconds: Delay between searches
        save_to_mongodb: Whether to save results to MongoDB
        check_cooldown: Whether to check cooldown before searching
        output_dir: Output directory for JSON files
        groups_filter: Optional list of groups to process (None = all groups)

    Returns:
        List of results for each group
    """
    # Calculate movements
    movements = calculate_group_movements(df)

    # Filter groups if specified
    if groups_filter:
        movements = movements[movements['Group'].isin(groups_filter)]
        print(f"\n🎯 Filtered to {len(movements)} specified groups")

    if len(movements) == 0:
        print("\n❌ No groups to process")
        return []

    # Determine search parameters for each group
    movements['Direction'], movements['Lookback_Days'], movements['Reason'] = zip(
        *movements.apply(lambda row: determine_search_params(row, threshold), axis=1)
    )

    # Display search plan
    print("\n" + "="*80)
    print("📋 SEARCH PLAN")
    print("="*80)
    print(f"{'Group':<25} {'5D Change':<12} {'10D Change':<12} {'Direction':<10} {'Lookback':<10} {'Reason':<30}")
    print("-"*80)

    for _, row in movements.iterrows():
        direction_emoji = "📈" if row['Direction'] == "bullish" else "📉" if row['Direction'] == "bearish" else "↔️"
        print(f"{row['Group']:<25} {row['5D_Change']:>10.1f}% {row['10D_Change']:>10.1f}% "
              f"{direction_emoji} {row['Direction']:<9} {row['Lookback_Days']:<10} {row['Reason']:<30}")

    print("="*80)

    # Confirm before proceeding
    if not groups_filter:  # Only ask for confirmation if processing all groups
        response = input(f"\n⚠️  This will run {len(movements)} searches. Continue? (y/n): ")
        if response.lower() != 'y':
            print("❌ Cancelled by user")
            return []

    # Run searches
    results = []

    print("\n" + "="*80)
    print("🚀 RUNNING SEARCHES")
    print("="*80)

    for idx, row in movements.iterrows():
        group = row['Group']
        direction = row['Direction']
        lookback_days = row['Lookback_Days']

        print(f"\n[{idx+1}/{len(movements)}] {group}")
        print(f"  Direction: {direction} | Lookback: {lookback_days} days")
        print(f"  Reason: {row['Reason']}")
        print("-"*80)

        # Check cooldown if enabled
        if check_cooldown and save_to_mongodb:
            can_trigger, cooldown_msg = can_auto_trigger(group)
            if not can_trigger:
                print(f"  ⏳ Skipping: {cooldown_msg}")
                results.append({
                    "group": group,
                    "success": False,
                    "skipped": True,
                    "reason": cooldown_msg,
                    "timestamp": datetime.now().isoformat()
                })
                continue

        try:
            # Run search
            direction_param = None if direction == "both" else direction
            search_result = search_catalysts(
                commodity_group=group,
                lookback_days=int(lookback_days),
                direction=direction_param
            )

            # Save to MongoDB if enabled
            if save_to_mongodb:
                summary = search_result.get("summary", "")
                timeline = search_result.get("timeline", [])

                # Save with direction from price movement analysis
                success = save_catalyst(
                    commodity_group=group,
                    summary=summary,
                    timeline=timeline,
                    search_trigger="auto",
                    direction=direction
                )

                if success:
                    print(f"  ✅ Saved to MongoDB")
                else:
                    print(f"  ⚠️  Search completed but failed to save to MongoDB")
            else:
                print(f"  ✅ Search completed (not saved to MongoDB)")

            results.append({
                "group": group,
                "success": True,
                "direction": direction,
                "lookback_days": lookback_days,
                "5d_change": row['5D_Change'],
                "10d_change": row['10D_Change'],
                "saved_to_mongodb": save_to_mongodb,
                "timestamp": datetime.now().isoformat()
            })

            # Delay before next search
            if idx < len(movements) - 1:
                print(f"\n  ⏳ Waiting {delay_seconds}s before next search...")
                time.sleep(delay_seconds)

        except Exception as e:
            print(f"  ❌ Error: {e}")
            results.append({
                "group": group,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })

    return results


def print_summary(results: List[Dict]):
    """Print summary of batch search results."""
    print("\n" + "="*80)
    print("📊 BATCH SEARCH SUMMARY")
    print("="*80)

    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success") and not r.get("skipped")]
    skipped = [r for r in results if r.get("skipped")]

    print(f"\n✅ Successful: {len(successful)}/{len(results)}")
    for r in successful:
        direction_emoji = "📈" if r['direction'] == "bullish" else "📉" if r['direction'] == "bearish" else "↔️"
        print(f"   • {r['group']:<25} {direction_emoji} {r['direction']:<9} ({r['lookback_days']}D lookback)")

    if skipped:
        print(f"\n⏳ Skipped (cooldown): {len(skipped)}/{len(results)}")
        for r in skipped:
            print(f"   • {r['group']:<25} {r['reason']}")

    if failed:
        print(f"\n❌ Failed: {len(failed)}/{len(results)}")
        for r in failed:
            print(f"   • {r['group']:<25} {r['error']}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Intelligent batch catalyst search with automated parameter detection"
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=3.0,
        help="Percentage threshold for significant movement (default: 3.0)"
    )
    parser.add_argument(
        "--delay",
        "-d",
        type=int,
        default=5,
        help="Delay in seconds between searches (default: 5)"
    )
    parser.add_argument(
        "--save-to-mongodb",
        action="store_true",
        help="Save results to MongoDB (default: False)"
    )
    parser.add_argument(
        "--skip-cooldown-check",
        action="store_true",
        help="Skip cooldown check (search all groups regardless of cooldown)"
    )
    parser.add_argument(
        "--groups",
        "-g",
        type=str,
        help='Comma-separated list of groups to process (e.g., "Iron Ore,HRC,Coal")'
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="output",
        help="Output directory for logs (default: output/)"
    )

    args = parser.parse_args()

    # Parse groups filter if provided
    groups_filter = None
    if args.groups:
        groups_filter = [g.strip() for g in args.groups.split(",")]
        print(f"🎯 Filtering to groups: {', '.join(groups_filter)}")

    print("\n" + "="*80)
    print("🤖 INTELLIGENT BATCH CATALYST SEARCH")
    print("="*80)
    print(f"Threshold: ±{args.threshold}%")
    print(f"Delay: {args.delay}s between searches")
    print(f"Save to MongoDB: {args.save_to_mongodb}")
    print(f"Check cooldown: {not args.skip_cooldown_check}")
    print("="*80)

    # Load data
    df = load_commodity_data()

    # Run batch search
    results = run_intelligent_batch_search(
        df=df,
        threshold=args.threshold,
        delay_seconds=args.delay,
        save_to_mongodb=args.save_to_mongodb,
        check_cooldown=not args.skip_cooldown_check,
        output_dir=args.output,
        groups_filter=groups_filter
    )

    # Print summary
    print_summary(results)

    # Save summary to file
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)

    summary_file = output_dir / f"intelligent_batch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    import json
    with summary_file.open("w") as f:
        json.dump({
            "config": {
                "threshold": args.threshold,
                "delay_seconds": args.delay,
                "save_to_mongodb": args.save_to_mongodb,
                "check_cooldown": not args.skip_cooldown_check,
                "groups_filter": groups_filter,
                "timestamp": datetime.now().isoformat()
            },
            "results": results
        }, f, indent=2)

    print(f"💾 Summary saved to: {summary_file}")


if __name__ == "__main__":
    main()
