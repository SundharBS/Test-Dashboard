import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import yfinance as yf

st.set_page_config(layout="wide")
st.title("📊 Investment Banking Dashboard")

# 🔄 AUTO REFRESH
st_autorefresh(interval=30000, key="refresh")

# ---------- LOAD DATA ----------
@st.cache_data(ttl=86400)
def load_data():
    df = pd.read_csv("financial_dataset.csv")
    df.columns = df.columns.str.strip()

    df["Shares"] = pd.to_numeric(df["Shares"], errors="coerce")
    df["Equity"] = pd.to_numeric(df["Equity"], errors="coerce")
    df["Revenue"] = pd.to_numeric(df["Revenue"], errors="coerce")
    df["NetIncome"] = pd.to_numeric(df.get("NetIncome"), errors="coerce")

    df = df.sort_values(["Symbol", "Year"])
    df = df.ffill()

    return df

# ---------- LIVE PRICE ----------
@st.cache_data(ttl=60)
def get_live_prices_bulk(stocks):
    prices = {}

    for stock in stocks:
        try:
            ticker = yf.Ticker(stock + ".NS")
            hist = ticker.history(period="1d")

            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
            else:
                price = None
        except:
            price = None

        prices[stock] = price

    return prices

# ---------- EXPORT ----------
def to_excel(df):
    return df.to_csv(index=True).encode("utf-8")

df = load_data()

if "Symbol" not in df.columns:
    st.error("❌ 'Symbol' column missing")
    st.stop()

stocks = sorted(df["Symbol"].dropna().unique())

selected_stocks = st.multiselect("🔍 Search Stocks", stocks)

if not selected_stocks:
    selected_stocks = [stocks[0]]

# 🔥 LIVE PRICES
live_prices = get_live_prices_bulk(selected_stocks)

tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 Overview", "📊 Comparables", "📊 Benchmark", "📊 Valuation"]
)

# =========================
# TAB 1 — OVERVIEW
# =========================
with tab1:

    col1, col2 = st.columns(2)
    start = col1.date_input("Start Date", pd.to_datetime("2022-01-01"))
    end = col2.date_input("End Date", pd.to_datetime("today"))

    st.subheader("Live Price")
    cols = st.columns(len(selected_stocks))

    for i, stock in enumerate(selected_stocks):
        price = live_prices.get(stock)

        if price is not None:
            cols[i].metric(stock, f"₹{round(price,2)}")
        else:
            cols[i].metric(stock, "N/A")

    # ---------- PRICE TREND ----------
    st.subheader("Historical Price Trend")

    price_df = pd.DataFrame()

    for stock in selected_stocks:
        try:
            data = yf.download(stock + ".NS", start=start, end=end)

            if data.empty:
                data = yf.download(stock + ".NS", period="1y")

            if not data.empty:
                series = data["Close"].dropna()
                series.name = stock
                price_df = pd.concat([price_df, series], axis=1)

        except:
            continue

    if not price_df.empty:
        st.line_chart(price_df)
    else:
        st.warning("No valid price data")

