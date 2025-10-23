#%%
"""
Query Grok via the xAI SDK to uncover the dominant freight-rate discussion topics on X (Twitter)
over the past seven days, tallying post share by theme.

NOTE: This is the original coworker script.
For commodity catalyst search, use catalyst_search.py instead.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from xai_sdk import Client
from xai_sdk.chat import system, user
from xai_sdk.search import SearchParameters, x_source


def load_api_key_from_env(file_path: str = ".env") -> str:
    """
    Prefer environment variable XAI_API_KEY; fall back to parsing .env if present.
    """
    env = os.getenv("XAI_API_KEY")
    if env:
        return env

    env_path = Path(file_path)
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

    raise ValueError("XAI_API_KEY not found in environment or .env")


def print_json_if_possible(text: str) -> bool:
    """Attempt to pretty print text as JSON, returning True if successful."""
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return False
    print(json.dumps(parsed, indent=2, ensure_ascii=False))
    return True


def main() -> None:
    api_key = load_api_key_from_env()
    client = Client(api_key=api_key, timeout=600)

    now = datetime.now(timezone.utc)
    three_months_ago = now - timedelta(days=7)

    search_config = SearchParameters(
        mode="on",
        from_date=three_months_ago,
        to_date=now,
        sources=[x_source()],
        max_search_results=28,
        return_citations=True,
    )

    chat = client.chat.create(model="grok-4", search_parameters=search_config)

    chat.append(
        system(
            "You are a freight market analyst. "
            "Search X (Twitter) for posts from the past seven days that discuss freight rates across shipping "
            "segments. Cluster the conversations into common topics, estimate their share of total chatter, and "
            "capture representative posts. "
            "Return STRICT JSON with fields: summary (string), observation_window (string ISO8601 range), "
            "topics (array of objects with keys name, description, post_count, percentage_of_discussion, "
            "representative_posts (array of cited_post ids), sentiment, notable_accounts (array of handles), "
            "supporting_quotes (array of strings)), "
            "total_posts (integer), and methodology_notes (array of strings). "
            "Leave fields null when details are not reported; do not fabricate data."
        )
    )
    chat.append(
        user(
            "What are the most common topics about freight rates on X over the last 7 days? "
            "Estimate how many posts or discussions each topic represents and provide the percentage share. "
            "Include representative citations."
        )
    )

    response = chat.sample()

    print("# Grok Response")
    if not print_json_if_possible(response.content):
        print(response.content)

    citations: Optional[list[str]] = getattr(response, "citations", None)
    if citations:
        print("\n# Citations")
        for citation in citations:
            print(f"- {citation}")

    usage = getattr(response, "usage", None)
    if usage and getattr(usage, "num_sources_used", None) is not None:
        print(f"\n# Sources Used: {usage.num_sources_used}")


if __name__ == "__main__":
    main()

# %%
