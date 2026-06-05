# src/backend/portfolio_optimizer.py
# ============================================================
# VSS PREDICTIVE FRAMEWORK 2.0 – Portfolio Optimizer
# ============================================================
# Stage 2: get_price_history_for_quant()   – data pipeline
# Stage 3: Seasonality → Markowitz → Monte Carlo Bootstrap
# ============================================================
# Luồng chạy:
#   ncn_rows  (top 3-5 NCN từ screener)
#   nav       (từ UI input, mặc định 1 tỷ)
#      ↓
#   [1] get_price_history_for_quant(tickers) → price_df  ~0.3s
#   [2] compute_seasonality_scores()         → top 5 mã
#   [3] run_markowitz_optimized()            → weights
#   [4] run_monte_carlo_bootstrap()          → 10k scenarios
#   [5] guillotine_check_and_retry()         → nếu MDD>15%, loại mã tệ nhất
#   [6] trả về QuantResult dict
# ============================================================

import os, logging, math
from datetime import datetime, date
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize, LinearConstraint, Bounds

logger = logging.getLogger(__name__)

# ── Constants ──
RF_ANNUAL      = 0.045          # Lãi suất phi rủi ro VN (~4.5% tiết kiệm 12T)
RF_DAILY       = RF_ANNUAL / 252
N_SCENARIOS    = 10_000
HORIZON_DAYS   = 22             # ~1 tháng giao dịch
MAX_WEIGHT     = 0.40           # Tối đa 40% 1 mã
MIN_WEIGHT     = 0.10           # Tối thiểu 10% 1 mã
LIQUIDITY_CAP  = 0.10           # Không vượt 10% ADV20-Value
GUILLOTINE_MDD = 0.15           # Ngưỡng Max Drawdown (VN-adjusted)
MAX_RETRY      = 4              # Số lần retry Guillotine tối đa
MIN_STOCKS     = 2              # Tối thiểu 2 mã để đa dạng hóa
MIN_HISTORY_DAYS = 180          # Tối thiểu 6 tháng dữ liệu giá


# ══════════════════════════════════════════════════════════════
# DATA CLASS – kết quả trả về
# ══════════════════════════════════════════════════════════════
@dataclass
class QuantResult:
    """Output của toàn bộ pipeline quant."""
    status: str                              # "ok" | "error" | "insufficient_data"
    tickers: list = field(default_factory=list)
    weights: list = field(default_factory=list)    # % tỷ trọng [0..1]
    quantities: list = field(default_factory=list) # Số cổ phiếu
    investment_values: list = field(default_factory=list)  # VND
    prices: list = field(default_factory=list)     # Giá hiện tại
    companies: list = field(default_factory=list)  # Tên công ty
    exchanges: list = field(default_factory=list)  # Sàn

    expected_return: float = 0.0    # Annualized
    expected_return_1m: float = 0.0 # 1-tháng horizon
    var_95: float = 0.0             # VaR 95% (1 tháng)
    max_drawdown: float = 0.0       # Max Drawdown ước tính (1 tháng)
    sharpe_ratio: float = 0.0
    portfolio_vol: float = 0.0      # Annualized volatility

    mc_returns: Optional[np.ndarray] = None   # shape (N_SCENARIOS,)
    seasonality_scores: dict = field(default_factory=dict)

    nav: float = 1_000_000_000.0
    guillotine_iterations: int = 0
    error_message: str = ""


# ══════════════════════════════════════════════════════════════
# STAGE 2: DATA PIPELINE
# ══════════════════════════════════════════════════════════════

def _get_processed_dir() -> str:
    """Tự động resolve đường dẫn tới data/processed."""
    this_dir = os.path.dirname(os.path.abspath(__file__))
    # src/backend → src → root
    root = os.path.dirname(os.path.dirname(this_dir))
    return os.path.join(root, "data", "processed")


