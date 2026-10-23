"""Public, read-only market dashboard. No private account connections or orders."""
import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Alpaca AI Dashboard", page_icon="📈", layout="wide")
st.title("📈 Alpaca AI Dashboard")
st.caption("Public market overview • Read-only • No brokerage access or trade execution")
st.warning("This public dashboard is not connected to the private bot. Gemini signals, account balances, and bot run logs are not published here.")

@st.cache_data(ttl=900, show_spinner=False)
def prices(symbol, period):
    data = yf.download(symbol, period=period, interval="1d", auto_adjust=True, progress=False, threads=False)
    if data.empty:
        return pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data.reset_index()

symbols = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"]
overview, stocks, gemini, lab, history = st.tabs(["Overview", "Stocks", "Gemini Signals", "Strategy Lab", "History"])
with overview:
    st.subheader("Market overview")
    st.caption("Prices are delayed or end-of-day depending on source availability; not trading quotes.")
    cols = st.columns(3)
    for idx, ticker in enumerate(["SPY", "QQQ", "NVDA"]):
        try:
            df = prices(ticker, "1mo")
            if len(df) >= 2:
                last, previous = float(df["Close"].iloc[-1]), float(df["Close"].iloc[-2])
                cols[idx].metric(ticker, f"${last:,.2f}", f"{(last / previous - 1)*100:+.2f}%")
            else:
                cols[idx].metric(ticker, "Unavailable")
        except Exception:
            cols[idx].metric(ticker, "Unavailable")
    st.info("Live bot health and research reports require a separate authenticated connection.")
with stocks:
    st.subheader("Stock charts")
    period = st.selectbox("Historical range", ["1mo", "3mo", "6mo", "1y", "2y"], index=2)
    chosen = st.multiselect("Show stocks", symbols, default=["SPY", "QQQ", "AAPL", "NVDA"], max_selections=6)
    if not chosen:
        st.info("Choose at least one symbol to display charts.")
    else:
        for i, ticker in enumerate(chosen):
            try:
                df = prices(ticker, period)
                if df.empty:
                    st.warning(f"{ticker}: market data unavailable.")
                    continue
                st.markdown(f"#### {ticker}")
                st.metric("Latest available close", f"${float(df['Close'].iloc[-1]):,.2f}")
                st.line_chart(df.set_index("Date")["Close"], y_label="USD")
                with st.expander(f"{ticker} historical prices"):
                    st.dataframe(df[["Date", "Open", "High", "Low", "Close", "Volume"]].tail(30).sort_values("Date", ascending=False), use_container_width=True, hide_index=True)
            except Exception:
                st.warning(f"{ticker}: could not load prices right now.")
with gemini:
    st.subheader("Gemini Signals")
    st.info("No real AI signals are connected. We will only show them here after choosing a secure sharing method.")
with lab:
    st.subheader("Strategy Lab")
    st.info("Private backtest reports are not synced to this public app.")
    st.caption("Backtests are historical and do not guarantee future performance.")
with history:
    st.subheader("Bot run history")
    st.info("GitHub Actions runs from the private repository are not connected.")
st.divider()
st.caption("Market data: Yahoo Finance via yfinance, subject to availability. Not financial advice.")
