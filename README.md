---
title: Vietcap Smart Screener
emoji: 📈
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
---

# Vietcap Smart Screener 📈

Nền tảng sàng lọc và phân tích cổ phiếu định lượng cho **thị trường chứng khoán Việt Nam** (HOSE · HNX · UPCoM) — xây dựng bằng Python + Plotly Dash, triển khai trên Hugging Face Spaces.

---

## Tính năng chính

### Sàng lọc & Lọc nhanh
- Toàn bộ cổ phiếu 3 sàn **HOSE, HNX, UPCoM** — lọc theo sàn giao dịch riêng biệt
- **60+ tiêu chí lọc** chia thành 8 nhóm, giao diện Wizard 3 cột trực quan
- Bộ lọc dạng slider với histogram phân phối thực tế, badge đếm mã real-time
- Lưu / tải lại bộ lọc cá nhân bất kỳ lúc nào
- Tìm kiếm nhanh theo mã hoặc tên công ty

### 11 Trường phái đầu tư tích hợp
| Trường phái | Tác giả / Nguồn gốc |
|---|---|
| **[Vietcap] Khuyến nghị - Team TVĐT** | Khẩu vị phòng thủ NCN K16 |
| Đầu tư giá trị (Value) | Benjamin Graham |
| Đầu tư phục hồi (Turnaround) | Sir John Templeton |
| Đầu tư chất lượng (Quality) | Charlie Munger / Terry Smith |
| Tăng trưởng giá hợp lý (GARP) | Peter Lynch |
| Cổ tức & Thu nhập (Dividend) | John Neff |
| Piotroski F-Score | Prof. Joseph Piotroski |
| Siêu cổ phiếu CANSLIM | William J. O'Neil |
| Tăng trưởng bền vững (Growth) | Philip A. Fisher |
| Công Thức Kỳ Diệu (Magic Formula) | Joel Greenblatt |

Khi chọn trường phái, hệ thống tự động hiển thị các **thẻ tiêu chí "Tham khảo"** (amber border) với ngưỡng của chiến lược — không ảnh hưởng kết quả lọc cho đến khi người dùng kéo slider.

### Chỉ số & Scoring
- **VGM Score** (Value + Growth + Momentum) — chấm điểm A → F cho từng mã
- **CANSLIM Score** (0–7) — 7 tiêu chí O'Neil chuẩn hoá
- **165+ chỉ số** mỗi mã: tài chính, kỹ thuật, VGM, Beta, Alpha, RS Rating
- **Forward P/E** ước tính tự động dựa trên EPS và tốc độ tăng trưởng

### Tab chi tiết (double-click vào mã)
| Tab | Nội dung |
|---|---|
| **Tổng quan** | Hồ sơ doanh nghiệp, 8 KPI, Báo cáo Sức khoẻ Tài chính (biểu đồ + progress bar) |
| **Biến động giá** | Biểu đồ nến / đường / vùng, MA, RSI, MACD, Volume, Pivot Points, tín hiệu kỹ thuật tổng hợp |
| **Biểu đồ TC** | 30+ biểu đồ tài chính theo template tuỳ chọn (doanh thu, lợi nhuận, FCF, ROE DuPont…) |
| **Tài chính** | Ma trận BCTC: IS / BS / CF theo năm hoặc theo quý (đơn vị triệu VND) |
| **Chỉ số** | 6 nhóm chỉ số (Per Share, Sinh lời, Thanh khoản, Đòn bẩy, Hiệu quả, Tăng trưởng) |
| **Kỹ thuật** | Signal Meter gauge, MA table, Oscillators table, Pivot Points |

### Công cụ bổ sung
- **Sector Heatmap** — treemap vốn hóa toàn thị trường, tô màu theo % thay đổi giá
- **So sánh hiệu suất** — nhiều mã cùng kỳ vs VNINDEX (chuẩn hoá về 100)
- **Danh mục đầu tư** — theo dõi lời/lỗ, so sánh với VNINDEX, lưu vào localStorage
- **Cảnh báo giá** — 10+ loại điều kiện, kiểm tra tự động mỗi 5 phút
- **Xuất CSV / Excel** — kết quả lọc với styling chuyên nghiệp
- **Xuất PDF 8 trang** — báo cáo phân tích đầy đủ (kỹ thuật, tài chính, định giá, xếp hạng)

---

## Cấu trúc dự án

```
├── main.py                              # Entry point (dev + production)
├── convert_to_parquet.py                # Chuyển raw data Excel → Parquet
├── Dockerfile                           # Deploy Hugging Face Spaces
├── requirements.txt
├── data/
│   ├── raw/                             # File Excel gốc (không commit lên git)
│   │   ├── BCTC THEO NĂM.xlsx
│   │   ├── BCTC THEO QUÝ.xlsx
│   │   ├── HISTORICAL PRICES.xlsx
│   │   └── INDEX.xlsx
│   └── processed/                       # Cache Parquet (tạo tự động)
│       ├── snapshot_cache.parquet       # Snapshot 165 chỉ số × toàn bộ mã
│       ├── market_prices.parquet
│       ├── financial_yearly.parquet
│       ├── financial_quarterly.parquet
│       └── index.parquet
├── assets/                              # CSS, JS, ảnh tĩnh
└── src/
    ├── app_instance.py                  # Khởi tạo Dash app
    ├── backend/
    │   ├── data_loader.py               # Cache 3 tầng: RAM / Parquet / rebuild
    │   ├── quant_engine.py              # Pipeline tính 165 chỉ số, VGM Score
    │   ├── quant_engine_strategies.py   # Logic 11 trường phái đầu tư
    │   └── technical_indicators.py      # 44 chỉ báo kỹ thuật vectorized
    ├── callbacks/                        # 18 callback modules
    │   ├── screener_callbacks.py        # Callback chính: lọc + detail modal
    │   ├── filter_interaction_callbacks.py  # Bộ lọc slider, strategy cards
    │   ├── financial_charts_callbacks.py    # 30+ biểu đồ tài chính
    │   ├── heatmap_callbacks.py
    │   ├── compare_callbacks.py
    │   ├── portfolio_callbacks.py
    │   ├── alert_callbacks.py
    │   └── ...
    ├── components/
    │   ├── header.py                    # Navbar + Hero banner
    │   └── sidebar.py                   # Bộ lọc inline, Stores, Wizard panel
    ├── pages/
    │   └── screener.py                  # Layout bảng AG Grid + Detail tabs
    ├── constants/
    │   └── gics_translation.py          # Dịch GICS Sector / Industry sang tiếng Việt
    └── utils/
        ├── chart_module.py              # Biểu đồ nến FireAnt-style
        └── chart_controls.py            # UI controls cho biểu đồ giá
```