def get_price_history_for_quant(
    tickers: list,
    n_years: int = 3,
    processed_dir: str = None,
) -> pd.DataFrame:
    """
    Load chuỗi giá lịch sử cho đúng tập mã cần thiết.
    Chỉ đọc ~5 ticker từ parquet (filter pushdown) → <0.5s RAM nhàn.

    Returns:
        pd.DataFrame index=Date, columns=Ticker, values=Price Close
        Trả về DataFrame rỗng nếu không có dữ liệu.
    """
    if not tickers:
        return pd.DataFrame()

    processed_dir = processed_dir or _get_processed_dir()
    parquet_path  = os.path.join(processed_dir, "market_prices.parquet")

    if not os.path.exists(parquet_path):
        logger.warning(f"[PortfolioOpt] Không tìm thấy {parquet_path}")
        return pd.DataFrame()

    cutoff = pd.Timestamp.now() - pd.DateOffset(years=n_years)

    try:
        t0 = pd.Timestamp.now()

        # Chỉ đọc 3 cột cần thiết — tránh load toàn bộ 50MB
        df = pd.read_parquet(
            parquet_path,
            columns=["Ticker", "Date", "Price Close"],
        )
        # Strip exchange suffix nếu còn
        df["Ticker"] = df["Ticker"].str.replace(
            r"\.(HNO|HN|HM)$", "", regex=True
        )
        df = df[df["Ticker"].isin(tickers)]
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"])
        df = df[df["Date"] >= cutoff]

        if df.empty:
            logger.warning(f"[PortfolioOpt] Không có giá cho {tickers}")
            return pd.DataFrame()

        pivot = (
            df.pivot_table(
                index="Date", columns="Ticker",
                values="Price Close", aggfunc="last",
            )
            .sort_index()
        )
        # Chỉ giữ lại tickers thực sự có đủ dữ liệu
        valid = [t for t in tickers if t in pivot.columns
                 and pivot[t].dropna().shape[0] >= MIN_HISTORY_DAYS]

        if not valid:
            logger.warning("[PortfolioOpt] Không đủ lịch sử giá cho bất kỳ mã nào")
            return pd.DataFrame()

        pivot = pivot[valid].dropna(how="all").ffill(limit=5)
        elapsed = (pd.Timestamp.now() - t0).total_seconds()
        logger.info(
            f"[PortfolioOpt] Price history loaded: {len(valid)} mã × "
            f"{len(pivot)} ngày | {elapsed:.2f}s"
        )
        return pivot

    except Exception as e:
        logger.error(f"[PortfolioOpt] get_price_history error: {e}")
        return pd.DataFrame()


def get_adv20_value_map(
    tickers: list,
    processed_dir: str = None,
) -> dict:
    """
    Tính ADV20 bằng VNĐ (Volume × Price Close trung bình 20 phiên).
    Trả về {ticker: avg_vnd_value}.
    """
    processed_dir = processed_dir or _get_processed_dir()
    parquet_path  = os.path.join(processed_dir, "market_prices.parquet")

    adv_map = {t: float("inf") for t in tickers}  # Default: no constraint
    if not os.path.exists(parquet_path):
        return adv_map

    try:
        df = pd.read_parquet(
            parquet_path,
            columns=["Ticker", "Date", "Price Close", "Volume"],
        )
        df["Ticker"] = df["Ticker"].str.replace(
            r"\.(HNO|HN|HM)$", "", regex=True
        )
        df = df[df["Ticker"].isin(tickers)]
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).sort_values("Date")
        df["Value"] = df["Price Close"] * df["Volume"]

        result = (
            df.groupby("Ticker")["Value"]
            .apply(lambda x: x.tail(20).mean())
            .to_dict()
        )
        adv_map.update({k: float(v) for k, v in result.items() if not math.isnan(v)})
        logger.info(f"[PortfolioOpt] ADV20 loaded for {list(adv_map.keys())}")
    except Exception as e:
        logger.warning(f"[PortfolioOpt] ADV20 error: {e}")

    return adv_map


# ══════════════════════════════════════════════════════════════
# STAGE 3a: SEASONALITY SCORING
# ══════════════════════════════════════════════════════════════

