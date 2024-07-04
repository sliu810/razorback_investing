import requests
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import streamlit as st
import os

def fetch_components_slickcharts(index):
    base_url = "https://www.slickcharts.com/"
    index_map = {
        'QQQ': 'nasdaq100',
        'SPX': 'sp500',
        'DOW': 'dowjones',
        'IWM': 'russell2000'
    }
    if index.upper() not in index_map:
        raise ValueError("Index must be either 'QQQ', 'SPX', 'DOW', or 'IWM'")
    
    url = f"{base_url}{index_map[index.upper()]}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    table = soup.find('table')
    
    data = []
    headers = []
    
    for i, row in enumerate(table.find_all('tr')):
        cols = [ele.text.strip() for ele in row.find_all('td')]
        if i == 0:
            headers = [ele.text.strip() for ele in row.find_all('th')]
        else:
            if len(cols) > 1:  # Ensure there is data in the row
                data.append(cols)
    
    df = pd.DataFrame(data, columns=headers)
    return df

def fetch_industry_info(symbol):
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        industry = info.get("industry", "N/A")
        return industry
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return "N/A"

def append_industry_info(df):
    industries = []
    for _, row in df.iterrows():
        industry = fetch_industry_info(row['Symbol'])
        industries.append(industry)
    
    df['Industry'] = industries
    return df

def load_dataframe_from_file(filename):
    return pd.read_excel(filename)

def save_dataframe_to_file(df, filename):
    df.to_excel(filename, index=False)
    print(f"Data saved to {filename}")

def get_dataframe(index):
    filename = f'df_{index.lower()}.xlsx'
    if os.path.exists(filename):
        df = load_dataframe_from_file(filename)
        print(f"Data loaded from {filename}")
    else:
        df = fetch_components_slickcharts(index)
        df = append_industry_info(df)
        save_dataframe_to_file(df, filename)
    return df

def fetch_all_performance_data(df, start_date, end_date):
    performance_data = []
    symbols = df['Symbol'].tolist()
    
    try:
        stock_data = yf.download(symbols, start=start_date, end=end_date, group_by='ticker', progress=False)
    except Exception as e:
        st.error(f"Error fetching stock data: {e}")
        return performance_data
    
    for symbol in symbols:
        try:
            hist = stock_data[symbol]
            if hist.empty:
                continue
            start_price = hist['Close'].iloc[0]
            end_price = hist['Close'].iloc[-1]
            percent_change = (end_price - start_price) / start_price * 100
            industry = df.loc[df['Symbol'] == symbol, 'Industry'].values[0]
            performance_data.append((symbol, percent_change, industry))
        except Exception as e:
            print(f"Error processing data for {symbol}: {e}")
            continue

    performance_data.sort(key=lambda x: x[1], reverse=True)
    return performance_data

def display_index_performance(df, period, top_n, bottom_n, start_date, end_date):
    if end_date is None:
        end_date = datetime.now()
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
    else:
        if period == 'ytd':
            start_date = datetime(end_date.year, 1, 1)
        else:
            delta = {
                '1d': 1,
                '5d': 5,
                '1m': 30,
                '6m': 182,
                '1y': 365,
                '2y': 365*2,
                '3y': 365*3,
                '5y': 365*5,
                '10y': 365*10,
                '20y': 365*20
            }[period]
            start_date = end_date - timedelta(days=delta)
            print("Start and end dates:", start_date, end_date)
    
    performance_data = fetch_all_performance_data(df, start_date, end_date)
    
    # Top performing stocks
    st.write(f"Top {top_n} Stocks:")
    top_performers = performance_data[:top_n]
    top_df = pd.DataFrame(top_performers, columns=["Symbol", "Percent Change", "Industry"])
    top_df["Percent Change"] = top_df["Percent Change"].apply(lambda x: f"{x:.1f}%")
    st.dataframe(top_df.style.applymap(lambda x: 'color: green' if isinstance(x, str) and x.endswith('%') else '', subset=['Percent Change']))

    # Bottom performing stocks
    st.write(f"\nBottom {bottom_n} Stocks:")
    bottom_performers = performance_data[-bottom_n:]
    bottom_df = pd.DataFrame(bottom_performers, columns=["Symbol", "Percent Change", "Industry"])
    bottom_df["Percent Change"] = bottom_df["Percent Change"].apply(lambda x: f"{x:.1f}%")
    st.dataframe(bottom_df.style.applymap(lambda x: 'color: red' if isinstance(x, str) and x.endswith('%') else '', subset=['Percent Change']))

    # Display number of companies per industry in top and bottom lists
    top_industries = pd.Series([industry for _, _, industry in performance_data[:top_n]]).value_counts()
    bottom_industries = pd.Series([industry for _, _, industry in performance_data[-bottom_n:]]).value_counts()
    
    st.write("Top Industries:")
    st.write(top_industries)
    
    st.write("Bottom Industries:")
    st.write(bottom_industries)

def get_and_display_index_performance(index, period, top_n, bottom_n, start_date=None, end_date=None):
    df = get_dataframe(index)
    display_index_performance(df, period, top_n, bottom_n, start_date, end_date)