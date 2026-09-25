# -*- coding: utf-8 -*-
"""
Download Japan earthquake data from 2 U.S. government sources.
  Source 1: USGS ANSS ComCat  (FDSN Event Web Service)
  Source 2: NOAA/NCEI HazEL   (Significant Earthquake DB + Tsunami DB)

Run:    python scripts/fetch_japan_quake_data.py
Output: data/raw_japan/*.csv
"""
import json, sys, time
from pathlib import Path

import pandas as pd
import requests

# ----- Japan bounding box -----
BOX = {
    "minlatitude": 24, "maxlatitude": 46,
    "minlongitude": 122, "maxlongitude": 150,
}
YEAR_FROM, YEAR_TO = 1990, 2027     # endtime for 2026 = 2027-01-01
MIN_MAG = 4.0                       # below 4.5 to keep aftershocks; the analysis picks Mc later

OUT = Path("data/raw_japan")
OUT.mkdir(parents=True, exist_ok=True)

S = requests.Session()
S.headers.update({"User-Agent": "ADY202m-student-project/1.0"})


def get(url, params=None, tries=4, timeout=120):
    for k in range(tries):
        try:
            r = S.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r
            print(f"    HTTP {r.status_code} (attempt {k+1})")
        except Exception as e:
            print(f"    error {type(e).__name__}: {e} (attempt {k+1})")
        time.sleep(3 * (k + 1))
    return None


# =========================================================
# SOURCE 1 - USGS: chunk by year (limit 20,000 per request)
# =========================================================
print("=" * 62)
print("SOURCE 1 - USGS ANSS ComCat (FDSN Event Web Service)")
print("=" * 62)

USGS = "https://earthquake.usgs.gov/fdsnws/event/1/query"
frames, failed = [], []

for year in range(YEAR_FROM, YEAR_TO):
    p = dict(BOX)
    p.update(format="csv", minmagnitude=MIN_MAG, orderby="time-asc",
             starttime=f"{year}-01-01", endtime=f"{year+1}-01-01")
    r = get(USGS, p)
    if r is None or not r.text.strip():
        print(f"  {year}: FAILED")
        failed.append(year)
        continue
    fp = OUT / f"usgs_{year}.csv"
    fp.write_text(r.text, encoding="utf-8")
    df = pd.read_csv(fp)
    frames.append(df)
    print(f"  {year}: {len(df):>6,} events")
    time.sleep(0.6)

if frames:
    usgs = pd.concat(frames, ignore_index=True)
    usgs = usgs.drop_duplicates(subset="id").sort_values("time")
    usgs.to_csv(OUT / "usgs_japan_1990_2026.csv", index=False)
    print(f"\n  => MERGED: {len(usgs):,} rows x {usgs.shape[1]} columns")
    print(f"     saved: {OUT/'usgs_japan_1990_2026.csv'}")
    for f in OUT.glob("usgs_[0-9]*.csv"):    # per-year chunks, now merged
        f.unlink()
else:
    print("  => NOTHING DOWNLOADED from USGS")
if failed:
    print(f"  !! failed years, run again: {failed}")


# =========================================================
# SOURCE 2 - NOAA/NCEI HazEL
# =========================================================
print()
print("=" * 62)
print("SOURCE 2 - NOAA/NCEI HazEL")
print("=" * 62)

BASE = "https://www.ngdc.noaa.gov/hazel/hazard-service/api/v1"
# several candidate paths because not all could be verified (the tsunami endpoint is rate-limited)
TARGETS = {
    "ncei_earthquakes": [f"{BASE}/earthquakes?country=JAPAN"],
    "ncei_tsunami_events": [
        f"{BASE}/tsunamis/events?country=JAPAN",
        f"{BASE}/tsunamis/events?doubtful=false&country=JAPAN",
        f"{BASE}/tsunami/events?country=JAPAN",
    ],
    "ncei_tsunami_runups": [
        f"{BASE}/tsunamis/runups?country=JAPAN",
        f"{BASE}/tsunamis/runups?doubtful=false&country=JAPAN",
        f"{BASE}/tsunami/runups?country=JAPAN",
    ],
}

for name, urls in TARGETS.items():
    print(f"\n  [{name}]")
    got = False
    for url in urls:
        r = get(url, tries=2, timeout=90)
        if r is None:
            print(f"    failed: {url}")
            continue
        try:
            js = r.json()
        except Exception:
            print(f"    not JSON: {url}")
            continue
        items = js.get("items", js if isinstance(js, list) else None)
        if not items:
            print(f"    empty: {url}")
            continue
        df = pd.json_normalize(items)
        # follow pagination if present
        total_pages = js.get("totalPages", 1) if isinstance(js, dict) else 1
        if total_pages and total_pages > 1:
            for pg in range(2, int(total_pages) + 1):
                sep = "&" if "?" in url else "?"
                r2 = get(f"{url}{sep}page={pg}", tries=2, timeout=90)
                if r2 is None:
                    break
                more = r2.json().get("items", [])
                if not more:
                    break
                df = pd.concat([df, pd.json_normalize(more)], ignore_index=True)
                time.sleep(0.5)
        df.to_csv(OUT / f"{name}.csv", index=False)
        (OUT / f"{name}_raw.json").write_text(
            json.dumps(js, ensure_ascii=False), encoding="utf-8")
        print(f"    OK  {len(df):,} rows x {df.shape[1]} columns  <- {url}")
        print(f"        saved: {OUT / (name + '.csv')}")
        got = True
        break
    if not got:
        print(f"    !! all paths FAILED for {name}")
    time.sleep(1.5)


# =========================================================
print()
print("=" * 62)
print("SUMMARY OF DOWNLOADED FILES")
print("=" * 62)
for f in sorted(OUT.glob("*.csv")):
    try:
        n = sum(1 for _ in f.open(encoding="utf-8", errors="ignore")) - 1
    except Exception:
        n = -1
    print(f"  {f.name:<40} {n:>8,} rows   {f.stat().st_size/1e6:>7.2f} MB")
print("\nDONE.")
