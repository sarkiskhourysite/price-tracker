"""Fetch USD prices of gold, silver, CHF, EUR, JPY, GBP and append a row to data/snapshots.json.
Run by GitHub Actions every 30 minutes. Uses only the Python standard library."""
import json
import time
import urllib.request
from pathlib import Path

SYMBOLS = {
    "XAU": "GC=F",        # gold, USD per oz (futures)
    "XAG": "SI=F",        # silver, USD per oz (futures)
    "CHF": "CHFUSD=X",
    "EUR": "EURUSD=X",
    "JPY": "JPYUSD=X",
    "GBP": "GBPUSD=X",
}
OUT = Path("data/snapshots.json")
MAX_ROWS = 5000


def price(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        meta = json.load(r)["chart"]["result"][0]["meta"]
    return float(meta["regularMarketPrice"])


def main():
    values = {}
    for key, sym in SYMBOLS.items():
        try:
            values[key] = price(sym)
        except Exception as e:  # keep going if one symbol fails
            print(f"{key} ({sym}) failed: {e}")
    if not values:
        raise SystemExit("No prices fetched; nothing saved.")

    OUT.parent.mkdir(exist_ok=True)
    rows = json.loads(OUT.read_text()) if OUT.exists() else []
    rows.append({"t": int(time.time() * 1000), "v": values})
    OUT.write_text(json.dumps(rows[-MAX_ROWS:]))
    print("Saved:", values)


if __name__ == "__main__":
    main()
