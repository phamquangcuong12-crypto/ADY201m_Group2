# ADY202m, Group 2: Short-term aftershock forecasting for the Japan-Kuril region

This topic replaces the earlier UAV topic (changed with the instructor's approval because the old dataset was not suitable).

## Two data sources, both U.S. federal agencies

| | Source 1 | Source 2 |
|---|---|---|
| Agency | **USGS** (U.S. Geological Survey, Department of the Interior) | **NOAA/NCEI** (Department of Commerce) |
| Dataset | ANSS ComCat via the FDSN Event Web Service | Global Significant Earthquake DB + Global Historical Tsunami DB |
| Original link | https://earthquake.usgs.gov/fdsnws/event/1/ | https://www.ngdc.noaa.gov/hazel/hazard-service/api/v1/ |
| Content | seismic parameters of each event | consequences: deaths, damage, tsunamis, runup |
| Volume | 40,931 events (M≥4.0, 1990-2026) | 429 earthquakes + 385 tsunamis + 12,939 runups |

Downloaded directly from the agency sites, **not** through Kaggle or a re-published copy.

```
python scripts/fetch_japan_quake_data.py
```

## Four research questions

| RQ | Question | Notebook |
|---|---|---|
| RQ1 | How are Japan-Kuril earthquakes distributed? Is depth related to aftershock productivity? | A |
| RQ2 | Does a forecast of aftershocks within 24h beat the naive / physics / Omori-Utsu baselines? | B |
| RQ3 | Do the results hold when changing the threshold, the split, dropping Tohoku, or changing the declustering? | C |
| RQ4 | Which sequences leave real consequences? Joins the three-tier NOAA/NCEI source. | D |

## Structure

```
Notebook_A_Nhom2_Japan_Aftershock.ipynb   Steps 0-3 + RQ1 figures
Notebook_B_Nhom2_Japan_Aftershock.ipynb   Steps 4 + 6a, RQ2
Notebook_C_Nhom2_Japan_Aftershock.ipynb   Steps 6b + 6c, RQ3
Notebook_D_Nhom2_Japan_Aftershock.ipynb   Step 7, RQ4 (second source)
scripts/fetch_japan_quake_data.py         downloads the data from the 2 APIs
data/raw_japan/                           original CSVs
data/processed/                           mainshocks.parquet + manifest.json
report/                                   table_*.csv + fig_*.png
sql/queries.sql, sql/queries_D.sql        13 queries, written by the notebooks
```

Run in order **A → B → C → D**. B/C/D check the SHA-256 of the file handed off by A, so an outdated version cannot be run by mistake.

## Key numbers (run on 2026-09-25)

- Clean catalog: 16,687 events from `Mc = 4.6`; Gutenberg-Richter `b = 1.02`
- Gardner-Knopoff flags 62.3% as aftershocks → **853 mainshock sequences M ≥ 5.5**
- Label: 34.5% of sequences have ≥1 aftershock within 24h / 100 km
- Source match: **97.3%** (108/111), median time offset **0 s** (max 2 s)
- NCEI three-tier join chain: **6,871 rows**, 7,601 runup points, highest **55.88 m**

### RQ2 results

| | Test AUC |
|---|---|
| Naive (majority class) | 0.500 |
| Classic Omori-Utsu (magnitude only) | 0.597 |
| **Extended Omori (magnitude + depth), 2-variable Poisson GLM** | **0.840** |
| Random Forest (magnitude + depth) | **0.846**, with a train-test gap of only **0.035** |

**98% of the improvement comes from adding depth, only 2% from the model type.**

Platt recalibration (2006-2015 window): Brier RF 0.161 → 0.155; extended Omori 0.380 → 0.171. AUC unchanged. Comparing Brier between ML and Omori is only fair after both are calibrated.

### RQ3 results: 6/8 checks ROBUST

- AUC CI95 = [0.788, 0.891]
- Dropping 2011 (Tohoku) entirely: AUC changes by **+0.001** → the conclusion does not depend on one earthquake
- Split by geographic region: AUC 0.821 (vs 0.845 with a time split)
- Changing the declustering parameters: AUC range only 0.020
- Dropping the 158 events with a default depth (10/33/35 km): AUC changes by **+0.009** → the depth signal does not come from filled-in values

**Two weak points, stated openly:**
1. Moving the label to a damaging threshold (M≥5.0/5.5) makes the train-test gap jump from 0.035 to 0.150
2. ML does **not** add anything significant beyond choosing the right variable (p = 0.40 against extended Omori)

## Three limitations to state in the Discussion

1. **USGS is not Japan's primary seismic agency.** JMA is, and the JMA catalog is complete down to ~M2-3 while USGS is only complete from M4.6. This work is a **method demo on a U.S. federal source**, not a tool usable for Japan.
2. **The region includes Russia's Kuril Islands**, so it is called the "Japan-Kuril region".
3. **The main contribution is a finding about the data** (depth controls aftershock productivity in a subduction zone), not a strong model.

## Sentences NOT to write in the report

- ❌ "The group's model is better than the Omori-Utsu law": the two do not use the same amount of input information.
- ❌ "Events not in NCEI are events without consequences": NCEI only records significant events, so absence is missing data.
- ❌ "The model is usable in practice": it has not been compared with ETAS, the model actually used in operations.
