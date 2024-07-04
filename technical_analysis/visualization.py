import matplotlib.pyplot as plt

def plot_stock_with_demark(data, ticker):
    plt.figure(figsize=(14, 7))
    plt.plot(data.index, data['Close'], label='Close Price', color='blue')
    
    setup_nines = data['Setup'] == 9
    if setup_nines.any():
        plt.scatter(data.index[setup_nines], data['Close'][setup_nines], color='green', label='Setup 9', marker='^', s=100)
    
    countdown_thirteens = data['Countdown'] == 13
    if countdown_thirteens.any():
        plt.scatter(data.index[countdown_thirteens], data['Close'][countdown_thirteens], color='red', label='Countdown 13', marker='v', s=100)

    plt.title(f'{ticker} Stock Price with DeMark Indicator')
    plt.xlabel('Date')
    plt.ylabel('Price')
    plt.legend()
    plt.grid(True)
    st.pyplot(plt.gcf())  # Use Streamlit to display the plot

# Example usage in app.py
import streamlit as st
import pandas as pd  # Ensure pandas is imported
from data_retrieval import fetch_stock_data
from technical_analysis.demark import calculate_td_sequential

def main():
    st.title('Stock Technical Analysis with DeMark Indicator')

    ticker = st.text_input('Enter stock ticker:', 'AAPL')
    start_date = st.date_input('Start date', pd.to_datetime('2022-01-01'))
    end_date = st.date_input('End date', pd.to_datetime('today'))

    if st.button('Analyze'):
        data = fetch_stock_data(ticker, start_date, end_date)
        if not data.empty:
            data = calculate_td_sequential(data)
            st.subheader(f'{ticker} Stock Price Data')
            st.write(data.tail())
            plot_stock_with_demark(data, ticker)
        else:
            st.write(f"No data found for {ticker}")

if __name__ == "__main__":
    main()