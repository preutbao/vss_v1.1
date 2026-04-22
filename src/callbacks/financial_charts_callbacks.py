# src/callbacks/financial_charts_callbacks.py
"""
Tab Biểu đồ tài chính — UI chọn template giống ảnh tham khảo.
User tick checkbox → render các biểu đồ tương ứng.

NOTE: fin-chart-selection-store phải được khai báo NGOÀI tab content
(trong screener.py layout) để template không bị reset khi chuyển tab.
Thêm dòng này vào layout trong screener.py nếu chưa có:
  dcc.Store(id="fin-chart-selection-store", data=[]),
"""
from dash import Input, Output, State, html, dcc, no_update, callback_context, ALL
from src.app_instance import app
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

C = {
    "revenue": "#3b82f6", "gross": "#10b981", "ebit": "#f59e0b",
    "net": "#a78bfa", "cfo": "#00d4ff", "fcf": "#34d399",
    "capex": "#f87171", "cfi": "#fb923c", "roe": "#10b981",
    "roa": "#3b82f6", "assets": "#3b82f6", "liabilities": "#ef4444",
    "equity": "#10b981", "cash": "#34d399",
    "grid": "rgba(255,255,255,0.05)", "bg": "#0c1220",
    "paper": "#0c1220", "text": "#7fa8cc",
}

LAYOUT_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=C["text"], size=10, family="JetBrains Mono, monospace"),
    margin=dict(l=10, r=15, t=36, b=40),
    legend=dict(
        bgcolor="rgba(9,21,38,0.85)",
        bordercolor="#1d4d80",
        borderwidth=1,
        font=dict(size=10, color="#c9d1d9", family="JetBrains Mono, monospace"),
        orientation="v",
        x=1.01, y=1,
        xanchor="left", yanchor="top",
    ),
    hoverlabel=dict(
        bgcolor="#091526", bordercolor="#1d4d80",
        font=dict(family="JetBrains Mono, monospace", size=11, color="#d6eaf8"),
    ),
    hovermode="x unified",
)
AX = dict(
    gridcolor=C["grid"],
    gridwidth=1,
    zeroline=False,
    tickfont=dict(color=C["text"], size=9, family="JetBrains Mono, monospace"),
    showline=False,
)

CHART_GROUPS = [
    {"group": "CHỈ SỐ ĐÁNH GIÁ",    "charts": [{"id":"co-tuc","label":"Cổ tức"}]},
    {"group": "CHỈ SỐ TĂNG TRƯỞNG", "charts": [{"id":"tang-truong-dt-ln","label":"Tăng trưởng Doanh thu & Lợi nhuận"}]},
    {"group": "CƠ CẤU DÒNG TIỀN",   "charts": [{"id":"luu-chuyen-dt","label":"Lưu chuyển dòng tiền"},{"id":"dong-tien-tu-do","label":"Dòng tiền tự do (FCF)"},{"id":"dong-tien-hdkd","label":"Dòng tiền Hoạt động Kinh doanh"}]},
    {"group": "CHỈ SỐ HIỆU QUẢ",    "charts": [{"id":"bien-loi-nhuan","label":"Biên lợi nhuận"},{"id":"hieu-qua-ql","label":"Hiệu quả Quản lý"},{"id":"f-score","label":"F Score"},{"id":"roe-dupont","label":"ROE - Phân tích Dupont"},{"id":"cl-loi-nhuan","label":"Chất lượng lợi nhuận"}]},
    {"group": "CƠ CẤU TÀI SẢN",     "charts": [{"id":"cc-tai-san","label":"Cơ cấu Tài sản"},{"id":"cc-nguon-von","label":"Cơ cấu Nguồn vốn"},{"id":"cc-no-vay","label":"Cơ cấu Nợ vay"},{"id":"cc-ts-ngan-han","label":"Cơ cấu Tài sản ngắn hạn"},{"id":"cc-ts-dai-han","label":"Cơ cấu Tài sản dài hạn"},{"id":"cc-vcsh","label":"Cơ cấu Vốn chủ sở hữu"},{"id":"cc-tien-dt-tc","label":"Cơ cấu Tiền & Đầu tư tài chính"}]},
    {"group": "CHỈ SỐ HOẠT ĐỘNG",   "charts": [{"id":"chu-ky-tien-mat","label":"Chu kỳ Tiền mặt"},{"id":"chi-so-tt","label":"Chỉ số thanh toán"},{"id":"nguoi-mua-tra-tt","label":"Người mua trả tiền trước"},{"id":"hq-ts-co-dinh","label":"Hiệu quả sử dụng tài sản cố định"},{"id":"pt-tk-ptnb","label":"Phải thu, Tồn kho & Phải trả người bán"},{"id":"dso","label":"Số ngày phải thu (DSO)"},{"id":"dio","label":"Số ngày tồn kho (DIO)"},{"id":"dpo","label":"Số ngày phải trả (DPO)"}]},
    {"group": "CƠ CẤU LỢI NHUẬN",   "charts": [{"id":"doanh-thu-thuan","label":"Doanh thu thuần"},{"id":"cc-loi-nhuan","label":"Cơ cấu Lợi nhuận"},{"id":"ln-sau-thue","label":"Lợi nhuận sau thuế"},{"id":"cc-dt-chiphi","label":"Cơ cấu Doanh thu & Chi phí"},{"id":"cc-lng-chiphi","label":"Cơ cấu LN gộp & Chi phí"},{"id":"cc-lnst-chiphi","label":"Cơ cấu LNST & Chi phí"},{"id":"cp-hoat-dong","label":"Chi phí hoạt động"},{"id":"cp-khau-hao","label":"Chi phí khấu hao"},{"id":"cp-sx-yeuto","label":"Chi phí sản xuất theo yếu tố"},{"id":"ebitda-lnst","label":"EBITDA & LNST"},{"id":"dt-thuan-ca-nam","label":"Doanh thu thuần (Cả năm)"},{"id":"lnst-ca-nam","label":"Lợi nhuận sau thuế (Cả năm)"}]},
]

ALL_CHART_IDS = {c["id"]: c["label"] for g in CHART_GROUPS for c in g["charts"]}

def _s(df, cols):
    for c in ([cols] if isinstance(cols, str) else cols):
        if c in df.columns:
            return pd.to_numeric(df[c], errors="coerce").fillna(0)
    return pd.Series(np.zeros(len(df)), index=df.index)

def _x(df): return df["Date"].dt.year.astype(str)+"-Q"+df["Date"].dt.quarter.astype(str)

def _meaningful(*series) -> bool:
    """True nếu ít nhất 1 series có giá trị thực sự khác 0/null."""
    for s in series:
        if s is None:
            continue
        try:
            import pandas as pd
            vals = pd.to_numeric(s, errors="coerce").dropna()
            if (vals.abs() > 1e-9).any():
                return True
        except Exception:
            pass
    return False

class _NoData(Exception):
    """Raise bên trong hàm render khi data toàn 0/null → chart bị skip."""
    pass


