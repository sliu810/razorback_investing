import streamlit as st
from datetime import datetime, timedelta
from stock_performance import get_and_print_stock_performance
from index_performance import get_and_display_index_performance

# Streamlit app
st.title('Stock and Index Performance Analysis')

# Section 1: Stock Performance
st.header('Stock Performance Analysis')
st.markdown("---")  # Horizontal rule for separation

with st.expander("Stock Performance Analysis"):
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

    if st.button('Analyze Stock Performance'):
        symbols_list = [symbol.strip() for symbol in symbols.split(',')]
        start_date_str = start_date.strftime('%Y-%m-%d') if start_date else None
        end_date_str = end_date.strftime('%Y-%m-%d') if end_date else None
        get_and_print_stock_performance(symbols_list, period=period, start_date=start_date_str, end_date=end_date_str, normalize=normalize)

# Section 2: Index Performance
st.header('Index Performance Analysis')
st.markdown("---")  # Horizontal rule for separation

with st.expander("Index Performance Analysis"):
    index = st.selectbox('Select index', ['QQQ', 'SPX', 'DOW', 'IWM'])
    index_period = st.selectbox('Select period for index', ['ytd', '1d', '5d', '1m', '6m', '1y', '2y', '3y', '5y', '10y', '20y'])

    index_use_specific_dates = st.checkbox('Use specific start and end dates for index', value=False)

    if index_use_specific_dates:
        index_default_start_date = datetime.now() - timedelta(days=365)
        index_default_end_date = datetime.now()
        index_start_date = st.date_input('Select start date for index', index_default_start_date)
        index_end_date = st.date_input('Select end date for index', index_default_end_date)
    else:
        index_start_date = None
        index_end_date = None

    top_n = st.number_input('Top N performing stocks', min_value=1, value=10)
    bottom_n = st.number_input('Bottom N performing stocks', min_value=1, value=10)

    if st.button('Analyze Index Performance'):
        index_start_date_str = index_start_date.strftime('%Y-%m-%d') if index_start_date else None
        index_end_date_str = index_end_date.strftime('%Y-%m-%d') if index_end_date else None
        get_and_display_index_performance(index, period=index_period, top_n=top_n, bottom_n=bottom_n, start_date=index_start_date_str, end_date=index_end_date_str)