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

            # ---------------- PEER MULTIPLES ----------------
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

            # ---------------- RELATIVE VALUATION ----------------
            rel_vals = []

            if eps and avg_pe:
                rel_vals.append(eps * avg_pe)

            if book and avg_pb:
                rel_vals.append(book * avg_pb)

            relative_value = sum(rel_vals)/len(rel_vals) if rel_vals else None

            # ---------------- DCF (IMPROVED) ----------------
            dcf_value = None

            if fcf and shares:
                growth = 0.06   # conservative
                discount = 0.10
                terminal_growth = 0.03

                future_fcf = fcf * (1 + growth)**5
                terminal_value = future_fcf * (1 + terminal_growth) / (discount - terminal_growth)

                dcf_total = (future_fcf / (discount**5)) + (terminal_value / (discount**5))
                dcf_value = dcf_total / shares

            # ---------------- FINAL TARGET ----------------
            vals = []

            if dcf_value:
                vals.append(dcf_value * 0.5)

            if relative_value:
                vals.append(relative_value * 0.5)

            if vals and price:
                target = sum(vals)

                upside = (target - price) / price * 100

                # cap unrealistic values
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
