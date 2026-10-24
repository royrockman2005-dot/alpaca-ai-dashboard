"""Public read-only market dashboard. Never loads private trading credentials."""
import json
import io
import urllib.request
import urllib.error
import zipfile
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

@st.cache_data(ttl=600, show_spinner=False)
def fetch_private_signals(token):
    """Read only latest valid completed V6 report. Token never leaves server."""
    api = "https://api.github.com/repos/royrockman2005-dot/alpaca-ai-trading-bot/actions/artifacts?per_page=50"
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json", "User-Agent": "private-streamlit-research-viewer"}
    request = urllib.request.Request(api, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        artifacts = json.load(response).get("artifacts", [])
    artifacts = sorted((a for a in artifacts if not a.get("expired") and a.get("name", "").startswith("v6-research-")), key=lambda a: a.get("created_at", ""), reverse=True)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            return None
    for artifact in artifacts[:8]:
        try:
            request = urllib.request.Request(artifact["archive_download_url"], headers=headers)
            try:
                urllib.request.build_opener(NoRedirect).open(request, timeout=20)
                continue
            except urllib.error.HTTPError as redirect:
                if redirect.code not in (301, 302, 303, 307, 308):
                    continue
                url = redirect.headers.get("Location", "")
                if not url.startswith("https://"):
                    continue
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "private-streamlit-research-viewer"}), timeout=30) as response:
                raw = response.read(10_000_001)
            if len(raw) > 10_000_000:
                continue
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                paths = sorted((p for p in archive.namelist() if p.split("/")[-1].startswith("signals_") and p.endswith(".json")), reverse=True)
                for path in paths:
                    if archive.getinfo(path).file_size > 1_000_000:
                        continue
                    record = json.loads(archive.read(path))
                    if record.get("research_only") is not True or record.get("v5_exit_code") != 0:
                        continue
                    timestamp = record.get("timestamp_utc")
                    result = {}
                    for entry in record.get("signals", []):
                        symbol = entry.get("symbol")
                        decision = entry.get("decision")
                        if isinstance(symbol, str) and symbol.isalpha() and symbol.isupper() and len(symbol) <= 5 and decision in ("BUY", "HOLD", "SELL"):
                            result[symbol] = {"decision": decision, "updated_at": timestamp}
                    return result, timestamp
        except (ValueError, OSError, KeyError, urllib.error.URLError, zipfile.BadZipFile):
            continue
    return {}, None

def public_signals():
    try:
        token = st.secrets.get("GITHUB_READ_TOKEN", "")
    except Exception:
        token = ""
    if token:
        try:
            return fetch_private_signals(token)
        except Exception:
            st.sidebar.warning("Private research feed unavailable. Check read-only token access.")
            return {}, None
    # No token: use only an explicitly published sanitized snapshot.
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

overview, stocks, gemini, lab, history, replay_tab = st.tabs(["Overview", "Stocks", "Gemini Signals", "Strategy Lab", "History", "Replay Lab"])
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

with st.expander("🧠 AI Agent Pipeline — מפת המערכת", expanded=False):
    st.caption("מפת ארכיטקטורה להמחשה בלבד. סטטוסים חיים אינם מחוברים לאתר הציבורי.")
    st.graphviz_chart("""digraph pipeline {
        rankdir=LR;
        graph [bgcolor="transparent", pad="0.2"];
        node [shape=box, style="rounded,filled", fillcolor="#17263b", fontcolor="white", color="#334155", fontsize=12];
        edge [color="#64748b"];
        market [label="Market Data"];
        scan [label="100 Stock Scanner"];
        technical [label="Technical Strategy"];
        news [label="News + Smart Money"];
        gemini [label="Gemini Review"];
        risk [label="Risk Controls"];
        paper [label="Paper Research - NO ORDERS"];
        replay [label="Historical Replay"];
        market -> scan -> technical;
        technical -> gemini;
        news -> gemini;
        gemini -> risk -> paper;
        market -> replay;
        replay -> gemini [style=dashed];
    }""", use_container_width=True)
    st.info("תרשים להמחשה בלבד. עדיין אין מערכת ניטור חיה או שיפור עצמי מאומת.")

