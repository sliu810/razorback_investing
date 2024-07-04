import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objs as go
import streamlit as st

def get_date_from_period(period):
    end_date = datetime.now()
    
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
    
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

def get_stock_performance(symbol, start_date, end_date=None):
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    stock = yf.Ticker(symbol)
    hist = stock.history(start=start_date, end=end_date)
    
    if hist.empty:
        st.warning(f"No data available for {symbol} in the specified period.")
        return None
    
    start_date_in_data = hist.index[0].strftime('%Y-%m-%d')
    end_date_in_data = hist.index[-1].strftime('%Y-%m-%d')
    
    if start_date > start_date_in_data or end_date < end_date_in_data:
        st.warning(f"Data for {symbol} is only available from {start_date_in_data} to {end_date_in_data}. Please adjust your date range.")
        return None
    
    start_price = round(hist['Close'].iloc[0], 1)
    end_price = round(hist['Close'].iloc[-1], 1)
    percent_change = round(((end_price - start_price) / start_price) * 100, 1)

    return {
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "start_price": start_price,
        "end_price": end_price,
        "percent_change": percent_change,
        "history": hist
    }

def print_stock_performance(results):
    if not results:
        st.write("No data available for the specified period.")
        return

    df = pd.DataFrame(results)
    df['percent_change'] = df['percent_change'].apply(lambda x: f"{x:.1f}%")
    df = df.sort_values(by='percent_change', ascending=False)
    st.write(df[['symbol', 'start_date', 'end_date', 'start_price', 'end_price', 'percent_change']])

def plot_stock_performance_interactive(results, price_type='Close', normalize=True):
    if not results:
        st.write("No data available to plot.")
        return

    fig = go.Figure()
    
    for result in results:
        hist = result['history']
        st.write(f"Plotting {result['symbol']} with {len(hist)} data points.")
        if normalize:
            hist = hist.copy()
            hist[price_type] = hist[price_type] / hist[price_type].iloc[0]
        fig.add_trace(go.Scatter(x=hist.index, y=hist[price_type], mode='lines', name=f'{result["symbol"]} ({price_type} Price)'))
    
    fig.update_layout(
        title=f"Stock Performance from {results[0]['start_date']} to {results[0]['end_date']}",
        xaxis_title='Date',
        yaxis_title=f'{"Normalized " if normalize else ""}{price_type} Price',
        hovermode='x unified'
    )
    
    st.plotly_chart(fig)

def get_and_print_stock_performance(symbols, period=None, start_date=None, end_date=None, normalize=True):
    if isinstance(symbols, str):
        symbols = [symbols]

    if period and not start_date:
        start_date, end_date = get_date_from_period(period)
    elif start_date and not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    results = []
    for symbol in symbols:
        result = get_stock_performance(symbol, start_date, end_date)
        if result:
            results.append(result)

    print_stock_performance(results)
    plot_stock_performance_interactive(results, price_type='Close', normalize=normalize)