def _empty(msg="Chưa có dữ liệu"):
    return go.Figure(layout=dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=30, b=10),
        annotations=[dict(text=msg, x=0.5, y=0.5, xref="paper", yref="paper",
                          showarrow=False, font=dict(color="#484f58", size=12,
                          family="JetBrains Mono, monospace"))]))

def _y_range_padded(series_list, pad_pct=0.10):
    """Tính [y_min - 10%range, y_max + 5%range] để trục Y không bắt đầu từ 0."""
    all_vals = []
    for s in series_list:
        try:
            vals = [v for v in s if v is not None and not np.isnan(v)]
            all_vals.extend(vals)
        except Exception:
            pass
    if not all_vals:
        return None
    y_min, y_max = min(all_vals), max(all_vals)
    rng = y_max - y_min if y_max != y_min else abs(y_max) * 0.2 or 1
    return [y_min - rng * pad_pct, y_max + rng * 0.05]

def _fig(title, traces, mode="bar", secondary=False, height=280, hline=None, y_pad=True):
    if secondary:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        for t, sy in traces:
            fig.add_trace(t, secondary_y=sy)
    else:
        fig = go.Figure()
        for t in traces:
            fig.add_trace(t)
    if hline is not None:
        fig.add_hline(y=hline, line_color="rgba(255,255,255,0.2)",
                      line_width=1, line_dash="dot")
    layout_kwargs = dict(**LAYOUT_BASE,
                         title=dict(text=title, font=dict(size=11, color="#c9d1d9",
                                    family="JetBrains Mono, monospace"), x=0),
                         height=height)
    if mode in ("group", "stack", "overlay", "relative"):
        layout_kwargs["barmode"] = mode
    fig.update_layout(**layout_kwargs)
    fig.update_xaxes(showgrid=False, **AX)
    if secondary:
        fig.update_yaxes(showgrid=True,  **AX, secondary_y=False)
        fig.update_yaxes(showgrid=False, **AX, secondary_y=True)
    else:
        fig.update_yaxes(showgrid=True, **AX)
        if y_pad:
            all_y = []
            for t in fig.data:
                if hasattr(t, "y") and t.y is not None:
                    all_y.append(list(t.y))
            yr = _y_range_padded(all_y)
            if yr:
                fig.update_yaxes(range=yr)
    return fig

def _apply_theme(fig, title=None, barmode=None, height=280, y_pad=True, secondary=False):
    """Áp dụng theme chuẩn cho mọi biểu đồ: font, màu nền, legend, y-axis padding."""
    layout_kwargs = dict(**LAYOUT_BASE, height=height)
    if title:
        layout_kwargs["title"] = dict(
            text=title,
            font=dict(size=11, color="#c9d1d9", family="JetBrains Mono, monospace"),
            x=0,
        )
    if barmode:
        layout_kwargs["barmode"] = barmode
    fig.update_layout(**layout_kwargs)
    fig.update_xaxes(showgrid=False, **AX)
    if secondary:
        fig.update_yaxes(showgrid=True,  **AX, secondary_y=False)
        fig.update_yaxes(showgrid=False, **AX, secondary_y=True)
    else:
        fig.update_yaxes(showgrid=True, **AX)
        if y_pad:
            all_y = []
            for t in fig.data:
                if hasattr(t, "y") and t.y is not None:
                    all_y.append(list(t.y))
            yr = _y_range_padded(all_y)
            if yr:
                fig.update_yaxes(range=yr)
    return fig


def c_tang_truong(df):
    _rev=_s(df,"Revenue from Business Activities - Total_x")
    if not _meaningful(_rev): raise _NoData("Không có dữ liệu doanh thu")
    x=_x(df); rev=_rev/1e9
    net=_s(df,"Net Income after Minority Interest")/1e9
    rg=rev.pct_change(4)*100; ng=net.pct_change(4)*100
    return _fig("Tăng trưởng DT & LN (Tỷ VND)",[
        (go.Bar(x=x,y=rev.values,name="Doanh thu",marker_color=C["revenue"]),False),
        (go.Bar(x=x,y=net.values,name="LNST",marker_color=C["net"]),False),
        (go.Scatter(x=x,y=rg.values,name="%YoY DT",mode="lines+markers",line=dict(color="#fff",width=1.5,dash="dot"),marker=dict(size=4)),True),
        (go.Scatter(x=x,y=ng.values,name="%YoY LN",mode="lines+markers",line=dict(color=C["ebit"],width=1.5,dash="dot"),marker=dict(size=4)),True),
    ], mode="group", secondary=True)

def c_cc_loi_nhuan(df):
    x=_x(df); rev=_s(df,"Revenue from Business Activities - Total_x")/1e9
    gross=_s(df,"Gross Profit - Industrials/Property - Total")/1e9
    ebit=_s(df,["Earnings before Interest & Taxes (EBIT)","Earnings before Interest & Taxes (EBIT)"])/1e9
    net=_s(df,"Net Income after Minority Interest")/1e9
    fig=go.Figure()
    for y_,n,c,op in[(rev,"Doanh thu",C["revenue"],0.4),(gross,"LN gộp",C["gross"],1),(ebit,"EBIT",C["ebit"],1),(net,"LNST",C["net"],1)]:
        fig.add_trace(go.Bar(x=x,y=y_.values,name=n,marker_color=c,opacity=op))
    _apply_theme(fig, title="Cơ cấu Lợi nhuận (Tỷ VND)", barmode="overlay", height=280)
    fig.update_xaxes(showgrid=False, **AX); fig.update_yaxes(**AX,ticksuffix="B"); return fig

def c_bien_loi_nhuan(df):
    x=_x(df); rev=_s(df,"Revenue from Business Activities - Total_x").replace(0,np.nan)
    gm=(_s(df,"Gross Profit - Industrials/Property - Total")/rev*100).fillna(0)
    em=(_s(df,["Earnings before Interest & Taxes (EBIT)","Earnings before Interest & Taxes (EBIT)"])/rev*100).fillna(0)
    nm=(_s(df,"Net Income after Minority Interest")/rev*100).fillna(0)
    fig=go.Figure()
    for y_,n,c in[(gm,"Biên gộp",C["gross"]),(em,"Biên EBIT",C["ebit"]),(nm,"Biên LNST",C["net"])]:
        fig.add_trace(go.Scatter(x=x,y=y_.values,name=n,mode="lines+markers",line=dict(color=c,width=2),marker=dict(size=5)))
    fig.add_hline(y=0,line_color="rgba(255,255,255,0.12)",line_width=1)
    _apply_theme(fig, title="Biên Lợi nhuận (%)", height=280)
    fig.update_xaxes(showgrid=False, **AX); fig.update_yaxes(**AX,ticksuffix="%"); return fig