def compute_seasonality_scores(
    price_df: pd.DataFrame,
    target_month: int = None,
    current_perf_map: dict = None,
) -> pd.Series:
    """
    Seasonality Score = 0.50 × Win Rate + 0.50 × Momentum(1M normalized)

    Win Rate: Tỷ lệ năm mà target_month có lợi nhuận dương
    Momentum: Hiệu suất 1 tháng gần nhất (chuẩn hóa 0..1)

    Args:
        price_df: DataFrame giá (Date × Ticker)
        target_month: Tháng mục tiêu (1-12), mặc định = tháng hiện tại
        current_perf_map: {ticker: perf_1m_value} từ snapshot (bổ sung)

    Returns:
        pd.Series {ticker: score} sắp xếp giảm dần
    """
    if price_df.empty:
        return pd.Series(dtype=float)

    target_month = target_month or datetime.now().month
    scores = {}

    for ticker in price_df.columns:
        series = price_df[ticker].dropna()
        if len(series) < 60:
            continue

        # ── Win Rate ──────────────────────────────────────────
        # Monthly returns cho target_month trong từng năm lịch sử
        monthly_ret = series.resample("ME").last().pct_change().dropna()
        target_rets = monthly_ret[monthly_ret.index.month == target_month]

        if len(target_rets) >= 2:
            win_rate = (target_rets > 0).mean()
        else:
            # Không đủ lịch sử theo tháng → dùng win rate tổng thể
            win_rate = (monthly_ret > 0).mean()

        # ── Momentum 1T ──────────────────────────────────────
        if current_perf_map and ticker in current_perf_map:
            # Ưu tiên dùng giá trị từ snapshot (đã tính sẵn)
            try:
                perf_raw = float(current_perf_map[ticker])
                # Chuẩn hóa: sigmoid-ish mapping [-20%, +20%] → [0, 1]
                momentum = 1 / (1 + math.exp(-perf_raw / 5))
            except Exception:
                momentum = 0.5
        else:
            # Tính từ chuỗi giá
            if len(series) >= 20:
                mom = (series.iloc[-1] / series.iloc[-20]) - 1
                momentum = 1 / (1 + math.exp(-mom * 100 / 5))
            else:
                momentum = 0.5

        scores[ticker] = 0.50 * win_rate + 0.50 * momentum

    return pd.Series(scores).sort_values(ascending=False)


# ══════════════════════════════════════════════════════════════
# STAGE 3b: MARKOWITZ OPTIMIZATION
# ══════════════════════════════════════════════════════════════

