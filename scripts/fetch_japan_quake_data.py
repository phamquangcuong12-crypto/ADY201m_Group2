# -*- coding: utf-8 -*-
"""
Tai du lieu dong dat Nhat Ban tu 2 nguon chinh phu My.
  Nguon 1: USGS ANSS ComCat  (FDSN Event Web Service)
  Nguon 2: NOAA/NCEI HazEL   (Significant Earthquake DB + Tsunami DB)

Chay:  python scripts/fetch_japan_quake_data.py
Ket qua: data/raw_japan/*.csv
"""
import json, sys, time
from pathlib import Path

import pandas as pd
import requests

# ----- Hop bao Nhat Ban -----
BOX = {
    "minlatitude": 24, "maxlatitude": 46,
    "minlongitude": 122, "maxlongitude": 150,
}
YEAR_FROM, YEAR_TO = 1990, 2027     # endtime cua 2026 = 2027-01-01
MIN_MAG = 4.0                       # lay thap hon 4.5 de con du chan; phan tich se chon Mc sau

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
            print(f"    HTTP {r.status_code} (lan {k+1})")
        except Exception as e:
            print(f"    loi {type(e).__name__}: {e} (lan {k+1})")
        time.sleep(3 * (k + 1))
    return None


# =========================================================
# NGUON 1 - USGS: chia chunk theo nam (gioi han 20.000/request)
# =========================================================
print("=" * 62)
print("NGUON 1 - USGS ANSS ComCat (FDSN Event Web Service)")
print("=" * 62)

USGS = "https://earthquake.usgs.gov/fdsnws/event/1/query"
frames, failed = [], []

for year in range(YEAR_FROM, YEAR_TO):
    p = dict(BOX)
    p.update(format="csv", minmagnitude=MIN_MAG, orderby="time-asc",
             starttime=f"{year}-01-01", endtime=f"{year+1}-01-01")
    r = get(USGS, p)
    if r is None or not r.text.strip():
        print(f"  {year}: THAT BAI")
        failed.append(year)
        continue
    fp = OUT / f"usgs_{year}.csv"
    fp.write_text(r.text, encoding="utf-8")
    df = pd.read_csv(fp)
    frames.append(df)
    print(f"  {year}: {len(df):>6,} su kien")
    time.sleep(0.6)

if frames:
    usgs = pd.concat(frames, ignore_index=True)
    usgs = usgs.drop_duplicates(subset="id").sort_values("time")
    usgs.to_csv(OUT / "usgs_japan_1990_2026.csv", index=False)
    print(f"\n  => GOP: {len(usgs):,} dong x {usgs.shape[1]} cot")
    print(f"     luu: {OUT/'usgs_japan_1990_2026.csv'}")
    for f in OUT.glob("usgs_1*.csv"):
        f.unlink()
else:
    print("  => KHONG TAI DUOC GI tu USGS")
if failed:
    print(f"  !! nam that bai, can chay lai: {failed}")


# =========================================================
# NGUON 2 - NOAA/NCEI HazEL
# =========================================================
print()
print("=" * 62)
print("NGUON 2 - NOAA/NCEI HazEL")
print("=" * 62)

BASE = "https://www.ngdc.noaa.gov/hazel/hazard-service/api/v1"
# nhieu duong dan ung vien vi t chua xac minh duoc het (endpoint tsunami bi rate-limit)
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
            print(f"    khong duoc: {url}")
            continue
        try:
            js = r.json()
        except Exception:
            print(f"    khong phai JSON: {url}")
            continue
        items = js.get("items", js if isinstance(js, list) else None)
        if not items:
            print(f"    rong: {url}")
            continue
        df = pd.json_normalize(items)
        # phan trang neu co
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
        print(f"    OK  {len(df):,} dong x {df.shape[1]} cot  <- {url}")
        print(f"        luu: {OUT / (name + '.csv')}")
        got = True
        break
    if not got:
        print(f"    !! THAT BAI het duong dan cho {name}")
    time.sleep(1.5)


# =========================================================
print()
print("=" * 62)
print("TOM TAT FILE DA TAI")
print("=" * 62)
for f in sorted(OUT.glob("*.csv")):
    try:
        n = sum(1 for _ in f.open(encoding="utf-8", errors="ignore")) - 1
    except Exception:
        n = -1
    print(f"  {f.name:<40} {n:>8,} dong   {f.stat().st_size/1e6:>7.2f} MB")
print("\nXONG. Bao lai cho Claude de chay checklist kha thi.")
