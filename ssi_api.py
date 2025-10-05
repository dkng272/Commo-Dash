"""
SSI/TCBS API functions for fetching stock price data
Simplified version for Commo Dashboard
"""

import requests
import pandas as pd
from datetime import datetime


def fetch_historical_price(ticker: str, start_date: str = None) -> pd.DataFrame:
    """
    Fetch stock historical price and volume data from TCBS API

    Parameters:
    - ticker: Stock ticker symbol (e.g., 'HPG', 'VNM')
    - start_date: Start date in 'YYYY-MM-DD' format (optional)

    Returns:
    - DataFrame with columns: tradingDate, open, high, low, close, volume
    """

    # TCBS API endpoint for historical data
    url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/bars-long-term"

    # Convert start_date string to timestamp if provided
    if start_date:
        start_timestamp = str(int(datetime.strptime(start_date, "%Y-%m-%d").timestamp()))
    else:
        # Default to 1 year ago
        start_timestamp = str(int((datetime.now().timestamp() - 365*24*60*60)))

    # Parameters for stock data
    params = {
        "ticker": ticker,
        "type": "stock",
        "resolution": "D",  # Daily data
        "from": start_timestamp,
        "to": str(int(datetime.now().timestamp()))
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }

    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        if 'data' in data:
            # Convert to DataFrame
            df = pd.DataFrame(data['data'])

            # Convert timestamp to datetime
            if 'tradingDate' in df.columns:
                # Check if tradingDate is already in ISO format
                if df['tradingDate'].dtype == 'object' and df['tradingDate'].str.contains('T').any():
                    df['tradingDate'] = pd.to_datetime(df['tradingDate'])
                else:
                    df['tradingDate'] = pd.to_datetime(df['tradingDate'], unit='ms')

            # Select relevant columns
            columns_to_keep = ['tradingDate', 'open', 'high', 'low', 'close', 'volume']
            df = df[[col for col in columns_to_keep if col in df.columns]]

            # Rename for consistency
            df = df.rename(columns={'tradingDate': 'Date', 'close': 'Price'})

            return df
        else:
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for {ticker}: {e}")
        return None
