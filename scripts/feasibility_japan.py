# -*- coding: utf-8 -*-
"""Feasibility check: 6-step checklist + Gardner-Knopoff declustering + baseline."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

RAW = Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw_japan")
R = 6371.0

def hav(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dp/2)**2 + np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2
    return 2*R*np.arcsin(np.sqrt(np.clip(a, 0, 1)))

def gk_window(m):
    """Gardner-Knopoff 1974: radius (km), time (days)."""
    d = 10**(0.1238*m + 0.983)
    t = np.where(m >= 6.5, 10**(0.032*m + 2.7389), 10**(0.5409*m - 0.547))
    return d, t

def line(c="-", n=64): print(c*n)

# ============ LOAD DATA ============
f = RAW / "usgs_japan_1990_2026.csv"
if not f.exists():
    sys.exit(f"{f} NOT FOUND - run fetch_japan_quake_data.py first")
eq = pd.read_csv(f, parse_dates=["time"], low_memory=False)
eq["time"] = pd.to_datetime(eq["time"], utc=True, errors="coerce")
eq = eq.dropna(subset=["time", "latitude", "longitude", "mag"]).sort_values("time").reset_index(drop=True)

line("="); print("STEP 0 - OVERVIEW OF SOURCE 1 (USGS)"); line("=")
print(f"  rows           : {len(eq):,}")
print(f"  columns        : {eq.shape[1]}")
print(f"  time range     : {eq['time'].min():%Y-%m-%d} -> {eq['time'].max():%Y-%m-%d}")
print(f"  magnitude      : {eq['mag'].min():.1f} -> {eq['mag'].max():.1f}")
print(f"  depth (km)     : {eq['depth'].min():.1f} -> {eq['depth'].max():.1f}")

# ============ STEP 4: near-constant + missing columns ============
line("="); print("STEP 4 - NEAR-CONSTANT / HEAVILY MISSING COLUMNS"); line("=")
rows = []
for c in eq.columns:
    nn = eq[c].notna().sum()
    if nn == 0:
        rows.append((c, 0, 0.0, 100.0, "COMPLETELY EMPTY")); continue
    top = eq[c].value_counts(dropna=True)
    dom = top.iloc[0]/nn*100
    flag = ""
    if dom >= 99: flag = "DROP (>=99% a single value)"
    elif dom >= 95: flag = "warning (>=95%)"
    if (1-nn/len(eq))*100 >= 50: flag = (flag+" ; missing>=50%").strip(" ;")
    rows.append((c, eq[c].nunique(dropna=True), dom, (1-nn/len(eq))*100, flag))
prof = pd.DataFrame(rows, columns=["column","nunique","%most_common","%missing","note"])
print(prof.to_string(index=False, float_format=lambda x: f"{x:6.2f}"))

# ============ Mc: Gutenberg-Richter, maximum curvature ============
line("="); print("MAGNITUDE COMPLETENESS (Mc)"); line("=")
bins = np.arange(np.floor(eq["mag"].min()*10)/10, eq["mag"].max()+0.1, 0.1)
h, _ = np.histogram(eq["mag"], bins=bins)
mc_maxc = bins[np.argmax(h)]
Mc = round(float(mc_maxc) + 0.2, 1)   # maximum curvature + 0.2 (Woessner&Wiemer)
print(f"  histogram mode      : M {mc_maxc:.1f}")
print(f"  chosen Mc (maxc+0.2): M {Mc:.1f}")
for m in [4.0, 4.5, 5.0, 5.5, 6.0]:
    print(f"  M >= {m:.1f} : {(eq['mag']>=m).sum():>7,} events")

# ============ STEPS 1-2: Gardner-Knopoff DECLUSTERING ============
line("="); print("DECLUSTERING Gardner-Knopoff 1974"); line("=")
cat = eq[eq["mag"] >= Mc].reset_index(drop=True).copy()
print(f"  catalog used (M>={Mc}): {len(cat):,} events")

t = cat["time"].values.astype("datetime64[s]").astype(np.int64)
la, lo, mg = cat["latitude"].values, cat["longitude"].values, cat["mag"].values
n = len(cat)
cluster = np.full(n, -1, np.int64)      # -1 = independent/mainshock
order = np.argsort(-mg)                 # descending magnitude

cid = 0
for i in order:
    if cluster[i] != -1:
        continue
    d_km, t_day = gk_window(mg[i])
    t_sec = t_day*86400
    lo_i = np.searchsorted(t, t[i])
    hi_i = np.searchsorted(t, t[i] + int(t_sec))
    if hi_i <= lo_i+1:
        continue
    idx = np.arange(lo_i, hi_i)
    idx = idx[(cluster[idx] == -1) & (mg[idx] < mg[i]) & (idx != i)]
    if idx.size == 0:
        continue
    dist = hav(la[i], lo[i], la[idx], lo[idx])
    hit = idx[dist <= d_km]
    if hit.size:
        cluster[hit] = cid
        cid += 1

cat["is_aftershock"] = cluster != -1
main = cat[~cat["is_aftershock"]].reset_index(drop=True)
print(f"  flagged as aftershocks: {int(cat['is_aftershock'].sum()):,} "
      f"({cat['is_aftershock'].mean()*100:.1f}%)")
print(f"  independent events    : {len(main):,}")
for m in [5.0, 5.5, 6.0, 6.5]:
    print(f"    of which M >= {m:.1f} : {(main['mag']>=m).sum():>6,}  <- independent GROUPS")

# ============ TARGET: aftershocks M>=Mc within 24h, <=100km ============
line("="); print("TARGET - aftershocks within 24h / 100 km"); line("=")
for MS_MIN in [5.0, 5.5, 6.0]:
    ms = main[main["mag"] >= MS_MIN].reset_index(drop=True)
    if len(ms) == 0:
        continue
    cnt = np.zeros(len(ms), np.int64)
    for k in range(len(ms)):
        t0 = np.datetime64(ms.loc[k, "time"].to_datetime64(), "s").astype(np.int64)
        a = np.searchsorted(t, t0); b = np.searchsorted(t, t0 + 86400)
        if b <= a: continue
        idx = np.arange(a, b)
        dist = hav(ms.loc[k,"latitude"], ms.loc[k,"longitude"], la[idx], lo[idx])
        cnt[k] = int(((dist <= 100) & (mg[idx] < ms.loc[k,"mag"])).sum())
    ms["n_after24h"] = cnt
    nz = (cnt > 0).mean()*100
    print(f"\n  [mainshock M >= {MS_MIN}]  n = {len(ms):,} sequences")
    print(f"    with >=1 aftershock : {int((cnt>0).sum()):,} ({nz:.1f}%)")
    print(f"    mean                : {cnt.mean():.2f}   median: {np.median(cnt):.0f}   max: {cnt.max()}")
    print(f"    percentiles 50/75/90/99: {np.percentile(cnt,[50,75,90,99]).round(1)}")
    # naive baseline
    tr = ms[ms["time"].dt.year <= 2015]["n_after24h"]
    te = ms[ms["time"].dt.year > 2015]["n_after24h"]
    if len(tr) and len(te):
        mae_mean = np.abs(te - tr.mean()).mean()
        mae_med  = np.abs(te - tr.median()).mean()
        print(f"    time-split 2015: train {len(tr):,} / test {len(te):,}")
        print(f"    BASELINE MAE (constant = train mean)  : {mae_mean:.3f}")
        print(f"    BASELINE MAE (constant = train median): {mae_med:.3f}")
        if MS_MIN == 5.5:
            ms.to_csv(RAW.parent / "feas_mainshocks_M55.csv", index=False)

# ============ SOURCE 2: NOAA/NCEI ============
line("="); print("SOURCE 2 - NOAA/NCEI + JOIN feasibility"); line("=")
for nm in ["ncei_earthquakes", "ncei_tsunami_events", "ncei_tsunami_runups"]:
    p = RAW / f"{nm}.csv"
    if not p.exists():
        print(f"  {nm:<22} FILE MISSING"); continue
    d = pd.read_csv(p, low_memory=False)
    print(f"  {nm:<22} {len(d):>6,} rows x {d.shape[1]:>3} columns")

pe = RAW / "ncei_earthquakes.csv"
if pe.exists():
    nc = pd.read_csv(pe, low_memory=False)
    nc = nc[nc.get("year", pd.Series(dtype=float)) >= 1990].copy()
    for c in ["month","day","hour","minute"]:
        if c not in nc: nc[c] = 0
    nc["ts"] = pd.to_datetime(dict(
        year=nc["year"], month=nc["month"].fillna(1).replace(0,1),
        day=nc["day"].fillna(1).replace(0,1),
        hour=nc["hour"].fillna(0), minute=nc["minute"].fillna(0)),
        errors="coerce", utc=True)
    nc = nc.dropna(subset=["ts","latitude","longitude"])
    print(f"\n  usable NCEI 1990+: {len(nc):,} events")
    matched, dts = 0, []
    for _, r in nc.iterrows():
        t0 = np.datetime64(r["ts"].to_datetime64(), "s").astype(np.int64)
        a = np.searchsorted(t, t0-3600); b = np.searchsorted(t, t0+3600)
        if b <= a: continue
        idx = np.arange(a, b)
        dist = hav(r["latitude"], r["longitude"], la[idx], lo[idx])
        if (dist <= 150).any():
            matched += 1
            dts.append(abs(t[idx[np.argmin(dist)]] - t0))
    print(f"  JOINED with USGS (+-1h, <=150km): {matched}/{len(nc)} "
          f"({matched/max(len(nc),1)*100:.1f}%)")
    if dts:
        print(f"  median time offset: {np.median(dts):.0f} s")
    for c in ["deaths","deathsTotal","damageMillionsDollars","tsunamiEventId","injuries","housesDestroyed"]:
        if c in nc:
            print(f"    {c:<24} has a value: {nc[c].notna().sum():>4}/{len(nc)}")

line("="); print("DONE"); line("=")
