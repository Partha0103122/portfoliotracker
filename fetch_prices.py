#!/usr/bin/env python3
"""
Fetches NSE stock prices using Google Finance (primary) and
NSE Bhavcopy CSV (fallback). No API key needed. Works on GitHub Actions.
"""

import json, re, sys, time, zipfile, io
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError

print("=== fetch_prices.py starting ===")
print(f"Python {sys.version.split()[0]}")

IST = timezone(timedelta(hours=5, minutes=30))

# (portfolio_symbol, google_finance_symbol)
# Google Finance replaces & with - in ticker names
HOLDINGS = [
    ("M&MFIN",     "M-MFIN"),
    ("VGUARD",     "VGUARD"),
    ("INDHOTEL",   "INDHOTEL"),
    ("WABAG",      "WABAG"),
    ("HDFCBANK",   "HDFCBANK"),
    ("DABUR",      "DABUR"),
    ("WONDERLA",   "WONDERLA"),
    ("PVRINOX",    "PVRINOX"),
    ("AHLUCONT",   "AHLUCONT"),
    ("AXISBANK",   "AXISBANK"),
    ("RELIANCE",   "RELIANCE"),
    ("ICICIBANK",  "ICICIBANK"),
    ("BHARTIARTL", "BHARTIARTL"),
    ("M&M",        "M-M"),
    ("LT",         "LT"),
    ("INDIGO",     "INDIGO"),
]

FALLBACK_PRICES = {
    "M&MFIN": 280.15, "VGUARD": 328.85, "INDHOTEL": 615.55,
    "WABAG": 1389.50, "HDFCBANK": 795.00, "DABUR": 442.85,
    "WONDERLA": 539.45, "PVRINOX": 1032.10, "AHLUCONT": 834.05,
    "AXISBANK": 1349.60, "RELIANCE": 1347.40, "ICICIBANK": 1346.80,
    "BHARTIARTL": 1846.90, "M&M": 3200.20, "LT": 4096.10, "INDIGO": 4608.00,
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
}


def fetch_google_finance(sym, goog_sym):
    """Scrape current price from Google Finance quote page."""
    url = f"https://www.google.com/finance/quote/{goog_sym}:NSE"
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=12) as r:
            html = r.read().decode("utf-8", errors="ignore")

        # Try multiple extraction patterns — Google changes their HTML occasionally
        patterns = [
            r'data-last-price="([\d.]+)"',
            r'"price"\s*:\s*"([\d,]+\.?\d*)"',
            r'class="YMlKec fxKbKc">([\d,]+\.?\d*)<',
            r'class="fxKbKc">([\d,]+\.?\d*)<',
            r'<div[^>]+YMlKec[^>]*>([\d,]+\.?\d*)<',
        ]
        for pat in patterns:
            m = re.search(pat, html)
            if m:
                price = float(m.group(1).replace(",", ""))
                if 10 < price < 500000:
                    return price

    except Exception as e:
        print(f"    Google Finance error for {sym} ({goog_sym}): {e}")
    return None


def fetch_nse_bhavcopy():
    """
    Download NSE official end-of-day Bhavcopy CSV.
    Returns {symbol: close_price} or {} if unavailable.
    Published by NSE after ~6 PM IST on trading days.
    """
    now_ist = datetime.now(IST)
    for delta in range(4):
        dt = now_ist - timedelta(days=delta)
        if dt.weekday() >= 5:
            continue
        date_str  = dt.strftime("%d%b%Y").upper()   # 17APR2026
        date_str2 = dt.strftime("%Y%m%d")           # 20260417
        year      = dt.strftime("%Y")
        mon       = dt.strftime("%b").upper()

        urls = [
            f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{date_str2}_F_0000.csv.zip",
            f"https://archives.nseindia.com/content/historical/EQUITIES/{year}/{mon}/cm{date_str}bhav.csv.zip",
        ]
        for url in urls:
            try:
                req = Request(url, headers={**HEADERS, "Referer": "https://www.nseindia.com"})
                with urlopen(req, timeout=15) as r:
                    data = r.read()
                zf = zipfile.ZipFile(io.BytesIO(data))
                csv_data = zf.read(zf.namelist()[0]).decode("utf-8")
                prices = {}
                for line in csv_data.splitlines()[1:]:
                    cols = line.split(",")
                    if len(cols) >= 6:
                        try:
                            prices[cols[0].strip().strip('"')] = float(cols[5].strip().strip('"'))
                        except ValueError:
                            pass
                if prices:
                    print(f"  NSE Bhavcopy: {dt.strftime('%d %b %Y')} — {len(prices)} symbols")
                    return prices
            except Exception as e:
                print(f"  Bhavcopy failed ({url[-35:]}): {e}")
    return {}


def main():
    prices = {}
    errors = []

    print("\n--- Fetching via Google Finance ---")
    for sym, goog_sym in HOLDINGS:
        price = fetch_google_finance(sym, goog_sym)
        if price:
            prices[sym] = round(price, 2)
            print(f"  ✓ {sym}: ₹{price:,.2f}")
        else:
            errors.append(sym)
            print(f"  ✗ {sym}: failed")
        time.sleep(0.4)

    # Fallback: NSE Bhavcopy for any failures
    if errors:
        print(f"\n--- NSE Bhavcopy fallback for {errors} ---")
        bhav = fetch_nse_bhavcopy()
        still_missing = []
        for sym in errors:
            # Try direct match, then without &
            key = sym if sym in bhav else sym.replace("&", "")
            if key in bhav:
                prices[sym] = round(bhav[key], 2)
                print(f"  ✓ {sym}: ₹{bhav[key]:,.2f} (bhavcopy)")
            else:
                prices[sym] = FALLBACK_PRICES.get(sym, 0)
                print(f"  ! {sym}: using fallback ₹{prices[sym]}")
                still_missing.append(sym)
        errors = still_missing

    # Determine market status
    now_ist = datetime.now(IST)
    h, m, wd = now_ist.hour, now_ist.minute, now_ist.weekday()
    market_open = wd < 5 and (h > 9 or (h == 9 and m >= 15)) and (h < 15 or (h == 15 and m <= 30))

    output = {
        "updated":       now_ist.isoformat(timespec="minutes"),
        "updated_epoch": int(datetime.now(timezone.utc).timestamp()),
        "market":        "open" if market_open else "closed",
        "fetched":       len(prices) - len(errors),
        "total":         len(HOLDINGS),
        "errors":        errors,
        "prices":        prices,
    }

    with open("prices.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n=== Done ===")
    print(f"Fetched : {output['fetched']}/{output['total']}")
    print(f"Market  : {output['market']}")
    print(f"Updated : {output['updated']}")
    if errors:
        print(f"Errors  : {errors}")

    # Always exit 0 so the workflow doesn't fail even on partial data
    sys.exit(0)


if __name__ == "__main__":
    main()