def run_markowitz_optimized(
    price_df: pd.DataFrame,
    nav: float,
    adv20_value_map: dict,
    min_weight: float = MIN_WEIGHT,
    max_weight: float = MAX_WEIGHT,
    rf_annual: float  = RF_ANNUAL,
) -> tuple:
    """
    Tối ưu tỷ trọng Markowitz → Maximize Sharpe Ratio
    với 3 ràng buộc VN-Market:

    (1) sum(W) = 1
    (2) min_weight ≤ Wi ≤ max_weight     (tránh all-in & dàn trải quá mỏng)
    (3) Wi × NAV ≤ 10% × ADV20_Value_i   (liquidity constraint)

    Returns:
        (weights_array, metrics_dict)
        weights_array: np.ndarray, sum=1
        metrics_dict:  {"expected_return", "volatility", "sharpe"}
    """
    tickers = list(price_df.columns)
    n = len(tickers)
    if n < 1:
        return np.array([1.0]), {}

    # Daily returns
    daily_ret = price_df.pct_change().dropna()

    if len(daily_ret) < 30:
        # Không đủ dữ liệu → equal weight
        w = np.full(n, 1.0 / n)
        return w, _calc_metrics(daily_ret, w, rf_annual)

    mu  = daily_ret.mean().values   # Expected daily return
    cov = daily_ret.cov().values    # Covariance matrix

    rf_daily = rf_annual / 252

    def neg_sharpe(w):
        port_ret = np.dot(mu, w)
        port_std = math.sqrt(np.dot(w, cov @ w))
        if port_std < 1e-9:
            return 0.0
        return -(port_ret - rf_daily) / port_std

    def neg_sharpe_grad(w):
        port_ret = np.dot(mu, w)
        port_var = np.dot(w, cov @ w)
        port_std = math.sqrt(max(port_var, 1e-12))
        excess   = port_ret - rf_daily
        grad_ret = mu
        grad_std = (cov @ w) / port_std
        return -(grad_ret * port_std - excess * grad_std) / (port_std ** 2)

    # ── Ràng buộc (3): Liquidity ─────────────────────────────
    # Wi ≤ min(max_weight, 0.10 × ADV20_Value_i / NAV)
    upper_bounds = []
    for t in tickers:
        adv_val = adv20_value_map.get(t, float("inf"))
        liq_cap = (LIQUIDITY_CAP * adv_val / nav) if nav > 0 and adv_val < float("inf") else max_weight
        upper_bounds.append(min(max_weight, liq_cap))

    # Nếu có mã có upper bound < min_weight → nới lỏng min_weight cho mã đó
    effective_lb = [min(min_weight, ub * 0.9) for ub in upper_bounds]

    bounds  = Bounds(lb=effective_lb, ub=upper_bounds)
    constraints = {"type": "eq", "fun": lambda w: w.sum() - 1,
                   "jac": lambda w: np.ones(n)}

    # Khởi tạo nhiều điểm để tránh local minimum
    best_result = None
    best_val    = np.inf

    w_init_list = [
        np.full(n, 1.0 / n),                      # Equal weight
        np.array([ub / sum(upper_bounds) for ub in upper_bounds]),  # Proportional to liquidity
    ]
    # Thêm 3 khởi tạo ngẫu nhiên
    rng = np.random.default_rng(42)
    for _ in range(3):
        w0 = rng.dirichlet(np.ones(n))
        # Clip về bounds
        w0 = np.clip(w0, effective_lb, upper_bounds)
        w0 /= w0.sum()
        w_init_list.append(w0)

    for w0 in w_init_list:
        try:
            res = minimize(
                neg_sharpe,
                w0,
                jac=neg_sharpe_grad,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
                options={"maxiter": 500, "ftol": 1e-10},
            )
            if res.success and res.fun < best_val:
                best_val    = res.fun
                best_result = res
        except Exception:
            continue

    if best_result is None or not best_result.success:
        # Fallback: equal weight clipped to bounds
        logger.warning("[PortfolioOpt] Markowitz không hội tụ → equal weight")
        w = np.clip(np.full(n, 1.0 / n), effective_lb, upper_bounds)
        w /= w.sum()
    else:
        w = best_result.x
        w = np.clip(w, 0, 1)
        w /= w.sum()

    metrics = _calc_metrics(daily_ret, w, rf_annual)
    logger.info(
        f"[PortfolioOpt] Markowitz done: "
        f"E[R]={metrics['expected_return']*100:.1f}% "
        f"σ={metrics['volatility']*100:.1f}% "
        f"Sharpe={metrics['sharpe']:.2f}"
    )
    return w, metrics


def _calc_metrics(daily_ret: pd.DataFrame, w: np.ndarray,
                  rf_annual: float) -> dict:
    """Tính E[R], σ, Sharpe từ weights và daily returns."""
    if daily_ret.empty:
        return {"expected_return": 0.0, "volatility": 0.0, "sharpe": 0.0}
    port = daily_ret.values @ w
    er   = float(port.mean() * 252)
    vol  = float(port.std() * math.sqrt(252))
    sharpe = (er - rf_annual) / vol if vol > 1e-9 else 0.0
    return {"expected_return": er, "volatility": vol, "sharpe": sharpe}


# ══════════════════════════════════════════════════════════════
# STAGE 3c: MONTE CARLO BOOTSTRAP (Vectorized numpy)
# ══════════════════════════════════════════════════════════════

def run_monte_carlo_bootstrap(
    daily_returns: pd.DataFrame,
    weights: np.ndarray,
    n_scenarios: int = N_SCENARIOS,
    horizon_days: int = HORIZON_DAYS,
) -> np.ndarray:
    """
    Historical Bootstrapping hoàn toàn vectorized với numpy.
    KHÔNG dùng Gaussian noise — bao gồm Fat Tails thực tế của VN-Market.

    10,000 scenarios × 22 ngày → < 50ms trên CPU

    Returns:
        np.ndarray shape (n_scenarios,) — Portfolio returns sau horizon_days
    """
    ret_vals = daily_returns.dropna().values    # shape (T, n_stocks)
    T        = ret_vals.shape[0]

    if T < horizon_days * 2:
        logger.warning("[MC] Không đủ lịch sử cho bootstrap")
        return np.array([])

    # Portfolio daily returns từ lịch sử
    port_daily = ret_vals @ weights             # shape (T,)

    # ── Vectorized bootstrap ──────────────────────────────────
    # Bốc mẫu ngẫu nhiên từ lịch sử thực (thay thế, tức Bootstrapping)
    rng = np.random.default_rng()
    idx = rng.integers(0, T, size=(n_scenarios, horizon_days))  # (10000, 22)

    sampled = port_daily[idx]                   # (10000, 22)
    # Cumulative return: (1+r1)(1+r2)...(1+rT) - 1
    cum_returns = np.prod(1.0 + sampled, axis=1) - 1.0  # (10000,)

    return cum_returns


