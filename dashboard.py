"""Public read-only market dashboard. Never loads private trading credentials."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Alpaca AI Dashboard", page_icon="📈", layout="wide")
st.title("📈 Alpaca AI Dashboard")
st.caption("Public market data • Research only • No trading or private account access")
st.warning("Public dashboard. Private bot results are not synced. Market data may be delayed.")

SYMBOLS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"]
PERIODS = {"יום": "1d", "יום קודם": "previous", "שבוע": "5d", "חודש": "1mo", "3 חודשים": "3mo", "חצי שנה": "6mo", "שנה": "1y"}
SESSIONS = {"שבוע": 5, "חודש": 21, "3 חודשים": 63, "חצי שנה": 126, "שנה": 252}

@st.cache_data(ttl=900, show_spinner=False)
def daily_prices(symbol):
    df = yf.download(symbol, period="2y", interval="1d", auto_adjust=True, progress=False, threads=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=["Close"]).sort_index()

@st.cache_data(ttl=900, show_spinner=False)
def intraday_prices(symbol):
    df = yf.download(symbol, period="5d", interval="5m", auto_adjust=True, progress=False, threads=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=["Close"]).sort_index()

def pct(a, b):
    return (float(a) / float(b) - 1) * 100 if float(b) else None

def display_pct(v):
    return f"{v:+.2f}%" if v is not None else "N/A"

def change_for(df, choice):
    close = df["Close"]
    if len(close) < 2:
        return None
    if choice == "יום":
        return pct(close.iloc[-1], close.iloc[-2])
    if choice == "יום קודם":
        return pct(close.iloc[-2], close.iloc[-3]) if len(close) >= 3 else None
    n = SESSIONS[choice]
    return pct(close.iloc[-1], close.iloc[-(n + 1)]) if len(close) > n else None

def chart_data(symbol, daily, choice):
    if choice == "יום":
        intra = intraday_prices(symbol)
        if not intra.empty:
            latest_date = intra.index[-1].date()
            return intra[intra.index.date == latest_date]["Close"], "5-minute bars; latest available session"
        return daily["Close"].tail(2), "Daily closes; intraday data unavailable"
    if choice == "יום קודם":
        intra = intraday_prices(symbol)
        if not intra.empty:
            days = sorted(set(intra.index.date))
            if len(days) >= 2:
                return intra[intra.index.date == days[-2]]["Close"], "5-minute bars; prior available session"
        return daily["Close"].tail(3).iloc[:2], "Daily closes; intraday data unavailable"
    n = SESSIONS[choice]
    return daily["Close"].tail(n + 1), "Daily closing prices"

def public_signals():
    # Optional, deliberately public-only, sanitized export. No secrets or private API requests.
    path = Path(__file__).with_name("signals_public.json")
    if not path.is_file():
        return {}, None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            return {}, None
        signals = obj.get("signals", {})
        return signals if isinstance(signals, dict) else {}, obj.get("updated_at")
    except (ValueError, OSError):
        return {}, None

signals, signals_time = public_signals()

def signal_label(symbol):
    entry = signals.get(symbol)
    if not isinstance(entry, dict):
        return "אין אות זמין", None
    raw = str(entry.get("decision", "")).upper()
    mapping = {"BUY": "קנייה", "HOLD": "המתנה", "SELL": "מכירה", "AVOID": "להימנע"}
    if raw not in mapping:
        return "אין אות זמין", None
    return mapping[raw], entry.get("updated_at") or signals_time

overview, stocks, gemini, lab, history = st.tabs(["Overview", "Stocks", "Gemini Signals", "Strategy Lab", "History"])
with overview:
    st.subheader("Market overview")
    cols = st.columns(3)
    for i, symbol in enumerate(["SPY", "QQQ", "NVDA"]):
        try:
            df = daily_prices(symbol)
            if len(df) >= 2:
                cols[i].metric(symbol, f"${float(df['Close'].iloc[-1]):,.2f}", display_pct(change_for(df, "יום")))
            else:
                cols[i].metric(symbol, "Unavailable")
        except Exception:
            cols[i].metric(symbol, "Unavailable")
    st.info("Bot status and account data are not connected to this public site.")

with stocks:
    st.subheader("Stock charts and performance")
    choice = st.segmented_control("תקופה להשוואה", list(PERIODS), default="יום")
    chosen = st.multiselect("בחר מניות", SYMBOLS, default=["SPY", "QQQ", "AAPL", "NVDA"], max_selections=6)
    st.caption("שינוי יומי מחושב מסגירות יומיות; שבוע/חודש/שנה לפי כמות ימי מסחר בקירוב. נתונים אינם בהכרח בזמן אמת.")
    for symbol in chosen:
        st.divider()
        st.markdown(f"### {symbol}")
        try:
            df = daily_prices(symbol)
            if df.empty:
                st.warning("Market data unavailable")
                continue
            close = float(df["Close"].iloc[-1])
            change = change_for(df, choice)
            status, updated = signal_label(symbol)
            c1, c2, c3 = st.columns(3)
            c1.metric("מחיר סגירה אחרון", f"${close:,.2f}")
            c2.metric(f"שינוי: {choice}", display_pct(change))
            c3.metric("החלטת הבוט", status)
            if updated:
                st.caption(f"Bot signal timestamp: {updated}")
            else:
                st.caption("No verified bot signal published for this stock.")
            series, note = chart_data(symbol, df, choice)
            if not series.empty:
                st.line_chart(series, y_label="USD")
            st.caption(note)
            with st.expander(f"{symbol} — מחירים היסטוריים"):
                view = df.tail(30).reset_index()
                st.dataframe(view, use_container_width=True, hide_index=True)
        except Exception:
            st.warning(f"{symbol}: data temporarily unavailable.")

with gemini:
    st.subheader("Gemini Signals")
    if not signals:
        st.info("אין עדיין אותות מאומתים מהבוט. חיבור הדוחות הפרטיים מחייב אישור לפני פרסום פומבי.")
    else:
        rows = [{"מניה": s, "החלטה": signal_label(s)[0], "עדכון": signal_label(s)[1]} for s in sorted(signals)]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("AI signals are research outputs, not investment advice or confirmed profitability.")
with lab:
    st.subheader("Strategy Lab")
    st.info("Private strategy tests are not automatically published.")
    st.caption("Historical backtests do not guarantee future performance.")
with history:
    st.subheader("History")
    st.info("Private GitHub Actions run logs are not connected.")
st.divider()
st.caption("Market data: Yahoo Finance via yfinance • No trading functionality • Not financial advice")
