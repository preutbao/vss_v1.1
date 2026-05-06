---
title: Vietcap Smart Screener
emoji: 📈
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
---

<div align="center">

# 📈 Vietcap Smart Screener

**Nền tảng sàng lọc cổ phiếu định lượng chuyên sâu cho thị trường chứng khoán Việt Nam**

*HOSE · HNX · UPCoM — Powered by Python + Plotly Dash*

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Dash](https://img.shields.io/badge/Dash-2.14-00d4ff?style=for-the-badge&logo=plotly&logoColor=white)](https://dash.plotly.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![HuggingFace](https://img.shields.io/badge/🤗_HuggingFace-Spaces-FFD21E?style=for-the-badge)](https://huggingface.co/spaces/preut/VietcapSmartScreener)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

[🚀 Demo Live](https://huggingface.co/spaces/preut/VietcapSmartScreener) · [📖 Docs](#cài-đặt--chạy-local) · [🐛 Issues](https://github.com/preut/VietcapSmartScreener/issues)

</div>

---

## 🎯 Tại sao VSS?

> *"Trong 1.500+ mã cổ phiếu niêm yết tại Việt Nam, việc tìm ra cổ phiếu đúng theo đúng chiến lược đầu tư của bạn không nên tốn hơn 30 giây."*

VSS là công cụ sàng lọc định lượng **duy nhất tại Việt Nam** tích hợp đồng thời:
- **165+ chỉ số** tài chính & kỹ thuật được tính toán tự động theo thời gian thực
- **10 trường phái đầu tư** kinh điển thế giới, được tham số hoá cho đặc thù thị trường Việt Nam
- **AI Chatbot (VinanceAI)** hỗ trợ phân tích và tư vấn cổ phiếu inline
- Pipeline ETL tự động cập nhật dữ liệu hàng ngày qua GitHub Actions

---

## ✨ Tính năng cốt lõi

### 🔍 Bộ lọc thông minh (Smart Filter Engine)
- **60+ tiêu chí lọc** chia thành 8 nhóm: Tổng quan · Định giá · Sinh lời · Tăng trưởng · Sức khỏe TC · Giá vs SMA · Chỉ báo kỹ thuật · Hành vi thị trường
- Giao diện Wizard 3 cột — chọn nhóm → chọn tiêu chí → kéo slider trực quan
- **Histogram phân phối thực tế** hiển thị bên trên mỗi slider — biết ngay bạn đang lọc ở phân vị nào của toàn thị trường
- Badge đếm số mã thỏa mãn **real-time** khi kéo slider (không cần bấm Apply)
- Lưu / tải lại bộ lọc cá nhân vào localStorage
- Lọc theo **sàn giao dịch** (HOSE / HNX / UPCoM), **ngành** (GICS Sector), **ngành con** (GICS Industry), **năm báo cáo**

### 🏛️ 10 Trường phái đầu tư tích hợp

| # | Trường phái | Tác giả / Nguồn gốc | Mã |
|---|---|---|---|
| 1 | **[Vietcap] Khuyến nghị - Team TVĐT** | Khẩu vị phòng thủ từ Team Vietcap | `STRAT_NCN` |
| 2 | Đầu tư giá trị (Value) | Benjamin Graham | `STRAT_VALUE` |
| 3 | Đầu tư phục hồi (Turnaround) | Sir John Templeton | `STRAT_TURNAROUND` |
| 4 | Đầu tư chất lượng (Quality) | Charlie Munger / Terry Smith | `STRAT_QUALITY` |
| 5 | Tăng trưởng giá hợp lý (GARP) | Peter Lynch | `STRAT_GARP` |
| 6 | Cổ tức & Thu nhập (Dividend) | John Neff | `STRAT_DIVIDEND` |
| 7 | Piotroski F-Score | Prof. Joseph Piotroski | `STRAT_PIOTROSKI` |
| 8 | Siêu cổ phiếu CANSLIM | William J. O'Neil | `STRAT_CANSLIM` |
| 9 | Tăng trưởng bền vững (Growth) | Philip A. Fisher | `STRAT_GROWTH` |
| 10 | Công Thức Kỳ Diệu (Magic Formula) | Joel Greenblatt | `STRAT_MAGIC` |

Khi chọn trường phái, hệ thống tự động hiển thị **thẻ tiêu chí "Tham khảo"** (amber border) với ngưỡng của chiến lược. Kéo slider để kích hoạt lọc thực sự.

### 📊 Hệ thống chấm điểm (Scoring Engine)

| Điểm | Mô tả | Trọng số |
|---|---|---|
| **VGM Score** (A→F) | Value + Growth + Momentum tổng hợp | V: 30% · G: 40% · M: 30% |
| **Value Score** | Dựa trên P/E, P/B, EV/EBITDA, P/S | Percentile rank toàn thị trường |
| **Growth Score** | ROE, ROA, Revenue Growth YoY, EPS Growth YoY | Có điều chỉnh theo ngành (Sector-relative) |
| **Momentum Score** | RS_1M, RS_3M, Perf_1M, Perf_1W | Relative Strength vs VNINDEX |
| **CANSLIM Score** (0–7) | 7 tiêu chí O'Neil chuẩn hoá | Chấm nhị phân từng tiêu chí |
| **Piotroski F-Score** (0–9) | 9 tiêu chí sức khỏe tài chính | Chấm nhị phân từng tiêu chí |

### 📋 Tab chi tiết cổ phiếu (Double-click để mở)

| Tab | Nội dung chi tiết |
|---|---|
| **Tổng quan** | Hồ sơ doanh nghiệp · 8 KPI cards · Báo cáo Sức khỏe Tài chính (biểu đồ lịch sử + progress bars) |
| **Biến động giá** | Biểu đồ nến/đường/vùng · MA/EMA · RSI · MACD · Volume · Pivot Points · Tín hiệu kỹ thuật tổng hợp |
| **Biểu đồ TC** | 30+ biểu đồ tài chính theo template tùy chọn (DT, LN, FCF, ROE DuPont, F-Score…) |
| **Tài chính** | Ma trận BCTC: IS / BS / CF theo năm hoặc quý (đơn vị triệu VND) |
| **Chỉ số** | 6 nhóm chỉ số: Per Share · Sinh lời · Thanh khoản · Đòn bẩy · Hiệu quả · Tăng trưởng |
| **Kỹ thuật** | Signal Meter gauge · MA table · Oscillators table · Pivot Points |

### 🛠️ Công cụ bổ sung

- **🗺️ Sector Heatmap** — Treemap vốn hoá toàn thị trường, tô màu theo % thay đổi giá (1T / 1M / 3M / 1Y)
- **📊 So sánh hiệu suất** — Nhiều mã cùng kỳ vs VNINDEX (chuẩn hoá về 100)
- **💼 Danh mục đầu tư** — Theo dõi lời/lỗ, so sánh với VNINDEX, lưu vào localStorage
- **🔔 Cảnh báo giá** — 10+ loại điều kiện, kiểm tra tự động mỗi 5 phút
- **📤 Xuất CSV / Excel** — Kết quả lọc với styling chuyên nghiệp (zebra striping, header màu)
- **📄 Xuất PDF 8 trang** — Báo cáo phân tích đầy đủ: kỹ thuật, tài chính, định giá, xếp hạng
- **🤖 VinanceAI Chatbot** — Trợ lý đầu tư tích hợp Gemini AI, hiểu ngữ cảnh screener đang dùng

---

## 🏗️ Kiến trúc hệ thống

### Cấu trúc thư mục

```
vietcap-smart-screener/
├── main.py                              # Entry point (dev + production)
├── daily_updater.py                     # ETL pipeline cập nhật giá hàng ngày
├── convert_to_parquet.py                # Chuyển raw data Excel → Parquet
├── Dockerfile                           # Deploy Hugging Face Spaces
├── requirements.txt
├── .github/
│   └── workflows/
│       └── daily_update.yml             # GitHub Actions: chạy ETL lúc 15h, push HF
├── data/
│   ├── raw/                             # File Excel gốc (KHÔNG commit lên git)
│   │   ├── BCTC THEO NĂM.xlsx
│   │   ├── BCTC THEO QUÝ.xlsx
│   │   ├── HISTORICAL PRICES.xlsx
│   │   └── INDEX.xlsx
│   └── processed/                       # Cache Parquet (tạo tự động)
│       ├── snapshot_cache.parquet       # 165+ chỉ số × toàn bộ mã (~1.500 mã)
│       ├── market_prices.parquet        # Lịch sử giá OHLCV
│       ├── financial_yearly.parquet     # BCTC theo năm
│       ├── financial_quarterly.parquet  # BCTC theo quý
│       └── index.parquet                # Dữ liệu VNINDEX
├── assets/                              # CSS, JS, ảnh tĩnh, favicon
└── src/
    ├── app_instance.py                  # Khởi tạo Dash app (theme, fonts, meta)
    ├── backend/
    │   ├── data_loader.py               # Cache 3 tầng: RAM / Parquet / rebuild
    │   ├── quant_engine.py              # Pipeline tính 165+ chỉ số, VGM Score
    │   ├── quant_engine_strategies.py   # Logic 10 trường phái đầu tư
    │   └── technical_indicators.py      # 44 chỉ báo kỹ thuật vectorized
    ├── callbacks/                        # 20 callback modules
    │   ├── screener_callbacks.py        # Callback chính: lọc + detail modal
    │   ├── filter_interaction_callbacks.py  # Bộ lọc slider, strategy cards
    │   ├── financial_charts_callbacks.py    # 30+ biểu đồ tài chính
    │   ├── chatbot_callbacks.py         # VinanceAI — Gemini integration
    │   ├── heatmap_callbacks.py
    │   ├── compare_callbacks.py
    │   ├── portfolio_callbacks.py
    │   ├── alert_callbacks.py
    │   ├── score_breakdown_callbacks.py
    │   ├── auth_callbacks.py
    │   ├── mode_callbacks.py            # Chế độ: Tích sản / Lướt sóng / Toàn TT
    │   └── ...
    ├── components/
    │   ├── header.py                    # Navbar + Hero banner + Login modal
    │   └── sidebar.py                   # Bộ lọc inline, Stores, Wizard panel
    ├── pages/
    │   └── screener.py                  # Layout bảng AG Grid + Detail tabs
    ├── constants/
    │   └── gics_translation.py          # Dịch GICS Sector / Industry → tiếng Việt
    └── utils/
        ├── chart_module.py              # Biểu đồ nến FireAnt-style
        ├── chart_controls.py            # UI controls cho biểu đồ giá
        └── chart_callbacks.py           # Callback biểu đồ nến
```

### Kiến trúc cache dữ liệu (3 tầng)

```
Request đến
    │
    ▼
[RAM cache — _snapshot_df]  ── hit ──→  return DataFrame  (~0ms)
    │ miss
    ▼
[Parquet cache — snapshot_cache.parquet]  ── hit + fresh ──→  load → RAM → return  (~150ms)
    │ miss / stale
    ▼
[Full rebuild — quant_engine pipeline]
    ├── load_market_data()       (~2s)
    ├── load_financial_data()    (~3s)
    ├── calculate_all_scores()   (~10s)
    └── save Parquet → RAM → return  (~15–25s tổng)
```

**Staleness detection:** Snapshot tự động rebuild khi phát hiện `mtime` của bất kỳ file nguồn nào (giá, BCTC, quant_engine.py) mới hơn file cache.

**Thread safety:** `_snapshot_build_lock` (double-checked locking) đảm bảo dù 100 request đến đồng thời, chỉ đúng **1 lần rebuild** được chạy.

### Pipeline cập nhật dữ liệu hàng ngày

```
GitHub Actions (15h00 T2-T6)
    │
    ├── Kiểm tra dữ liệu đã up-to-date?  ──→  Thoát sớm nếu có
    │
    ├── Download ~1.500 mã  (SSI iBoard API  →  fallback VNDirect)
    │   └── Sequential + 450ms delay (chống bị block IP)
    │
    ├── Download VNINDEX
    │
    ├── Merge vào market_prices.parquet
    │
    ├── Xoá snapshot_cache.parquet  (invalidate cache)
    │
    ├── Commit + Push → GitHub (main)
    │
    └── Force push → Hugging Face Spaces (main)
```

---

## 🚀 Cài đặt & Chạy local

### Yêu cầu hệ thống

| | Tối thiểu | Khuyến nghị |
|---|---|---|
| RAM | 2 GB | 4–8 GB |
| CPU | 1 core | 2+ cores |
| Python | 3.11+ | 3.11 |
| Disk | 1 GB | 2 GB+ |

### Bước 1: Clone repo

```bash
git clone https://github.com/preut/VietcapSmartScreener.git
cd VietcapSmartScreener
```

### Bước 2: Cài dependencies

```bash
pip install -r requirements.txt
```

### Bước 3: Chuẩn bị dữ liệu

Đặt 4 file Excel vào thư mục `data/raw/`:

```
data/raw/
├── BCTC THEO NĂM.xlsx          # BCTC theo năm (BS + IS + CF + COMP)
├── BCTC THEO QUÝ.xlsx          # BCTC theo quý
├── HISTORICAL PRICES.xlsx      # Lịch sử giá OHLCV + thông tin công ty (Sheet1)
└── INDEX.xlsx                   # Dữ liệu VNINDEX
```

> **Lần đầu chạy:** `main.py` sẽ tự động gọi `convert_to_parquet.py` để chuyển đổi raw data → Parquet (mất ~5–15 phút). Các lần sau load từ cache chỉ mất vài giây.

### Bước 4: Chạy app

```bash
python main.py
# → http://127.0.0.1:8050
```

### Bước 5 (Tùy chọn): Cấu hình AI Chatbot

Tạo file `.env` tại thư mục gốc:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash
```

---

## 🐳 Deploy với Docker

```bash
# Build image
docker build -t vss-screener .

# Chạy container
docker run -p 7860:7860 \
  -v $(pwd)/data:/app/data \
  -e GEMINI_API_KEY=your_key \
  vss-screener
```

---

## ☁️ Deploy lên Hugging Face Spaces

```bash
# Repo cần có:
#   Dockerfile, main.py, requirements.txt, src/, assets/
#   data/processed/*.parquet  (khuyến nghị để tránh rebuild lúc startup)

# Cấu hình biến môi trường trong HF Space Settings:
#   HF_TOKEN        → token để push tự động từ GitHub Actions
#   GEMINI_API_KEY  → API key cho VinanceAI chatbot
```

**Biến môi trường Docker (có thể override):**

| Biến | Mặc định | Mô tả |
|---|---|---|
| `PORT` | `7860` | Port lắng nghe (HF Spaces yêu cầu 7860) |
| `GUNICORN_WORKERS` | `1` | Số worker (tăng nếu RAM ≥ 8 GB) |
| `GUNICORN_THREADS` | `4` | Thread per worker |
| `GUNICORN_TIMEOUT` | `120` | Request timeout (giây) |

---

## ⚙️ Cấu hình nâng cao

### Chế độ Debug (DEV_MODE)

```python
# src/backend/data_loader.py
DEV_MODE = True   # Chỉ đọc 5 sheet đầu mỗi file → tăng tốc debug
```

### Tắt/Bật auto-update giá (yfinance)

```python
# src/backend/data_loader.py
AUTO_UPDATE = False   # Tắt (mặc định) → dùng daily_updater.py thay thế
```

### Invalidate snapshot cache thủ công

```bash
# Xoá file cache để buộc rebuild toàn bộ pipeline chỉ số
rm data/processed/snapshot_cache.parquet
```

### Dọn dẹp trước khi commit

```bash
python clean_session.py
# Xoá __pycache__, .pytest_cache, .DS_Store
```

---

## 📊 Cấu trúc dữ liệu đầu vào

### HISTORICAL PRICES.xlsx
- `Sheet1` — Thông tin công ty: Ticker, Exchange (`.HM`/`.HN`/`.HNO`), GICS Sector/Industry
- Mỗi sheet còn lại — Lịch sử giá OHLCV của 1 ticker (cột: Ticker, Date, Open, High, Low, Close, Volume)

### BCTC THEO NĂM.xlsx / BCTC THEO QUÝ.xlsx
- Sheet `COMP` — Thông tin doanh nghiệp (Ticker, GICS, Auditor, Founded Year…)
- Các sheet `BS_*` — Bảng cân đối kế toán
- Các sheet `IS_*` — Kết quả kinh doanh
- Các sheet `CF_*` — Lưu chuyển tiền tệ

### INDEX.xlsx
- Cột `Date` + cột giá đóng cửa VNINDEX (`JCI_Close`) — dùng làm benchmark cho RS, Beta, Alpha

---

## 🔧 Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Dash 2.14 · Dash AG Grid 31 · Dash DAQ 0.5 · Plotly 5.18 |
| **UI Components** | Dash Bootstrap Components 1.5 · Font Awesome 6 · Google Fonts (Inter, Sora, Roboto Mono) |
| **Data Processing** | Pandas 2.1 · NumPy 1.26 · SciPy 1.11 · PyArrow 14 |
| **Visualization** | Plotly 5.18 · Matplotlib 3.8 · Squarify 0.4 |
| **File I/O** | OpenPyXL 3.1 · ReportLab 4.0 (PDF) |
| **AI** | Google Generative AI (Gemini 2.0 Flash) |
| **Production Server** | Gunicorn 21 (gthread worker) |
| **Infrastructure** | Docker · GitHub Actions · Hugging Face Spaces |

---

## 📈 Luồng tính toán chỉ số (Quant Engine)

```
df_price (latest snapshot/ticker)
    │
    ├── calculate_financial_metrics()
    │   ├── Smart Mapping (SMART_MAPPING dict) → chuẩn hoá tên cột BCTC
    │   ├── P/E, P/B, P/S, EV/EBITDA, Market Cap
    │   ├── ROE, ROA, Net Margin, Gross Margin, EBIT Margin
    │   ├── D/E, Current Ratio, Net Cash
    │   └── EPS, BVPS, DPS, Dividend Yield
    │
    ├── calculate_growth_metrics()
    │   ├── Revenue Growth YoY, Revenue CAGR 5Y
    │   └── EPS Growth YoY, EPS CAGR 5Y
    │
    ├── calculate_technical_indicators()  [vectorized via groupby]
    │   ├── SMA 5/10/20/50/100/200, Price vs SMA
    │   ├── RSI(14), MACD(12,26,9), BB Width(20)
    │   ├── Beta, Alpha (252 ngày, thinly-traded filter)
    │   ├── RS_3D / RS_1M / RS_3M / RS_1Y / RS_Avg (vs VNINDEX)
    │   ├── Performance 1W/1M/3M/6M/1Y/YTD
    │   ├── 52W High/Low, Pct_From_High/Low_1Y/All
    │   ├── GTGD_1W / GTGD_10D / GTGD_1M
    │   ├── Volume vs SMA 5/10/20/50, Avg_Vol
    │   ├── Consec_Up / Consec_Down
    │   └── Candlestick_Pattern
    │
    ├── calculate_value_score()    → Grade A–F (P/E 35% + P/B 30% + EV/EBITDA 20% + P/S 15%)
    ├── calculate_growth_score()   → Grade A–F (ROE 25% + ROA 15% + Rev Growth 30% + EPS Growth 30%)
    ├── calculate_momentum_score() → Grade A–F (RS_1M 35% + RS_3M 30% + Perf_1M 20% + Perf_1W 15%)
    ├── calculate_vgm_score()      → Grade A–F (V 30% + G 40% + M 30%, staleness adjustment)
    └── calculate_canslim_score()  → Score 0–7
```

---

## 🤝 Đội ngũ phát triển

| Vai trò | Thành viên |
|---|---|
| **Kiến trúc & Backend** | Ngô Cao Nguyên (Lead Developer) |
| **Chiến lược đầu tư** | Ngô Cao Nguyên (K16 · Vietcap TVĐT) |
| **Chiến lược đầu tư** | Phan Đặng Anh Kiệt (K16 · Vietcap TVĐT) |
| **Chiến lược đầu tư** | Cao Huỳnh Tuyết Trân (K16 · Vietcap TVĐT) |

> **Liên hệ tư vấn đầu tư:** 0946 700 605 (Zalo/SMS)

---

## ⚠️ Tuyên bố miễn trừ trách nhiệm

> Toàn bộ thông tin, phân tích, điểm số và kết quả sàng lọc trên nền tảng này **chỉ mang tính chất tham khảo**, không phải khuyến nghị mua/bán cổ phiếu. Nhà đầu tư cần tự thực hiện nghiên cứu và chịu hoàn toàn trách nhiệm cho các quyết định đầu tư của mình.

---

## 📄 License

Dự án được phát hành dưới giấy phép [MIT License](LICENSE).

---

<div align="center">

**Built with ❤️ by Vietcap Smart Screener Team**

*"Dữ liệu không biết nói dối. Nhưng bạn cần công cụ đúng để nghe thấy nó."*

</div>
