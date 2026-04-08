import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date
from streamlit_autorefresh import st_autorefresh
from nsepython import nse_eq

st.set_page_config(layout="wide")
st.title("📊 Investment Banking Dashboard")

# ---------------- AUTO REFRESH ----------------
st_autorefresh(interval=30000, key="auto_refresh")

# ---------------- DATE ----------------
start_date = st.sidebar.date_input("Start Date", date(2023,1,1))
end_date = st.sidebar.date_input("End Date", date.today())

# ---------------- NSE PRICE ----------------
@st.cache_data(ttl=15)
def get_nse_price(ticker):
    try:
        return nse_eq(ticker.replace(".NS",""))["priceInfo"]["lastPrice"]
    except:
        return None

# ---------------- CSV ----------------
@st.cache_data(ttl=86400)
def load_csv():
    df = pd.read_csv("nse_stocks.csv")
    df.columns = df.columns.str.strip()
    if "SERIES" in df.columns:
        df = df[df["SERIES"]=="EQ"]
    return df

@st.cache_data(ttl=86400)
def build_map():
    df = load_csv()
    mp = {}
    for _, r in df.iterrows():
        name = r.get("NAME OF COMPANY","")
        sym = r.get("SYMBOL","")
        if sym:
            mp[f"{name} ({sym})"] = sym+".NS"
    return mp

stock_map = build_map()

# ---------------- SEARCH ----------------
selected = st.multiselect("🔍 Search Stocks", list(stock_map.keys()))
tickers = [stock_map[i] for i in selected]

# ---------------- SAFE PLOT ----------------
def safe_plot(data_dict, title):
    st.subheader(title)

    if not data_dict:
        st.warning(f"{title} not available")
        return

    try:
        df = pd.DataFrame(data_dict)

        df = df.apply(pd.to_numeric, errors='coerce')
        df = df.dropna(how="all")
        df = df.dropna(axis=1, how="all")

        if df.empty or df.shape[1] == 0:
            st.warning(f"{title} not available")
            return

        df = df.sort_index()

        st.line_chart(df)

    except:
        st.warning(f"{title} failed to render")

# ---------------- TABS ----------------
tab1, tab2, tab3, tab4 = st.tabs(["📈 Overview","📊 Comparables","📉 Benchmark","💰 Valuation"])

# ---------------- OVERVIEW ----------------
with tab1:
    if tickers:
        st.subheader("Live Prices")
        for t in tickers:
            st.write(f"{t}: ₹{get_nse_price(t)}")

        try:
            st.subheader("Intraday")
            intraday = yf.download(tickers, period="1d", interval="5m")["Close"]
            st.line_chart(intraday)
        except:
            st.warning("Intraday data not available")

        try:
            st.subheader("Historical Trend")
            hist = yf.download(tickers, start=start_date, end=end_date)["Close"]
            st.line_chart(hist)
        except:
            st.warning("Historical data not available")

