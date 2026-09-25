-- Nhom 2 - ADY202m - du bao du chan vung Nhat-Kuril
-- Nguon 1: USGS ANSS ComCat | Nguon 2: NOAA/NCEI
-- File nay do Notebook_A tu ghi ra khi chay.

-- ======================================================================
-- Q1_phan_bo_theo_tang_do_sau
-- ======================================================================
SELECT CASE WHEN depth <  30 THEN '1. 0-30 km (vo)'
            WHEN depth <  70 THEN '2. 30-70 km'
            WHEN depth < 150 THEN '3. 70-150 km'
            WHEN depth < 300 THEN '4. 150-300 km'
            ELSE                  '5. 300+ km (sau)' END      AS tang_do_sau,
       COUNT(*)                                               AS so_su_kien,
       ROUND(AVG(mag), 2)                                     AS mag_trung_binh,
       ROUND(MAX(mag), 1)                                     AS mag_lon_nhat,
       ROUND(100.0 * SUM(CASE WHEN is_aftershock THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_la_du_chan
FROM quakes
GROUP BY tang_do_sau
ORDER BY tang_do_sau;

-- ======================================================================
-- Q2_thong_ke_theo_thap_ky
-- ======================================================================
SELECT CAST(FLOOR(YEAR(time) / 10) * 10 AS INTEGER)  AS thap_ky,
       COUNT(*)                                      AS so_su_kien,
       ROUND(AVG(mag), 2)                            AS mag_tb,
       ROUND(STDDEV_SAMP(mag), 2)                    AS mag_sd,
       ROUND(QUANTILE_CONT(mag, 0.5), 2)             AS mag_trung_vi,
       ROUND(AVG(depth), 1)                          AS do_sau_tb,
       COUNT(DISTINCT CAST(time AS DATE))            AS so_ngay_co_su_kien
FROM quakes
GROUP BY thap_ky
ORDER BY thap_ky;

-- ======================================================================
-- Q3_dac_trung_cua_so_24h_RANGE
-- ======================================================================
SELECT id, time, mag, depth,
       COUNT(*)  OVER w24 - 1        AS so_tran_24h_truoc,
       ROUND(MAX(mag) OVER w24, 1)   AS mag_lon_nhat_24h_truoc,
       ROUND(AVG(mag) OVER w24, 2)   AS mag_tb_24h_truoc,
       COUNT(*)  OVER w7d - 1        AS so_tran_7ngay_truoc
FROM quakes
WINDOW w24 AS (ORDER BY time RANGE BETWEEN INTERVAL '24' HOURS PRECEDING AND CURRENT ROW),
       w7d AS (ORDER BY time RANGE BETWEEN INTERVAL  '7' DAYS  PRECEDING AND CURRENT ROW)
ORDER BY so_tran_24h_truoc DESC
LIMIT 20;

-- ======================================================================
-- Q4_kiem_tra_chat_luong
-- ======================================================================
SELECT 'id bi trung'                AS phep_kiem, COUNT(*) AS so_dong_loi FROM (
         SELECT id FROM quakes GROUP BY id HAVING COUNT(*) > 1)
UNION ALL SELECT 'toa do ngoai hop bao', COUNT(*) FROM quakes
          WHERE latitude NOT BETWEEN 24 AND 46 OR longitude NOT BETWEEN 122 AND 150
UNION ALL SELECT 'do sau am',            COUNT(*) FROM quakes WHERE depth < 0
UNION ALL SELECT 'magnitude ngoai [Mc,10]', COUNT(*) FROM quakes WHERE mag < 4.0 OR mag > 10
UNION ALL SELECT 'thieu thoi gian',      COUNT(*) FROM quakes WHERE time IS NULL;

-- ======================================================================
-- Q5_join_hai_nguon
-- ======================================================================
SELECT n.locationName                       AS dia_diem,
       CAST(n.ts AS DATE)                    AS ngay,
       q.mag                                 AS mag_usgs,
       ROUND(q.depth, 1)                     AS do_sau_usgs,
       n.deathsTotal                         AS so_chet,
       n.damageMillionsDollars               AS thiet_hai_trieu_usd,
       CASE WHEN n.tsunamiEventId IS NOT NULL THEN 'co' ELSE 'khong' END AS co_song_than,
       l.d_km                                AS lech_km,
       l.d_giay                              AS lech_giay
FROM link      l
INNER JOIN ncei   n ON n.id = l.ncei_id
INNER JOIN quakes q ON q.id = l.usgs_id
WHERE n.deathsTotal IS NOT NULL OR n.damageMillionsDollars IS NOT NULL
ORDER BY n.deathsTotal DESC NULLS LAST
LIMIT 15;

-- ======================================================================
-- Q6_manh_nhat_moi_thap_ky
-- ======================================================================
SELECT thap_ky, place AS dia_diem, mag, ROUND(depth,1) AS do_sau, CAST(time AS DATE) AS ngay, hang
FROM (SELECT CAST(FLOOR(YEAR(time)/10)*10 AS INTEGER) AS thap_ky, place, mag, depth, time,
             RANK() OVER (PARTITION BY FLOOR(YEAR(time)/10) ORDER BY mag DESC) AS hang
      FROM quakes)
WHERE hang <= 3
ORDER BY thap_ky, hang;

-- ======================================================================
-- Q7_manh_nhat_toan_vung
-- ======================================================================
SELECT CAST(time AS DATE) AS ngay, place AS dia_diem, mag, ROUND(depth,1) AS do_sau_km, magType AS thang_do
FROM quakes
ORDER BY mag DESC
LIMIT 10;

-- ======================================================================
-- Q8_tang_do_sau_tren_muc_chung
-- ======================================================================
SELECT CASE WHEN depth <  30 THEN '0-30 km'   WHEN depth <  70 THEN '30-70 km'
            WHEN depth < 150 THEN '70-150 km' WHEN depth < 300 THEN '150-300 km'
            ELSE '300+ km' END                       AS tang_do_sau,
       COUNT(*)                                      AS so_chuoi,
       ROUND(AVG(n_after24h), 2)                     AS du_chan_tb,
       ROUND(100.0 * AVG(any_after), 1)              AS pct_co_du_chan
FROM mainshocks
GROUP BY tang_do_sau
HAVING AVG(n_after24h) > (SELECT AVG(n_after24h) FROM mainshocks)
ORDER BY du_chan_tb DESC;

-- ======================================================================
-- Q9_khoang_cach_giua_cac_tran
-- ======================================================================
SELECT CAST(time AS DATE) AS ngay, place AS dia_diem, mag,
       ROUND(DATE_DIFF('minute', tran_truoc, time) / 60.0, 2) AS gio_tu_tran_truoc,
       ROUND(DATE_DIFF('minute', time, tran_sau)  / 60.0, 2)  AS gio_den_tran_sau,
       mag_truoc AS mag_tran_truoc
FROM (SELECT time, place, mag,
             LAG(time)  OVER (ORDER BY time) AS tran_truoc,
             LEAD(time) OVER (ORDER BY time) AS tran_sau,
             LAG(mag)   OVER (ORDER BY time) AS mag_truoc
      FROM quakes WHERE mag >= 6.0)
WHERE tran_truoc IS NOT NULL AND tran_sau IS NOT NULL
ORDER BY gio_tu_tran_truoc
LIMIT 15;

