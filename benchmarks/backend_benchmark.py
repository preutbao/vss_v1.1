# benchmarks/backend_benchmark.py
"""
Benchmark hiệu năng backend FSS
================================
File này bị mất và được dựng lại từ mã mẫu ở MỤC 10 của tài liệu
"Phương pháp kiểm thử và công bố hiệu năng hệ thống FSS" (summarize,
dataframe_fingerprint, benchmark_ram_cache, benchmark_parquet_cache,
environment_info gần như giữ nguyên cấu trúc gốc), bổ sung:

  - Scenario D (Lọc dữ liệu backend) — mục 5.4 PDF, chưa có code mẫu.
  - Scenario H (Cache stampede / thread safety) — mục 5.8 PDF, chưa có code mẫu.
  - Scenario "wifeed_parse" — đo chi phí parse + filter dữ liệu Wifeed
    realtime (KHÔNG có trong PDF gốc — bổ sung riêng cho tính năng mới).
  - Scenario "cache_invalidation" — đo ảnh hưởng của
    wifeed_updater._merge_eod_into_price_parquet() lên data_loader._MARKET_CACHE
    và tính KHÔNG lan truyền của việc invalidation này sang get_snapshot_df()
    (KHÔNG có trong PDF gốc — bổ sung riêng cho tính năng mới).

2 ĐIỂM ĐÃ SỬA so với mã mẫu gốc trong PDF (không phải lỗi của bạn, phát
hiện được trong lúc dựng lại):

  1. `dataframe_fingerprint()` gốc dùng thẳng `pd.util.hash_pandas_object()`
     — hàm này CRASH với `TypeError: unhashable type: 'list'` trên snapshot
     thật, vì cột `Sparkline_30D` được lưu dạng python list (xem
     `data_loader.get_snapshot_df()`, đoạn chuyển ndarray → list cho
     Pyarrow). Bản dựng lại chuẩn hóa các cột list/ndarray thành chuỗi
     TRƯỚC khi hash — vẫn nhạy với thay đổi dữ liệu, chỉ không crash.
  2. `environment_info()` gốc hard-code phiên bản `pandas.__version__` là
     phiên bản DUY NHẤT được ghi — bản dựng lại lấy phiên bản THẬT của
     toàn bộ stack (dash, plotly, pyarrow, gunicorn...) bằng
     `importlib.metadata` tại thời điểm chạy, để báo cáo luôn khớp với
     môi trường THỰC TẾ đang benchmark, không phụ thuộc requirements.txt
     (đã xác nhận requirements.txt gửi kèm là bản CŨ, lệch với JSON kết
     quả benchmark trước — dash 2.14.2 vs dash 3.3.0 thực tế đã chạy).

LƯU Ý QUAN TRỌNG (đọc trước khi diễn giải số liệu — xem thêm mục 14 PDF):
  - Kết quả CHỈ đại diện cho máy/thời điểm chạy benchmark này. Phải chạy
    lại trên môi trường production thật (Gunicorn, không phải dev server)
    để có số liệu công bố chính thức (mục 14.8 PDF).
  - `_snapshot_stale()` trong data_loader.py so sánh mtime của CHÍNH CÁC
    FILE MÃ NGUỒN (data_loader.py, quant_engine.py, technical_indicators.py)
    với snapshot_cache.parquet. Nếu vừa `git pull`/checkout, các file này
    có thể có mtime mới hơn snapshot → Scenario B/A sẽ luôn rơi vào nhánh
    rebuild dù dữ liệu không đổi. Không phải bug của benchmark — đây là
    hành vi thật của hệ thống, cần ghi chú lại trong báo cáo nếu gặp.
  - Scenario "cache_invalidation" và "wifeed_parse" KHÔNG gọi mạng thật
    (không gọi Wifeed API) — dùng dữ liệu mẫu / bản sao file cục bộ, để
    kết quả tái lập được và không tốn quota / vi phạm rate-limit Wifeed.

Cách chạy:
    python benchmarks/backend_benchmark.py
    python benchmarks/backend_benchmark.py --fast     # giảm số vòng lặp để test nhanh
    python benchmarks/backend_benchmark.py --wifeed-sample /path/to/wifeed_output.txt

Cũng có thể import và gọi run_all_benchmarks() từ script khác (dùng bởi
run_all_tests.py ở thư mục gốc dự án).
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import statistics
import sys
import threading
import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import psutil

# ─────────────────────────────────────────────────────────────────────────────
# Setup đường dẫn — cho phép `from src.backend import ...` chạy được dù
# script này nằm trong benchmarks/ (không phải tests/), giống conftest.py
# ─────────────────────────────────────────────────────────────────────────────
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.backend import data_loader          # noqa: E402
from src.backend import wifeed_updater as wu  # noqa: E402

RESULTS_DIR = Path(ROOT_DIR, "benchmark_results")

# Vị trí ứng viên cho file mẫu Wifeed (JSON thô, đúng format response API)
_WIFEED_SAMPLE_CANDIDATES = [
    Path(ROOT_DIR, "benchmarks", "wifeed_output.txt"),
    Path(ROOT_DIR, "benchmarks", "fixtures", "wifeed_output.txt"),
    Path(ROOT_DIR, "data", "samples", "wifeed_output.txt"),
    Path(ROOT_DIR, "wifeed_output.txt"),
]

# Điểm dữ liệu API fetch latency do người dùng tự chạy và cung cấp thủ công
# (KHÔNG được đo bởi script này — xem docstring benchmark_wifeed_parse()).
_MANUAL_WIFEED_API_SAMPLE = {
    "source": "user_reported_manual_run",
    "note": (
        "Do người dùng tự gọi API Wifeed thật và cung cấp thủ công — "
        "KHÔNG phải kết quả đo tự động của script này. N=1, không có "
        "phân phối P50/P95. Không dùng số này để công bố SLA."
    ),
    "recorded_at_vn": "2026-08-29 10:25:00",
    "elapsed_seconds": 2.1,
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS CHUNG (mục 10 PDF)
# ─────────────────────────────────────────────────────────────────────────────

def percentile(values, q):
    return float(np.percentile(values, q))


def summarize(values_ms):
    if not values_ms:
        return {
            "samples": 0, "mean_ms": None, "median_ms": None, "p90_ms": None,
            "p95_ms": None, "p99_ms": None, "min_ms": None, "max_ms": None,
            "std_ms": None,
        }
    return {
        "samples": len(values_ms),
        "mean_ms": statistics.mean(values_ms),
        "median_ms": statistics.median(values_ms),
        "p90_ms": percentile(values_ms, 90),
        "p95_ms": percentile(values_ms, 95),
        "p99_ms": percentile(values_ms, 99),
        "min_ms": min(values_ms),
        "max_ms": max(values_ms),
        "std_ms": statistics.pstdev(values_ms),
    }


def dataframe_fingerprint(df: pd.DataFrame) -> int:
    """
    Băm nội dung DataFrame để kiểm tra tính nhất quán giữa các lần đọc/build.

    [FIX so với mã mẫu gốc — xem docstring đầu file]: chuẩn hóa các cột
    kiểu list/ndarray (vd Sparkline_30D) thành chuỗi trước khi hash, vì
    pd.util.hash_pandas_object() không hash được object dtype chứa list.
    """
    if df is None or df.empty:
        return 0
    df_hashable = df.copy()
    for col in df_hashable.columns:
        if df_hashable[col].dtype == object:
            sample = df_hashable[col].dropna()
            if not sample.empty and isinstance(sample.iloc[0], (list, np.ndarray, dict)):
                df_hashable[col] = df_hashable[col].apply(
                    lambda x: str(list(x)) if isinstance(x, (list, np.ndarray))
                    else (str(x) if isinstance(x, dict) else x)
                )
    hashed = pd.util.hash_pandas_object(df_hashable.sort_index(axis=1), index=True)
    return int(hashed.sum())


def _pkg_version(name: str) -> str:
    try:
        import importlib.metadata as ilmd
        return ilmd.version(name)
    except Exception:
        try:
            mod = __import__(name)
            return getattr(mod, "__version__", "unknown")
        except Exception:
            return "not_installed"


def environment_info():
    """
    [MỞ RỘNG so với mã mẫu PDF] Lấy phiên bản THẬT của toàn bộ stack tại
    thời điểm chạy (importlib.metadata), không hard-code — tránh lệch với
    requirements.txt (đã xác nhận requirements.txt là bản cũ, không phản
    ánh môi trường thật đã dùng để chạy benchmark trước đây: dash 2.14.2
    (file) vs dash 3.3.0 (JSON benchmark thật đã công bố)).
    """
    process = psutil.Process(os.getpid())
    vm = psutil.virtual_memory()

    files_info = {}
    for key in ("parquet_snapshot", "parquet_price", "parquet_financial_y", "parquet_financial_q"):
        fname = data_loader.FILES.get(key)
        if not fname:
            continue
        fpath = Path(data_loader.PROCESSED_DIR, fname)
        files_info[f"{key}_mb"] = round(fpath.stat().st_size / 1024**2, 3) if fpath.exists() else None

    return {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "cpu_model": platform.processor() or platform.machine(),
        "cpu_physical": psutil.cpu_count(logical=False),
        "cpu_logical": psutil.cpu_count(logical=True),
        "total_ram_gb": round(vm.total / 1024**3, 2),
        "available_ram_gb": round(vm.available / 1024**3, 2),
        "process_rss_mb": round(process.memory_info().rss / 1024**2, 2),
        "pandas_version": pd.__version__,
        "numpy_version": np.__version__,
        "pyarrow_version": _pkg_version("pyarrow"),
        "dash_version": _pkg_version("dash"),
        "plotly_version": _pkg_version("plotly"),
        "gunicorn_version": _pkg_version("gunicorn"),
        "psutil_version": _pkg_version("psutil"),
        "storage_type": "chưa xác nhận thủ công — ghi tay vào báo cáo (SSD/NVMe/HDD)",
        "test_environment": "chưa xác nhận — ghi tay (local dev / staging / production Gunicorn)",
        "files": files_info,
        "requirements_txt_warning": (
            "requirements.txt trong repo được xác nhận là bản CŨ (chưa update). "
            "KHÔNG dùng requirements.txt để ghi phiên bản vào báo cáo — dùng "
            "các trường *_version phía trên (đọc trực tiếp từ môi trường đang chạy)."
        ),
    }


@contextmanager
def measure_stage(label: str, sink: dict):
    t0 = time.perf_counter_ns()
    try:
        yield
    finally:
        sink[label] = (time.perf_counter_ns() - t0) / 1_000_000


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO A — RAM cache hit (mục 5.1 PDF)
# ─────────────────────────────────────────────────────────────────────────────

def benchmark_ram_cache(iterations: int = 1000) -> dict:
    df = data_loader.get_snapshot_df()
    if df is None or df.empty:
        return {"error": "get_snapshot_df() trả về rỗng — kiểm tra dữ liệu trước khi benchmark."}

    expected_shape = df.shape
    expected_hash = dataframe_fingerprint(df)

    durations = []
    error_count = 0
    for _ in range(iterations):
        start = time.perf_counter_ns()
        result = data_loader.get_snapshot_df()
        end = time.perf_counter_ns()
        if result.shape != expected_shape or dataframe_fingerprint(result) != expected_hash:
            error_count += 1
        durations.append((end - start) / 1_000_000)

    summary = summarize(durations)
    summary.update({
        "error_rate": error_count / iterations if iterations else 0.0,
        "snapshot_rows": expected_shape[0],
        "snapshot_cols": expected_shape[1],
        "consistency_hash": expected_hash,
    })
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO B — Parquet cache hit (mục 5.2 PDF)
# ─────────────────────────────────────────────────────────────────────────────

def benchmark_parquet_cache(iterations: int = 30) -> dict:
    snapshot_path = Path(data_loader.PROCESSED_DIR, data_loader.FILES["parquet_snapshot"])
    if not snapshot_path.exists():
        return {"error": f"Không tìm thấy {snapshot_path} — chạy get_snapshot_df() một lần trước."}

    durations = []
    shapes = []
    fingerprints = []
    for _ in range(iterations):
        with data_loader._snapshot_lock:
            data_loader._snapshot_df = None
        gc.collect()

        start = time.perf_counter_ns()
        result = data_loader.get_snapshot_df()
        end = time.perf_counter_ns()

        durations.append((end - start) / 1_000_000)
        shapes.append(result.shape)
        fingerprints.append(dataframe_fingerprint(result))

    shape_consistent = len(set(shapes)) == 1
    hash_consistent = len(set(fingerprints)) == 1

    # [Theo mục 5.2 PDF] "cold" và "warm" filesystem cache không được đánh
    # đồng. Lần đọc ĐẦU TIÊN trong vòng lặp trên có khả năng cao nhất là
    # cold (OS chưa cache file); các lần sau gần như chắc chắn là warm vì
    # cùng file vừa được đọc. Ta báo cáo riêng, không gộp percentile.
    first_read_ms = durations[0] if durations else None
    warm_reads = durations[1:] if len(durations) > 1 else []

    return {
        "all_reads": summarize(durations),
        "first_read_ms_likely_cold": first_read_ms,
        "warm_reads": summarize(warm_reads),
        "shape_consistent": shape_consistent,
        "hash_consistent": hash_consistent,
        "note": (
            "'first_read_ms_likely_cold' KHÔNG đảm bảo cold thật (OS page "
            "cache có thể đã warm từ trước lần chạy benchmark này — vd IDE, "
            "lệnh cat, backup tool). Muốn cold thật cần drop OS cache thủ "
            "công (vd `sync; echo 3 > /proc/sys/vm/drop_caches` trên Linux, "
            "cần quyền root) TRƯỚC khi chạy scenario này, hoặc restart máy."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO D — Lọc dữ liệu trên backend (mục 5.4 PDF — không có code mẫu)
# ─────────────────────────────────────────────────────────────────────────────

def _time_filter(fn, df, iterations):
    durations = []
    output_rows_set = set()
    error_count = 0
    for _ in range(iterations):
        start = time.perf_counter_ns()
        try:
            out = fn(df)
            output_rows_set.add(len(out))
        except Exception:
            error_count += 1
            out = None
        end = time.perf_counter_ns()
        durations.append((end - start) / 1_000_000)
    summary = summarize(durations)
    summary["error_rate"] = error_count / iterations if iterations else 0.0
    summary["output_rows"] = output_rows_set.pop() if len(output_rows_set) == 1 else sorted(output_rows_set)
    return summary


def benchmark_filter_scenarios(iterations: int = 200) -> dict:
    """
    5 truy vấn chuẩn theo mục 5.4 PDF. Điều kiện lọc được xây dựng PHÒNG
    THỦ (chỉ áp dụng nếu cột tồn tại) và dùng NGƯỠNG THEO PHÂN VỊ của
    chính snapshot hiện tại (không hard-code số tuyệt đối) để kịch bản
    luôn có ý nghĩa dù dữ liệu/thị trường thay đổi theo thời gian.
    """
    df = data_loader.get_snapshot_df()
    if df is None or df.empty:
        return {"error": "get_snapshot_df() trả về rỗng — kiểm tra dữ liệu trước khi benchmark."}

    def q(col, pct, min_valid_ratio=0.05):
        """
        Trả về ngưỡng phân vị, hoặc None nếu cột thiếu / dữ liệu hợp lệ SAU
        pd.to_numeric() quá ít để phân vị có ý nghĩa.

        [FIX — bug phát hiện lúc chạy thật]: bản trước dùng `default=10.0`
        cố định khi series rỗng. Nếu cột (vd 'ROE (%)') gần như toàn NaN sau
        to_numeric ở snapshot thật, threshold=10.0 vẫn được áp lên `series >
        10.0` trên CHÍNH cột toàn-NaN đó → NaN > 10.0 luôn False cho mọi
        dòng → output_rows = 0 một cách ĐÁNH LỪA (trông như "không mã nào
        đạt điều kiện" trong khi thực ra là benchmark không lọc được gì).
        Từ giờ: không đủ dữ liệu hợp lệ (< min_valid_ratio) → trả None →
        nơi gọi phải bỏ qua điều kiện đó (coi như không lọc), giống Q5.
        """
        if col not in df.columns:
            return None
        series = pd.to_numeric(df[col], errors="coerce")
        valid = series.dropna()
        if len(df) == 0 or len(valid) / len(df) < min_valid_ratio:
            return None
        return float(valid.quantile(pct))

    def _column_health(col):
        if col not in df.columns:
            return {"exists": False}
        raw_dtype = str(df[col].dtype)
        numeric = pd.to_numeric(df[col], errors="coerce")
        non_null = int(numeric.notna().sum())
        return {
            "exists": True,
            "raw_dtype": raw_dtype,
            "non_null_after_to_numeric": non_null,
            "non_null_pct": round(non_null / len(df) * 100, 2) if len(df) else 0.0,
            "sample_raw_values": [repr(v) for v in df[col].dropna().head(3).tolist()],
        }

    results = {}

    # Chẩn đoán sức khỏe các cột số dùng trong Q2/Q3/Q5 — để BẤT KỲ anomaly
    # nào giống bug trên (output_rows=0 bất thường) đều tự giải thích được
    # ngay trong kết quả JSON, không cần đoán mò lại từ đầu.
    results["_column_health"] = {
        col: _column_health(col)
        for col in ["ROE (%)", "P/E", "P/B", "D/E", "Market Cap", "Volume",
                    "Exchange", "Sector", "Date"]
    }

    # Q1 — không lọc gì, trả toàn bộ thị trường
    results["Q1_no_filter"] = _time_filter(lambda d: d, df, iterations)

    # Q2 — một điều kiện số (ROE > ngưỡng median → khoảng nửa thị trường).
    # Nếu ROE (%) không đủ dữ liệu hợp lệ để tính median có ý nghĩa (xem
    # _column_health['ROE (%)'] để biết vì sao), Q2 trả nguyên df (giống
    # Q1) thay vì áp 1 threshold vô nghĩa.
    roe_thresh = q("ROE (%)", 0.5)
    def _q2(d):
        if roe_thresh is None or "ROE (%)" not in d.columns:
            return d
        return d[pd.to_numeric(d["ROE (%)"], errors="coerce") > roe_thresh]
    results["Q2_single_roe"] = _time_filter(_q2, df, iterations)

    # Q3 — 5 điều kiện thuộc nhiều nhóm, ngưỡng RỘNG (percentile thấp) để
    # gần như KHÔNG loại ai — mô phỏng đúng hành vi Q3 trong JSON cũ
    # (output_rows == toàn bộ thị trường).
    def _q3(d):
        mask = pd.Series(True, index=d.index)
        conds = [
            ("P/E", 0.01, "gt"), ("ROE (%)", 0.01, "gt"),
            ("Market Cap", 0.01, "gt"), ("Volume", 0.01, "gt"),
            ("D/E", 0.99, "lt"),
        ]
        for col, pct, op in conds:
            if col not in d.columns:
                continue
            thresh = q(col, pct)
            if thresh is None:
                continue
            series = pd.to_numeric(d[col], errors="coerce")
            mask &= (series > thresh) if op == "gt" else (series < thresh)
        return d[mask]
    results["Q3_five_conditions"] = _time_filter(_q3, df, iterations)

    # Q4 — lọc theo sàn + ngành + năm báo cáo -> tập con nhỏ, chọn lọc
    def _q4(d):
        mask = pd.Series(True, index=d.index)
        if "Exchange" in d.columns:
            top_exchange = d["Exchange"].mode()
            if not top_exchange.empty:
                mask &= d["Exchange"] == top_exchange.iloc[0]
        if "Sector" in d.columns:
            top_sector = d.loc[mask, "Sector"].mode() if mask.any() else d["Sector"].mode()
            if not top_sector.empty:
                mask &= d["Sector"] == top_sector.iloc[0]
        if "Date" in d.columns:
            years = pd.to_datetime(d["Date"], errors="coerce").dt.year
            latest_year = years.max()
            if pd.notna(latest_year):
                mask &= years == latest_year
        return d[mask]
    results["Q4_exchange_sector"] = _time_filter(_q4, df, iterations)

    # Q5 — bộ lọc phức tạp 10-15 điều kiện (ngưỡng rất rộng) + sắp xếp
    def _q5(d):
        mask = pd.Series(True, index=d.index)
        candidate_cols = [
            "P/E", "P/B", "P/S", "EV/EBITDA", "ROE (%)", "ROA (%)",
            "D/E", "Dividend Yield (%)", "Market Cap", "Volume",
            "EPS Growth YoY (%)", "Revenue Growth YoY (%)", "Avg_Vol_20D",
        ]
        used = 0
        for col in candidate_cols:
            if col not in d.columns or used >= 15:
                continue
            thresh = q(col, 0.005)
            if thresh is None:
                continue
            series = pd.to_numeric(d[col], errors="coerce")
            mask &= series >= thresh
            used += 1
        out = d[mask]
        sort_col = "Market Cap" if "Market Cap" in out.columns else out.columns[0]
        return out.sort_values(sort_col, ascending=False)
    results["Q5_complex_10conds"] = _time_filter(_q5, df, iterations)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO H — Cache stampede / thread safety (mục 5.8 PDF — không có code mẫu)
# ─────────────────────────────────────────────────────────────────────────────

def benchmark_thread_safety(n_threads: int = 20, timeout_s: float = 180.0) -> dict:
    """
    Xóa RAM + Parquet snapshot, bắn n_threads gọi get_snapshot_df() ĐỒNG
    THỜI (dùng threading.Barrier để tối đa hóa khả năng va chạm thật),
    kiểm tra _build_snapshot_df() chỉ chạy đúng 1 lần.

    An toàn: sao lưu snapshot_cache.parquet TRƯỚC khi xóa, phục hồi lại
    (hoặc giữ nguyên bản build mới nếu build thành công) trong finally.
    KHÔNG được chạy song song với các scenario khác dùng chung
    _snapshot_df (chạy cuối cùng trong run_all_benchmarks()).
    """
    snap_path = Path(data_loader.PROCESSED_DIR, data_loader.FILES["parquet_snapshot"])
    backup_path = snap_path.with_suffix(".bench_backup.parquet")

    had_original = snap_path.exists()
    if had_original:
        import shutil
        shutil.copy2(snap_path, backup_path)

    build_count = {"n": 0}
    build_lock = threading.Lock()
    original_build = data_loader._build_snapshot_df

    def counting_build():
        with build_lock:
            build_count["n"] += 1
        return original_build()

    thread_results = {}
    thread_errors = []

    def worker(barrier, idx):
        t_wait_start = time.perf_counter()
        try:
            barrier.wait(timeout=30)
        except threading.BrokenBarrierError:
            thread_errors.append(f"thread-{idx}: barrier broken (timeout chờ các thread khác)")
            return
        t_start = time.perf_counter()
        try:
            df = data_loader.get_snapshot_df()
            t_end = time.perf_counter()
            thread_results[idx] = {
                "wait_s": round(t_start - t_wait_start, 4),
                "get_s": round(t_end - t_start, 4),
                "shape": df.shape,
                "fingerprint": dataframe_fingerprint(df),
            }
        except Exception as e:
            thread_errors.append(f"thread-{idx}: {e}")

    try:
        with data_loader._snapshot_lock:
            data_loader._snapshot_df = None
        if snap_path.exists():
            snap_path.unlink()

        data_loader._build_snapshot_df = counting_build

        barrier = threading.Barrier(n_threads)
        threads = [threading.Thread(target=worker, args=(barrier, i)) for i in range(n_threads)]

        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=timeout_s)
        total_time_s = time.perf_counter() - t0

        alive = [t for t in threads if t.is_alive()]
        deadlock_count = len(alive)

        shapes = {r["shape"] for r in thread_results.values()}
        hashes = {r["fingerprint"] for r in thread_results.values()}

        return {
            "n_threads": n_threads,
            "build_count": build_count["n"],
            "error_count": len(thread_errors),
            "errors": thread_errors[:10],
            "deadlock_count": deadlock_count,
            "total_time_s": round(total_time_s, 3),
            "shape_consistent": len(shapes) <= 1,
            "hash_consistent": len(hashes) <= 1,
            "threads_completed": len(thread_results),
            "pass": (
                build_count["n"] == 1
                and len(thread_errors) == 0
                and deadlock_count == 0
                and len(shapes) <= 1
                and len(hashes) <= 1
                and len(thread_results) == n_threads
            ),
            "note": (
                "threading.Lock/Barrier chỉ đồng bộ trong CÙNG 1 process. "
                "Nếu Gunicorn chạy nhiều worker, mỗi worker có lock riêng — "
                "'build_count == 1' chỉ đúng trong phạm vi 1 process (mục 5.8 PDF)."
            ),
        }
    finally:
        data_loader._build_snapshot_df = original_build
        # Khôi phục trạng thái: nếu build mới trong test đã thành công và
        # ghi snapshot mới, GIỮ NGUYÊN (dữ liệu vẫn đúng, chỉ là build lại
        # từ cùng nguồn). Chỉ khôi phục từ backup nếu benchmark làm mất
        # file mà không build lại được (vd tất cả thread lỗi).
        if had_original and not snap_path.exists() and backup_path.exists():
            import shutil
            shutil.copy2(backup_path, snap_path)
        if backup_path.exists():
            backup_path.unlink()
        with data_loader._snapshot_lock:
            data_loader._snapshot_df = None  # ép lần gọi tiếp theo đọc lại từ đĩa, tránh state bẩn


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO MỚI 1 — wifeed_parse: chi phí parse + filter response Wifeed
# ─────────────────────────────────────────────────────────────────────────────

def _find_wifeed_sample(explicit_path: str | None = None) -> Path | None:
    if explicit_path:
        p = Path(explicit_path)
        return p if p.exists() else None
    for candidate in _WIFEED_SAMPLE_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def benchmark_wifeed_parse(iterations: int = 100, sample_path: str | None = None) -> dict:
    """
    Đo chi phí THUẦN CPU của việc parse + filter 1 response Wifeed
    (~1500-1700 mã, 1 lần gọi API duy nhất) — KHÔNG bao gồm thời gian
    mạng (HTTP request). Thời gian mạng là biến độc lập, không tái lập
    được qua benchmark cục bộ (phụ thuộc Wifeed server, băng thông...) —
    xem `manual_api_fetch_sample` trong kết quả trả về: đây là 1 điểm dữ
    liệu do người dùng TỰ chạy và cung cấp thủ công (N=1), không phải kết
    quả benchmark tự động.
    """
    path = _find_wifeed_sample(sample_path)
    if path is None:
        return {
            "error": (
                "Không tìm thấy file mẫu wifeed_output.txt. Đặt file tại "
                "benchmarks/wifeed_output.txt hoặc truyền --wifeed-sample <path>."
            ),
            "searched_paths": [str(p) for p in _WIFEED_SAMPLE_CANDIDATES],
        }

    raw_text = path.read_text(encoding="utf-8")
    payload = json.loads(raw_text)
    data = payload.get("data", payload) if isinstance(payload, dict) else payload

    if not isinstance(data, list) or not data:
        return {"error": f"File mẫu '{path}' không đúng format response Wifeed (thiếu 'data': [...])."}

    parse_all_durations = []
    parse_stocks_durations = []
    n_all, n_stocks, n_index = None, None, None
    error_count = 0

    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        try:
            df_all = wu._parse_wifeed_response_all(data)
        except Exception:
            error_count += 1
            continue
        t1 = time.perf_counter_ns()
        df_stocks = wu._parse_wifeed_response(data)
        t2 = time.perf_counter_ns()

        parse_all_durations.append((t1 - t0) / 1_000_000)
        parse_stocks_durations.append((t2 - t1) / 1_000_000)
        n_all, n_stocks = len(df_all), len(df_stocks)
        n_index = int(df_all["Ticker"].isin(
            ["VNINDEX", "VN30", "HNXINDEX", "HNX30", "UPCOM"]
        ).sum()) if "Ticker" in df_all.columns else None

    return {
        "sample_file": str(path),
        "raw_records": len(data),
        "parse_all_ms": summarize(parse_all_durations),
        "parse_and_filter_stocks_ms": summarize(parse_stocks_durations),
        "error_rate": error_count / iterations if iterations else 0.0,
        "output_rows": {
            "total_all_symbols": n_all,
            "stocks_with_ceiling": n_stocks,
            "index_symbols_found": n_index,
            "excluded_no_ceiling": (n_all - n_stocks) if (n_all is not None and n_stocks is not None) else None,
        },
        "manual_api_fetch_sample": _MANUAL_WIFEED_API_SAMPLE,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO MỚI 2 — cache_invalidation: _merge_eod_into_price_parquet() ảnh
# hưởng thế nào lên data_loader._MARKET_CACHE và get_snapshot_df()
# ─────────────────────────────────────────────────────────────────────────────

def benchmark_cache_invalidation(
    warm_iterations: int = 300,
    reload_iterations: int = 20,
    merge_iterations: int = 5,
) -> dict:
    """
    Chạy TRÊN BẢN SAO tạm thời của market_prices.parquet (không đụng file
    thật) để đo 3 chỉ tiêu:

      1. market_cache_warm_hit_ms  — load_market_data() khi _MARKET_CACHE
         đang HIT (chỉ là dict lookup, kỳ vọng ~0ms).
      2. market_cache_reload_after_invalidate_ms — chi phí đọc lại toàn bộ
         parquet giá SAU KHI _MARKET_CACHE bị clear (giống hành vi thật
         của _merge_eod_into_price_parquet() mỗi lần EOD được append).
      3. merge_eod_write_ms — chi phí GHI thật của
         _merge_eod_into_price_parquet() (đọc parquet cũ + upsert + ghi
         lại + clear cache).

    Đồng thời kiểm chứng 1 rủi ro đã ghi trong tài liệu nội bộ dự án:
    _merge_eod_into_price_parquet() chỉ clear `data_loader._MARKET_CACHE`
    (dùng bởi load_market_data()) — KHÔNG đụng tới `_snapshot_df`/
    snapshot_cache.parquet (dùng bởi get_snapshot_df(), nguồn dữ liệu
    chính của UI screener). Nghĩa là sau khi Wifeed append EOD, UI vẫn có
    thể hiển thị dữ liệu cũ cho tới khi snapshot được rebuild theo cách
    khác (không tự động theo EOD append này).
    """
    import shutil
    import tempfile

    real_price_path = Path(data_loader.PROCESSED_DIR, data_loader.FILES["parquet_price"])
    if not real_price_path.exists():
        return {"error": f"Không tìm thấy {real_price_path} — cần market_prices.parquet để benchmark."}

    tmp_dir = tempfile.mkdtemp(prefix="fss_bench_cache_invalidation_")
    tmp_price_path = Path(tmp_dir, data_loader.FILES["parquet_price"])
    shutil.copy2(real_price_path, tmp_price_path)

    orig_processed_dir = data_loader.PROCESSED_DIR
    orig_wifeed_price_path = wu._PRICE_PATH
    orig_market_cache = dict(data_loader._MARKET_CACHE)

    # [FIX — bug phát hiện lúc chạy thật, đã được xác nhận và vá đúng]:
    # get_snapshot_df() tự tính snap_path = os.path.join(PROCESSED_DIR,
    # FILES["parquet_snapshot"]) MỖI LẦN GỌI. Vì benchmark này monkeypatch
    # data_loader.PROCESSED_DIR sang tmp_dir, bước kiểm chứng cuối (mục 4 —
    # gọi lại get_snapshot_df() để so fingerprint) sẽ khiến hàm đó nhìn
    # snap_path trỏ vào tmp_dir. Nếu tmp_dir KHÔNG có sẵn snapshot_cache.parquet,
    # get_snapshot_df() sẽ nghĩ "parquet bị xóa", tự XÓA RAM cache thật
    # (_snapshot_df) rồi kích hoạt FULL REBUILD ngoài ý muốn (tốn hàng chục
    # giây, và làm mất luôn snapshot RAM đã làm nóng cho các scenario khác).
    # Sao chép sẵn snapshot_cache.parquet (và financial_yearly.parquet để
    # phòng trường hợp phải rebuild) vào tmp_dir để loại bỏ hoàn toàn rủi ro
    # này — KHÔNG sửa logic sản phẩm, chỉ đảm bảo bản sao tạm "nhìn giống"
    # thư mục thật ở mức tối thiểu cần thiết.
    for files_key in ("parquet_snapshot", "parquet_financial_y"):
        fname = data_loader.FILES.get(files_key)
        if not fname:
            continue
        src = Path(orig_processed_dir, fname)
        if src.exists():
            shutil.copy2(src, Path(tmp_dir, fname))

    result = {}
    try:
        data_loader.PROCESSED_DIR = tmp_dir
        wu._PRICE_PATH = str(tmp_price_path)
        data_loader._MARKET_CACHE["data"] = None
        data_loader._MARKET_CACHE["ts"] = 0.0

        # ── 1. Warm cache rồi đo cache-hit ──────────────────────────────
        df_first = data_loader.load_market_data()
        if df_first is None or df_first.empty:
            return {"error": "load_market_data() trên bản sao tạm trả về rỗng."}

        warm_durations = []
        for _ in range(warm_iterations):
            t0 = time.perf_counter_ns()
            data_loader.load_market_data()
            t1 = time.perf_counter_ns()
            warm_durations.append((t1 - t0) / 1_000_000)
        result["market_cache_warm_hit_ms"] = summarize(warm_durations)

        # ── 2. Clear cache thủ công N lần rồi đo reload cost ────────────
        reload_durations = []
        for _ in range(reload_iterations):
            data_loader._MARKET_CACHE["data"] = None
            data_loader._MARKET_CACHE["ts"] = 0.0
            gc.collect()
            t0 = time.perf_counter_ns()
            data_loader.load_market_data()
            t1 = time.perf_counter_ns()
            reload_durations.append((t1 - t0) / 1_000_000)
        result["market_cache_reload_after_invalidate_ms"] = summarize(reload_durations)

        # ── 3. Đo chi phí ghi thật của _merge_eod_into_price_parquet() ──
        base_df = data_loader.load_market_data()
        keep_cols = ["Ticker", "Date", "Price Open", "Price High", "Price Low", "Price Close", "Volume", "Turnover"]
        available_cols = [c for c in keep_cols if c in base_df.columns]
        sample_row = base_df.iloc[[0]][available_cols].copy()

        merge_durations = []
        cache_cleared_each_time = []
        for i in range(merge_iterations):
            df_eod = sample_row.copy()
            df_eod["Date"] = pd.Timestamp.now().normalize() - pd.Timedelta(days=merge_iterations - i)
            data_loader._MARKET_CACHE["data"] = "SENTINEL_BEFORE_MERGE"
            data_loader._MARKET_CACHE["ts"] = time.time()

            t0 = time.perf_counter_ns()
            ok = wu._merge_eod_into_price_parquet(df_eod)
            t1 = time.perf_counter_ns()

            merge_durations.append((t1 - t0) / 1_000_000)
            cache_cleared_each_time.append(
                ok is True and data_loader._MARKET_CACHE["data"] is None
            )

        result["merge_eod_write_ms"] = summarize(merge_durations)
        result["merge_eod_cache_cleared_every_time"] = all(cache_cleared_each_time)

        # ── 4. Kiểm chứng get_snapshot_df() KHÔNG bị invalidate bởi EOD merge ──
        if data_loader._snapshot_df is not None:
            fp_before = dataframe_fingerprint(data_loader._snapshot_df)
            fp_after = dataframe_fingerprint(data_loader.get_snapshot_df())
            result["snapshot_df_unaffected_by_eod_merge"] = (fp_before == fp_after)
            result["snapshot_coherency_note"] = (
                "True nghĩa là ĐÚNG như tài liệu nội bộ ghi nhận: EOD merge "
                "KHÔNG làm snapshot_df (nguồn dữ liệu UI) tự làm mới theo. "
                "Đây là rủi ro cache-coherency thật của hệ thống, không phải "
                "lỗi của benchmark."
            )
        else:
            result["snapshot_df_unaffected_by_eod_merge"] = None
            result["snapshot_coherency_note"] = (
                "Bỏ qua kiểm tra này — RAM snapshot (_snapshot_df) chưa được "
                "làm nóng. Chạy benchmark_ram_cache() trước để có kết quả này."
            )

        return result
    finally:
        data_loader.PROCESSED_DIR = orig_processed_dir
        wu._PRICE_PATH = orig_wifeed_price_path
        data_loader._MARKET_CACHE.clear()
        data_loader._MARKET_CACHE.update(orig_market_cache)
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

def _run_scenario(name, fn, *args, **kwargs):
    print(f"[Benchmark] Đang chạy: {name} ...", flush=True)
    t0 = time.perf_counter()
    try:
        result = fn(*args, **kwargs)
    except Exception as e:
        result = {"error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()}
    elapsed = time.perf_counter() - t0
    status = "OK" if "error" not in result else "LỖI"
    print(f"[Benchmark]   -> {status} ({elapsed:.2f}s)", flush=True)
    return result


def run_all_benchmarks(fast: bool = False, wifeed_sample: str | None = None) -> dict:
    scale = 20 if fast else 1  # /20 số vòng lặp cho lần chạy thử nhanh

    result = {
        "timestamp": int(time.time()),
        "timestamp_human": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "fast (giảm iterations, chỉ để test nhanh — KHÔNG dùng số này để công bố)" if fast else "full",
        "environment": environment_info(),
    }

    # Scenario A trước tiên — vừa đo RAM cache, vừa "làm nóng" _snapshot_df
    # cho các scenario sau (D, cache_invalidation) dùng lại, tránh rebuild lặp.
    result["scenario_a_ram_cache"] = _run_scenario(
        "A - RAM cache", benchmark_ram_cache, max(50, 1000 // scale)
    )

    if "error" not in result["scenario_a_ram_cache"]:
        df = data_loader.get_snapshot_df()
        result["snapshot_metadata"] = {
            "total_tickers": int(len(df)),
            "total_columns": int(df.shape[1]),
            "exchanges": df["Exchange"].value_counts().to_dict() if "Exchange" in df.columns else {},
            "sectors_count": int(df["Sector"].nunique()) if "Sector" in df.columns else None,
            "fingerprint": dataframe_fingerprint(df),
        }

    result["scenario_b_parquet_cache"] = _run_scenario(
        "B - Parquet cache", benchmark_parquet_cache, max(5, 30 // scale)
    )
    result["scenario_d_filter"] = _run_scenario(
        "D - Filter computation", benchmark_filter_scenarios, max(20, 200 // scale)
    )
    result["scenario_wifeed_parse"] = _run_scenario(
        "wifeed_parse (mới)", benchmark_wifeed_parse, max(10, 100 // scale), wifeed_sample
    )
    result["scenario_cache_invalidation"] = _run_scenario(
        "cache_invalidation (mới)", benchmark_cache_invalidation,
        max(30, 300 // scale), max(5, 20 // scale), max(2, 5 // scale)
    )
    # Scenario H cuối cùng — phá RAM + disk cache, disruptive nhất.
    result["scenario_h_thread_safety"] = _run_scenario(
        "H - Thread safety / cache stampede", benchmark_thread_safety, 20
    )

    return result


def main():
    parser = argparse.ArgumentParser(description="FSS backend performance benchmark")
    parser.add_argument("--fast", action="store_true", help="Giảm số vòng lặp để chạy thử nhanh (KHÔNG dùng để công bố)")
    parser.add_argument("--wifeed-sample", type=str, default=None, help="Đường dẫn file wifeed_output.txt mẫu")
    parser.add_argument("--out", type=str, default=None, help="Đường dẫn file JSON kết quả (mặc định: benchmark_results/backend_benchmark_<ts>.json)")
    args = parser.parse_args()

    result = run_all_benchmarks(fast=args.fast, wifeed_sample=args.wifeed_sample)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else RESULTS_DIR / f"backend_benchmark_{result['timestamp']}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print("\n" + "=" * 70)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print("=" * 70)
    print(f"\n[Saved] {out_path}")

    return result


if __name__ == "__main__":
    main()