# ADY202m — Nhóm 2 — Dự báo dư chấn ngắn hạn vùng Nhật Bản – Kuril

Đề tài thay cho đề tài UAV cũ (đổi có sự đồng ý của giảng viên do dataset cũ không phù hợp).

## Hai nguồn dữ liệu, cả hai đều là cơ quan liên bang Hoa Kỳ

| | Nguồn 1 | Nguồn 2 |
|---|---|---|
| Cơ quan | **USGS** (U.S. Geological Survey, Bộ Nội vụ) | **NOAA/NCEI** (Bộ Thương mại) |
| Bộ dữ liệu | ANSS ComCat qua FDSN Event Web Service | Global Significant Earthquake DB + Global Historical Tsunami DB |
| Link gốc | https://earthquake.usgs.gov/fdsnws/event/1/ | https://www.ngdc.noaa.gov/hazel/hazard-service/api/v1/ |
| Nội dung | tham số địa chấn từng trận | hậu quả: chết người, thiệt hại, sóng thần, runup |
| Khối lượng | 40.930 trận (M≥4.0, 1990–2026) | 429 trận + 385 sóng thần + 12.939 runup |

Tải trực tiếp từ trang cơ quan, **không** qua Kaggle hay bản đăng lại.

```
python scripts/fetch_japan_quake_data.py
```

## Bốn câu hỏi nghiên cứu

| RQ | Nội dung | Notebook |
|---|---|---|
| RQ1 | Động đất vùng Nhật–Kuril phân bố thế nào? Độ sâu có liên quan tới năng suất dư chấn? | A |
| RQ2 | Dự báo có dư chấn trong 24h có thắng mốc naive / vật lý / Omori–Utsu? | B |
| RQ3 | Kết quả có bền khi đổi ngưỡng, đổi cách chia, bỏ Tohoku, đổi cách tách cụm? | C |
| RQ4 | Chuỗi nào để lại hậu quả thật? Ghép nguồn NOAA/NCEI ba tầng. | D |

## Cấu trúc

```
Notebook_A_Nhom2_Japan_Aftershock.ipynb   Bước 0–3 + hình RQ1
Notebook_B_Nhom2_Japan_Aftershock.ipynb   Bước 4 + 6a, RQ2
Notebook_C_Nhom2_Japan_Aftershock.ipynb   Bước 6b + 6c, RQ3
Notebook_D_Nhom2_Japan_Aftershock.ipynb   Bước 7, RQ4 (nguồn thứ hai)
scripts/fetch_japan_quake_data.py         tải dữ liệu từ 2 API
data/raw_japan/                           CSV gốc
data/processed/                           mainshocks.parquet + manifest.json
report/                                   table_*.csv + fig_*.png
sql/queries.sql, sql/queries_D.sql        13 truy vấn, notebook tự ghi ra
```

Chạy theo thứ tự **A → B → C → D**. B/C/D kiểm SHA-256 của file A bàn giao nên không chạy nhầm bản cũ được.

## Số chính (chạy ngày 25/09/2026)

- Catalog sạch: 16.687 trận từ `Mc = 4.6`; hệ số Gutenberg–Richter `b = 1.02`
- Gardner–Knopoff tách được 62,3% là dư chấn → **853 chuỗi trận chính M ≥ 5.5**
- Nhãn: 34,5% chuỗi có ≥1 dư chấn trong 24h / 100 km
- Ghép hai nguồn: **97,3%** (108/111), lệch thời gian trung vị **28 giây**
- Chuỗi ghép ba tầng NCEI: **6.871 dòng**, 7.601 điểm runup, cao nhất **55,88 m**

### Kết quả RQ2

| | AUC test |
|---|---|
| Naive (lớp phổ biến) | 0,500 |
| Omori–Utsu cổ điển (chỉ magnitude) | 0,597 |
| **Omori mở rộng (magnitude + độ sâu), Poisson GLM 2 biến** | **0,840** |
| Random Forest (magnitude + độ sâu) | **0,846** — khoảng cách train−test chỉ **0,035** |

**98% mức cải thiện đến từ việc thêm độ sâu, chỉ 2% từ loại mô hình.**

### Kết quả RQ3 — 5/7 phép kiểm BỀN

- CI95 của AUC = [0,788 – 0,891]
- Bỏ hẳn năm 2011 (Tohoku): AUC đổi **+0,001** → kết luận không phụ thuộc một trận
- Chia theo vùng địa lý: AUC 0,821 (so với 0,845 chia theo thời gian)
- Đổi tham số tách cụm: biến thiên chỉ 0,020

**Hai điểm yếu, ghi rõ không giấu:**
1. Đổi nhãn sang ngưỡng gây hại (M≥5.0/5.5) thì khoảng cách train−test nhảy 0,035 → 0,150
2. ML **không** đóng góp đáng kể ngoài việc chọn đúng biến (p = 0,40 so với Omori mở rộng)

## Ba giới hạn phải nêu trong Discussion

1. **USGS không phải cơ quan địa chấn chính của Nhật** — JMA mới là, và catalog JMA đầy đủ tới ~M2–3 còn USGS chỉ tới M4.6. Bài này là **demo phương pháp trên nguồn liên bang Hoa Kỳ**, không phải công cụ dùng được cho Nhật.
2. **Vùng gồm cả quần đảo Kuril của Nga** nên gọi là "vùng Nhật–Kuril".
3. **Đóng góp chính là một phát hiện về dữ liệu** (độ sâu chi phối năng suất dư chấn ở đới hút chìm), không phải một mô hình mạnh.

## Câu KHÔNG được viết trong report

- ❌ "Mô hình của nhóm tốt hơn định luật Omori–Utsu" — hai bên không dùng cùng lượng thông tin đầu vào.
- ❌ "Trận không có trong NCEI là trận không gây hậu quả" — NCEI chỉ ghi trận đáng kể; vắng mặt là thiếu dữ liệu.
- ❌ "Mô hình dùng được thực tế" — chưa so với ETAS, là mô hình thực sự dùng trong vận hành.
