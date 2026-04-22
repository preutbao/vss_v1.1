---
title: Vietcap Smart Screener
emoji: 📈
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
---

# IDX Smart Screener 🇮🇩

Hệ thống sàng lọc và phân tích cổ phiếu định lượng cho thị trường chứng khoán Indonesia (IDX) — xây dựng bằng Python + Plotly Dash, triển khai trên Hugging Face Spaces.

## Tính năng chính

- **966 mã cổ phiếu** — toàn bộ thị trường IDX, 11 nhóm ngành GICS
- **60 tiêu chí lọc** theo 8 nhóm: Thông tin chung · Định giá · Sinh lời · Tăng trưởng · Sức khỏe · Biến động giá & KL · Chỉ báo kỹ thuật · Hành vi thị trường
- **9 trường phái đầu tư** tích hợp: Value (Graham) · Turnaround (Templeton) · Quality (Munger) · GARP (Lynch) · Dividend (Neff) · Piotroski F-Score · CANSLIM (O'Neil) · Growth (Fisher) · Magic Formula (Greenblatt)
- **165 chỉ số** mỗi mã: tài chính, kỹ thuật, VGM scores (thang A–F), Beta, Alpha, RS Rating
- **Tab chi tiết 6 tab**: Tổng quan · Biến động giá (nến/đường/vùng + JCI overlay) · 39 biểu đồ tài chính · Báo cáo BCTC · Chỉ số · Kỹ thuật
- **Xuất PDF 8 trang** chuẩn in ấn
- **Công cụ bổ sung**: Sector Heatmap · So sánh hiệu suất nhiều mã vs JCI · Danh mục đầu tư · Cảnh báo giá

## Cấu trúc dự án

```
├── main.py                          # Entry point (dev + production)
├── convert_to_parquet.py            # Chuyển raw data → Parquet
├── Dockerfile                       # Deploy Hugging Face Spaces
├── requirements.txt
├── data/
│   ├── raw/                         # File Excel/CSV gốc (không commit)
│   └── processed/                   # Cache Parquet (tạo tự động)
├── assets/                          # CSS, JS tĩnh
└── src/
    ├── backend/
    │   ├── data_loader.py           # Load + cache dữ liệu (3 tầng RAM/Parquet/rebuild)
    │   ├── quant_engine.py          # Pipeline tính 165 chỉ số
    │   ├── quant_engine_strategies.py  # Logic 9 trường phái
    │   └── technical_indicators.py  # 44 chỉ báo kỹ thuật vectorized
    ├── callbacks/                   # 18 callback modules
    ├── components/                  # Header, Sidebar
    ├── pages/                       # Layout screener
    └── utils/                       # Biểu đồ nến
```

## Cài đặt & chạy local

```bash
# 1. Clone repo
git clone <repo-url> && cd idx-smart-screener

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Đặt raw data vào data/raw/
#    Cần 4 file:
#      - Dữ liệu lịch sử giá 2019-2026.xlsx (hoặc .csv)
#      - BCTC THEO NĂM.xlsx
#      - BCTC THEO QUÝ.xlsx
#      - Indonesia Index.xlsx

# 4. Chạy — main.py tự động convert raw → Parquet nếu chưa có
python main.py
# → http://127.0.0.1:8050
```

## Deploy Hugging Face Spaces

```bash
# Repo cần có:
#   Dockerfile, main.py, requirements.txt, src/, assets/
#   data/processed/*.parquet  (nên include để tránh convert khi startup)

# Nếu không include Parquet, hệ thống tự chạy convert_to_parquet.py
# khi khởi động lần đầu (cần có data/raw/ trong repo)
```

## Kiến trúc cache dữ liệu

| Tầng | Cơ chế | Thời gian |
|------|--------|-----------|
| RAM | `_snapshot_df` (DataFrame module-level) | < 1ms |
| Disk | `snapshot_cache.parquet` (966 mã × 165 cột) | ~150ms |
| Full rebuild | Chạy lại pipeline khi source thay đổi | ~13–23s |

> **Lưu ý RAM**: snapshot cache dưới dạng DataFrame (~3MB) thay vì `list[dict]` (~9MB). BCTC quý (~100MB) chỉ load khi user mở tab chi tiết, không giữ trong RAM.

## Yêu cầu hệ thống

| | Tối thiểu | Khuyến nghị |
|---|---|---|
| RAM | 2 GB | 4 GB+ |
| CPU | 1 core | 2 core+ |
| Python | 3.11+ | 3.11 |
| Disk | 500 MB | 1 GB+ |

## Nguồn dữ liệu

- **Giá lịch sử**: Yahoo Finance (yfinance) — tự động cập nhật hàng ngày
- **BCTC**: Phòng iBT — Trường Đại học Kinh tế Luật (UEL), ĐHQG-HCM
- **Chỉ số JCI**: Yahoo Finance (`^JKSE`) — tự động cập nhật hàng ngày

## Tech stack

`Dash 2.14` · `Dash AG Grid 31` · `Pandas 2.1` · `NumPy 1.26` · `Plotly 5.18` · `PyArrow 14` · `ReportLab 4` · `Gunicorn 21` · `Docker`