# data_retrieval.py
import yfinance as yf
import pandas as pd
from datetime import datetime

def fetch_stock_data(ticker, start_date=None, end_date=None):
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    data = yf.download(ticker, start=start_date, end=end_date)
    return data

# Example usage:
# df = fetch_stock_data("AAPL", "2022-01-01", "2023-01-01")
# print(df.head())