def c_luu_chuyen(df):
    _cfo=_s(df,["Net Cash Flow from Operating Activities","Net Cash Flow from Operating Activities"])
    if not _meaningful(_cfo): raise _NoData("Không có dữ liệu dòng tiền")
    x=_x(df)
    cfo=_cfo/1e9
    cfi=_s(df,"Net Cash Flow from Investing Activities")/1e9
    cff=_s(df,"Net Cash Flow from Financing Activities")/1e9
    fig=go.Figure()
    for y_,n,c in[(cfo,"CFO",C["cfo"]),(cfi,"CFI",C["cfi"]),(cff,"CFF",C["ebit"])]:
        fig.add_trace(go.Bar(x=x,y=y_.values,name=n,marker_color=c))
    fig.add_hline(y=0,line_color="rgba(255,255,255,0.12)",line_width=1)
    _apply_theme(fig, title="Lưu chuyển Dòng tiền (Tỷ VND)", barmode="group", height=280)
    fig.update_xaxes(showgrid=False, **AX); fig.update_yaxes(**AX,ticksuffix="B"); return fig

def c_fcf(df):
    _cfo=_s(df,["Net Cash Flow from Operating Activities","Net Cash Flow from Operating Activities"])
    _cap=_s(df,["Capital Expenditures - Total_x","Capital Expenditures - Total_y"])
    if not _meaningful(_cfo, _cap): raise _NoData("Không có dữ liệu FCF")
    x=_x(df)
    cfo=_cfo/1e9
    capex=_cap.abs()/1e9
    fcf_=_s(df,"Free Cash Flow")/1e9; fcf_p=fcf_ if fcf_.abs().sum()>0 else cfo-capex
    colors_=[C["fcf"] if v>=0 else C["capex"] for v in fcf_p.values]
    fig=go.Figure()
    fig.add_trace(go.Bar(x=x,y=cfo.values,name="CFO",marker_color=C["cfo"]))
    fig.add_trace(go.Bar(x=x,y=(-capex).values,name="CAPEX",marker_color=C["capex"]))
    fig.add_trace(go.Scatter(x=x,y=fcf_p.values,name="FCF",mode="lines+markers",line=dict(color="#fff",width=2),marker=dict(size=6,color=colors_)))
    fig.add_hline(y=0,line_color="rgba(255,255,255,0.12)",line_width=1)
    _apply_theme(fig, title="Dòng tiền tự do (FCF) (Tỷ VND)", barmode="group", height=280)
    fig.update_xaxes(showgrid=False, **AX); fig.update_yaxes(**AX,ticksuffix="B"); return fig

def c_hdkd(df):
    _cfo=_s(df,["Net Cash Flow from Operating Activities","Net Cash Flow from Operating Activities"])
    if not _meaningful(_cfo): raise _NoData("Không có dữ liệu HĐKD")
    x=_x(df)
    cfo=_cfo/1e9
    net=_s(df,"Net Income after Minority Interest")/1e9
    ratio=(cfo/net.replace(0,np.nan)*100).fillna(0)
    return _fig("Dòng tiền HĐKD vs LNST",[
        (go.Bar(x=x,y=cfo.values,name="CFO",marker_color=C["cfo"]),False),
        (go.Bar(x=x,y=net.values,name="LNST",marker_color=C["net"]),False),
        (go.Scatter(x=x,y=ratio.values,name="CFO/LNST%",mode="lines+markers",line=dict(color=C["ebit"],width=1.5,dash="dot"),marker=dict(size=4)),True),
    ],mode="group",secondary=True)

def c_roe_dupont(df):
    x=_x(df); rev=_s(df,"Revenue from Business Activities - Total_x").replace(0,np.nan)
    assets=_s(df,["Total Assets","Total Assets"]).replace(0,np.nan)
    equity=_s(df,["Common Equity - Total","Common Equity - Total"]).replace(0,np.nan)
    net=_s(df,"Net Income after Minority Interest")
    nm=(net/rev*100).fillna(0); at=(rev/assets).fillna(0); lev=(assets/equity).fillna(0); roe=(net/equity*100).fillna(0)
    fig=make_subplots(rows=2,cols=2,subplot_titles=["ROE (%)","Net Margin (%)","Vòng quay TS","Đòn bẩy TC"])
    for (r_,c_,y_,col) in[(1,1,roe,C["roe"]),(1,2,nm,C["net"]),(2,1,at,C["revenue"]),(2,2,lev,C["ebit"])]:
        t=(go.Scatter(x=x,y=y_.values,mode="lines+markers",line=dict(color=col,width=2),showlegend=False) if r_==1 else go.Bar(x=x,y=y_.values,marker_color=col,showlegend=False))
        fig.add_trace(t,row=r_,col=c_)
    _apply_theme(fig, title="ROE - Phân tích Dupont", height=400)
    _ax = dict(showgrid=False, gridcolor=C["grid"], zeroline=False, tickfont=dict(color=C["text"], size=9))
    for r_ in [1,2]:
        for c__ in [1,2]:
            fig.update_xaxes(**_ax, row=r_, col=c__)
            fig.update_yaxes(**_ax, row=r_, col=c__)
    return fig

def c_hieu_qua(df):
    x=_x(df); rev=_s(df,"Revenue from Business Activities - Total_x").replace(0,np.nan)
    assets=_s(df,["Total Assets","Total Assets"]).replace(0,np.nan); equity=_s(df,["Common Equity - Total","Common Equity - Total"]).replace(0,np.nan)
    net=_s(df,"Net Income after Minority Interest")
    roe=(net/equity*100).fillna(0); roa=(net/assets*100).fillna(0); ros=(net/rev*100).fillna(0)
    fig=go.Figure()
    for y_,n,c in[(roe,"ROE",C["roe"]),(roa,"ROA",C["roa"]),(ros,"ROS",C["ebit"])]:
        fig.add_trace(go.Scatter(x=x,y=y_.values,name=n,mode="lines+markers",line=dict(color=c,width=2),marker=dict(size=5)))
    fig.add_hline(y=0,line_color="rgba(255,255,255,0.12)",line_width=1)
    _apply_theme(fig, title="Hiệu quả Quản lý (%)", height=280)
    fig.update_xaxes(showgrid=False, **AX); fig.update_yaxes(**AX,ticksuffix="%"); return fig

def c_cl_ln(df):
    x=_x(df); cfo=_s(df,["Net Cash Flow from Operating Activities","Net Cash Flow from Operating Activities"])
    net=_s(df,"Net Income after Minority Interest").replace(0,np.nan)
    r=(cfo/net).fillna(0); colors_=[C["fcf"] if v>=1 else C["capex"] for v in r.values]
    fig=go.Figure(); fig.add_trace(go.Bar(x=x,y=r.values,name="CFO/LNST",marker_color=colors_))
    fig.add_hline(y=1,line_color=C["gross"],line_width=1.5,line_dash="dot")
    _apply_theme(fig, title="Chất lượng LN (CFO/LNST)", height=280)
    fig.update_xaxes(showgrid=False, **AX); fig.update_yaxes(**AX); return fig

def c_cc_ts(df):
    x=_x(df); cur=_s(df,["Total Current Assets","Total Current Assets"])/1e9
    non=(_s(df,["Total Assets","Total Assets"])-cur*1e9)/1e9
    fig=go.Figure()
    fig.add_trace(go.Bar(x=x,y=cur.values,name="TS ngắn hạn",marker_color=C["assets"]))
    fig.add_trace(go.Bar(x=x,y=non.values,name="TS dài hạn",marker_color="#6366f1"))
    _apply_theme(fig, title="Cơ cấu Tài sản (Tỷ VND)", barmode="stack", height=280)
    fig.update_xaxes(showgrid=False, **AX); fig.update_yaxes(**AX,ticksuffix="B"); return fig

