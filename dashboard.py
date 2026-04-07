import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date
import time
from io import BytesIO

st.set_page_config(layout="wide")
st.title("📊 Investment Banking Dashboard")

# ---------------- AUTO REFRESH ----------------
refresh_rate = st.sidebar.slider("Auto Refresh (seconds)", 10, 120, 30)

if "last_run" not in st.session_state:
    st.session_state.last_run = time.time()

if time.time() - st.session_state.last_run > refresh_rate:
    st.session_state.last_run = time.time()
    st.rerun()

# ---------------- DATE ----------------
start_date = st.sidebar.date_input("Start Date", date(2023,1,1))
end_date = st.sidebar.date_input("End Date", date.today())

# ---------------- EXCEL FUNCTION ----------------
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# ---------------- STOCK LIST ----------------
stock_map = {
    "Apple (AAPL)": "AAPL",
    "Microsoft (MSFT)": "MSFT",
    "Tesla (TSLA)": "TSLA",
    "Amazon (AMZN)": "AMZN",
    "Google (GOOGL)": "GOOGL",
    "Meta (META)": "META",
    "Nvidia (NVDA)": "NVDA",
    "Reliance (RELIANCE.NS)": "RELIANCE.NS",
    "TCS (TCS.NS)": "TCS.NS",
    "Infosys (INFY.NS)": "INFY.NS",
    "HDFC Bank (HDFCBANK.NS)": "HDFCBANK.NS",
    "ICICI Bank (ICICIBANK.NS)": "ICICIBANK.NS",
    "Axis Bank (AXISBANK.NS)": "AXISBANK.NS",
    "SBI (SBIN.NS)": "SBIN.NS",
    "ITC (ITC.NS)": "ITC.NS"
}

selected_display = st.multiselect("🔍 Search Stocks", options=list(stock_map.keys()))
tickers = [stock_map[name] for name in selected_display]

def safe_download(ticker, **kwargs):
    try:
        return yf.download(ticker, **kwargs)
    except:
        return pd.DataFrame()

# ---------------- TABS (FIXED ERROR) ----------------
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Overview","📊 Comparables","📉 Benchmark","💰 Valuation"
])

# ---------------- OVERVIEW ----------------
with tab1:
    if not tickers:
        st.warning("Select stocks")
    else:
        st.subheader("Live Prices")

        for t in tickers:
            try:
                info = yf.Ticker(t).info
                price = info.get("currentPrice")
                prev = info.get("previousClose")

                if price and prev:
                    change = ((price - prev) / prev) * 100
                    st.write(f"{t}: ₹{price} ({round(change,2)}%)")
            except:
                st.write(f"{t}: Data unavailable")

        # Intraday
        st.subheader("Intraday Movement")
        data_live = safe_download(tickers, period="1d", interval="5m")

        if not data_live.empty:
            close_live = data_live["Close"] if isinstance(data_live.columns, pd.MultiIndex) else data_live
            st.line_chart(close_live)

        # Historical
        st.subheader("Historical Trend")
        data_hist = safe_download(tickers, start=start_date, end=end_date)

        if not data_hist.empty:
            close_hist = data_hist["Close"] if isinstance(data_hist.columns, pd.MultiIndex) else data_hist
            st.line_chart(close_hist)

# ---------------- COMPARABLES ----------------
with tab2:
    rows = []
    sectors = {}

    for t in tickers:
        try:
            info = yf.Ticker(t).info
            price = info.get("currentPrice")
            eps = info.get("trailingEps")
            book = info.get("bookValue")
            roe = info.get("returnOnEquity")
            sector = info.get("sector")

            sectors[t] = sector

            pe = price / eps if price and eps else None
            pb = price / book if price and book else None

            rows.append({
                "Company": t,
                "Sector": sector,
                "Price": round(price,2) if price else None,
                "P/E": round(pe,2) if pe else None,
                "P/B": round(pb,2) if pb else None,
                "ROE": roe
            })
        except:
            pass

    df = pd.DataFrame(rows)
    st.dataframe(df)

    # -------- PEERS --------
    st.subheader("Peer Comparison")

    peer_rows = []
    peer_universe = list(stock_map.values())

    for t in tickers:
        sector = sectors.get(t)

        for p in peer_universe:
            try:
                info = yf.Ticker(p).info

                if info.get("sector") == sector and p != t:
                    price = info.get("currentPrice")
                    eps = info.get("trailingEps")
                    book = info.get("bookValue")

                    pe = price / eps if price and eps else None
                    pb = price / book if price and book else None

                    peer_rows.append({
                        "Company": p,
                        "Sector": sector,
                        "P/E": round(pe,2) if pe else None,
                        "P/B": round(pb,2) if pb else None,
                        "ROE": info.get("returnOnEquity")
                    })
            except:
                pass

    peer_df = pd.DataFrame(peer_rows).drop_duplicates()
    st.dataframe(peer_df)

    st.download_button("📥 Download Comparables", to_excel(peer_df), "comparables.xlsx")

