# app.py
import streamlit as st
import yfinance as yf
from datetime import datetime
from demark import demark_setup, demark_countdown
from rsi import calculate_rsi
import matplotlib.pyplot as plt

def fetch_stock_data(ticker, start_date, end_date):
    return yf.download(ticker, start=start_date, end=end_date)

def plot_stock_with_indicators(data, ticker, indicators):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    
    # Plot the stock price
    ax1.plot(data.index, data['Close'], label='Close Price')

    if 'DeMark' in indicators:
        data = demark_setup(data)
        data = demark_countdown(data)

        bullish_setup = data[data['Setup'] == 9]
        bearish_setup = data[data['Setup'] == -9]
        bullish_countdown = data[data['Countdown'] == 13]
        bearish_countdown = data[data['Countdown'] == -13]

        ax1.scatter(bullish_setup.index, bullish_setup['Close'], color='green', marker='^', s=100, label='Bullish Setup 9')
        ax1.scatter(bearish_setup.index, bearish_setup['Close'], color='red', marker='v', s=100, label='Bearish Setup 9')
        ax1.scatter(bullish_countdown.index, bullish_countdown['Close'], color='blue', marker='^', s=100, label='Bullish Countdown 13')
        ax1.scatter(bearish_countdown.index, bearish_countdown['Close'], color='orange', marker='v', s=100, label='Bearish Countdown 13')

    ax1.set_title(f"{ticker} Price and Indicators")
    ax1.legend(loc='upper left')

    # Plot RSI
    if 'RSI' in indicators:
        data = calculate_rsi(data)
        ax2.plot(data.index, data['RSI'], label='RSI', color='purple')
        ax2.axhline(70, color='red', linestyle='--', alpha=0.5)
        ax2.axhline(30, color='green', linestyle='--', alpha=0.5)
        ax2.set_title('Relative Strength Index (RSI)')
        ax2.legend(loc='upper left')

    plt.tight_layout()
    st.pyplot(fig)

def main():
    st.title("Stock Technical Analysis")

    ticker = st.text_input('Enter Stock Ticker', 'AAPL')
    start_date = st.date_input('Start date', datetime(2022, 1, 1))
    end_date = st.date_input('End date', datetime.today())
    indicators = ['DeMark', 'RSI']
    selected_indicators = st.multiselect('Select Indicators', indicators, default=indicators)

    if st.button('Analyze'):
        data = fetch_stock_data(ticker, start_date, end_date)
        plot_stock_with_indicators(data, ticker, selected_indicators)

if __name__ == "__main__":
    main()