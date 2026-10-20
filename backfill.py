"""One-time backfill: fetch past prices and merge them into data/snapshots.json.

- last ~58 days  : one point every 30 minutes
- older (up to 1 year): one point per day
Existing rows (collected live) are never changed; backfill only fills the time BEFORE the first existing row.
Uses only the Python standard library."""
import json
import urllib.request
from pathlib import Path

SYMBOLS = {
    "XAU": "GC=F",
    "XAG": "SI=F",
    "CHF": "CHFUSD=X",
    "EUR": "EURUSD=X",
    "JPY": "JPYUSD=X",
    "GBP": "GBPUSD=X",
}
OUT = Path("data/snapshots.json")
MAX_ROWS = 20000
STEP = 1800  # seconds


def fetch(symbol, interval, rng):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?interval={interval}&range={rng}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.load(r)["chart"]["result"][0]
    ts = res.get("timestamp") or []
    closes = res["indicators"]["quote"][0]["close"]
    return [(t, c) for t, c in zip(ts, closes) if c is not None]


def merge(series_30m, series_daily, first_live_ms):
    """series_*: {key: [(unix_seconds, price), ...]}. Returns sorted rows [{t, v}] older than first_live_ms."""
    rows = {}
    # 30-minute part: bucket every bar to its 30-minute slot
    for key, pts in series_30m.items():
        for t, c in pts:
            slot = (t // STEP) * STEP
            rows.setdefault(slot * 1000, {})[key] = round(c, 6)
    # daily part: one row per day (noon UTC), only for days not covered by the 30-minute part
    covered_days = {ms // 1000 // 86400 for ms in rows}
    for key, pts in series_daily.items():
        for t, c in pts:
            day = t // 86400
            if day in covered_days:
                continue
            rows.setdefault((day * 86400 + 43200) * 1000, {})[key] = round(c, 6)
    out = [{"t": t, "v": v} for t, v in sorted(rows.items()) if t < first_live_ms]
    # carry the last known value forward so every row shows all assets
    last = {}
    for r in out:
        for k in SYMBOLS:
            if k in r["v"]:
                last[k] = r["v"][k]
            elif k in last:
                r["v"][k] = last[k]
    return out


def main():
    rows = json.loads(OUT.read_text()) if OUT.exists() else []
    first_live = rows[0]["t"] if rows else 10**15

    s30, sd = {}, {}
    for key, sym in SYMBOLS.items():
        try:
            s30[key] = fetch(sym, "30m", "58d")
        except Exception as e:
            print(f"{key} 30m failed: {e}")
        try:
            sd[key] = fetch(sym, "1d", "1y")
        except Exception as e:
            print(f"{key} 1d failed: {e}")

    old = merge(s30, sd, first_live)
    if not old:
        raise SystemExit("Nothing fetched; data left unchanged.")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps((old + rows)[-MAX_ROWS:]))
    print(f"Added {len(old)} past rows; total {len(old) + len(rows)}.")


if __name__ == "__main__":
    main()