# ---------------- BENCHMARK ----------------
with tab3:
    benchmark = "^NSEI"
    bench = safe_download(benchmark, start=start_date, end=end_date)

    if not bench.empty:
        bench_close = bench["Close"].dropna()
        if isinstance(bench_close, pd.DataFrame):
            bench_close = bench_close.iloc[:,0]

        bench_return = (bench_close.iloc[-1] / bench_close.iloc[0]) - 1

        results = []

        for t in tickers:
            try:
                stock = safe_download(t, start=start_date, end=end_date)
                close = stock["Close"].dropna()

                if isinstance(close, pd.DataFrame):
                    close = close.iloc[:,0]

                r = (close.iloc[-1] / close.iloc[0]) - 1

                results.append({
                    "Stock": t,
                    "Return %": round(r*100,2),
                    "Benchmark %": round(bench_return*100,2),
                    "Outperformance %": round((r-bench_return)*100,2)
                })
            except:
                pass

        df_bench = pd.DataFrame(results)
        st.dataframe(df_bench)

        st.download_button("📥 Download Benchmark", to_excel(df_bench), "benchmark.xlsx")

# ---------------- REALISTIC VALUATION ----------------
with tab4:
    results = []

    for t in tickers:
        try:
            info = yf.Ticker(t).info

            price = info.get("currentPrice")
            eps = info.get("trailingEps")
            book = info.get("bookValue")
            fcf = info.get("freeCashflow")
            shares = info.get("sharesOutstanding")
            sector = info.get("sector")

            # -------- PEER MULTIPLES --------
            peer_pes = []
            peer_pbs = []

            for p in stock_map.values():
                try:
                    p_info = yf.Ticker(p).info
                    if p_info.get("sector") == sector and p != t:

                        p_price = p_info.get("currentPrice")
                        p_eps = p_info.get("trailingEps")
                        p_book = p_info.get("bookValue")

                        if p_price and p_eps:
                            peer_pes.append(p_price / p_eps)

                        if p_price and p_book:
                            peer_pbs.append(p_price / p_book)

                except:
                    pass

            avg_pe = sum(peer_pes)/len(peer_pes) if peer_pes else None
            avg_pb = sum(peer_pbs)/len(peer_pbs) if peer_pbs else None

            # -------- RELATIVE --------
            rel_vals = []

            if eps and avg_pe:
                rel_vals.append(eps * avg_pe)

            if book and avg_pb:
                rel_vals.append(book * avg_pb)

            relative_value = sum(rel_vals)/len(rel_vals) if rel_vals else None

            # -------- DCF --------
            dcf_value = None
            if fcf and shares:
                growth = 0.06
                discount = 0.10
                terminal_growth = 0.03

                future_fcf = fcf * (1 + growth)**5
                terminal_value = future_fcf * (1 + terminal_growth) / (discount - terminal_growth)

                dcf_total = (future_fcf / (discount**5)) + (terminal_value / (discount**5))
                dcf_value = dcf_total / shares

            # -------- FINAL --------
            vals = []

            if dcf_value:
                vals.append(dcf_value * 0.5)

            if relative_value:
                vals.append(relative_value * 0.5)

            if vals and price:
                target = sum(vals)
                upside = (target - price) / price * 100

                upside = max(min(upside, 100), -50)

                if upside > 15:
                    rec = "BUY"
                elif upside < -15:
                    rec = "SELL"
                else:
                    rec = "HOLD"

                results.append({
                    "Stock": t,
                    "Price": round(price,2),
                    "Target": round(target,2),
                    "Upside %": round(upside,2),
                    "Recommendation": rec
                })

        except:
            pass

    df_val = pd.DataFrame(results)

    if not df_val.empty:
        df_val = df_val.sort_values(by="Upside %", ascending=False)
        st.dataframe(df_val)

        top = df_val.iloc[0]
        st.success(f"🏆 Top Pick: {top['Stock']} ({top['Upside %']}%)")

    st.download_button("📥 Download Valuation", to_excel(df_val), "valuation.xlsx")
