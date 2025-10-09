#%%
import requests
import pandas as pd
from datetime import datetime
import json
import time

#%%
# ==================== CONFIGURATION ====================
# Fill in your credentials here
API_KEY = "Pr89gLihPAMBJpbUT7PJFT2UB"  # Your X API Key
API_SECRET_KEY = "oGgGykbXPPuVquCLjx7U5aYBRfiVZZ2dQe1UoUKEJdf1giGxZv"  # Your X API Secret Key
BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAO2P4gEAAAAAs3E3CHPPj5ogLkMrdJl5aj0TqYE%3DQy8HK0ILl9mszBfPnCO0S3m920GgekRTKGhOoRCWBqNJF1cS7c"  # Your X Bearer Token

# User IDs to track (fill in the user IDs you want to monitor)
USER_IDS = [
    "542400049",  # Example user ID
    # "87654321",  # Add more user IDs here
]

# Tweet parameters
MAX_RESULTS = 15  # Number of tweets to fetch per user (max 100)
TWEET_FIELDS = "created_at,text"  # Only get timestamp and text

# Rate limiting
RETRY_DELAY = 60  # Seconds to wait when rate limited (default 60s)
MAX_RETRIES = 3  # Maximum number of retry attempts

#%%
def fetch_user_tweets(user_id, bearer_token, max_results=None):
    """
    Fetch recent tweets from a specific user using X API v2.

    Parameters:
    - user_id: X user ID (string)
    - bearer_token: Your X API Bearer Token
    - max_results: Number of tweets to fetch (uses global MAX_RESULTS if None, min 5, max 100)

    Returns:
    - List of tweet dictionaries
    """
    if max_results is None:
        max_results = MAX_RESULTS

    url = f"https://api.twitter.com/2/users/{user_id}/tweets"

    headers = {
        "Authorization": f"Bearer {bearer_token}"
    }

    # Option 1: Exclude retweets to only get original tweets (full text guaranteed)
    # Option 2: Include retweets but they will be truncated (starts with "RT @username:")
    # Currently using Option 1 - change exclude value to include retweets
    params = {
        "max_results": max_results,
        "tweet.fields": TWEET_FIELDS,
        "exclude": "retweets,replies"  # Remove "retweets," to include retweets (will be truncated)
    }

    try:
        response = requests.get(url, headers=headers, params=params)

        # Check rate limit headers
        rate_limit = response.headers.get('x-rate-limit-limit', 'N/A')
        rate_remaining = response.headers.get('x-rate-limit-remaining', 'N/A')
        rate_reset = response.headers.get('x-rate-limit-reset', 'N/A')

        if rate_reset != 'N/A':
            reset_time = datetime.fromtimestamp(int(rate_reset))
            print(f"📊 Rate Limit Info: {rate_remaining}/{rate_limit} requests remaining")
            print(f"   Reset time: {reset_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Handle rate limiting
        if response.status_code == 429:
            print("\n⚠️  RATE LIMIT HIT!")
            print("This likely means you're on the FREE tier which allows only 1 request per 15 minutes.")
            print("Solutions:")
            print("1. Wait 15 minutes between requests (Free tier)")
            print("2. Upgrade to Basic ($100/month) for 10 requests per 15 min")
            print("3. Upgrade to Pro ($5000/month) for 1500 requests per 15 min")

            if rate_reset != 'N/A':
                wait_seconds = max(int(rate_reset) - int(time.time()), 0) + 5
                wait_minutes = wait_seconds / 60
                print(f"\n⏰ Rate limit resets in {wait_minutes:.1f} minutes")
                print(f"Would need to wait until {reset_time.strftime('%H:%M:%S')}")

            return []

        # Print other errors
        if response.status_code != 200:
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")

        response.raise_for_status()

        data = response.json()

        if 'data' in data:
            # Detect tier based on rate limit
            if rate_limit == '1':
                print("📝 Note: You appear to be on the FREE tier (1 request/15 min limit)")
            elif rate_limit == '10':
                print("📝 Note: You appear to be on the BASIC tier (10 requests/15 min limit)")

            return data['data']
        else:
            print(f"No tweets found for user {user_id}")
            return []

    except requests.exceptions.RequestException as e:
        print(f"Error fetching tweets for user {user_id}: {e}")
        return []

def fetch_all_users_tweets(user_ids, bearer_token, max_results=None):
    """
    Fetch tweets from multiple users.

    Parameters:
    - user_ids: List of user IDs
    - bearer_token: Your X API Bearer Token
    - max_results: Number of tweets per user (uses global MAX_RESULTS if None)

    Returns:
    - DataFrame with all tweets
    """
    if max_results is None:
        max_results = MAX_RESULTS

    all_tweets = []

    for user_id in user_ids:
        print(f"Fetching tweets for user {user_id}...")
        tweets = fetch_user_tweets(user_id, bearer_token, max_results)

        for tweet in tweets:
            all_tweets.append({
                'user_id': user_id,
                'tweet_id': tweet['id'],
                'created_at': tweet['created_at'],
                'text': tweet['text']
            })

    df = pd.DataFrame(all_tweets)

    if not df.empty:
        df['created_at'] = pd.to_datetime(df['created_at'])
        df = df.sort_values('created_at', ascending=False)

    return df

def save_to_csv(df, filename=None):
    """
    Save tweets to CSV file.

    Parameters:
    - df: DataFrame with tweets
    - filename: Output filename (default: tweets_YYYYMMDD_HHMMSS.csv)
    """
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'tweets_{timestamp}.csv'

    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"Saved {len(df)} tweets to {filename}")


def save_to_json(df, filename=None):
    """
    Save tweets to JSON file.

    Parameters:
    - df: DataFrame with tweets
    - filename: Output filename (default: tweets_YYYYMMDD_HHMMSS.json)
    """
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'tweets_{timestamp}.json'

    df.to_json(filename, orient='records', date_format='iso', indent=2)
    print(f"Saved {len(df)} tweets to {filename}")

#%%
# ==================== MAIN EXECUTION ====================
if __name__ == "__main__":
    # Validate configuration
    if not BEARER_TOKEN:
        print("ERROR: BEARER_TOKEN is not set. Please fill in your X API Bearer Token.")
    elif not USER_IDS:
        print("ERROR: USER_IDS list is empty. Please add user IDs to track.")
    else:
        print(f"Fetching tweets from {len(USER_IDS)} users...")
        print(f"Max results per user: {MAX_RESULTS}")
        print("-" * 50)

        # Fetch tweets
        tweets_df = fetch_all_users_tweets(USER_IDS, BEARER_TOKEN)

        if not tweets_df.empty:
            print("-" * 50)
            print(f"Total tweets fetched: {len(tweets_df)}")
            print("\nSample tweets:")
            print(tweets_df[['user_id', 'created_at', 'text']].head())

            # Save to files
            save_to_csv(tweets_df)
            save_to_json(tweets_df)
        else:
            print("No tweets fetched. Please check your configuration.")

#%%
# ==================== HOW TO FIND USER IDS ====================
# Don't waste API calls on username lookups!
# Use free online tools instead:
#
# 1. TweeterID.com - https://tweeterid.com/
# 2. CodeOfaNinja - https://www.codeofaninja.com/tools/find-twitter-id/
#
# Common User IDs:
# - Elon Musk: 44196397
# - Barack Obama: 813286
# - Bill Gates: 50393960
# - CNN Breaking News: 15492359
