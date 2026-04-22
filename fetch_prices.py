#!/usr/bin/env python3
"""
Fetches live NSE stock prices via yfinance and writes prices.json.
Run by GitHub Actions every 15 minutes during NSE market hours.
"""

import json
import yfinance as yf
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

HOLDINGS = [
    ("M&MFIN",    "M&MFIN.NS"),
    ("VGUARD",    "VGUARD.NS"),
    ("INDHOTEL",  "INDHOTEL.NS"),
    ("WABAG",     "WABAG.NS"),
    ("HDFCBANK",  "HDFCBANK.NS"),
    ("DABUR",     "DABUR.NS"),
    ("WONDERLA",  "WONDERLA.NS"),
    ("PVRINOX",   "PVRINOX.NS"),
    ("AHLUCONT",  "AHLUCONT.NS"),
    ("AXISBANK",  "AXISBANK.NS"),
    ("RELIANCE",  "RELIANCE.NS"),
    ("ICICIBANK", "ICICIBANK.NS"),
    ("BHARTIARTL","BHARTIARTL.NS"),
    ("M&M",       "M&M.NS"),
    ("LT",        "LT.NS"),
    ("INDIGO",    "INDIGO.NS"),
]

# Fallback prices (Apr 17 2026) - used if fetch fails for a stock
FALLBACK = {
    "M&MFIN": 280.15, "VGUARD": 328.85, "INDHOTEL": 615.55,
    "WABAG": 1389.50, "HDFCBANK": 795.00, "DABUR": 442.85,
    "WONDERLA": 539.45, "PVRINOX": 1032.10, "AHLUCONT": 834.05,
    "AXISBANK": 1349.60, "RELIANCE": 1347.40, "ICICIBANK": 1346.80,
    "BHARTIARTL": 1846.90, "M&M": 3200.20, "LT": 4096.10, "INDIGO": 4608.00,
}

def fetch_prices():
    tickers = [t for _, t in HOLDINGS]
    prices = {}
    errors = []

    try:
        # Batch download - faster and more reliable
        tickers_str = " ".join(tickers)
        data = yf.download(tickers_str, period="2d", interval="1d",
                           progress=False, auto_adjust=True)

        close = data["Close"] if "Close" in data else data

        for sym, ticker in HOLDINGS:
            try:
                series = close[ticker].dropna()
                if len(series) > 0:
                    prices[sym] = round(float(series.iloc[-1]), 2)
                else:
                    prices[sym] = FALLBACK[sym]
                    errors.append(sym)
            except Exception as e:
                prices[sym] = FALLBACK[sym]
                errors.append(sym)

    except Exception as e:
        print(f"Batch download failed: {e}, trying individual...")
        # Fallback: fetch one by one
        for sym, ticker in HOLDINGS:
            try:
                tk = yf.Ticker(ticker)
                hist = tk.history(period="2d")
                if not hist.empty:
                    prices[sym] = round(float(hist["Close"].iloc[-1]), 2)
                else:
                    prices[sym] = FALLBACK[sym]
                    errors.append(sym)
            except Exception as e2:
                prices[sym] = FALLBACK[sym]
                errors.append(sym)

    now_ist = datetime.now(IST)
    now_h = now_ist.hour
    now_m = now_ist.minute
    market_open = (now_h > 9 or (now_h == 9 and now_m >= 15)) and \
                  (now_h < 15 or (now_h == 15 and now_m <= 30)) and \
                  now_ist.weekday() < 5

    output = {
        "updated": datetime.now(IST).isoformat(timespec="minutes"),
        "updated_epoch": int(datetime.now(timezone.utc).timestamp()),
        "market": "open" if market_open else "closed",
        "fetched": len(prices) - len(errors),
        "total": len(HOLDINGS),
        "errors": errors,
        "prices": prices,
    }

    with open("prices.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"✓ Wrote prices.json — {output['fetched']}/{output['total']} fetched")
    if errors:
        print(f"  Fallback used for: {', '.join(errors)}")
    print(f"  Market: {output['market']} | Time: {output['updated']}")
    return output

if __name__ == "__main__":
    fetch_prices()