def compute_risk_metrics(
    mc_returns: np.ndarray,
    daily_returns: pd.DataFrame,
    weights: np.ndarray,
) -> dict:
    """
    Từ 10,000 kịch bản → các chỉ số rủi ro quan trọng.

    Returns dict:
        expected_return_1m: E[R] kỳ vọng 1 tháng
        var_95:             Value at Risk 95% (5th percentile)
        cvar_95:            Conditional VaR (trung bình phần đuôi trái)
        max_drawdown:       Max Drawdown từ 10,000 paths (rolling peak method)
        prob_loss:          Xác suất thua lỗ
        best_case:          95th percentile (upside)
    """
    if len(mc_returns) == 0:
        return {k: 0.0 for k in ["expected_return_1m","var_95","cvar_95",
                                  "max_drawdown","prob_loss","best_case"]}

    expected_1m = float(np.mean(mc_returns))
    var_95      = float(np.percentile(mc_returns, 5))    # 5th → 95% VaR
    cvar_95     = float(np.mean(mc_returns[mc_returns <= var_95]))
    best_case   = float(np.percentile(mc_returns, 95))
    prob_loss   = float((mc_returns < 0).mean())

    # ── Max Drawdown từ Path simulation (bổ sung) ─────────────
    # Tái tạo N paths ngắn, tính max drawdown trên từng path
    # Dùng daily returns gốc để tái mô phỏng nhanh
    mdd = _estimate_max_drawdown(daily_returns, weights)

    return {
        "expected_return_1m": expected_1m,
        "var_95":             var_95,
        "cvar_95":            cvar_95,
        "max_drawdown":       mdd,
        "prob_loss":          prob_loss,
        "best_case":          best_case,
    }


def _estimate_max_drawdown(
    daily_returns: pd.DataFrame,
    weights: np.ndarray,
    n_paths: int = 2000,
    horizon_days: int = HORIZON_DAYS,
) -> float:
    """
    Ước tính Max Drawdown bằng bootstrap paths (dùng riêng cho Guillotine).
    Nhẹ hơn full MC (2000 paths thay vì 10000).
    """
    if daily_returns.empty:
        return 0.0
    port_daily = (daily_returns.dropna().values @ weights).flatten()
    T = len(port_daily)
    if T < horizon_days:
        return float(abs(np.min(port_daily)))

    rng = np.random.default_rng(0)
    idx = rng.integers(0, T, size=(n_paths, horizon_days))
    sampled = port_daily[idx]               # (n_paths, horizon)

    # Cumulative return path cho mỗi scenario
    cum_paths = np.cumprod(1.0 + sampled, axis=1)  # (n_paths, horizon)

    # Rolling max và drawdown
    rolling_max = np.maximum.accumulate(cum_paths, axis=1)
    drawdowns   = (cum_paths - rolling_max) / rolling_max  # âm

    # Lấy max drawdown tệ nhất trên mỗi path rồi lấy percentile 95%
    worst_per_path = np.min(drawdowns, axis=1)  # âm, hình dạng (n_paths,)
    mdd_95 = abs(float(np.percentile(worst_per_path, 5)))  # 5th pctile là tệ nhất

    return mdd_95


# ══════════════════════════════════════════════════════════════
# STAGE 3d: GUILLOTINE RULE + RETRY
# ══════════════════════════════════════════════════════════════

