import streamlit as st
from yahooquery import Ticker
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests

# -----------------
# CONFIG
# -----------------
st.set_page_config(page_title="Stock Dashboard", page_icon="📈", layout="wide")
st.title("📊 Stock Information Dashboard with RSI & Sector Comparison")

# -----------------
# Alpha Vantage Fallback
# -----------------
ALPHA_VANTAGE_KEY = "60W4OV8MQ1HVW2P8"  # Get free key from: https://www.alphavantage.co/support/#api-key

def get_alpha_vantage(symbol):
    """Fetch historical data from Alpha Vantage if Yahooquery fails"""
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
        df = df.tail(250)  # Limit to ~1 year
        return df
    except Exception:
        return None

# -----------------
# Yahooquery Primary Data
# -----------------
@st.cache_data
def get_yahoo_data(symbol):
    try:
        ticker = Ticker(symbol)
        hist = ticker.history(period="1y")
        if hist is None or hist.empty:
            return None, None
        hist = hist.loc[symbol.upper()]  # Remove multiindex symbol level
        hist.reset_index(inplace=True)
        hist['date'] = pd.to_datetime(hist['date'])
        hist.set_index('date', inplace=True)
        info = ticker.asset_profile
        recs = ticker.recommendation_trend
        summary = ticker.summary_detail
        return hist, {'info': info, 'recs': recs, 'summary': summary, 'peers': ticker.peers}
    except Exception:
        return None, None

# -----------------
# Technical Functions
# -----------------
def calculate_ma(hist_df, days):
    return hist_df['close'].rolling(window=days).mean().iloc[-1]

def get_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_analyst_rating(recs):
    try:
        latest = recs.tail(1)
        buy = int(latest['strongBuy'].iloc[0] + latest['buy'].iloc[0])
        hold = int(latest['hold'].iloc[0])
        sell = int(latest['sell'].iloc[0] + latest['strongSell'].iloc[0])
        total = buy + hold + sell
        if total == 0:
            return None
        buy_pct, hold_pct, sell_pct = (buy / total)*100, (hold / total)*100, (sell / total)*100
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

# -----------------
# Chart Functions
# -----------------
def create_price_chart(hist_data, low_200):
    hist_data['MA20'] = hist_data['close'].rolling(window=20).mean()
    hist_data['MA50'] = hist_data['close'].rolling(window=50).mean()

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=hist_data.index,
        open=hist_data['open'],
        high=hist_data['high'],
        low=hist_data['low'],
        close=hist_data['close'],
        name='Price',
        increasing_line_color='green',
        decreasing_line_color='red'
    ))
    fig.add_trace(go.Scatter(x=hist_data.index, y=hist_data['MA20'], name='20-Day MA', line=dict(color='orange')))
    fig.add_trace(go.Scatter(x=hist_data.index, y=hist_data['MA50'], name='50-Day MA', line=dict(color='blue')))
    fig.add_hline(y=low_200, line_dash="dash", line_color="red", annotation_text=f"200-Day Low: {low_200:.2f}")

    fig.update_layout(
        xaxis_rangeslider_visible=True,  # Scroll bar
        height=500,
        template="plotly_white",
        hovermode="x unified",
        xaxis_title="Date",
        yaxis_title="Price ($)"
    )

    # Limit initial view to last year
    if len(hist_data) > 0:
        start_date = hist_data.index.max() - pd.Timedelta(days=365)
        fig.update_xaxes(range=[start_date, hist_data.index.max()])

    return fig

def create_rsi_chart(rsi_series):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rsi_series.index, y=rsi_series, mode='lines', name='RSI', line=dict(color='purple')))
    fig.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Overbought")
    fig.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Oversold")
    fig.update_layout(height=250, template="plotly_white", yaxis_title="RSI")
    return fig

# -----------------
# User Input
# -----------------
col1, col2 = st.columns([3, 1])
with col1:
    stock_symbol = st.text_input("Enter Stock Symbol (e.g., AAPL, MSFT, GOOGL)", value="AAPL")