def c_cc_nv(df):
    x=_x(df); liab=_s(df,["Total Liabilities","Total Liabilities"])/1e9
    eq=_s(df,["Total Shareholders' Equity incl Minority Intr & Hybrid Debt","Common Equity - Total","Common Equity - Total"])/1e9
    fig=go.Figure()
    fig.add_trace(go.Bar(x=x,y=liab.values,name="Nợ phải trả",marker_color=C["liabilities"]))
    fig.add_trace(go.Bar(x=x,y=eq.values,name="VCSH",marker_color=C["equity"]))
    _apply_theme(fig, title="Cơ cấu Nguồn vốn (Tỷ VND)", barmode="stack", height=280)
    fig.update_xaxes(showgrid=False, **AX); fig.update_yaxes(**AX,ticksuffix="B"); return fig

def c_cc_no(df):
    _st=_s(df,"Short-Term Debt & Current Portion of Long-Term Debt")
    _lt=_s(df,"Debt - Long-Term - Total")
    if not _meaningful(_st, _lt): raise _NoData("Không có dữ liệu nợ vay")
    x=_x(df); st=_st/1e9
    lt=_lt/1e9
    fig=go.Figure()
    fig.add_trace(go.Bar(x=x,y=st.values,name="Nợ ngắn hạn",marker_color=C["capex"]))
    fig.add_trace(go.Bar(x=x,y=lt.values,name="Nợ dài hạn",marker_color=C["cfi"]))
    _apply_theme(fig, title="Cơ cấu Nợ vay (Tỷ VND)", barmode="stack", height=280)
    fig.update_xaxes(showgrid=False, **AX); fig.update_yaxes(**AX,ticksuffix="B"); return fig

def c_cc_tsnh(df):
    x=_x(df); cash=_s(df,["Cash & Cash Equivalents - Total_x","Cash & Cash Equivalents - Total"])/1e9
    recv=_s(df,"Trade Accounts & Trade Notes Receivable - Net")/1e9; inv=_s(df,"Inventories - Total")/1e9
    other=(_s(df,["Total Current Assets","Total Current Assets"])-(cash+recv+inv)*1e9)/1e9
    fig=go.Figure()
    for y_,n,c in[(cash,"Tiền mặt",C["cash"]),(recv,"Phải thu",C["revenue"]),(inv,"Tồn kho",C["ebit"]),(other,"Khác","#94a3b8")]:
        fig.add_trace(go.Bar(x=x,y=y_.values,name=n,marker_color=c))
    _apply_theme(fig, title="Cơ cấu TS ngắn hạn (Tỷ VND)", barmode="stack", height=280)
    fig.update_xaxes(showgrid=False, **AX); fig.update_yaxes(**AX,ticksuffix="B"); return fig

def c_chi_so_tt(df):
    x=_x(df); cur_a=_s(df,["Total Current Assets","Total Current Assets"]); cur_l=_s(df,["Total Current Liabilities","Total Current Liabilities"]).replace(0,np.nan)
    inv=_s(df,"Inventories - Total"); cash=_s(df,["Cash & Cash Equivalents - Total_x","Cash & Cash Equivalents - Total"])
    cr=(cur_a/cur_l).fillna(0); qr=((cur_a-inv)/cur_l).fillna(0); car=(cash/cur_l).fillna(0)
    fig=go.Figure()
    for y_,n,c in[(cr,"Current Ratio",C["cfo"]),(qr,"Quick Ratio",C["gross"]),(car,"Cash Ratio",C["ebit"])]:
        fig.add_trace(go.Scatter(x=x,y=y_.values,name=n,mode="lines+markers",line=dict(color=c,width=2),marker=dict(size=5)))
    fig.add_hline(y=1,line_color="rgba(255,255,255,0.2)",line_width=1,line_dash="dot")
    _apply_theme(fig, title="Chỉ số Thanh toán (lần)", height=280)
    fig.update_xaxes(showgrid=False, **AX); fig.update_yaxes(**AX,ticksuffix="x"); return fig

def c_ccc(df):
    x=_x(df); rev=_s(df,"Revenue from Business Activities - Total_x").replace(0,np.nan)
    cogs=_s(df,"Cost of Revenues - Total").abs().replace(0,np.nan)
    recv=_s(df,"Trade Accounts & Trade Notes Receivable - Net"); inv=_s(df,"Inventories - Total")
    pay=_s(df,"Trade Accounts & Trade Notes Payable - Short-Term")
    dso=(recv/rev*90).fillna(0); dio=(inv/cogs*90).fillna(0); dpo=(pay/cogs*90).fillna(0); ccc=dso+dio-dpo
    fig=go.Figure()
    fig.add_trace(go.Bar(x=x,y=dso.values,name="DSO",marker_color=C["revenue"]))
    fig.add_trace(go.Bar(x=x,y=dio.values,name="DIO",marker_color=C["ebit"]))
    fig.add_trace(go.Bar(x=x,y=(-dpo).values,name="-DPO",marker_color=C["gross"]))
    fig.add_trace(go.Scatter(x=x,y=ccc.values,name="CCC",mode="lines+markers",line=dict(color="#fff",width=2),marker=dict(size=5)))
    _apply_theme(fig, title="Chu kỳ Tiền mặt (ngày)", barmode="relative", height=280)
    fig.update_xaxes(showgrid=False, **AX); fig.update_yaxes(**AX,ticksuffix=" ngày"); return fig

def c_dxo(df, mode):
    x=_x(df); rev=_s(df,"Revenue from Business Activities - Total_x").replace(0,np.nan)
    cogs=_s(df,"Cost of Revenues - Total").abs().replace(0,np.nan)
    recv=_s(df,"Trade Accounts & Trade Notes Receivable - Net"); inv=_s(df,"Inventories - Total")
    pay=_s(df,"Trade Accounts & Trade Notes Payable - Short-Term")
    if mode=="dso": y_,n,c,t=(recv/rev*90).fillna(0),"DSO",C["revenue"],"Số ngày phải thu (DSO)"
    elif mode=="dio": y_,n,c,t=(inv/cogs*90).fillna(0),"DIO",C["ebit"],"Số ngày tồn kho (DIO)"
    else: y_,n,c,t=(pay/cogs*90).fillna(0),"DPO",C["gross"],"Số ngày phải trả (DPO)"
    fig=go.Figure(); fig.add_trace(go.Bar(x=x,y=y_.values,name=n,marker_color=c))
    _apply_theme(fig, title=t, height=280)
    fig.update_xaxes(showgrid=False, **AX); fig.update_yaxes(**AX,ticksuffix=" ngày"); return fig

