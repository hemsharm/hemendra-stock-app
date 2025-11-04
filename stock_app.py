import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import traceback

st.set_page_config(page_title="Stock Dashboard", page_icon="📈", layout="wide")
st.title("📊 Stock Dashboard with RSI, Earnings & Sector Comparison")

# -----------------
# Alpha Vantage Fallback
# -----------------
ALPHA_VANTAGE_KEY = "CLARG2WA7A7N6T4G"

def get_alpha_vantage(symbol):
    try:
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={ALPHA_VANTAGE_KEY}&outputsize=full"
        data = requests.get(url).json()
        if "Time Series (Daily)" not in data:
            return None
        df = pd.DataFrame(data["Time Series (Daily)"]).T
        df.columns = ['open', 'high', 'low', 'close', 'volume']
        df = df.astype(float)
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)
        return df.tail(250)
    except Exception:
        return None

# -----------------
# yfinance Data
# -----------------
@st.cache_data
def get_yahoo_data(symbol):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1y")
        if hist.empty:
            return None, None
        hist.columns = hist.columns.str.lower()
        
        info = ticker.info
        quarterly_income = ticker.quarterly_income_stmt
        recommendations = ticker.recommendations
        
        return hist, {
            'info': info,
            'quarterly_income': quarterly_income,
            'recommendations': recommendations
        }
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None, None

# -----------------
# Helpers
# -----------------
def calculate_ma(hist_df, days):
    return hist_df['close'].rolling(window=days).mean().iloc[-1]

def get_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_analyst_rating(recommendations):
    try:
        if recommendations is None or recommendations.empty:
            return None
        recent = recommendations.tail(10)
        buy_count = recent[recent['To Grade'].str.contains('Buy|Outperform|Overweight', case=False, na=False)].shape[0]
        hold_count = recent[recent['To Grade'].str.contains('Hold|Neutral', case=False, na=False)].shape[0]
        sell_count = recent[recent['To Grade'].str.contains('Sell|Underperform|Underweight', case=False, na=False)].shape[0]
        
        total = buy_count + hold_count + sell_count
        if total == 0:
            return None
        
        buy_pct = (buy_count / total) * 100
        hold_pct = (hold_count / total) * 100
        sell_pct = (sell_count / total) * 100
        
        if buy_pct >= 60:
            overall = "Strong Buy"
        elif buy_pct >= 40:
            overall = "Buy"
        elif hold_pct >= 50:
            overall = "Hold"
        elif sell_pct >= 40:
            overall = "Sell"
        else:
            overall = "Hold"
        
        return {
            'overall': overall, 'buy': buy_count, 'hold': hold_count, 'sell': sell_count,
            'buy_pct': buy_pct, 'hold_pct': hold_pct, 'sell_pct': sell_pct
        }
    except Exception:
        return None

def create_price_chart(hist_data, low_200):
    hist_data = hist_data.copy()
    hist_data['MA20'] = hist_data['close'].rolling(window=20).mean()
    hist_data['MA50'] = hist_data['close'].rolling(window=50).mean()
    
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=hist_data.index, open=hist_data['open'], high=hist_data['high'],
        low=hist_data['low'], close=hist_data['close'], name='Price',
        increasing_line_color='green', decreasing_line_color='red'
    ))
    fig.add_trace(go.Scatter(x=hist_data.index, y=hist_data['MA20'], name='20-Day MA', line=dict(color='orange')))
    fig.add_trace(go.Scatter(x=hist_data.index, y=hist_data['MA50'], name='50-Day MA', line=dict(color='blue')))
    fig.add_hline(y=low_200, line_dash="dash", line_color="red", annotation_text=f"200-Day Low: {low_200:.2f}")
    
    fig.update_layout(xaxis_rangeslider_visible=True, height=500, template="plotly_white", hovermode="x unified")
    return fig

def create_rsi_chart(rsi_series):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rsi_series.index, y=rsi_series, mode='lines', line=dict(color='purple'), name="RSI"))
    fig.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Overbought")
    fig.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Oversold")
    fig.update_layout(height=250, template="plotly_white", yaxis_title="RSI")
    return fig

# -----------------
# Session State Initialization
# -----------------
if 'hist_data' not in st.session_state:
    st.session_state.hist_data = None
if 'data' not in st.session_state:
    st.session_state.data = None
if 'stock_symbol' not in st.session_state:
    st.session_state.stock_symbol = "AAPL"

# -----------------
# UI
# -----------------
col1, col2 = st.columns([3, 1])
with col1:
    stock_symbol = st.text_input("Enter Stock Symbol (e.g., AAPL, MSFT)", value=st.session_state.stock_symbol)
with col2:
    st.write("")
    fetch_btn = st.button("Fetch Data")

