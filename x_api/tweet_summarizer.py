#%%
import json
import openai
from pathlib import Path

#%%
# ==================== CONFIGURATION ====================
OPENAI_API_KEY = "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"  # Fill in your OpenAI API key
MODEL = "gpt-5-mini"  # GPT-5 model

#%%
def load_tweets_from_json(filepath):
    """Load tweets from JSON file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        tweets = json.load(f)
    return tweets

def create_summary_prompt(tweets):
    """Create prompt for ChatGPT to summarize tweets"""
    tweets_text = "\n\n".join([
        f"Tweet {i+1} ({tweet['created_at']}):\n{tweet['text']}"
        for i, tweet in enumerate(tweets)
    ])

    prompt = f"""Summarize the following tweets. Extract revelent news and information on commodities market, mostly pertaining to metals and steel

Tweets:
{tweets_text}"""

    return prompt

def summarize_tweets(tweets, api_key, model=MODEL):
    """Send tweets to ChatGPT and get summary"""
    client = openai.OpenAI(api_key=api_key)

    prompt = create_summary_prompt(tweets)

    response = client.responses.create(
        model=model,
        input=prompt,
        temperature=1.0
    )

    return response.output_text

#%%
# ==================== MAIN EXECUTION ====================
if __name__ == "__main__":
    # Find the most recent tweets JSON file
    json_files = sorted(Path('.').glob('tweets_*.json'), reverse=True)

    if not json_files:
        print("ERROR: No tweets JSON file found")
    elif not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY is not set. Please fill in your API key.")
    else:
        tweet_file = json_files[0]
        print(f"Loading tweets from: {tweet_file}")

        tweets = load_tweets_from_json(tweet_file)
        print(f"Found {len(tweets)} tweets\n")

        print("Generating summary with ChatGPT...")
        summary = summarize_tweets(tweets, OPENAI_API_KEY)

        print("\n" + "="*50)
        print("TWEET SUMMARY")
        print("="*50 + "\n")
        print(summary)

        # Save summary to file
        summary_file = tweet_file.stem + "_summary.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(summary)
        print(f"\n\nSummary saved to: {summary_file}")