def c_ebitda(df):
    _eb=_s(df,"Earnings before Interest Taxes Depreciation & Amortization")
    _net=_s(df,"Net Income after Minority Interest")
    if not _meaningful(_eb, _net): raise _NoData("Không có dữ liệu EBITDA")
    x=_x(df); ebitda=_eb/1e9
    net=_net/1e9
    return _fig("EBITDA & LNST (Tỷ VND)",[
        (go.Bar(x=x,y=ebitda.values,name="EBITDA",marker_color=C["ebit"]),False),
        (go.Bar(x=x,y=net.values,name="LNST",marker_color=C["net"]),False),
        (go.Scatter(x=x,y=(net/ebitda.replace(0,np.nan)*100).fillna(0).values,name="LNST/EBITDA%",mode="lines+markers",line=dict(color="#fff",width=1.5,dash="dot"),marker=dict(size=4)),True),
    ],mode="group",secondary=True)

def c_dt_thuan(df):
    x=_x(df); rev=_s(df,"Revenue from Business Activities - Total_x")/1e9; yoy=rev.pct_change(4)*100
    fig=make_subplots(specs=[[{"secondary_y":True}]])
    fig.add_trace(go.Bar(x=x,y=rev.values,name="Doanh thu",marker_color=C["revenue"]),secondary_y=False)
    fig.add_trace(go.Scatter(x=x,y=yoy.values,name="%YoY",mode="lines+markers",line=dict(color=C["ebit"],width=1.5,dash="dot"),marker=dict(size=4)),secondary_y=True)
    _ax=dict(gridcolor=C["grid"],zeroline=False,tickfont=dict(color=C["text"],size=9))
    _apply_theme(fig, title="Doanh thu thuần (Tỷ VND)", height=280)
    fig.update_xaxes(showgrid=False,**_ax)
    fig.update_yaxes(showgrid=True,ticksuffix="B",**_ax,secondary_y=False)
    fig.update_yaxes(showgrid=False,ticksuffix="%",**_ax,secondary_y=True)
    return fig

def c_ln_st(df):
    x=_x(df); net=_s(df,"Net Income after Minority Interest")/1e9; yoy=net.pct_change(4)*100
    colors_=[C["gross"] if v>=0 else C["capex"] for v in net.values]
    fig=make_subplots(specs=[[{"secondary_y":True}]])
    fig.add_trace(go.Bar(x=x,y=net.values,name="LNST",marker_color=colors_),secondary_y=False)
    fig.add_trace(go.Scatter(x=x,y=yoy.values,name="%YoY",mode="lines+markers",line=dict(color=C["ebit"],width=1.5,dash="dot"),marker=dict(size=4)),secondary_y=True)
    _ax=dict(gridcolor=C["grid"],zeroline=False,tickfont=dict(color=C["text"],size=9))
    _apply_theme(fig, title="Lợi nhuận sau thuế (Tỷ VND)", height=280)
    fig.update_xaxes(showgrid=False,**_ax)
    fig.update_yaxes(showgrid=True,ticksuffix="B",**_ax,secondary_y=False)
    fig.update_yaxes(showgrid=False,ticksuffix="%",**_ax,secondary_y=True)
    return fig

def c_cc_dtcp(df):
    x=_x(df); rev=_s(df,"Revenue from Business Activities - Total_x")/1e9
    cogs=_s(df,"Cost of Revenues - Total").abs()/1e9; opex=_s(df,"Operating Expenses - Total")/1e9
    fig=go.Figure()
    fig.add_trace(go.Bar(x=x,y=rev.values,name="Doanh thu",marker_color=C["revenue"]))
    fig.add_trace(go.Bar(x=x,y=(-cogs).values,name="Giá vốn",marker_color=C["liabilities"]))
    fig.add_trace(go.Bar(x=x,y=(-opex).values,name="Chi phí HĐ",marker_color=C["cfi"]))
    _apply_theme(fig, title="Cơ cấu DT & Chi phí (Tỷ VND)", barmode="relative", height=280)
    fig.update_xaxes(showgrid=False, **AX); fig.update_yaxes(**AX,ticksuffix="B"); return fig

def c_cp_kh(df):
    _dep=_s(df,["Depreciation Depletion & Amortization - Total","Depreciation & Depletion - PPE - CF - to Reconcile","Depreciation - Total"])
    if not _meaningful(_dep): raise _NoData("Không có dữ liệu khấu hao")
    x=_x(df); dep=_dep.abs()/1e9
    rev=_s(df,"Revenue from Business Activities - Total_x").replace(0,np.nan); r=(dep*1e9/rev*100).fillna(0)
    return _fig("Chi phí Khấu hao",[
        (go.Bar(x=x,y=dep.values,name="Khấu hao",marker_color=C["cfi"]),False),
        (go.Scatter(x=x,y=r.values,name="KH/DT%",mode="lines+markers",line=dict(color=C["ebit"],width=1.5,dash="dot"),marker=dict(size=4)),True),
    ],mode="group",secondary=True)

def c_ict(df):
    x=_x(df); ebit=_s(df,["Earnings before Interest & Taxes (EBIT)","Earnings before Interest & Taxes (EBIT)"])/1e9
    int_=_s(df,["Interest Expense - Total","Interest Expense - Net"]).abs().replace(0,np.nan)/1e9
    icr=(ebit/int_).fillna(0)
    return _fig("Khả năng TT lãi vay",[
        (go.Bar(x=x,y=ebit.values,name="EBIT",marker_color=C["ebit"]),False),
        (go.Bar(x=x,y=int_.values,name="Lãi vay",marker_color=C["capex"]),False),
        (go.Scatter(x=x,y=icr.values,name="ICR",mode="lines+markers",line=dict(color="#fff",width=2),marker=dict(size=5)),True),
    ],mode="group",secondary=True)

def c_co_tuc(df):
    dps=_s(df,"DPS - Common - Net - Issue - By Announcement Date")
    if not _meaningful(dps): raise _NoData("Không có dữ liệu cổ tức")
    x=_x(df)
    fig=go.Figure(); fig.add_trace(go.Bar(x=x,y=dps.values,name="DPS",marker_color=C["gross"]))
    _apply_theme(fig, title="Cổ tức DPS (VND/CP)", height=280)
    fig.update_xaxes(showgrid=False, **AX); fig.update_yaxes(**AX); return fig