---

## Cài đặt & Chạy local

```bash
# 1. Clone repo
git clone <repo-url> && cd vietcap-smart-screener

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Đặt raw data vào data/raw/
#    Cần 4 file:
#      - BCTC THEO NĂM.xlsx
#      - BCTC THEO QUÝ.xlsx
#      - HISTORICAL PRICES.xlsx
#      - INDEX.xlsx

# 4. Chạy — hệ thống tự convert raw → Parquet nếu chưa có
python main.py
# → http://127.0.0.1:8050
```

> **Lưu ý:** Lần đầu chạy khi chưa có Parquet, `main.py` sẽ tự gọi `convert_to_parquet.py` (mất 5–15 phút tuỳ kích thước data). Các lần sau load từ cache Parquet, chỉ mất vài giây.

---

## Kiến trúc cache dữ liệu

```
Request đến
    │
    ▼
[RAM cache] ── hit ──→ return DataFrame (~0ms)
    │ miss
    ▼
[Parquet cache] ── hit ──→ load file → lưu RAM → return (~150ms)
    │ miss / stale
    ▼
[Full rebuild] ── quant_engine pipeline ──→ lưu Parquet → lưu RAM → return (~15–25s)
```

Snapshot cache (`snapshot_cache.parquet`) tự động rebuild khi phát hiện file nguồn (giá, BCTC, code engine) có `mtime` mới hơn file cache.

**Thread safety:** `_snapshot_build_lock` (double-checked locking) đảm bảo dù 100 request đến đồng thời, chỉ đúng 1 lần rebuild được chạy.

---

## Cấu trúc dữ liệu đầu vào

### HISTORICAL PRICES.xlsx
- `Sheet1` — thông tin công ty (Ticker, GICS Sector, Exchange suffix `.HM/.HN/.HNO`)
- Mỗi sheet còn lại — lịch sử giá OHLCV của 1 ticker

### BCTC THEO NĂM.xlsx / BCTC THEO QUÝ.xlsx
- Sheet `COMP` — thông tin doanh nghiệp (Ticker, GICS, Auditor…)
- Các sheet `BS_*`, `IS_*`, `CF_*` — dữ liệu bảng cân đối / kết quả kinh doanh / lưu chuyển tiền tệ

### INDEX.xlsx
- Cột `Date` và cột giá chỉ số VN-Index (dùng làm benchmark)

---

## Deploy lên Hugging Face Spaces

```bash
# Repo cần có:
#   Dockerfile, main.py, requirements.txt, src/, assets/
#   data/processed/*.parquet  (khuyến nghị include để tránh rebuild khi startup)

# Nếu không include Parquet, hệ thống tự chạy convert_to_parquet.py
# khi khởi động lần đầu (cần có data/raw/ trong repo)
```

Biến môi trường Docker (có thể override):

| Biến | Mặc định | Mô tả |
|---|---|---|
| `PORT` | `7860` | Port lắng nghe (HF Spaces yêu cầu 7860) |
| `GUNICORN_WORKERS` | `1` | Số worker (tăng nếu RAM ≥ 8GB) |
| `GUNICORN_THREADS` | `4` | Thread per worker |
| `GUNICORN_TIMEOUT` | `120` | Request timeout (giây) |

---

## Yêu cầu hệ thống

| | Tối thiểu | Khuyến nghị |
|---|---|---|
| RAM | 2 GB | 4 GB+ |
| CPU | 1 core | 2 core+ |
| Python | 3.11+ | 3.11 |
| Disk | 500 MB | 1 GB+ |

---

## Tech stack

`Dash 2.14` · `Dash AG Grid 31` · `Dash DAQ 0.5` · `Pandas 2.1` · `NumPy 1.26` · `SciPy 1.11` · `Plotly 5.18` · `PyArrow 14` · `Matplotlib 3.8` · `Squarify 0.4` · `ReportLab 4` · `OpenPyXL 3.1` · `Gunicorn 21` · `Docker`

---

## Lưu ý vận hành

- **Auto-update yfinance:** Tắt theo mặc định (`AUTO_UPDATE = False` trong `data_loader.py`). Bật lại khi cần cập nhật giá tự động.
- **DEV_MODE:** Đặt `DEV_MODE = True` để chỉ đọc 5 sheet đầu mỗi file (tăng tốc khi debug).
- **Dọn dẹp cache:** Chạy `python clean_session.py` để xóa `__pycache__` trước khi commit.
- **Invalidate snapshot:** Xóa `data/processed/snapshot_cache.parquet` để buộc rebuild toàn bộ pipeline chỉ số.