with col2:
    st.write("")
    fetch_btn = st.button("Get Stock Data")

# -----------------
# Main Logic
# -----------------
if fetch_btn and stock_symbol.strip():
    with st.spinner(f"Fetching data for {stock_symbol.upper()}..."):
        hist_data, data = get_yahoo_data(stock_symbol)

        # Fallback to Alpha Vantage
        if hist_data is None or hist_data.empty:
            st.warning("Yahoo data not available — trying Alpha Vantage fallback...")
            hist_data = get_alpha_vantage(stock_symbol.upper())
            data = {'info': {}, 'recs': pd.DataFrame(), 'summary': {}, 'peers': []} if hist_data is not None else None

        if hist_data is None or hist_data.empty:
            st.error(f"❌ Could not fetch data for {stock_symbol.upper()} — please check symbol or try again later.")
        else:
            # Company name
            try:
                company_name = data['info'][stock_symbol.upper()]['longBusinessSummary'][:50] + "..."
            except:
                company_name = stock_symbol.upper()

            current_price = hist_data['close'].iloc[-1]
            st.subheader(f"{company_name} ({stock_symbol.upper()}) — ${current_price:.2f}")

            # Metrics
            low_200 = hist_data['low'].tail(200).min()
            ma50 = calculate_ma(hist_data, 50)
            ma20 = calculate_ma(hist_data, 20)
            rsi_series = get_rsi(hist_data['close'])
            analyst_data = get_analyst_rating(data['recs']) if data['recs'] is not None and not data['recs'].empty else None

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("200-Day Low", f"${low_200:.2f}", f"{((current_price - low_200)/low_200)*100:.2f}%")
            c2.metric("50-Day MA", f"${ma50:.2f}", f"{((current_price - ma50)/ma50)*100:.2f}%")
            c3.metric("20-Day MA", f"${ma20:.2f}", f"{((current_price - ma20)/ma20)*100:.2f}%")
            c4.metric("RSI (14)", f"{rsi_series.iloc[-1]:.2f}")
            if analyst_data:
                c5.metric("Analyst Rating", analyst_data['overall'])
            else:
                c5.metric("Analyst Rating", "N/A")

            # Charts
            st.plotly_chart(create_price_chart(hist_data, low_200), use_container_width=True)
            st.plotly_chart(create_rsi_chart(rsi_series), use_container_width=True)

            # Analyst Breakdown
            if analyst_data:
                st.write("### Analyst Breakdown")
                st.write(f"🟢 Buy: {analyst_data['buy']} ({analyst_data['buy_pct']:.1f}%)")
                st.write(f"🟡 Hold: {analyst_data['hold']} ({analyst_data['hold_pct']:.1f}%)")
                st.write(f"🔴 Sell: {analyst_data['sell']} ({analyst_data['sell_pct']:.1f}%)")

            # Sector Comparison
            st.subheader("📈 Sector Comparison")
            try:
                sector_name = data['summary'][stock_symbol.upper()]['sector']
                st.write(f"**Sector:** {sector_name}")
            except:
                st.write("Sector info not available")
                sector_name = None

            if sector_name and data['peers']:
                st.write(f"Peers in {sector_name} sector: {', '.join(data['peers'])}")
                perf_data = {}
                for peer in data['peers'][:5]:  # limit to 5 peers
                    peer_hist, _ = get_yahoo_data(peer)
                    if peer_hist is not None and not peer_hist.empty:
                        start_price = peer_hist['close'].iloc[0]
                        end_price = peer_hist['close'].iloc[-1]
                        perf_data[peer] = ((end_price - start_price) / start_price) * 100
                if perf_data:
                    perf_df = pd.DataFrame(list(perf_data.items()), columns=["Symbol", "1Y % Change"])
                    perf_df.sort_values("1Y % Change", ascending=False, inplace=True)
                    st.dataframe(perf_df)