def c_f_score(df):
    """Piotroski F-Score (0-9): 9 tiêu chí nhị phân."""
    x = _x(df)
    assets    = _s(df, ["Total Assets","Total Assets"]).replace(0, np.nan)
    net       = _s(df, "Net Income after Minority Interest")
    cfo       = _s(df, ["Net Cash Flow from Operating Activities","Net Cash Flow from Operating Activities"])
    rev       = _s(df, "Revenue from Business Activities - Total_x").replace(0, np.nan)
    cur_a     = _s(df, ["Total Current Assets","Total Current Assets"])
    cur_l     = _s(df, ["Total Current Liabilities","Total Current Liabilities"]).replace(0, np.nan)
    lt_debt   = _s(df, "Debt - Long-Term - Total")
    equity    = _s(df, ["Common Equity - Total","Common Equity - Total"]).replace(0, np.nan)
    gross     = _s(df, "Gross Profit - Industrials/Property - Total")

    roa       = net / assets
    roa_prev  = roa.shift(1)
    cfo_a     = cfo / assets
    gr_margin = (gross / rev).fillna(0)
    at        = rev / assets
    lev       = lt_debt / assets
    cr        = cur_a / cur_l

    f = pd.Series(0, index=df.index, dtype=float)
    f += (roa > 0).astype(int)
    f += (cfo_a > 0).astype(int)
    f += (roa > roa_prev).astype(int)
    f += (cfo_a > roa).astype(int)               # Accruals
    f += (lev < lev.shift(1)).astype(int)         # Đòn bẩy giảm
    f += (cr > cr.shift(1)).astype(int)           # Thanh khoản tăng
    f += (gr_margin > gr_margin.shift(1)).astype(int)
    f += (at > at.shift(1)).astype(int)

    colors_ = [C["gross"] if v >= 7 else C["ebit"] if v >= 5 else C["capex"] for v in f.values]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=f.values, name="F-Score", marker_color=colors_,
                         text=f.values.astype(int), textposition="outside",
                         textfont=dict(color="#c9d1d9", size=10)))
    fig.add_hline(y=6, line_color=C["gross"], line_width=1.5, line_dash="dot",
                  annotation_text="≥6 tốt", annotation_font_color=C["gross"])
    fig.add_hline(y=3, line_color=C["capex"], line_width=1, line_dash="dot",
                  annotation_text="≤3 yếu", annotation_font_color=C["capex"])
    _apply_theme(fig, title="Piotroski F-Score (0-8)", height=280)
    fig.update_xaxes(showgrid=False, **AX)
    fig.update_yaxes(**AX, tickvals=list(range(9)))
    return fig


def c_lai_vay_bq(df):
    """Chi phí lãi vay bình quân = Lãi vay / Nợ vay."""
    x    = _x(df)
    int_ = _s(df, ["Interest Expense - Total","Interest Expense - Net"]).abs() / 1e9
    debt = _s(df, ["Debt - Total","Short-Term Debt & Current Portion of Long-Term Debt"]).replace(0, np.nan) / 1e9
    rate = (int_ / debt * 100).fillna(0)
    return _fig("Chi phí lãi vay bình quân (%)", [
        (go.Bar(x=x, y=int_.values, name="Lãi vay (Tỷ VND)", marker_color=C["capex"]), False),
        (go.Scatter(x=x, y=rate.values, name="Tỷ lệ LS%", mode="lines+markers",
                    line=dict(color=C["ebit"], width=2), marker=dict(size=5)), True),
    ], mode="group", secondary=True)


def c_cc_tien_dt(df):
    """Cơ cấu Tiền & Đầu tư tài chính ngắn hạn."""
    x    = _x(df)
    cash = _s(df, ["Cash & Cash Equivalents - Total_x","Cash & Cash Equivalents - Total"]) / 1e9
    sti  = _s(df, "Short-Term Investments - Total") / 1e9
    fig  = go.Figure()
    fig.add_trace(go.Bar(x=x, y=cash.values, name="Tiền & TĐ tiền", marker_color=C["cash"]))
    fig.add_trace(go.Bar(x=x, y=sti.values,  name="Đầu tư TC NH",   marker_color=C["cfo"]))
    _apply_theme(fig, title="Tiền & Đầu tư TC ngắn hạn (Tỷ VND)", barmode="stack", height=280)
    fig.update_xaxes(showgrid=False, **AX)
    fig.update_yaxes(**AX, ticksuffix="B")
    return fig


def c_cc_vcsh(df):
    """Cơ cấu Vốn chủ sở hữu."""
    x        = _x(df)
    paid_in  = _s(df, "Common Equity - Total") / 1e9
    retained = _s(df, "Retained Earnings - Total") / 1e9
    other    = (_s(df, ["Total Shareholders' Equity incl Minority Intr & Hybrid Debt","Common Equity - Total"])
                - paid_in * 1e9 - retained * 1e9) / 1e9
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=paid_in.values,  name="Vốn góp",          marker_color=C["revenue"]))
    fig.add_trace(go.Bar(x=x, y=retained.values, name="LN giữ lại",       marker_color=C["gross"]))
    fig.add_trace(go.Bar(x=x, y=other.values,    name="Khác",             marker_color="#94a3b8"))
    _apply_theme(fig, title="Cơ cấu VCSH (Tỷ VND)", barmode="stack", height=280)
    fig.update_xaxes(showgrid=False, **AX)
    fig.update_yaxes(**AX, ticksuffix="B")
    return fig


def c_cc_ts_dh(df):
    """Cơ cấu Tài sản dài hạn."""
    x   = _x(df)
    ppe = _s(df, "Property Plant & Equipment - Net - Total") / 1e9
    inv = _s(df, "Investments - Long-Term") / 1e9
    cur = _s(df, ["Total Current Assets","Total Current Assets"]) / 1e9
    tot = _s(df, ["Total Assets","Total Assets"]) / 1e9
    lta = (tot - cur).clip(lower=0)
    oth = (lta - ppe - inv).clip(lower=0)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=ppe.values, name="TSCĐ (Net)",    marker_color=C["assets"]))
    fig.add_trace(go.Bar(x=x, y=inv.values, name="Đầu tư DH",    marker_color=C["cfo"]))
    fig.add_trace(go.Bar(x=x, y=oth.values, name="Khác",          marker_color="#94a3b8"))
    _apply_theme(fig, title="Cơ cấu TS dài hạn (Tỷ VND)", barmode="stack", height=280)
    fig.update_xaxes(showgrid=False, **AX)
    fig.update_yaxes(**AX, ticksuffix="B")
    return fig


def c_nguoi_mua_tra_tt(df):
    """Người mua trả tiền trước = Advance from customers / Revenue."""
    x    = _x(df)
    recv = _s(df, "Trade Accounts & Trade Notes Receivable - Net") / 1e9
    rev  = _s(df, "Revenue from Business Activities - Total_x").replace(0, np.nan)
    days = (recv * 1e9 / rev * 90).fillna(0)
    return _fig("Người mua trả tiền trước (ngày phải thu)", [
        (go.Bar(x=x, y=recv.values, name="Phải thu KH (Tỷ)", marker_color=C["revenue"]), False),
        (go.Scatter(x=x, y=days.values, name="Số ngày thu",  mode="lines+markers",
                    line=dict(color=C["ebit"], width=2), marker=dict(size=5)), True),
    ], mode="group", secondary=True)


def c_hq_ts_co_dinh(df):
    """Hiệu quả sử dụng tài sản cố định = Revenue / Net PPE."""
    x   = _x(df)
    rev = _s(df, "Revenue from Business Activities - Total_x") / 1e9
    ppe = _s(df, "Property Plant & Equipment - Net - Total").replace(0, np.nan)
    fat = (rev * 1e9 / ppe).fillna(0)
    return _fig("Hiệu quả tài sản cố định", [
        (go.Bar(x=x, y=(ppe / 1e9).values, name="TSCĐ Net (Tỷ)", marker_color=C["assets"]), False),
        (go.Scatter(x=x, y=fat.values, name="Vòng quay TSCĐ", mode="lines+markers",
                    line=dict(color=C["ebit"], width=2), marker=dict(size=5)), True),
    ], mode="group", secondary=True)


