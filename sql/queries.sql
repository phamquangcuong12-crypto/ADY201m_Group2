-- Group 2 - ADY202m - aftershock forecasting, Japan-Kuril region
-- Source 1: USGS ANSS ComCat | Source 2: NOAA/NCEI
-- This file is written by Notebook_A when it runs.

-- ======================================================================
-- Q1_depth_band_distribution
-- ======================================================================
SELECT CASE WHEN depth <  30 THEN '1. 0-30 km (crustal)'
            WHEN depth <  70 THEN '2. 30-70 km'
            WHEN depth < 150 THEN '3. 70-150 km'
            WHEN depth < 300 THEN '4. 150-300 km'
            ELSE                  '5. 300+ km (deep)' END     AS depth_band,
       COUNT(*)                                               AS n_events,
       ROUND(AVG(mag), 2)                                     AS mean_mag,
       ROUND(MAX(mag), 1)                                     AS max_mag,
       ROUND(100.0 * SUM(CASE WHEN is_aftershock THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_aftershocks
FROM quakes
GROUP BY depth_band
ORDER BY depth_band;

-- ======================================================================
-- Q2_stats_by_decade
-- ======================================================================
SELECT CAST(FLOOR(YEAR(time) / 10) * 10 AS INTEGER)  AS decade,
       COUNT(*)                                      AS n_events,
       ROUND(AVG(mag), 2)                            AS mean_mag,
       ROUND(STDDEV_SAMP(mag), 2)                    AS sd_mag,
       ROUND(QUANTILE_CONT(mag, 0.5), 2)             AS median_mag,
       ROUND(AVG(depth), 1)                          AS mean_depth,
       COUNT(DISTINCT CAST(time AS DATE))            AS n_days_with_events
FROM quakes
GROUP BY decade
ORDER BY decade;

-- ======================================================================
-- Q3_24h_window_features_RANGE
-- ======================================================================
SELECT id, time, mag, depth,
       COUNT(*)  OVER w24 - 1        AS n_events_prev_24h,
       ROUND(MAX(mag) OVER w24, 1)   AS max_mag_prev_24h,
       ROUND(AVG(mag) OVER w24, 2)   AS mean_mag_prev_24h,
       COUNT(*)  OVER w7d - 1        AS n_events_prev_7d
FROM quakes
WINDOW w24 AS (ORDER BY time RANGE BETWEEN INTERVAL '24' HOURS PRECEDING AND CURRENT ROW),
       w7d AS (ORDER BY time RANGE BETWEEN INTERVAL  '7' DAYS  PRECEDING AND CURRENT ROW)
ORDER BY n_events_prev_24h DESC
LIMIT 20;

-- ======================================================================
-- Q4_quality_checks
-- ======================================================================
SELECT 'duplicate id'               AS check_name, COUNT(*) AS n_bad_rows FROM (
         SELECT id FROM quakes GROUP BY id HAVING COUNT(*) > 1)
UNION ALL SELECT 'coordinates outside bounding box', COUNT(*) FROM quakes
          WHERE latitude NOT BETWEEN 24 AND 46 OR longitude NOT BETWEEN 122 AND 150
UNION ALL SELECT 'negative depth',       COUNT(*) FROM quakes WHERE depth < 0
UNION ALL SELECT 'magnitude outside [Mc,10]', COUNT(*) FROM quakes WHERE mag < 4.0 OR mag > 10
UNION ALL SELECT 'missing time',         COUNT(*) FROM quakes WHERE time IS NULL;

-- ======================================================================
-- Q5_join_two_sources
-- ======================================================================
SELECT n.locationName                       AS location,
       CAST(n.ts AS DATE)                    AS date,
       q.mag                                 AS mag_usgs,
       ROUND(q.depth, 1)                     AS depth_usgs,
       n.deathsTotal                         AS deaths,
       n.damageMillionsDollars               AS damage_million_usd,
       CASE WHEN n.tsunamiEventId IS NOT NULL THEN 'yes' ELSE 'no' END AS has_tsunami,
       l.d_km                                AS offset_km,
       l.d_sec                               AS offset_sec
FROM link      l
INNER JOIN ncei   n ON n.id = l.ncei_id
INNER JOIN quakes q ON q.id = l.usgs_id
WHERE n.deathsTotal IS NOT NULL OR n.damageMillionsDollars IS NOT NULL
ORDER BY n.deathsTotal DESC NULLS LAST
LIMIT 15;

-- ======================================================================
-- Q6_strongest_per_decade
-- ======================================================================
SELECT decade, place AS location, mag, ROUND(depth,1) AS depth, CAST(time AS DATE) AS date, rank
FROM (SELECT CAST(FLOOR(YEAR(time)/10)*10 AS INTEGER) AS decade, place, mag, depth, time,
             RANK() OVER (PARTITION BY FLOOR(YEAR(time)/10) ORDER BY mag DESC) AS rank
      FROM quakes)
WHERE rank <= 3
ORDER BY decade, rank;

-- ======================================================================
-- Q7_strongest_overall
-- ======================================================================
SELECT CAST(time AS DATE) AS date, place AS location, mag, ROUND(depth,1) AS depth_km, magType AS mag_scale
FROM quakes
ORDER BY mag DESC
LIMIT 10;

-- ======================================================================
-- Q8_depth_bands_above_average
-- ======================================================================
SELECT CASE WHEN depth <  30 THEN '0-30 km'   WHEN depth <  70 THEN '30-70 km'
            WHEN depth < 150 THEN '70-150 km' WHEN depth < 300 THEN '150-300 km'
            ELSE '300+ km' END                       AS depth_band,
       COUNT(*)                                      AS n_sequences,
       ROUND(AVG(n_after24h), 2)                     AS mean_aftershocks,
       ROUND(100.0 * AVG(any_after), 1)              AS pct_with_aftershock
FROM mainshocks
GROUP BY depth_band
HAVING AVG(n_after24h) > (SELECT AVG(n_after24h) FROM mainshocks)
ORDER BY mean_aftershocks DESC;

-- ======================================================================
-- Q9_time_between_events
-- ======================================================================
SELECT CAST(time AS DATE) AS date, place AS location, mag,
       ROUND(DATE_DIFF('minute', prev_time, time) / 60.0, 2) AS hours_since_prev,
       ROUND(DATE_DIFF('minute', time, next_time)  / 60.0, 2) AS hours_to_next,
       prev_mag AS mag_prev_event
FROM (SELECT time, place, mag,
             LAG(time)  OVER (ORDER BY time) AS prev_time,
             LEAD(time) OVER (ORDER BY time) AS next_time,
             LAG(mag)   OVER (ORDER BY time) AS prev_mag
      FROM quakes WHERE mag >= 6.0)
WHERE prev_time IS NOT NULL AND next_time IS NOT NULL
ORDER BY hours_since_prev
LIMIT 15;