with st.expander("🔎 Agent Health — אבחון רכיבים", expanded=False):
    st.caption("מצב רכיבים לפי המבחנים האחרונים, לא ניטור בזמן אמת.")
    st.dataframe(pd.DataFrame([
        {"רכיב":"Historical data", "מצב":"100 מניות עם נתונים", "פעולה הבאה":"בדיקות במספר תאריכים"},
        {"רכיב":"Technical replay", "מצב":"מחקר פעיל", "פעולה הבאה":"Walk-forward ומדדי סיכון"},
        {"רכיב":"Gemini historical review", "מצב":"שגיאת API בהרצה האחרונה", "פעולה הבאה":"אבחון קוד השגיאה בדוח V6.8"},
        {"רכיב":"Live execution", "מצב":"כבוי", "פעולה הבאה":"לא להפעיל ללא בקרות"},
    ]), use_container_width=True, hide_index=True)
    st.warning("כשל Gemini אינו אות מסחר. אין להציג החלטה כאילו התקבלה ממנו.")

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
    st.subheader("Strategy Lab — השוואה לשוק")
    st.caption("השוואה היסטורית של קנייה והחזקה בלבד; אינה מייצגת ביצועים של הבוט.")
    benchmark_choice = st.selectbox("טווח בדיקה", ["חודש", "3 חודשים", "חצי שנה", "שנה"], index=1, key="benchmark_period")
    benchmark_symbols = st.multiselect("מניות להשוואה מול SPY", SYMBOLS[2:], default=["AAPL", "NVDA"], max_selections=5, key="benchmark_symbols")
    n = SESSIONS[benchmark_choice]
    comparisons = {}
    for symbol in ["SPY"] + benchmark_symbols:
        try:
            df = daily_prices(symbol)
            if len(df) >= n + 1:
                series = df["Close"].tail(n + 1).reset_index(drop=True)
                comparisons[symbol] = (series / float(series.iloc[0]) - 1) * 100
        except Exception:
            pass
    if "SPY" in comparisons:
        frame = pd.DataFrame(comparisons)
        st.line_chart(frame, y_label="תשואה מצטברת (%)")
        st.dataframe(pd.DataFrame([
            {"מניה": symbol, "תשואת קנייה והחזקה": f"{float(values.iloc[-1]):+.2f}%",
             "פער מול SPY": f"{float(values.iloc[-1] - comparisons['SPY'].iloc[-1]):+.2f}%"}
            for symbol, values in comparisons.items()
        ]), use_container_width=True, hide_index=True)
        st.caption("ההשוואה לפי מספר ימי מסחר, לא תאריכי התחלה מדויקים; לא כולל עלויות מסחר. מניות עם נתונים חסרים מושמטות.")
    else:
        st.warning("נתוני SPY אינם זמינים כעת.")
    st.divider()
    st.subheader("V6.8 — סיכום מבחן היסטורי")
    st.caption("תוצאות מדווחות מהרצה קודמת של 15.09.2026, לא נתונים חיים. Gemini נכשל בהרצה זו.")
    c1, c2, c3 = st.columns(3)
    c1.metric("מניות שנבדקו", "100")
    c2.metric("עסקאות טכניות", "38")
    c3.metric("תשואה ממוצעת נטו", "-0.0201%")
    st.info("18 מתוך 38 עסקאות היו רווחיות (47.4%). Gemini: 0 החלטות מאומתות מתוך 10 ניסיונות. המדגם הוא יום אחד בלבד.")
    st.warning("אין להסיק מהמדגם יתרון מסחרי או תשואה צפויה. הנתונים ההיסטוריים אינם מסונכרנים אוטומטית.")

with history:
    st.subheader("History")
    st.info("Private GitHub Actions run logs are not connected.")
with replay_tab:
    st.subheader("V6.7 — Historical replay")
    st.caption("מחקר בלבד: החלטות לפי נרות של 5 דקות שהושלמו לפני זמן הבדיקה. ללא Gemini היסטורי וללא מסחר.")
    replay_symbol = st.selectbox("בחר מניה לבדיקה", SYMBOLS, index=4, key="replay_symbol")
    st.caption("הנתונים מגיעים מ-Yahoo Finance; זמינות נרות של 5 דקות מוגבלת בדרך כלל לתקופה האחרונה.")
    if st.button("הרץ מבחן היסטורי", key="run_replay"):
        try:
            from datetime import timedelta
            from v67_point_in_time import replay
            from v67_batch_replay import batch_replay, summary
            data = intraday_prices(replay_symbol)
            if data.empty:
                st.warning("לא התקבלו נתוני 5 דקות למניה.")
            else:
                bars = [(ts.to_pydatetime(), float(row["Open"]), float(row["High"]),
                         float(row["Low"]), float(row["Close"])) for ts, row in data.iterrows()]
                outcomes = batch_replay(bars, step=6)
                report = summary(outcomes)
                a, b, c = st.columns(3)
                a.metric("החלטות קנייה", report["buy_decisions"])
                b.metric("אחוז עסקאות רווחיות", f'{report["win_rate_pct"]:.1f}%' if report["win_rate_pct"] is not None else "אין מספיק נתונים")
                c.metric("תשואה ממוצעת נטו", f'{report["avg_net_pct"]:+.2f}%' if report["avg_net_pct"] is not None else "—")
                st.json(report)
                st.caption("זה אינו מבחן מדויק של הבוט עם Gemini. מדגם קטן ואותה תקופת שוק אינם הוכחה ליתרון מסחרי.")
        except Exception as exc:
            st.error(f"Replay unavailable: {type(exc).__name__}")
st.divider()
st.caption("Market data: Yahoo Finance via yfinance • No trading functionality • Not financial advice")