def c_pt_tk_ptnb(df):
    """Phải thu, Tồn kho & Phải trả người bán."""
    x    = _x(df)
    recv = _s(df, "Trade Accounts & Trade Notes Receivable - Net") / 1e9
    inv  = _s(df, "Inventories - Total") / 1e9
    pay  = _s(df, "Trade Accounts & Trade Notes Payable - Short-Term") / 1e9
    fig  = go.Figure()
    for y_, n, c in [(recv, "Phải thu KH", C["revenue"]),
                     (inv,  "Tồn kho",     C["ebit"]),
                     (pay,  "Phải trả NB", C["gross"])]:
        fig.add_trace(go.Bar(x=x, y=y_.values, name=n, marker_color=c))
    _apply_theme(fig, title="Phải thu, Tồn kho & Phải trả NB (Tỷ VND)", barmode="group", height=280)
    fig.update_xaxes(showgrid=False, **AX)
    fig.update_yaxes(**AX, ticksuffix="B")
    return fig


def c_cp_sx_yeuto(df):
    """Chi phí sản xuất kinh doanh theo yếu tố."""
    x    = _x(df)
    cogs = _s(df, "Cost of Revenues - Total").abs() / 1e9
    opex = _s(df, "Operating Expenses - Total") / 1e9
    dep  = _s(df, ["Depreciation Depletion & Amortization - Total","Depreciation & Depletion - PPE - CF - to Reconcile","Depreciation - Total"]).abs() / 1e9
    int_ = _s(df, ["Interest Expense - Total","Interest Expense - Net"]).abs() / 1e9
    fig  = go.Figure()
    for y_, n, c in [(cogs, "Giá vốn",      C["liabilities"]),
                     (opex, "CP Hoạt động", C["cfi"]),
                     (dep,  "Khấu hao",     "#94a3b8"),
                     (int_, "Lãi vay",      C["capex"])]:
        fig.add_trace(go.Bar(x=x, y=y_.values, name=n, marker_color=c))
    _apply_theme(fig, title="Chi phí SX theo yếu tố (Tỷ VND)", barmode="stack", height=280)
    fig.update_xaxes(showgrid=False, **AX)
    fig.update_yaxes(**AX, ticksuffix="B")
    return fig


RENDER_MAP = {
    "co-tuc": c_co_tuc, "tang-truong-dt-ln": c_tang_truong,
    "luu-chuyen-dt": c_luu_chuyen, "dong-tien-tu-do": c_fcf, "dong-tien-hdkd": c_hdkd,
    "bien-loi-nhuan": c_bien_loi_nhuan, "hieu-qua-ql": c_hieu_qua,
    "f-score": c_f_score, "roe-dupont": c_roe_dupont, "cl-loi-nhuan": c_cl_ln,
    "cc-tai-san": c_cc_ts, "cc-nguon-von": c_cc_nv, "cc-no-vay": c_cc_no,
    "cc-ts-ngan-han": c_cc_tsnh, "cc-ts-dai-han": c_cc_ts_dh,
    "cc-vcsh": c_cc_vcsh, "cc-tien-dt-tc": c_cc_tien_dt,
    "chu-ky-tien-mat": c_ccc, "chi-so-tt": c_chi_so_tt,
    "nguoi-mua-tra-tt": c_nguoi_mua_tra_tt, "hq-ts-co-dinh": c_hq_ts_co_dinh,
    "pt-tk-ptnb": c_pt_tk_ptnb,
    "dso": lambda df: c_dxo(df, "dso"), "dio": lambda df: c_dxo(df, "dio"),
    "dpo": lambda df: c_dxo(df, "dpo"),
    "doanh-thu-thuan": c_dt_thuan, "cc-loi-nhuan": c_cc_loi_nhuan, "ln-sau-thue": c_ln_st,
    "cc-dt-chiphi": c_cc_dtcp, "cc-lng-chiphi": c_cc_loi_nhuan, "cc-lnst-chiphi": c_cc_dtcp,
    "cp-hoat-dong": c_cc_dtcp, "cp-khau-hao": c_cp_kh, "cp-sx-yeuto": c_cp_sx_yeuto,
    "ebitda-lnst": c_ebitda, "dt-thuan-ca-nam": c_dt_thuan, "lnst-ca-nam": c_ln_st,
}


def build_template_picker(saved_selection=None):
    """Panel chọn template biểu đồ. saved_selection: list các chart id đã chọn trước đó."""
    saved_selection = saved_selection or []

    def group_col(g):
        return html.Div([
            html.Div(g["group"], style={"fontSize":"11px","fontWeight":"700","color":"#7fa8cc",
                "marginBottom":"8px","paddingBottom":"6px","borderBottom":"1px solid #21262d","letterSpacing":"0.5px"}),
            *[html.Div(dcc.Checklist(
                id={"type":"fin-chart-check","index":c["id"]},
                options=[{"label":c["label"],"value":c["id"]}],
                value=[c["id"]] if c["id"] in saved_selection else [],  # ← restore
                inputStyle={"marginRight":"6px","accentColor":"#ef4444"},
                labelStyle={"fontSize":"12px","color":"#c9d1d9","cursor":"pointer"},
            ), style={"marginBottom":"8px"}) for c in g["charts"]],
        ], style={"flex":"1","minWidth":"190px","padding":"0 14px 0 0"})

    cols=[[],[],[]]
    for i,g in enumerate(CHART_GROUPS): cols[i%3].append(group_col(g))

    return html.Div([
        html.Div("TEMPLATE MẶC ĐỊNH", style={"padding":"14px 20px 10px","borderBottom":"1px solid #21262d",
            "fontSize":"14px","fontWeight":"700","color":"#c9d1d9"}),
        html.Div([
            html.Div([html.I(className="fas fa-search",style={"position":"absolute","left":"10px","top":"50%",
                "transform":"translateY(-50%)","color":"#484f58","fontSize":"12px","pointerEvents":"none"}),
                dcc.Input(id="fin-chart-search",placeholder="Nhập loại biểu đồ muốn thêm",debounce=True,
                style={"width":"100%","padding":"7px 10px 7px 32px","backgroundColor":"#0d1117","color":"#c9d1d9",
                    "border":"1px solid #30363d","borderRadius":"6px","fontSize":"12px","outline":"none"}),
            ],style={"position":"relative","flex":"1"}),
            dbc.Button("Xóa lọc",id="fin-chart-clear-all",color="danger",outline=True,size="sm",style={"fontSize":"12px"}),
            dbc.Button([html.I(className="fas fa-check",style={"marginRight":"5px"}),"THÊM VÀO TEMPLATE"],
                id="fin-chart-apply-btn",size="sm",
                style={"fontSize":"12px","backgroundColor":"#ef4444","border":"none","borderRadius":"6px","color":"white"}),
        ],style={"display":"flex","gap":"10px","alignItems":"center","padding":"10px 20px","borderBottom":"1px solid #21262d"}),
        html.Div([html.Div(col,style={"display":"flex","flexDirection":"column"}) for col in cols],
            style={"display":"flex","flexDirection":"row","padding":"16px 20px","overflowY":"auto","maxHeight":"460px","gap":"0"}),
    ],style={"backgroundColor":"#0c1220","border":"1px solid #21262d","borderRadius":"8px","overflow":"hidden"})


