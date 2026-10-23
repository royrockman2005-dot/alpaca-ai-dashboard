"""Public demo dashboard. No credentials, account access, or trading."""
import streamlit as st

st.set_page_config(page_title="Alpaca AI Dashboard",page_icon="📈",layout="wide")
st.title("📈 Alpaca AI Dashboard")
st.caption("Public demo • No API keys • No live account data • No order execution")
st.info("This is a public demonstration. All displayed status is illustrative, not live trading results.")
a,b,c=st.columns(3)
a.metric("Bot mode","RESEARCH ONLY")
b.metric("Broker connection","Not connected")
c.metric("Latest signals","No live data")
tabs=st.tabs(["Overview","Stocks","Gemini Signals","Strategy Lab","History"])
with tabs[0]:
    st.subheader("Overview")
    st.write("The private trading bot and its reports are not connected to this public demo.")
    st.write("Next: configure a private, authenticated data source before displaying any real reports.")
with tabs[1]:
    st.subheader("Stocks")
    st.write("Live stock data is not enabled yet. No market prices are shown.")
with tabs[2]:
    st.subheader("Gemini Signals")
    st.write("No real Gemini signals are exposed on this public site.")
with tabs[3]:
    st.subheader("Strategy Lab")
    st.write("Historical tests of the private bot are not published here.")
    st.warning("Historical backtests do not establish future profitability.")
with tabs[4]:
    st.subheader("History")
    st.write("Private run history is not connected.")
st.divider()
st.caption("Alpaca AI • Display only • Not financial advice")
