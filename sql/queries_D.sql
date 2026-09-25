-- Group 2 - ADY202m - Notebook_D: NOAA/NCEI three-tier join chain

-- ======================================================================
-- D1_foreign_key_check
-- ======================================================================
SELECT 'earthquake -> tsunami (eq.tsunamiEventId)' AS key_chain,
       COUNT(*) FILTER (WHERE e.tsunamiEventId IS NOT NULL)          AS has_key,
       COUNT(*) FILTER (WHERE t.id IS NOT NULL)                      AS matched,
       COUNT(*)                                                      AS total
FROM ncei_eq e LEFT JOIN ncei_ts t ON t.id = e.tsunamiEventId
UNION ALL
SELECT 'tsunami -> runup (ru.tsunamiEventId)',
       COUNT(*), COUNT(*) FILTER (WHERE t2.id IS NOT NULL), COUNT(*)
FROM ncei_ru r LEFT JOIN ncei_ts t2 ON t2.id = r.tsunamiEventId;

-- ======================================================================
-- D2_full_three_tier_chain
-- ======================================================================
SELECT e.locationName                      AS earthquake,
       e.year                              AS year,
       e.eqMagnitude                       AS magnitude,
       e.deathsTotal                       AS deaths,
       t.maxWaterHeight                    AS max_wave_height_m,
       t.numRunups                         AS n_measurement_points,
       COUNT(r.id)                         AS n_runups_matched,
       ROUND(MAX(r.runupHt), 2)            AS max_runup_m,
       ROUND(AVG(r.runupHt), 2)            AS mean_runup_m
FROM ncei_eq e
INNER JOIN ncei_ts t ON t.id = e.tsunamiEventId
LEFT  JOIN ncei_ru r ON r.tsunamiEventId = t.id
GROUP BY e.locationName, e.year, e.eqMagnitude, e.deathsTotal, t.maxWaterHeight, t.numRunups
HAVING COUNT(r.id) > 0
ORDER BY max_runup_m DESC, year, earthquake
LIMIT 15;

-- ======================================================================
-- D3_runup_by_distance
-- ======================================================================
SELECT CASE WHEN r.distFromSource <  100 THEN '1. under 100 km'
            WHEN r.distFromSource <  300 THEN '2. 100-300 km'
            WHEN r.distFromSource < 1000 THEN '3. 300-1000 km'
            ELSE                              '4. over 1000 km' END AS distance_band,
       COUNT(*)                        AS n_measurement_points,
       ROUND(AVG(r.runupHt), 2)        AS mean_runup_m,
       ROUND(MAX(r.runupHt), 2)        AS max_runup_m,
       ROUND(QUANTILE_CONT(r.runupHt, 0.5), 2) AS median_runup_m
FROM ncei_ru r
WHERE r.runupHt IS NOT NULL AND r.distFromSource IS NOT NULL
GROUP BY distance_band
ORDER BY distance_band;

-- ======================================================================
-- D4_join_both_sources
-- ======================================================================
SELECT m.place                      AS location_usgs,
       CAST(m.time AS DATE)         AS date,
       m.mag                        AS mag_usgs,
       ROUND(m.depth, 1)            AS depth_usgs,
       m.n_after24h                 AS aftershocks_24h,
       e.deathsTotal                AS deaths_noaa,
       e.damageMillionsDollars      AS damage_million_usd,
       CASE WHEN e.tsunamiEventId IS NOT NULL THEN 'yes' ELSE 'no' END AS has_tsunami
FROM usgs_ms m
INNER JOIN link l ON l.usgs_id = m.id
INNER JOIN ncei_eq e ON e.id = l.ncei_id
ORDER BY e.deathsTotal DESC NULLS LAST, m.time
LIMIT 15;

