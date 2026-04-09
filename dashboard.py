import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import yfinance as yf
from nsepython import nse_eq
from io import BytesIO

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

    df = df.sort_values(["Symbol", "Year"])
    df = df.ffill()

    return df

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer)
    return output.getvalue()

df = load_data()
stocks = sorted(df["Symbol"].unique())

selected_stocks = st.multiselect("🔍 Search Stocks", stocks)
if not selected_stocks:
    selected_stocks = [stocks[0]]

tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 Overview", "📊 Comparables", "📊 Benchmark", "📊 Valuation"]
)

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

    st.download_button(
        "📥 Download Comparables",
        to_excel(comp_df),
        file_name="comparables.xlsx"
    )

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

        st.download_button(
            "📥 Download Revenue Trend",
            to_excel(rev_df),
            file_name="revenue_trend.xlsx"
        )

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

        st.download_button(
            "📥 Download ROE Trend",
            to_excel(roe_df),
            file_name="roe_trend.xlsx"
        )

    # ---------- P/B ----------
    st.subheader("P/B Trend")

    pb_df = pd.DataFrame()

    for s in selected_stocks:
        try:
            data = df[df["Symbol"] == s].copy()

            data["Shares"] = data["Shares"].replace(0, pd.NA)
            data["Shares"] = data["Shares"].ffill()
            data["BVPS"] = data["Equity"] / data["Shares"]

            data = data.dropna(subset=["BVPS"])

            if not data.empty:
                price = yf.download(s + ".NS", period="10y")["Close"]

                if isinstance(price, pd.Series) and not price.empty:
                    pb_series = []

                    for _, row in data.iterrows():
                        year = int(row["Year"])
                        bvps = float(row["BVPS"])

                        price_val = float(price.iloc[-1])
                        pb_val = price_val / bvps

                        pb_series.append((year, pb_val))

                    temp = pd.DataFrame(pb_series, columns=["Year", s]).set_index("Year")
                    pb_df = pd.concat([pb_df, temp], axis=1)

        except:
            continue

    if not pb_df.empty:
        st.line_chart(pb_df)

        st.download_button(
            "📥 Download P/B Trend",
            to_excel(pb_df),
            file_name="pb_trend.xlsx"
        )

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

        st.download_button(
            "📥 Download Profit Margin",
            to_excel(margin_df),
            file_name="margin_trend.xlsx"
        )x