# ---------------- COMPARABLES ----------------
with tab2:

    rows = []

    for t in tickers:
        try:
            stock = yf.Ticker(t)
            info = stock.info
            price = get_nse_price(t)

            eps = info.get("trailingEps") or 0
            book = info.get("bookValue") or 0
            roe = info.get("returnOnEquity")
            roa = info.get("returnOnAssets")

            pe = (price / eps) if price and eps else None
            pb = (price / book) if price and book else None

            if roe is None:
                ni = info.get("netIncomeToCommon")
                eq = info.get("totalStockholderEquity")
                if ni and eq:
                    roe = ni / eq

            if roa is None:
                ni = info.get("netIncomeToCommon")
                assets = info.get("totalAssets")
                if ni and assets:
                    roa = ni / assets

            rows.append({
                "Company": t,
                "Price": round(price,2) if price else None,
                "P/E": round(pe,2) if pe else None,
                "P/B": round(pb,2) if pb else None,
                "ROE %": round(roe*100,2) if roe else None,
                "ROA %": round(roa*100,2) if roa else None
            })

        except:
            rows.append({
                "Company": t,
                "Price": None,
                "P/E": None,
                "P/B": None,
                "ROE %": None,
                "ROA %": None
            })

    df = pd.DataFrame(rows)
    st.dataframe(df.fillna("N/A"))

    # ---------- REVENUE ----------
    rev_data = {}
    for t in tickers:
        try:
            inc = yf.Ticker(t).financials.T
            if "Total Revenue" in inc.columns:
                rev_data[t] = inc["Total Revenue"]
        except:
            continue
    safe_plot(rev_data, "📊 Revenue Trend")

    # ---------- ROE ----------
    roe_data = {}
    for t in tickers:
        try:
            stock = yf.Ticker(t)
            inc = stock.financials.T
            bal = stock.balance_sheet.T

            ni_col = [c for c in inc.columns if "net" in c.lower()]
            eq_col = [c for c in bal.columns if "equity" in c.lower()]

            if ni_col and eq_col:
                roe_data[t] = inc[ni_col[0]] / bal[eq_col[0]]
        except:
            continue
    safe_plot(roe_data, "📊 ROE Trend")

    # ---------- P/B TREND ----------
    pb_data = {}

    for t in tickers:
        try:
            stock = yf.Ticker(t)
            bal = stock.balance_sheet.T

            if bal.empty:
                continue

            eq_col = [c for c in bal.columns if "equity" in c.lower()]
            if not eq_col:
                continue

            shares = stock.info.get("sharesOutstanding")
            if not shares:
                continue

            price = yf.download(t, period="5y")["Close"]
            if price.empty:
                continue

            values = []

            for dt in bal.index:
                try:
                    p = price.loc[:dt].iloc[-1]
                    eq = bal.loc[dt, eq_col[0]]

                    val = p / (eq / shares)

                    if isinstance(val, (int, float)):
                        values.append(val)
                    else:
                        values.append(None)

                except:
                    values.append(None)

            s = pd.Series(values, index=bal.index)

            if s.notna().sum() > 1:
                pb_data[t] = s

        except:
            continue

    safe_plot(pb_data, "📊 P/B Trend")

    # ---------- MARGIN ----------
    margin_data = {}
    for t in tickers:
        try:
            inc = yf.Ticker(t).financials.T

            ni_col = [c for c in inc.columns if "net" in c.lower()]
            rev_col = [c for c in inc.columns if "revenue" in c.lower()]

            if ni_col and rev_col:
                margin_data[t] = inc[ni_col[0]] / inc[rev_col[0]]
        except:
            continue
    safe_plot(margin_data, "📊 Profit Margin Trend")

# ---------------- BENCHMARK ----------------
with tab3:
    try:
        bench = yf.download("^NSEI", start=start_date, end=end_date)["Close"]
        results = []

        for t in tickers:
            s = yf.download(t, start=start_date, end=end_date)["Close"]

            if len(s) > 1:
                r = (s.iloc[-1]/s.iloc[0]) - 1
                b = (bench.iloc[-1]/bench.iloc[0]) - 1

                results.append({
                    "Stock": t,
                    "Return %": r * 100,
                    "Benchmark %": b * 100
                })

        st.dataframe(pd.DataFrame(results))
    except:
        st.warning("Benchmark data not available")

# ---------------- VALUATION ----------------
with tab4:
    results = []

    for t in tickers:
        try:
            info = yf.Ticker(t).info
            price = get_nse_price(t)
            eps = info.get("trailingEps")

            if price and eps:
                target = eps * 20
                upside = (target - price) / price * 100

                rec = "BUY" if upside > 15 else "SELL" if upside < -15 else "HOLD"

                results.append({
                    "Stock": t,
                    "Price": price,
                    "Target": target,
                    "Upside %": upside,
                    "Recommendation": rec
                })
        except:
            continue

    st.dataframe(pd.DataFrame(results))