# -----------------
# Fetch Data
# -----------------
if fetch_btn and stock_symbol.strip():
    st.session_state.stock_symbol = stock_symbol.upper()
    with st.spinner(f"Fetching data for {stock_symbol.upper()}..."):
        hist_data, data = get_yahoo_data(stock_symbol)

        if hist_data is None or hist_data.empty:
            st.warning("Yahoo data not available — trying Alpha Vantage fallback...")
            hist_data = get_alpha_vantage(stock_symbol.upper())
            data = {'info': {}, 'quarterly_income': pd.DataFrame(), 'recommendations': pd.DataFrame()}

        if hist_data is None or hist_data.empty:
            st.error(f"❌ Could not fetch data for {stock_symbol.upper()}")
            st.session_state.hist_data = None
            st.session_state.data = None
        else:
            st.session_state.hist_data = hist_data
            st.session_state.data = data

# -----------------
# Display Data (if available)
# -----------------
if st.session_state.hist_data is not None and st.session_state.data is not None:
    hist_data = st.session_state.hist_data
    data = st.session_state.data
    
    try:
        company_name = data['info'].get('longName', st.session_state.stock_symbol)
    except:
        company_name = st.session_state.stock_symbol

    current_price = hist_data['close'].iloc[-1]
    st.subheader(f"{company_name} ({st.session_state.stock_symbol}) — ${current_price:.2f}")

    low_200 = hist_data['low'].tail(200).min()
    ma50 = calculate_ma(hist_data, 50)
    ma20 = calculate_ma(hist_data, 20)
    rsi_series = get_rsi(hist_data['close'])
    analyst_data = get_analyst_rating(data['recommendations'])

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("200-Day Low", f"${low_200:.2f}", f"{((current_price - low_200)/low_200)*100:.2f}%")
    c2.metric("50-Day MA", f"${ma50:.2f}", f"{((current_price - ma50)/ma50)*100:.2f}%")
    c3.metric("20-Day MA", f"${ma20:.2f}", f"{((current_price - ma20)/ma20)*100:.2f}%")
    c4.metric("RSI (14)", f"{rsi_series.iloc[-1]:.2f}")
    c5.metric("Analyst Rating", analyst_data['overall'] if analyst_data else "N/A")
    
    try:
        eps_value = data['info'].get('trailingEps', None)
        c6.metric("EPS (TTM)", f"${eps_value:.2f}" if eps_value else "N/A")
    except:
        c6.metric("EPS (TTM)", "N/A")

    # Chart Range Dropdown - NOW WORKS DYNAMICALLY
    chart_range = st.selectbox("📅 Select chart range", ["3M", "6M", "1Y"], index=2)
    days_back = {"3M": 90, "6M": 180, "1Y": 365}[chart_range]
    filtered_data = hist_data[hist_data.index >= hist_data.index.max() - pd.Timedelta(days=days_back)]
    filtered_rsi = get_rsi(filtered_data['close'])

    # Quarterly Earnings
    st.write("---")
    try:
        quarterly_df = data['quarterly_income']
        
        if isinstance(quarterly_df, pd.DataFrame) and not quarterly_df.empty:
            last4_cols = quarterly_df.columns[:4]
            display_data = []
            
            for col in last4_cols:
                quarter_data = {'Quarter End': col.strftime('%Y-%m-%d')}
                
                if 'Total Revenue' in quarterly_df.index:
                    rev_val = quarterly_df.loc['Total Revenue', col]
                    quarter_data['Revenue ($)'] = f"${rev_val:,.0f}" if pd.notnull(rev_val) else "N/A"
                
                if 'Net Income Common Stockholders' in quarterly_df.index:
                    ni_val = quarterly_df.loc['Net Income Common Stockholders', col]
                    quarter_data['Net Income ($)'] = f"${ni_val:,.0f}" if pd.notnull(ni_val) else "N/A"
                
                if 'Basic EPS' in quarterly_df.index:
                    eps_val = quarterly_df.loc['Basic EPS', col]
                    quarter_data['EPS'] = f"${eps_val:.2f}" if pd.notnull(eps_val) else "N/A"
                
                display_data.append(quarter_data)
            
            if display_data:
                display_df = pd.DataFrame(display_data)
                st.subheader("📊 Last 4 Quarter Earnings")
                st.table(display_df)
            else:
                st.write("Could not extract quarterly earnings data.")
        else:
            st.write("No quarterly earnings data available.")
    except Exception as e:
        st.write(f"Error displaying quarterly earnings: {e}")

    st.write("---")
    st.plotly_chart(create_price_chart(filtered_data, low_200), use_container_width=True)
    st.plotly_chart(create_rsi_chart(filtered_rsi), use_container_width=True)

    if analyst_data:
        st.write("### Analyst Breakdown")
        st.write(f"🟢 Buy: {analyst_data['buy']} ({analyst_data['buy_pct']:.1f}%)")
        st.write(f"🟡 Hold: {analyst_data['hold']} ({analyst_data['hold_pct']:.1f}%)")
        st.write(f"🔴 Sell: {analyst_data['sell']} ({analyst_data['sell_pct']:.1f}%)")

    st.subheader("📈 Sector & Industry")
    try:
        sector = data['info'].get('sector', 'N/A')
        industry = data['info'].get('industry', 'N/A')
        st.write(f"**Sector:** {sector}")
        st.write(f"**Industry:** {industry}")
    except:
        st.write("Sector/Industry info not available")