def guillotine_check_and_retry(
    price_df: pd.DataFrame,
    nav: float,
    adv20_map: dict,
    max_dd_limit: float = GUILLOTINE_MDD,
) -> tuple:
    """
    Chạy Markowitz → MC → kiểm tra Max Drawdown.
    Nếu MDD > max_dd_limit: loại mã có Individual Risk Contribution cao nhất
    và chạy lại (tối đa MAX_RETRY lần).

    Returns:
        (final_weights, final_metrics, mc_returns, n_iterations, tickers_used)
    """
    remaining_df = price_df.copy()
    iterations   = 0

    while len(remaining_df.columns) >= MIN_STOCKS and iterations < MAX_RETRY:
        iterations += 1
        tickers = list(remaining_df.columns)

        # Run Markowitz
        weights, mk_metrics = run_markowitz_optimized(
            remaining_df, nav, adv20_map
        )
        if len(weights) != len(tickers):
            break

        # Run MC
        daily_ret = remaining_df.pct_change().dropna()
        mc_ret    = run_monte_carlo_bootstrap(daily_ret, weights)
        risk_met  = compute_risk_metrics(mc_ret, daily_ret, weights)

        mdd = risk_met["max_drawdown"]
        logger.info(
            f"[Guillotine] Iter {iterations}: {tickers} | MDD={mdd*100:.1f}% "
            f"(limit={max_dd_limit*100:.0f}%)"
        )

        # ── PASS → trả kết quả ───────────────────────────────
        if mdd <= max_dd_limit or len(tickers) <= MIN_STOCKS:
            return weights, mk_metrics, mc_ret, risk_met, iterations, tickers

        # ── FAIL → loại mã tệ nhất ──────────────────────────
        # Mã tệ nhất = mã có Individual Volatility Contribution cao nhất
        cov    = daily_ret.cov().values
        # Marginal Risk Contribution = (cov @ w) / portfolio_vol
        port_var = float(weights @ cov @ weights)
        mrc = (cov @ weights) / math.sqrt(max(port_var, 1e-12))
        # Weighted contribution
        risk_contrib = weights * mrc
        worst_idx    = int(np.argmax(risk_contrib))
        worst_ticker = tickers[worst_idx]

        logger.warning(
            f"[Guillotine] MDD {mdd*100:.1f}% > {max_dd_limit*100:.0f}% → "
            f"Loại mã rủi ro nhất: {worst_ticker}"
        )
        remaining_df = remaining_df.drop(columns=[worst_ticker])

    # Fallback: chạy lần cuối với những gì còn lại
    tickers  = list(remaining_df.columns)
    weights, mk_metrics = run_markowitz_optimized(
        remaining_df, nav, adv20_map
    )
    daily_ret = remaining_df.pct_change().dropna()
    mc_ret    = run_monte_carlo_bootstrap(daily_ret, weights)
    risk_met  = compute_risk_metrics(mc_ret, daily_ret, weights)

    return weights, mk_metrics, mc_ret, risk_met, iterations, tickers


# ══════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ══════════════════════════════════════════════════════════════

