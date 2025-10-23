"""
Commodity Catalyst Search using xAI Grok

Searches X (Twitter) for catalysts driving significant commodity price movements.
Outputs results to console.

Usage:
    python catalyst_search.py --commodity "Iron Ore" --days 7 --direction bullish
    python catalyst_search.py --commodity "Tungsten" --days 5
    python catalyst_search.py --config search_config.json
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
import argparse

from xai_sdk import Client
from xai_sdk.chat import system, user
from xai_sdk.search import SearchParameters, x_source


def load_api_key_from_env(file_path: str = ".env") -> str:
    """
    Load XAI API key from multiple sources (priority order):
    1. Streamlit secrets (for deployed app)
    2. Environment variable XAI_API_KEY
    3. .env file (for local development)
    """
    # Try Streamlit secrets first (for deployed app)
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and "XAI_API_KEY" in st.secrets:
            return st.secrets["XAI_API_KEY"]
    except (ImportError, FileNotFoundError, KeyError):
        pass

    # Try environment variable
    env = os.getenv("XAI_API_KEY")
    if env:
        return env

    # Try .env file (local development only)
    # Look in the same directory as this script
    script_dir = Path(__file__).parent
    env_path = script_dir / file_path

    if env_path.is_file():
        with env_path.open("r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.startswith("export "):
                    line = line[len("export ") :].strip()
                key, value = line.split("=", 1)
                if key.strip() == "XAI_API_KEY":
                    return value.strip().strip('"').strip("'")

    raise ValueError("XAI_API_KEY not found in Streamlit secrets, environment, or .env")


def parse_json_response(text: str) -> tuple[bool, Optional[dict]]:
    """Parse JSON response."""
    try:
        return True, json.loads(text.strip())
    except (json.JSONDecodeError, TypeError):
        return False, None


def search_catalysts(
    commodity_group: str,
    lookback_days: int = 7,
    direction: Optional[str] = None,
    api_key: Optional[str] = None
) -> dict:
    """
    Search X for catalysts affecting a specific commodity group.

    Args:
        commodity_group: Name of commodity (e.g., "Iron Ore", "Tungsten", "HRC")
        lookback_days: Number of days to search back (default: 7)
        direction: Optional price direction ("bullish", "bearish", or None for both)
        api_key: xAI API key (if not provided, loads from environment)

    Returns:
        dict: Structured catalyst data with timeline
    """
    if api_key is None:
        api_key = load_api_key_from_env()

    client = Client(api_key=api_key, timeout=600)

    now = datetime.now(timezone.utc)
    search_start = now - timedelta(days=lookback_days)

    search_config = SearchParameters(
        mode="on",
        from_date=search_start,
        to_date=now,
        sources=[x_source()],
        max_search_results=28,
        return_citations=True,
    )

    chat = client.chat.create(model="grok-2-latest", search_parameters=search_config)

    # System prompt - concise but with key details
    chat.append(
        system(
            "You are a commodity analyst. Find the specific events that moved commodity prices. "
            "\n"
            "Return STRICT JSON (no markdown):\n"
            "{\n"
            '  "summary": "1-2 sentences max",\n'
            '  "timeline": [\n'
            '    {"date": "YYYY-MM-DD", "event": "2-3 sentences with key details"},\n'
            '    {"date": "YYYY-MM-DD", "event": "2-3 sentences with key details"}\n'
            "  ]\n"
            "}\n"
            "\n"
            "STRICT Rules:\n"
            "- Summary: MAXIMUM 2 sentences\n"
            "- Each event: 2-3 sentences with specifics (what, who, why, impact)\n"
            "- Include concrete details: quantities, prices, countries, companies, policy names\n"
            "- Timeline: only events with specific dates\n"
            "- Sort newest first\n"
            "- NO markdown code blocks\n"
        )
    )

    # User prompt - simple and direct (inspired by successful Vietnamese prompt)
    direction_text = ""
    if direction:
        direction_text = f" ({direction} movement)" if direction in ["bullish", "bearish"] else ""

    chat.append(
        user(
            f"Find the reasons why {commodity_group} prices moved significantly{direction_text} "
            f"over the past {lookback_days} days. "
            f"\n\n"
            f"For each catalyst, identify the SPECIFIC DATE when it happened. "
            f"What was the main driver? What specific events occurred on which dates?"
        )
    )

    print(f"🔍 Searching X for {commodity_group} catalysts ({lookback_days} days)...")
    response = chat.sample()

    # Parse JSON response
    success, parsed_data = parse_json_response(response.content)

    if success and parsed_data:
        # Add metadata
        parsed_data["_meta"] = {
            "search_timestamp": now.isoformat(),
            "commodity_group": commodity_group
        }

        return parsed_data
    else:
        # Fallback if not JSON
        print("⚠️  Warning: Response was not valid JSON. Returning raw text.")
        return {
            "_meta": {
                "search_timestamp": now.isoformat(),
                "commodity_group": commodity_group,
                "parse_error": True
            },
            "raw_response": response.content
        }




def main():
    parser = argparse.ArgumentParser(
        description="Search X (Twitter) for commodity price catalysts using Grok"
    )
    parser.add_argument(
        "--commodity",
        "-c",
        type=str,
        help='Commodity group name (e.g., "Iron Ore", "Tungsten", "HRC")'
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
        "--config",
        type=str,
        help="Path to JSON config file with search parameters"
    )

    args = parser.parse_args()

    # Load from config file if provided
    if args.config:
        with open(args.config, "r") as f:
            config = json.load(f)
        commodity = config.get("commodity_group")
        days = config.get("lookback_days", 7)
        direction = config.get("direction", "both")
    else:
        commodity = args.commodity
        days = args.days
        direction = args.direction if args.direction != "both" else None

    if not commodity:
        print("❌ Error: --commodity is required (or provide --config)")
        parser.print_help()
        return

    print(f"\n{'='*60}")
    print(f"Commodity Catalyst Search")
    print(f"{'='*60}")
    print(f"Commodity: {commodity}")
    print(f"Lookback: {days} days")
    print(f"Direction: {direction or 'both'}")
    print(f"{'='*60}\n")

    try:
        # Run search
        results = search_catalysts(
            commodity_group=commodity,
            lookback_days=days,
            direction=direction
        )

        # Display summary
        print("\n" + "="*60)
        print("✅ Search Complete")
        print("="*60)

        if "_meta" in results and results["_meta"].get("parse_error"):
            print("⚠️  Warning: Could not parse as JSON. Check output file for raw response.")
        else:
            # Display summary
            summary = results.get("summary", "No summary available")
            print(f"\nSummary:\n{summary}\n")

            # Display timeline
            timeline = results.get("timeline", [])
            if timeline:
                print(f"Timeline ({len(timeline)} events):")
                for entry in timeline[:10]:  # Show up to 10 events
                    date = entry.get("date", "Unknown")
                    event = entry.get("event", "No description")
                    print(f"  • {date}: {event}")

                if len(timeline) > 10:
                    print(f"  ... and {len(timeline) - 10} more events")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
