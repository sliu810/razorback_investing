import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objs as go
import streamlit as st
from collections import Counter

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

def fetch_components_slickcharts(index):
    base_url = "https://www.slickcharts.com/"
    index_map = {
        'QQQ': 'nasdaq100',
        'SPX': 'sp500',
        'DOW': 'dowjones'
    }
    if index.upper() not in index_map:
        raise ValueError("Index must be either 'QQQ', 'SPX', or 'DOW'")
    
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
        print(f"Fetched industry for {symbol}: {industry}")
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

def display_top_bottom_stocks(df, period, top_n, bottom_n, start_date=None, end_date=None):
    end_date = datetime.now().strftime('%Y-%m-%d') if end_date is None else end_date
    
    if start_date:
        start_date = start_date
    else:
        if period == 'ytd':
            start_date = datetime.now().replace(month=1, day=1).strftime('%Y-%m-%d')
        else:
            start_date, _ = get_date_from_period(period)
    
    performance_data = fetch_all_performance_data(df, start_date, end_date)
    
    print(f"Top {top_n} Stocks:")
    for symbol, company, performance, industry in performance_data[:top_n]:
        print(f"{symbol} ({company} - {industry}): {performance*100:.1f}%")
    
    print(f"\nBottom {bottom_n} Stocks:")
    for symbol, company, performance, industry in performance_data[-bottom_n:]:
        print(f"{symbol} ({company} - {industry}): {performance*100:.1f}%")
    
    # Display industry stats
    industry_counter_top = Counter([industry for _, _, _, industry in performance_data[:top_n]])
    industry_counter_bottom = Counter([industry for _, _, _, industry in performance_data[-bottom_n:]])

    print("\nIndustry Distribution in Top Performers:")
    for industry, count in industry_counter_top.items():
        print(f"{industry}: {count} companies")

    print("\nIndustry Distribution in Bottom Performers:")
    for industry, count in industry_counter_bottom.items():
        print(f"{industry}: {count} companies")

# Streamlit app
st.title('Stock Performance Analysis')
symbols = st.text_input('Enter stock symbols separated by commas (e.g., AAPL, MSFT, TSLA, BTC-USD, TQQQ)', 'AAPL, MSFT, TSLA, BTC-USD, TQQQ')
period = st.selectbox('Select period', ['ytd', '1d', '5d', '1m', '6m', '1y', '2y', '3y', '5y', '10y', '20y'])

use_specific_dates = st.checkbox('Use specific start and end dates', value=False)

if use_specific_dates:
    default_start_date = datetime.now() - timedelta(days=365)
    default_end_date = datetime.now()
    start_date = st.date_input('Select start date', default_start_date)
    end_date = st.date_input('Select end date', default_end_date)
else:
    start_date = None
    end_date = None

normalize = st.checkbox('Normalize stock prices', value=True)

if st.button('Analyze'):
    symbols_list = [symbol.strip() for symbol in symbols.split(',')]
    start_date_str = start_date.strftime('%Y-%m-%d') if start_date else None