def run_full_pipeline(
    ncn_rows: list,
    nav: float       = 1_000_000_000.0,
    processed_dir: str = None,
    target_month: int  = None,
    max_picks: int     = 5,
) -> QuantResult:
    """
    Chạy toàn bộ pipeline VSS Predictive 2.0 từ NCN rows → QuantResult.

    Args:
        ncn_rows:     List[dict] từ _prepare_ncn_rows() trong screener_pdf_callback
        nav:          Vốn đầu tư (VND), từ UI input
        processed_dir: Đường dẫn tới data/processed (auto-detect nếu None)
        target_month: Tháng chiến lược (auto = tháng hiện tại)
        max_picks:    Số mã tối đa đưa vào tối ưu (default 5)

    Returns:
        QuantResult dataclass
    """
    if not ncn_rows:
        return QuantResult(status="insufficient_data",
                           error_message="Không có NCN rows")

    tickers_all = [r["ticker"] for r in ncn_rows[:max_picks]]
    perf_map    = {}
    price_map   = {}
    company_map = {}
    exchange_map= {}
    for r in ncn_rows[:max_picks]:
        t = r["ticker"]
        # Lấy giá trị Perf_1M nếu có
        try:
            pm_str = str(r.get("perf_1m", "")).replace("%","").replace("+","")
            perf_map[t] = float(pm_str)
        except Exception:
            perf_map[t] = 0.0
        # Giá hiện tại
        try:
            price_map[t] = float(str(r.get("price","0")).replace(",",""))
        except Exception:
            price_map[t] = 0.0
        company_map[t]  = r.get("company", t)
        exchange_map[t] = r.get("exchange", "—")

    # ── Stage 2: Load giá ────────────────────────────────────
    logger.info(f"[Pipeline] Tickers: {tickers_all} | NAV: {nav:,.0f}")
    price_df = get_price_history_for_quant(
        tickers_all, n_years=3, processed_dir=processed_dir
    )
    valid_tickers = list(price_df.columns) if not price_df.empty else []

    if len(valid_tickers) < MIN_STOCKS:
        logger.warning("[Pipeline] Không đủ dữ liệu giá lịch sử")
        return QuantResult(
            status="insufficient_data",
            tickers=tickers_all,
            nav=nav,
            error_message=(
                "Cần ít nhất 2 mã có dữ liệu giá lịch sử ≥ 6 tháng. "
                "Hiện tại hệ thống không tìm thấy đủ dữ liệu trong "
                "market_prices.parquet. Hãy kiểm tra lại data pipeline."
            ),
        )

    adv20_map = get_adv20_value_map(valid_tickers, processed_dir)

    # ── Stage 3a: Seasonality – lọc top max_picks mã ────────
    season_scores = compute_seasonality_scores(
        price_df, target_month=target_month, current_perf_map=perf_map
    )
    top_tickers = list(season_scores.head(max_picks).index)
    # Đảm bảo không mất mã nếu season_scores không đủ
    for t in valid_tickers:
        if t not in top_tickers and len(top_tickers) < max_picks:
            top_tickers.append(t)

    price_df = price_df[[t for t in top_tickers if t in price_df.columns]]

    # ── Stage 3b + 3c + 3d: Markowitz → MC → Guillotine ─────
    try:
        (weights, mk_metrics, mc_returns, risk_metrics,
         n_iter, final_tickers) = guillotine_check_and_retry(
            price_df, nav, adv20_map
        )
    except Exception as e:
        logger.error(f"[Pipeline] Optimization error: {e}")
        return QuantResult(
            status="error",
            tickers=valid_tickers,
            nav=nav,
            error_message=str(e),
        )

    # ── Tính số lượng cổ phiếu và giá trị đầu tư ────────────
    quantities, inv_values, current_prices = [], [], []
    for i, t in enumerate(final_tickers):
        w = float(weights[i]) if i < len(weights) else 0.0
        p = price_map.get(t, 0.0)
        # Lấy giá từ price_df nếu price_map=0
        if p <= 0 and t in price_df.columns:
            try:
                p = float(price_df[t].dropna().iloc[-1])
            except Exception:
                p = 1.0
        inv_val = nav * w
        qty = int(inv_val / p / 100) * 100 if p > 0 else 0  # Làm tròn lô 100 cp
        quantities.append(qty)
        inv_values.append(inv_val)
        current_prices.append(p)

    result = QuantResult(
        status="ok",
        tickers=final_tickers,
        weights=[float(w) for w in weights[:len(final_tickers)]],
        quantities=quantities,
        investment_values=inv_values,
        prices=current_prices,
        companies=[company_map.get(t, t) for t in final_tickers],
        exchanges=[exchange_map.get(t, "—") for t in final_tickers],

        expected_return    = mk_metrics.get("expected_return", 0.0),
        expected_return_1m = risk_metrics.get("expected_return_1m", 0.0),
        var_95             = risk_metrics.get("var_95", 0.0),
        max_drawdown       = risk_metrics.get("max_drawdown", 0.0),
        sharpe_ratio       = mk_metrics.get("sharpe", 0.0),
        portfolio_vol      = mk_metrics.get("volatility", 0.0),

        mc_returns             = mc_returns,
        seasonality_scores     = season_scores.to_dict(),
        nav                    = nav,
        guillotine_iterations  = n_iter,
    )

    logger.info(
        f"[Pipeline] Done: {final_tickers} | "
        f"Weights={[f'{w*100:.0f}%' for w in result.weights]} | "
        f"E[R]={result.expected_return*100:.1f}% | "
        f"VaR={result.var_95*100:.1f}% | "
        f"MDD={result.max_drawdown*100:.1f}%"
    )
    return result