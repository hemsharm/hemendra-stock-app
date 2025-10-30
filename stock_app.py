import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time

# -----------------------
# Streamlit Page Config
# -----------------------
st.set_page_config(
    page_title="Stock Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title("📊 Stock Information Dashboard")
st.markdown("Enter a stock symbol to get analyst ratings, moving averages, and charts")

# -----------------------
# Helper Functions
# -----------------------
@st.cache_data
def get_stock_history(symbol, period="1y", retries=3):
    """Fetch stock history with retries to handle Yahoo throttling"""
    for attempt in range(retries):
        try:
            ticker = yf.Ticker(symbol.upper())
            hist = ticker.history(period=period)
            if not hist.empty:
                return hist
        except Exception:
            pass
        time.sleep(1)  # wait before retry
    return pd.DataFrame()

def get_analyst_rating(ticker):
    """Get simplified analyst recommendation data"""
    try:
        recommendations = ticker.recommendations
        if recommendations is None or recommendations.empty:
            return None
        latest = recommendations.tail(10)
        buy = latest[latest['To Grade'].str.contains('Buy|Outperform|Overweight', case=False, na=False)].shape[0]
        hold = latest[latest['To Grade'].str.contains('Hold|Neutral', case=False, na=False)].shape[0]
        sell = latest[latest['To Grade'].str.contains('Sell|Underperform|Underweight', case=False, na=False)].shape[0]
        total = buy + hold + sell
        if total == 0:
            return None
        buy_pct, hold_pct, sell_pct = (buy/total)*100, (hold/total)*100, (sell/total)*100
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
            'overall': overall,
            'buy': buy, 'hold': hold, 'sell': sell,
            'buy_pct': buy_pct, 'hold_pct': hold_pct, 'sell_pct': sell_pct
        }
    except Exception:
        return None

def calculate_ma(hist_df, days):
    return hist_df['Close'].rolling(window=days).mean().iloc[-1]

def create_price_chart(hist_data, low_200):
    hist_data['MA20'] = hist_data['Close'].rolling(window=20).mean()
    hist_data['MA50'] = hist_data['Close'].rolling(window=50).mean()
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=hist_data.index,
        open=hist_data['Open'],
        high=hist_data['High'],
        low=hist_data['Low'],
        close=hist_data['Close'],
        name='Price',
        increasing_line_color='green',
        decreasing_line_color='red'
    ))
    fig.add_trace(go.Scatter(x=hist_data.index, y=hist_data['MA20'], name='20-Day MA', line=dict(color='orange')))
    fig.add_trace(go.Scatter(x=hist_data.index, y=hist_data['MA50'], name='50-Day MA', line=dict(color='blue')))
    fig.add_hline(y=low_200, line_dash="dash", line_color="red", annotation_text=f"200-Day Low: {low_200:.2f}")
    fig.update_layout(xaxis_rangeslider_visible=False, height=500, template="plotly_white")
    return fig

# -----------------------
# User Input
# -----------------------
col1, col2 = st.columns([3, 1])
with col1:
    stock_symbol = st.text_input("Enter Stock Symbol (e.g., AAPL, MSFT, GOOGL)", value="AAPL")
with col2:
    st.write("")
    fetch_btn = st.button("Get Stock Data")

# -----------------------
# Main Execution
# -----------------------
if fetch_btn and stock_symbol.strip():
    with st.spinner(f"Fetching data for {stock_symbol.upper()}..."):
        hist_data = get_stock_history(stock_symbol)

        if hist_data.empty:
            st.error(f"❌ Could not fetch data for {stock_symbol.upper()} — please check symbol or try again later.")
        else:
            ticker = yf.Ticker(stock_symbol.upper())

            # Try fast_info first for reliability
            try:
                current_price = getattr(ticker.fast_info, 'last_price', None)
            except Exception:
                current_price = None

            if current_price is None:
                try:
                    current_price = ticker.info.get('currentPrice', hist_data['Close'].iloc[-1])
                except Exception:
                    current_price = hist_data['Close'].iloc[-1]

            try:
                company_name = ticker.info.get('longName', stock_symbol.upper())
            except Exception:
                company_name = stock_symbol.upper()

            st.subheader(f"{company_name} ({stock_symbol.upper()}) — ${current_price:.2f}")

            # Calculate metrics
            low_200 = hist_data['Low'].tail(200).min()
            ma_50 = calculate_ma(hist_data, 50)
            ma_20 = calculate_ma(hist_data, 20)
            analyst_data = get_analyst_rating(ticker)

            # Metrics Dashboard
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("200-Day Low", f"${low_200:.2f}", f"{((current_price - low_200)/low_200)*100:.2f}%")
            c2.metric("50-Day MA", f"${ma_50:.2f}", f"{((current_price - ma_50)/ma_50)*100:.2f}%")
            c3.metric("20-Day MA", f"${ma_20:.2f}", f"{((current_price - ma_20)/ma_20)*100:.2f}%")
            if analyst_data:
                c4.metric("Analyst Rating", analyst_data['overall'])
            else:
                c4.metric("Analyst Rating", "N/A")

            st.plotly_chart(create_price_chart(hist_data, low_200), use_container_width=True)

            # Analyst Breakdown
            if analyst_data:
                st.write("### Analyst Breakdown (Last 10)")
                st.write(f"🟢 Buy: {analyst_data['buy']} ({analyst_data['buy_pct']:.1f}%)")
                st.write(f"🟡 Hold: {analyst_data['hold']} ({analyst_data['hold_pct']:.1f}%)")
                st.write(f"🔴 Sell: {analyst_data['sell']} ({analyst_data['sell_pct']:.1f}%)")