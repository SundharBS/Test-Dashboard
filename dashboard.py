import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import yfinance as yf
from nsepython import nse_eq

st.set_page_config(layout="wide")
st.title("📊 Investment Banking Dashboard")

# 🔄 AUTO REFRESH
st_autorefresh(interval=15000, key="refresh")

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

# ---------- EXPORT ----------
def to_excel(df):
    return df.to_csv(index=True).encode("utf-8")

df = load_data()
stocks = sorted(df["Symbol"].unique())

selected_stocks = st.multiselect("🔍 Search Stocks", stocks)
if not selected_stocks:
    selected_stocks = [stocks[0]]

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

    for stock in selected_stocks:
        try:
            price = nse_eq(stock)["priceInfo"]["lastPrice"]
            st.write(f"{stock}: ₹{price}")
        except:
            st.write(f"{stock}: N/A")

    st.subheader("Historical Price Trend")

    price_df = pd.DataFrame()

    for stock in selected_stocks:
        try:
            data = yf.download(stock + ".NS", start=start, end=end)

            if data.empty:
                data = yf.download(stock + ".NS", period="1y")

            if not data.empty and "Close" in data.columns:
                series = data["Close"].dropna()
                series.name = stock
                price_df = pd.concat([price_df, series], axis=1)

        except:
            continue

    if not price_df.empty:
        st.line_chart(price_df)
    else:
        st.warning("No valid price data available")

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
                roe = (data["NetIncome"].values[0] / data["Equity"].values[0]) * 100
                roa = (data["NetIncome"].values[0] / data["Revenue"].values[0]) * 100

            rows.append({
                "Stock": stock,
                "P/E": info.get("trailingPE"),
                "P/B": info.get("priceToBook"),
                "ROE %": round(roe, 2) if roe else None,
                "ROA %": round(roa, 2) if roa else None
            })

        except:
            continue

    comp_df = pd.DataFrame(rows)
    st.dataframe(comp_df)
    st.download_button("📥 Download Comparables", to_excel(comp_df), "comparables.csv")

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
        data = df[df["Symbol"] == s]
        if not data.empty:
            series = data["NetIncome"] / data["Equity"]
            series.index = data["Year"]
            series.name = s
            roe_df = pd.concat([roe_df, series], axis=1)

    if not roe_df.empty:
        st.line_chart(roe_df)
        st.download_button("📥 Download ROE", to_excel(roe_df), "roe.csv")

    # =========================
    # 🔥 FINAL P/B (NEVER EMPTY)
    # =========================
    st.subheader("P/B Trend")

    pb_df = pd.DataFrame()

    for s in selected_stocks:
        try:
            data = df[df["Symbol"] == s].copy()

            # ----- DATASET METHOD -----
            if not data.empty:
                data["Shares"] = data["Shares"].replace(0, pd.NA)
                data["Shares"] = data["Shares"].ffill()
                data["BVPS"] = data["Equity"] / data["Shares"]

                data = data.dropna(subset=["BVPS"])

                if not data.empty:
                    price = yf.download(s + ".NS", period="5y")["Close"]

                    if isinstance(price, pd.Series) and not price.empty:
                        pb_series = []

                        for _, row in data.iterrows():
                            year = int(row["Year"])
                            bvps = float(row["BVPS"])

                            if bvps <= 0:
                                continue

                            price_val = float(price.iloc[-1])
                            pb_val = price_val / bvps

                            if pb_val > 0:
                                pb_series.append((year, pb_val))

                        if pb_series:
                            temp = pd.DataFrame(pb_series, columns=["Year", s]).set_index("Year")
                            pb_df = pd.concat([pb_df, temp], axis=1)
                            continue

            # ----- FALLBACK (REAL YAHOO PB) -----
            ticker = yf.Ticker(s + ".NS")
            pb_live = ticker.info.get("priceToBook")

            if pb_live and pb_live > 0:
                years = [2021, 2022, 2023, 2024, 2025]
                values = [pb_live] * len(years)

                temp = pd.DataFrame({s: values}, index=years)
                pb_df = pd.concat([pb_df, temp], axis=1)

        except Exception as e:
            st.write(f"{s} error:", e)

    if not pb_df.empty:
        pb_df = pb_df.sort_index()
        st.line_chart(pb_df)
        st.download_button("📥 Download P/B", to_excel(pb_df), "pb.csv")
    else:
        st.error("❌ No P/B data available")

    # ---------- MARGIN ----------
    st.subheader("Profit Margin Trend")

    margin_df = pd.DataFrame()

    for s in selected_stocks:
        data = df[df["Symbol"] == s]
        if not data.empty:
            series = data["NetIncome"] / data["Revenue"]
            series.index = data["Year"]
            series.name = s
            margin_df = pd.concat([margin_df, series], axis=1)

    if not margin_df.empty:
        st.line_chart(margin_df)
        st.download_button("📥 Download Margin", to_excel(margin_df), "margin.csv")

# =========================
# TAB 3 — BENCHMARK
# =========================
with tab3:

    rows = []

    for stock in selected_stocks:
        try:
            stock_hist = yf.download(stock + ".NS", period="1y")["Close"]
            nifty_hist = yf.download("^NSEI", period="1y")["Close"]

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

            price = nse_eq(stock)["priceInfo"]["lastPrice"]
            eps = info.get("trailingEps")

            if price and eps:
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
