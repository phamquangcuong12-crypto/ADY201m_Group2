-- Nhom 2 - ADY202m - Notebook_D: chuoi ghep ba tang cua NOAA/NCEI

-- ======================================================================
-- D1_kiem_tra_khoa_ngoai
-- ======================================================================
SELECT 'earthquake -> tsunami (eq.tsunamiEventId)' AS chuoi_khoa,
       COUNT(*) FILTER (WHERE e.tsunamiEventId IS NOT NULL)          AS co_khoa,
       COUNT(*) FILTER (WHERE t.id IS NOT NULL)                      AS ghep_duoc,
       COUNT(*)                                                      AS tong
FROM ncei_eq e LEFT JOIN ncei_ts t ON t.id = e.tsunamiEventId
UNION ALL
SELECT 'tsunami -> runup (ru.tsunamiEventId)',
       COUNT(*), COUNT(*) FILTER (WHERE t2.id IS NOT NULL), COUNT(*)
FROM ncei_ru r LEFT JOIN ncei_ts t2 ON t2.id = r.tsunamiEventId;

-- ======================================================================
-- D2_chuoi_ba_tang_day_du
-- ======================================================================
SELECT e.locationName                      AS tran_dong_dat,
       e.year                              AS nam,
       e.eqMagnitude                       AS magnitude,
       e.deathsTotal                       AS so_chet,
       t.maxWaterHeight                    AS song_cao_nhat_m,
       t.numRunups                         AS so_diem_do,
       COUNT(r.id)                         AS so_runup_ghep_duoc,
       ROUND(MAX(r.runupHt), 2)            AS runup_cao_nhat_m,
       ROUND(AVG(r.runupHt), 2)            AS runup_trung_binh_m
FROM ncei_eq e
INNER JOIN ncei_ts t ON t.id = e.tsunamiEventId
LEFT  JOIN ncei_ru r ON r.tsunamiEventId = t.id
GROUP BY e.locationName, e.year, e.eqMagnitude, e.deathsTotal, t.maxWaterHeight, t.numRunups
HAVING COUNT(r.id) > 0
ORDER BY runup_cao_nhat_m DESC
LIMIT 15;

-- ======================================================================
-- D3_runup_theo_khoang_cach
-- ======================================================================
SELECT CASE WHEN r.distFromSource <  100 THEN '1. duoi 100 km'
            WHEN r.distFromSource <  300 THEN '2. 100-300 km'
            WHEN r.distFromSource < 1000 THEN '3. 300-1000 km'
            ELSE                              '4. tren 1000 km' END AS khoang_cach,
       COUNT(*)                        AS so_diem_do,
       ROUND(AVG(r.runupHt), 2)        AS runup_tb_m,
       ROUND(MAX(r.runupHt), 2)        AS runup_max_m,
       ROUND(QUANTILE_CONT(r.runupHt, 0.5), 2) AS runup_trung_vi_m
FROM ncei_ru r
WHERE r.runupHt IS NOT NULL AND r.distFromSource IS NOT NULL
GROUP BY khoang_cach
ORDER BY khoang_cach;

-- ======================================================================
-- D4_noi_ca_hai_nguon
-- ======================================================================
SELECT m.place                      AS dia_diem_usgs,
       CAST(m.time AS DATE)         AS ngay,
       m.mag                        AS mag_usgs,
       ROUND(m.depth, 1)            AS do_sau_usgs,
       m.n_after24h                 AS so_du_chan_24h,
       e.deathsTotal                AS so_chet_noaa,
       e.damageMillionsDollars      AS thiet_hai_trieu_usd,
       CASE WHEN e.tsunamiEventId IS NOT NULL THEN 'co' ELSE 'khong' END AS co_song_than
FROM usgs_ms m
INNER JOIN link l ON l.usgs_id = m.id
INNER JOIN ncei_eq e ON e.id = l.ncei_id
ORDER BY e.deathsTotal DESC NULLS LAST
LIMIT 15;