@app.callback(
    Output("tab-fin-charts-content", "children"),
    Input("detail-tabs", "active_tab"),
    Input("fin-chart-period-store", "data"),
    State("screener-table", "selectedRows"),
    State("fin-chart-selection-store", "data"),  # ← đọc template đang lưu
    prevent_initial_call=True,
)
def render_fin_charts_tab(active_tab, period, selected_rows, saved_selection):
    if active_tab != "tab-fin-charts":
        return no_update
    if not selected_rows:
        return html.P("Chọn một cổ phiếu để xem biểu đồ.",
                      style={"color": "#484f58", "padding": "20px", "textAlign": "center"})
    ticker = selected_rows[0].get("Ticker", "")
    period = period or "quarterly"
    try:
        from src.backend.data_loader import load_financial_data
        df_all = load_financial_data(period)
        if df_all is None or df_all.empty:
            raise ValueError("Không có dữ liệu BCTC")
        df = df_all[df_all["Ticker"] == ticker].sort_values("Date").tail(
            10 if period == "quarterly" else 7)
        if df.empty:
            raise ValueError(f"Không có dữ liệu cho {ticker}")
    except Exception as e:
        return html.P(str(e), style={"color": "#ef4444", "padding": "20px"})

    # Restore checkbox states từ template đã lưu trong session
    saved_selection = saved_selection or []

    return html.Div([
        html.Div([
            html.Span("Kỳ báo cáo:", style={"color": "#7fa8cc", "fontSize": "11px", "marginRight": "8px"}),
            dbc.ButtonGroup([
                dbc.Button("Quý", id="fin-chart-period-quarterly", size="sm",
                           color="primary" if period == "quarterly" else "secondary",
                           outline=period != "quarterly", style={"fontSize": "11px"}),
                dbc.Button("Năm", id="fin-chart-period-yearly", size="sm",
                           color="primary" if period == "yearly" else "secondary",
                           outline=period != "yearly", style={"fontSize": "11px"}),
            ]),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "12px", "padding": "8px 0"}),
        build_template_picker(saved_selection),   # ← truyền saved_selection để restore checkboxes
        html.Div(id="fin-charts-render-area", style={"marginTop": "14px"}),
        dcc.Store(id="fin-chart-df-ticker", data=ticker),
        dcc.Store(id="fin-chart-df-period", data=period),
    ], style={"padding": "12px 16px"})


@app.callback(
    Output("fin-chart-selection-store", "data"),
    Input("fin-chart-apply-btn", "n_clicks"),
    Input("fin-chart-clear-all", "n_clicks"),
    State({"type": "fin-chart-check", "index": ALL}, "value"),
    State({"type": "fin-chart-check", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def update_selection(n_apply, n_clear, all_vals, all_ids):
    ctx = callback_context
    if not ctx.triggered:
        return no_update
    if "clear-all" in ctx.triggered[0]["prop_id"]:
        return []
    return [v for vals in (all_vals or []) for v in (vals or [])]


@app.callback(
    Output("fin-charts-render-area","children"),
    Input("fin-chart-selection-store","data"),
    State("fin-chart-df-ticker","data"),
    State("fin-chart-df-period","data"),
    prevent_initial_call=True,
)
def render_charts(selected, ticker, period):
    if not selected:
        return html.Div([html.I(className="fas fa-chart-bar",style={"fontSize":"28px","color":"#30363d","marginBottom":"6px"}),
            html.P("Tick chọn biểu đồ → bấm 'THÊM VÀO TEMPLATE'",style={"color":"#484f58","fontSize":"12px"})],
            style={"textAlign":"center","padding":"30px"})
    try:
        from src.backend.data_loader import load_financial_data
        df_all=load_financial_data(period or "quarterly")
        df=df_all[df_all["Ticker"]==ticker].sort_values("Date").tail(10 if (period or "quarterly")=="quarterly" else 7)
        charts_html=[]
        pairs=[selected[i:i+2] for i in range(0,len(selected),2)]
        # Vẽ từng chart, skip nếu _NoData
        skipped = []
        valid_items = []
        for cid in selected:
            fn = RENDER_MAP.get(cid)
            label = ALL_CHART_IDS.get(cid, cid)
            if fn is None:
                continue
            try:
                fig = fn(df)
                fig.update_layout(height=fig.layout.height or 280)
                valid_items.append((label, fig))
            except _NoData as e:
                skipped.append(label)
                logger.info(f"Skip '{cid}': {e}")
            except Exception as e:
                logger.warning(f"{cid}: {e}")

        if skipped:
            charts_html.append(html.Div([
                html.I(className="fas fa-info-circle",
                       style={"color":"#f59e0b","marginRight":"6px","fontSize":"11px"}),
                html.Span("Ẩn " + str(len(skipped)) + " biểu đồ không có dữ liệu: " + " · ".join(skipped),
                          style={"color":"#7fa8cc","fontSize":"11px"}),
            ], style={"padding":"8px 12px","marginBottom":"10px",
                      "backgroundColor":"rgba(245,158,11,0.07)",
                      "border":"1px solid rgba(245,158,11,0.25)",
                      "borderRadius":"6px","display":"flex","alignItems":"center"}))

        if not valid_items:
            charts_html.append(html.Div([
                html.I(className="fas fa-database",
                       style={"fontSize":"28px","color":"#30363d","marginBottom":"6px"}),
                html.P("Không có dữ liệu để vẽ.", style={"color":"#484f58","fontSize":"12px"}),
            ], style={"textAlign":"center","padding":"30px"}))
            return html.Div(charts_html)

        pairs = [valid_items[i:i+2] for i in range(0, len(valid_items), 2)]
        for pair in pairs:
            row = []
            for label, fig in pair:
                row.append(html.Div(dcc.Graph(figure=fig, config={"displayModeBar":False},
                    style={"height":str(fig.layout.height)+"px"}),
                    style={"flex":"1","minWidth":"0","backgroundColor":"#0c1220","borderRadius":"8px",
                           "border":"1px solid #21262d","overflow":"hidden"}))
            charts_html.append(html.Div(row,style={"display":"flex","gap":"10px","marginBottom":"10px"}))
        return html.Div(charts_html)
    except Exception as e:
        logger.error(f"Render error: {e}"); return html.P(str(e),style={"color":"#ef4444"})


@app.callback(
    Output("fin-chart-period-store","data"),
    Input("fin-chart-period-quarterly","n_clicks"),
    Input("fin-chart-period-yearly","n_clicks"),
    prevent_initial_call=True,
)
def switch_period(n_q,n_y):
    ctx=callback_context
    if not ctx.triggered: return "quarterly"
    return "yearly" if "yearly" in ctx.triggered[0]["prop_id"] else "quarterly"