# =========================
# TAB 2 — COMPARABLES
# =========================
with tab2:

    st.subheader("Live Comparables")

    rows = []
    latest_year = df["Year"].max()

    for stock in selected_stocks:
        try:
            ticker = yf.Ticker(stock + ".NS")
            info = ticker.info

            data = df[(df["Symbol"] == stock) & (df["Year"] == latest_year)]

            roe = None
            roa = None

            if not data.empty:
                try:
                    roe = (data["NetIncome"].values[0] / data["Equity"].values[0]) * 100
                except:
                    pass

                try:
                    roa = (data["NetIncome"].values[0] / data["Revenue"].values[0]) * 100
                except:
                    pass

            rows.append({
                "Stock": stock,
                "P/E": info.get("trailingPE"),
                "P/B": info.get("priceToBook"),
                "ROE %": round(roe, 2) if roe is not None else None,
                "ROA %": round(roa, 2) if roa is not None else None
            })

        except:
            continue

    comp_df = pd.DataFrame(rows)

    if not comp_df.empty:
        st.dataframe(comp_df)
        st.download_button("📥 Download Comparables", to_excel(comp_df), "comparables.csv")
    else:
        st.warning("No comparables data available")

    # ---------- REVENUE ----------
    st.subheader("Revenue Trend")
    rev_df = pd.DataFrame()

    for s in selected_stocks:
        data = df[df["Symbol"] == s]
        if not data.empty:
            series = data.set_index("Year")["Revenue"]
            series.name = s
            rev_df = pd.concat([rev_df, series], axis=1)

    if not rev_df.empty:
        st.line_chart(rev_df)
        st.download_button("📥 Download Revenue", to_excel(rev_df), "revenue.csv")

    # ---------- ROE ----------
    st.subheader("ROE Trend")
    roe_df = pd.DataFrame()

    for s in selected_stocks:
        data = df[df["Symbol"] == s].copy()

        if not data.empty:
            data = data.dropna(subset=["NetIncome", "Equity"])
            data = data[data["Equity"] != 0]

            if not data.empty:
                data["ROE"] = (data["NetIncome"] / data["Equity"]) * 100
                series = data.set_index("Year")["ROE"]
                series.name = s
                roe_df = pd.concat([roe_df, series], axis=1)

    if not roe_df.empty:
        st.line_chart(roe_df)
        st.download_button("📥 Download ROE", to_excel(roe_df), "roe.csv")
    else:
        st.warning("No ROE data available")

    # ---------- P/B ----------
    st.subheader("P/B Trend")
    pb_df = pd.DataFrame()

    for s in selected_stocks:
        try:
            data = df[df["Symbol"] == s].copy()

            if not data.empty:
                data = data.dropna(subset=["Equity", "Shares"])
                data = data[data["Shares"] != 0]

                if not data.empty:
                    data["BVPS"] = data["Equity"] / data["Shares"]

                    price = live_prices.get(s)

                    if price is not None:
                        data["PB"] = price / data["BVPS"]

                        series = data.set_index("Year")["PB"]
                        series.name = s
                        pb_df = pd.concat([pb_df, series], axis=1)

        except:
            continue

    if not pb_df.empty:
        st.line_chart(pb_df)
        st.download_button("📥 Download P/B", to_excel(pb_df), "pb.csv")
    else:
        st.warning("No P/B data available")

# =========================
# TAB 3 — BENCHMARK
# =========================
with tab3:

    rows = []

    try:
        nifty_hist = yf.download("^NSEI", period="1y")["Close"]
    except:
        nifty_hist = None

    for stock in selected_stocks:
        try:
            stock_hist = yf.download(stock + ".NS", period="1y")["Close"]

            if nifty_hist is not None:
                stock_return = (stock_hist.iloc[-1] / stock_hist.iloc[0] - 1) * 100
                nifty_return = (nifty_hist.iloc[-1] / nifty_hist.iloc[0] - 1) * 100

                rows.append({
                    "Stock": stock,
                    "Stock Return %": round(stock_return, 2),
                    "Benchmark %": round(nifty_return, 2)
                })

        except:
            continue

    st.dataframe(pd.DataFrame(rows))

# =========================
# TAB 4 — VALUATION
# =========================
with tab4:

    rows = []

    for stock in selected_stocks:
        try:
            ticker = yf.Ticker(stock + ".NS")
            info = ticker.info

            price = live_prices.get(stock)
            eps = info.get("trailingEps")

            if price is not None and eps:
                intrinsic = eps * 20
                upside = ((intrinsic - price) / price) * 100

                rec = "HOLD"
                if upside > 15:
                    rec = "BUY"
                elif upside < -15:
                    rec = "SELL"

                rows.append({
                    "Stock": stock,
                    "Price": price,
                    "Intrinsic Value": intrinsic,
                    "Upside %": round(upside, 2),
                    "Recommendation": rec
                })

        except:
            continue

    st.dataframe(pd.DataFrame(rows))
