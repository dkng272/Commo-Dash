"""
Batch Catalyst Search

Run catalyst searches for multiple commodity groups at once.
Useful for weekly market scans or post-market analysis.

Usage:
    python batch_search.py --config batch_config.json
    python batch_search.py --commodities "Iron Ore,HRC,Coal" --days 7
"""

import json
import time
import argparse
from pathlib import Path
from datetime import datetime

from catalyst_search import search_catalysts, save_to_json


def load_batch_config(config_path: str) -> dict:
    """Load batch search configuration from JSON file."""
    with open(config_path, "r") as f:
        return json.load(f)


def run_batch_search(
    commodities: list[str],
    lookback_days: int = 7,
    direction: str = None,
    output_dir: str = "output",
    delay_seconds: int = 5
) -> list[dict]:
    """
    Run catalyst searches for multiple commodities.

    Args:
        commodities: List of commodity group names
        lookback_days: Number of days to search back
        direction: Optional price direction filter
        output_dir: Output directory for JSON files
        delay_seconds: Delay between searches to avoid rate limits

    Returns:
        list[dict]: List of results for each commodity
    """
    results = []

    print(f"\n{'='*60}")
    print(f"Batch Catalyst Search")
    print(f"{'='*60}")
    print(f"Commodities: {len(commodities)}")
    print(f"Lookback: {lookback_days} days")
    print(f"Direction: {direction or 'both'}")
    print(f"Delay: {delay_seconds}s between searches")
    print(f"{'='*60}\n")

    for idx, commodity in enumerate(commodities, 1):
        print(f"\n[{idx}/{len(commodities)}] Processing: {commodity}")
        print("-" * 60)

        try:
            # Run search
            result = search_catalysts(
                commodity_group=commodity,
                lookback_days=lookback_days,
                direction=direction
            )

            # Save to file
            output_file = save_to_json(result, output_dir=output_dir)
            print(f"✅ Saved to: {output_file}")

            # Add to results
            results.append({
                "commodity": commodity,
                "success": True,
                "output_file": output_file,
                "timestamp": datetime.now().isoformat()
            })

            # Delay before next search (except for last one)
            if idx < len(commodities):
                print(f"\n⏳ Waiting {delay_seconds}s before next search...")
                time.sleep(delay_seconds)

        except Exception as e:
            print(f"❌ Error processing {commodity}: {e}")
            results.append({
                "commodity": commodity,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })

    return results


def print_summary(results: list[dict]):
    """Print summary of batch search results."""
    print("\n" + "="*60)
    print("Batch Search Summary")
    print("="*60)

    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    print(f"\n✅ Successful: {len(successful)}/{len(results)}")
    for r in successful:
        print(f"   • {r['commodity']}")

    if failed:
        print(f"\n❌ Failed: {len(failed)}/{len(results)}")
        for r in failed:
            print(f"   • {r['commodity']}: {r['error']}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Run batch catalyst searches for multiple commodities"
    )
    parser.add_argument(
        "--commodities",
        "-c",
        type=str,
        help='Comma-separated list of commodities (e.g., "Iron Ore,HRC,Coal")'
    )
    parser.add_argument(
        "--days",
        "-d",
        type=int,
        default=7,
        help="Number of days to search back (default: 7)"
    )
    parser.add_argument(
        "--direction",
        choices=["bullish", "bearish", "both"],
        default="both",
        help="Price direction filter (default: both)"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="output",
        help="Output directory for JSON files (default: output/)"
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=5,
        help="Delay in seconds between searches (default: 5)"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to JSON config file with batch search parameters"
    )

    args = parser.parse_args()

    # Load from config file if provided
    if args.config:
        config = load_batch_config(args.config)
        commodities = config.get("commodities", [])
        days = config.get("lookback_days", 7)
        direction = config.get("direction", "both")
        delay = config.get("delay_seconds", 5)
        output_dir = config.get("output_dir", "output")
    else:
        if not args.commodities:
            print("❌ Error: --commodities is required (or provide --config)")
            parser.print_help()
            return

        commodities = [c.strip() for c in args.commodities.split(",")]
        days = args.days
        direction = args.direction if args.direction != "both" else None
        delay = args.delay
        output_dir = args.output

    # Run batch search
    results = run_batch_search(
        commodities=commodities,
        lookback_days=days,
        direction=direction,
        output_dir=output_dir,
        delay_seconds=delay
    )

    # Print summary
    print_summary(results)

    # Save batch summary
    summary_file = Path(output_dir) / f"batch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with summary_file.open("w") as f:
        json.dump({
            "batch_config": {
                "commodities": commodities,
                "lookback_days": days,
                "direction_filter": direction,
                "timestamp": datetime.now().isoformat()
            },
            "results": results
        }, f, indent=2)

    print(f"📊 Batch summary saved to: {summary_file}")


if __name__ == "__main__":
    main()
