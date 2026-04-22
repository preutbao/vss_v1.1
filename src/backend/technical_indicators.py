# src/backend/technical_indicators.py
"""
Module tính toán Technical Indicators - VECTORIZED VERSION
Nhanh hơn 10-50x so với phiên bản loop-per-ticker.
"""

import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def _sma(series, window):
    return series.rolling(window, min_periods=max(1, window // 2)).mean()

def _rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def _macd_histogram(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, min_periods=fast).mean()
    ema_slow = series.ewm(span=slow, min_periods=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, min_periods=signal).mean()
    return macd_line - signal_line

def _bb_width(series, period=20, std_dev=2):
    mid = series.rolling(period, min_periods=period).mean()
    std = series.rolling(period, min_periods=period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return ((upper - lower) / mid.replace(0, np.nan)) * 100

def _consec_streaks(series):
    arr = series.values
    if len(arr) < 2:
        return 0, 0
    direction = np.sign(np.diff(arr))
    if len(direction) == 0:
        return 0, 0
    last_dir = direction[-1]
    streak = 0
    for d in reversed(direction):
        if d == last_dir and d != 0:
            streak += 1
        else:
            break
    return (streak, 0) if last_dir > 0 else (0, streak)

def _detect_candle(row):
    try:
        o = float(row.get('Price Open') or 0)
        h = float(row.get('Price High') or 0)
        c = float(row.get('Price Close') or 0)
        l = float(row.get('Price Low') or 0)
        if any(v <= 0 for v in [o, h, c, l]):
            return 'N/A'
        body = abs(c - o)
        rng  = h - l
        if rng == 0:
            return 'Doji'
        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - l
        body_pct   = body / rng
        if body_pct < 0.1:
            return 'Doji'
        if body_pct > 0.7:
            return 'Marubozu Tang' if c > o else 'Marubozu Giam'
        if lower_wick > 2 * body and upper_wick < body:
            return 'Hammer (Tang)' if c > o else 'Hanging Man (Giam)'
        if upper_wick > 2 * body and lower_wick < body:
            return 'Shooting Star (Giam)' if c < o else 'Inverted Hammer (Tang)'
        return 'Nen Tang' if c > o else 'Nen Giam'
    except Exception:
        return 'N/A'


def calculate_technical_indicators(df_price, df_index=None):
    if df_price is None or df_price.empty:
        return pd.DataFrame()

    logger.info("Bat dau tinh Technical Indicators (vectorized)...")

    df = df_price.copy()
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date', 'Price Close'])
    df = df.sort_values(['Ticker', 'Date'])

    price_col  = 'Price Close'
    volume_col = 'Volume'
    if volume_col not in df.columns:
        df[volume_col] = 0

    grp = df.groupby('Ticker', sort=False)

    # ── Prev_Close (giá đóng cửa ngày hôm trước — dùng tô màu SSI) ──────────
    # shift(1) trong group => phần tử liền trước của cùng ticker
    df['_prev_close'] = grp[price_col].transform(lambda s: s.shift(1))

    # Rolling indicators (vectorized via transform)
    for w in [5, 10, 20, 50, 100, 200]:
        df[f'_sma{w}'] = grp[price_col].transform(lambda s, w=w: _sma(s, w))

    df['RSI_14']         = grp[price_col].transform(lambda s: _rsi(s, 14))
    df['MACD_Histogram'] = grp[price_col].transform(_macd_histogram)
    df['BB_Width']       = grp[price_col].transform(_bb_width)

    for w in [5, 10, 20, 50]:
        df[f'_vol_sma{w}'] = grp[volume_col].transform(lambda s, w=w: _sma(s, w))

    # FIX: Cut the bad last date before snapshotting
    raw_max_date = df['Date'].max()
    df = df[df['Date'] < raw_max_date]

    # Snapshot (last row per ticker)
    snap = df.groupby('Ticker', sort=False).last().reset_index()
    max_date = snap['Date'].max()

    # ── Prev_Close & Price_Change_Pct vào snapshot ───────────────────────────
    snap['Prev_Close'] = snap['_prev_close'].round(0)

    # % thay đổi so với ngày hôm trước (chuẩn SSI)
    snap['Price_Change_Pct'] = np.where(
        (snap['_prev_close'] > 0) & snap['_prev_close'].notna(),
        ((snap[price_col] - snap['_prev_close']) / snap['_prev_close'] * 100).round(2),
        np.nan
    )

    # Price vs SMA
    for w in [5, 10, 20, 50, 100, 200]:
        sma_col = f'_sma{w}'
        snap[f'Price_vs_SMA{w}'] = np.where(
            snap[sma_col] > 0,
            ((snap[price_col] - snap[sma_col]) / snap[sma_col] * 100).round(2),
            np.nan
        )

    # Volume vs SMA + Avg_Vol
    for w in [5, 10, 20, 50]:
        vol_sma = snap[f'_vol_sma{w}']
        snap[f'Vol_vs_SMA{w}'] = np.where(vol_sma > 0, (snap[volume_col] / vol_sma).round(2), np.nan)
        snap[f'Avg_Vol_{w}D']  = vol_sma.round(0)

    # RSI State
    snap['RSI_State'] = np.select(
        [snap['RSI_14'] >= 70, snap['RSI_14'] <= 30],
        ['Overbought (Mua qua)', 'Oversold (Ban qua)'],
        default='Neutral'
    )
    snap.loc[snap['RSI_14'].isna(), 'RSI_State'] = None
    snap['RSI_14']         = snap['RSI_14'].round(2)
    snap['MACD_Histogram'] = snap['MACD_Histogram'].round(4)
    snap['BB_Width']       = snap['BB_Width'].round(2)

    # 52W High/Low
    date_1y  = max_date - pd.Timedelta(days=365)
    df_1y    = df[df['Date'] >= date_1y]
    hi_lo_1y = df_1y.groupby('Ticker')[price_col].agg(High_52W='max', Low_52W='min').reset_index()
    snap     = snap.merge(hi_lo_1y, on='Ticker', how='left')

    snap['Break_High_52W']   = (snap[price_col] >= snap['High_52W'] * 0.99).astype(int)
    snap['Break_Low_52W']    = (snap[price_col] <= snap['Low_52W']  * 1.01).astype(int)
    snap['Pct_From_High_1Y'] = ((snap[price_col] - snap['High_52W']) / snap['High_52W'] * 100).round(2)
    snap['Pct_From_Low_1Y']  = ((snap[price_col] - snap['Low_52W'])  / snap['Low_52W']  * 100).round(2)

    hi_lo_all = df.groupby('Ticker')[price_col].agg(_all_high='max', _all_low='min').reset_index()
    snap = snap.merge(hi_lo_all, on='Ticker', how='left')
    snap['Pct_From_High_All'] = ((snap[price_col] - snap['_all_high']) / snap['_all_high'] * 100).round(2)
    snap['Pct_From_Low_All']  = ((snap[price_col] - snap['_all_low'])  / snap['_all_low']  * 100).round(2)

    # GTGD
    if 'Turnover' in df.columns:
        tv_col = 'Turnover'
    else:
        df['_turnover'] = df[price_col] * df[volume_col]
        tv_col = '_turnover'

    for label, days in [('1W', 5), ('10D', 10), ('1M', 20)]:
        gtgd_vals = df.groupby('Ticker')[tv_col].apply(
            lambda s, d=days: s.tail(d).sum() if len(s) >= d else np.nan
        ).reset_index()
        gtgd_vals.columns = ['Ticker', f'GTGD_{label}']
        snap = snap.merge(gtgd_vals, on='Ticker', how='left')

    # Consec + Candlestick
    streak_data = {}
    for ticker, td in df.groupby('Ticker', sort=False):
        cu, cd = _consec_streaks(td[price_col])
        candle  = _detect_candle(td.iloc[-1].to_dict())
        streak_data[ticker] = {'Consec_Up': cu, 'Consec_Down': cd, 'Candlestick_Pattern': candle}
    streak_df = pd.DataFrame.from_dict(streak_data, orient='index').reset_index()
    streak_df.rename(columns={'index': 'Ticker'}, inplace=True)
    snap = snap.merge(streak_df, on='Ticker', how='left')

    # Beta / Alpha / RS (vectorized)
    snap['Beta']   = np.nan
    snap['Alpha']  = np.nan
    snap['RS_3D']  = np.nan
    snap['RS_1M']  = np.nan
    snap['RS_3M']  = np.nan
    snap['RS_1Y']  = np.nan
    snap['RS_Avg'] = np.nan

    if df_index is not None and not df_index.empty:
        try:
            idx = df_index.copy()
            idx['Date'] = pd.to_datetime(idx['Date'], errors='coerce')
            idx = idx.dropna(subset=['Date','JCI_Close']).set_index('Date')['JCI_Close'].sort_index()
            jci_ret = idx.pct_change()

            price_wide = df.pivot_table(index='Date', columns='Ticker', values=price_col, aggfunc='last')
            price_wide = price_wide.sort_index()
            ret_wide   = price_wide.pct_change()

            common = ret_wide.index.intersection(jci_ret.index)
            if len(common) >= 30:
                r_stocks = ret_wide.loc[common].tail(252)
                r_jci    = jci_ret.reindex(r_stocks.index)
                rj_arr   = r_jci.values
                var_jci  = np.nanvar(rj_arr)

                betas, alphas = {}, {}

                # Thinly-traded filter: mã giao dịch thưa có beta gần 0
                # không phải vì ít rủi ro mà vì giá đứng yên nhiều ngày.
                # Ngưỡng: >= 60% số ngày trong 252 phiên phải có return khác 0.
                MIN_ACTIVE_DAYS_PCT = 0.60
                MIN_OBS = 30

                if var_jci > 0:
                    for ticker in r_stocks.columns:
                        rt = r_stocks[ticker].values
                        mask = ~(np.isnan(rt) | np.isnan(rj_arr))
                        if mask.sum() < MIN_OBS:
                            continue

                        rt_c = rt[mask]; rj_c = rj_arr[mask]

                        # Kiểm tra thinly-traded: bao nhiêu % ngày có return != 0
                        active_pct = (rt_c != 0).sum() / len(rt_c)
                        if active_pct < MIN_ACTIVE_DAYS_PCT:
                            # Quá nhiều ngày đứng giá → beta không đáng tin
                            continue

                        b = np.cov(rt_c, rj_c)[0,1] / np.var(rj_c)
                        a = (rt_c.mean() - b * rj_c.mean()) * 252 * 100
                        betas[ticker]  = round(float(b), 3)
                        alphas[ticker] = round(float(a), 2)

                snap['Beta']  = snap['Ticker'].map(betas)
                snap['Alpha'] = snap['Ticker'].map(alphas)

            # RS
            jci_latest = idx.reindex(price_wide.index, method='ffill').iloc[-1]
            def _rs_map(days):
                target = max_date - pd.Timedelta(days=days)
                past   = price_wide[price_wide.index <= target]
                if past.empty:
                    return {}
                t_chg = ((price_wide.iloc[-1] - past.iloc[-1]) / past.iloc[-1].replace(0, np.nan) * 100)
                past_jci = idx[idx.index <= target]
                j_chg = (jci_latest - past_jci.iloc[-1]) / past_jci.iloc[-1] * 100 if not past_jci.empty else 0
                return (t_chg - j_chg).round(2).to_dict()

            snap['RS_1M'] = snap['Ticker'].map(_rs_map(30))
            snap['RS_3M'] = snap['Ticker'].map(_rs_map(90))
            snap['RS_1Y'] = snap['Ticker'].map(_rs_map(365))
            snap['RS_3D'] = snap['Ticker'].map(_rs_map(3))
            rs_df = snap[['RS_3D','RS_1M','RS_3M','RS_1Y']].apply(pd.to_numeric, errors='coerce')
            snap['RS_Avg'] = rs_df.mean(axis=1).round(2)

        except Exception as e:
            logger.warning(f"Beta/Alpha/RS error: {e}")

    # Performance
    perf_lookup = {}
    try:
        year_start = pd.Timestamp(max_date.year, 1, 1)
        for ticker, td in df.groupby('Ticker', sort=False):
            p_now = td[price_col].iloc[-1]
            if p_now <= 0:
                continue
            perfs = {}
            for label, days in [('1W',7),('1M',30),('3M',90),('6M',180),('1Y',365)]:
                target = max_date - pd.Timedelta(days=days)
                past   = td[td['Date'] <= target]
                if not past.empty and past[price_col].iloc[-1] > 0:
                    perfs[f'Perf_{label}'] = round(
                        (p_now - past[price_col].iloc[-1]) / past[price_col].iloc[-1] * 100, 2)
            ytd_past = td[td['Date'] >= year_start]
            if not ytd_past.empty and ytd_past[price_col].iloc[0] > 0:
                perfs['Perf_YTD'] = round(
                    (p_now - ytd_past[price_col].iloc[0]) / ytd_past[price_col].iloc[0] * 100, 2)
            perf_lookup[ticker] = perfs
    except Exception as e:
        logger.warning(f"Perf error: {e}")

    for label in ['Perf_1W','Perf_1M','Perf_3M','Perf_6M','Perf_1Y','Perf_YTD']:
        snap[label] = snap['Ticker'].map({t: v.get(label) for t, v in perf_lookup.items()})

    # Drop internal cols (giữ lại Prev_Close và Price_Change_Pct)
    drop_cols = [c for c in snap.columns if c.startswith('_')]
    snap.drop(columns=drop_cols, inplace=True, errors='ignore')

    # Only return Ticker + technical indicator columns (exclude raw OHLCV)
    exclude = {'Date','Price Close','Price Open','Price High','Price Low',
               'Volume','Turnover','Avg_Vol_20D'}
    keep = ['Ticker'] + [c for c in snap.columns if c not in exclude and c != 'Ticker']
    result = snap[[c for c in keep if c in snap.columns]].copy()

    logger.info(f"Technical Indicators xong: {len(result)} ma, {len(result.columns)-1} chi so")
    return result


def calculate_price_performance(df_price):
    if df_price is None or df_price.empty:
        return pd.DataFrame()
    df = df_price.copy()
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date','Price Close']).sort_values(['Ticker','Date'])
    max_date   = df['Date'].max()
    year_start = pd.Timestamp(max_date.year, 1, 1)
    records = []
    for ticker, td in df.groupby('Ticker', sort=False):
        p_now = td['Price Close'].iloc[-1]
        if p_now <= 0:
            continue
        perf = {'Ticker': ticker}
        for label, days in [('1W',7),('1M',30),('3M',90),('6M',180),('9M',270),('1Y',365)]:
            target = max_date - pd.Timedelta(days=days)
            past   = td[td['Date'] <= target]
            if not past.empty and past['Price Close'].iloc[-1] > 0:
                perf[f'Perf_{label}'] = round(
                    (p_now - past['Price Close'].iloc[-1]) / past['Price Close'].iloc[-1] * 100, 2)
        ytd_past = td[td['Date'] >= year_start]
        if not ytd_past.empty and ytd_past['Price Close'].iloc[0] > 0:
            perf['Perf_YTD'] = round(
                (p_now - ytd_past['Price Close'].iloc[0]) / ytd_past['Price Close'].iloc[0] * 100, 2)
        records.append(perf)
    return pd.DataFrame(records)