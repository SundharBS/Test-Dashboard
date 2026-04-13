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
            prices[stock] = float(hist["Close"].iloc[-1]) if not hist.empty else None
        except:
            prices[stock] = None
    return prices

# ---------- PRICE HISTORY ----------
@st.cache_data(ttl=3600)
def get_price_history(symbol):
    return yf.Ticker(symbol + ".NS").history(period="10y")

# ---------- CAGR ----------
def calculate_cagr(series):
    try:
        series = series.dropna()
        if len(series) < 2:
            return None
        start = series.iloc[0]
        end = series.iloc[-1]
        n = len(series) - 1
        if start <= 0 or end <= 0:
            return None
        return ((end / start) ** (1 / n) - 1) * 100
    except:
        return None

# ---------- DCF ----------
def calculate_dcf(net_income_series, growth_rate=0.1, discount_rate=0.12):
    try:
        net_income_series = net_income_series.dropna()
        if len(net_income_series) == 0:
            return None

        last_cashflow = net_income_series.iloc[-1]

        value = 0
        for t in range(1, 6):
            future_cf = last_cashflow * ((1 + growth_rate) ** t)
            discounted = future_cf / ((1 + discount_rate) ** t)
            value += discounted

        return value
    except:
        return None

# ---------- EXPORT ----------
def to_excel(df):
    return df.to_csv(index=True).encode("utf-8")

df = load_data()

stocks = sorted(df["Symbol"].dropna().unique())

selected_stocks = st.multiselect("🔍 Search Stocks", stocks)
if not selected_stocks:
    selected_stocks = [stocks[0]]

live_prices = get_live_prices_bulk(selected_stocks)

tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 Overview", "📊 Comparables", "📊 Benchmark", "📊 Valuation"]
)

# =========================
# TAB 1 — OVERVIEW
# =========================
with tab1:

    st.subheader("Live Price")
    cols = st.columns(len(selected_stocks))

    for i, stock in enumerate(selected_stocks):
        price = live_prices.get(stock)
        cols[i].metric(stock, f"₹{round(price,2)}" if price else "N/A")

    # ---------- HISTORICAL PRICE (FIXED) ----------
    st.subheader("Historical Price Trend")

    col1, col2 = st.columns(2)
    start = col1.date_input("Start Date", pd.to_datetime("2022-01-01"))
    end = col2.date_input("End Date", pd.to_datetime("today"))

    price_df = pd.DataFrame()

    for stock in selected_stocks:
        try:
            data = yf.download(stock + ".NS", start=start, end=end)

            if data.empty:
                data = yf.download(stock + ".NS", period="1y")

            if not data.empty:
                series = data["Close"].dropna()
                series.name = str(stock)
                price_df = pd.concat([price_df, series], axis=1)

        except:
            continue

    if not price_df.empty:
        price_df = price_df.apply(pd.to_numeric, errors="coerce")
        st.line_chart(price_df)
    else:
        st.warning("⚠️ No price data available")

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
            if not data.empty and data["Equity"].values[0] != 0:
                roe = (data["NetIncome"].values[0] / data["Equity"].values[0]) * 100

            rows.append({
                "Stock": stock,
                "P/E": info.get("trailingPE"),
                "P/B": info.get("priceToBook"),
                "ROE %": round(roe, 2) if roe else None
            })

        except:
            continue

    st.dataframe(pd.DataFrame(rows))

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

    # ---------- ROE ----------
    st.subheader("ROE Trend")
    roe_df = pd.DataFrame()

    for s in selected_stocks:
        data = df[df["Symbol"] == s].copy()
        data = data[data["Equity"] != 0]

        if not data.empty:
            data["ROE"] = (data["NetIncome"] / data["Equity"]) * 100
            series = data.set_index("Year")["ROE"]
            series.name = s
            roe_df = pd.concat([roe_df, series], axis=1)

    if not roe_df.empty:
        st.line_chart(roe_df)

    # ---------- P/B (HYBRID FINAL) ----------
    st.subheader("P/B Trend")

    pb_df = pd.DataFrame()

    for s in selected_stocks:
        try:
            data = df[df["Symbol"] == s].copy()
            data = data.dropna(subset=["Equity", "Shares"])
            data = data[data["Shares"] != 0]

            if data.empty:
                continue

            data["BVPS"] = data["Equity"] / data["Shares"]

            hist = get_price_history(s)
            if hist.empty:
                continue

            hist = hist.reset_index()
            hist["Year"] = hist["Date"].dt.year

            yearly_price = hist.groupby("Year")["Close"].last().reset_index()

            merged = pd.merge(data, yearly_price, on="Year", how="inner")

            if merged.empty:
                continue

            merged["PB"] = merged["Close"] / merged["BVPS"]

            series = merged.set_index("Year")["PB"]
            series.name = str(s)

            pb_df = pd.concat([pb_df, series], axis=1)

        except:
            continue

    if not pb_df.empty:
        st.line_chart(pb_df)
    else:
        st.warning("⚠️ No P/B data available")

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

    st.subheader("DCF Valuation")

    rows = []

    for stock in selected_stocks:
        try:
            data = df[df["Symbol"] == stock]
            if data.empty:
                continue

            price = live_prices.get(stock)

            growth = calculate_cagr(data["NetIncome"])
            if growth is None:
                growth = 10
            growth = growth / 100

            intrinsic = calculate_dcf(data["NetIncome"], growth)

            if intrinsic is None:
                last_income = data["NetIncome"].dropna()
                if not last_income.empty:
                    intrinsic = last_income.iloc[-1] * 10

            if intrinsic is not None:

                if price is not None:
                    upside = ((intrinsic - price) / price) * 100

                    rec = "HOLD"
                    if upside > 20:
                        rec = "BUY"
                    elif upside < -20:
                        rec = "SELL"
                else:
                    upside = None
                    rec = "N/A"

                rows.append({
                    "Stock": stock,
                    "Price": round(price, 2) if price else None,
                    "DCF Value": round(intrinsic, 2),
                    "Upside %": round(upside, 2) if upside else None,
                    "Recommendation": rec
                })

        except:
            continue

    if rows:
        st.dataframe(pd.DataFrame(rows))
    else:
        st.warning("⚠️ No valuation data available")
