# src/pages/onboarding.py
# ─────────────────────────────────────────────────────────────────────────────
# IPS Onboarding — Giao diện FULL-PAGE liền mạch (kiểu onboarding.html)
#
# Hiển thị toàn màn hình khi user chưa thiết lập hồ sơ.
# Sau khi nhấn "Áp dụng ngay" ở Bước 5, profile-setup-done → True.
#
# Giữ nguyên 100% component IDs để callbacks trong
# investor_profile_callbacks.py không cần sửa.
# ─────────────────────────────────────────────────────────────────────────────

from dash import html, dcc
import dash_bootstrap_components as dbc

# ── Màu sắc nhất quán với dark theme VSS ─────────────────────────────────────
_VOID    = "#040810"
_BASE    = "#070e1c"
_SURFACE = "#0a1628"
_CARD    = "#0d1d36"
_ELEVATED= "#112340"
_HOVER   = "#172d50"
_BORDER  = "#1a3a60"
_BORDER_HI = "#2a5a90"

_ACCENT  = "#00e5ff"
_ACCENT2 = "#0090ff"
_GREEN   = "#00e676"
_AMBER   = "#ffb703"
_RED     = "#ff3d57"

_T1 = "#e8f4ff"
_T2 = "#7aafcc"
_T3 = "#3d6a8a"
_T4 = "#1d4060"

_FF_DISPLAY = "'Syne', 'Montserrat', sans-serif"
_FF_BODY    = "'DM Sans', 'Inter', sans-serif"
_FF_MONO    = "'DM Mono', 'JetBrains Mono', monospace"


# ── Hero Slideshow section ─────────────────────────────────────────────────
def _hero_section():
    return html.Section(
        id="hero-section",
        className="hero",
        children=[
            html.Div(id="hero-progress", className="hero-progress-bar", style={"width": "0%"}),
            html.Div(id="hero-slides-container"),
            html.Div(className="hero-controls", children=[
                html.Button("←", id="hero-prev", className="hero-btn"),
                html.Button("→", id="hero-next", className="hero-btn"),
                html.Span("01 / 10", id="hero-counter", className="hero-counter"),
                html.Span("· ← → keys", className="hero-keys"),
            ]),
            html.Div(id="hero-legend", className="hero-legend"),
            html.Div(id="hero-credit", className="hero-credit"),
            html.Div(id="hero-eras", className="hero-eras"),
            html.Div(className="hero-timeline", children=[
                html.Div(id="tl-inner", className="tl-inner"),
            ]),
        ]
    )


# ── Progress Rail (dạng dot + line như onboarding.html) ─────────────────────
def _progress_rail():
    steps = [
        ("1", "Mục tiêu"),
        ("2", "Rủi ro"),
        ("3", "Ràng buộc"),
        ("4", "Chiến lược"),
        ("5", "Xác nhận"),
    ]
    children = []
    for i, (num, label) in enumerate(steps, 1):
        dot_cls = "rail-dot" + (" active" if i == 1 else "")
        lbl_cls = "rail-label" + (" active" if i == 1 else "")
        children.append(html.Div([
            html.Div(num, id=f"dot-{i}", className=dot_cls),
            html.Div(label, id=f"lbl-{i}", className=lbl_cls),
        ], className="rail-step"))
        if i < 5:
            children.append(html.Div(id=f"line-{i}", className="rail-line"))

    return html.Div(children, id="progress-rail", className="progress-rail")


# ── Choice card (icon + label + sub-label) ───────────────────────────────────
def _choice_card(id_str, icon_emoji, label, sub, group, value):
    return html.Div(
        [
            html.Div("✓", className="check"),
            html.Span(icon_emoji, className="choice-icon"),
            html.Div(label, className="choice-label"),
            html.Div(sub, className="choice-sub"),
        ],
        id={"type": "ips-choice", "id": id_str},
        **{"data-value": value, "data-group": group},
        className="choice-card",
    )


# ── Step eyebrow (số bước + đường kẻ) ────────────────────────────────────────
def _step_eyebrow(num_text):
    return html.Div([
        html.Span(num_text, className="step-num"),
        html.Div(className="step-line"),
    ], className="step-eyebrow")


# ── STEP 1: Mục tiêu ─────────────────────────────────────────────────────────
def _step1():
    return html.Div(id="ips-step-1", className="section", children=[
        _step_eyebrow("Bước 01 / 05"),
        html.H2([
            "Mục tiêu đầu tư", html.Br(),
            html.Em("chính của bạn"), " là gì?"
        ], className="step-title"),
        html.P(
            "Câu trả lời này quyết định toàn bộ chiến lược và bộ lọc được áp dụng cho danh mục của bạn.",
            className="step-desc"
        ),
        html.Div([
            _choice_card("goal-preserve", "🛡️", "Bảo toàn vốn",       "An toàn là ưu tiên số 1",        "goal", "preserve"),
            _choice_card("goal-income",   "🪙", "Tạo dòng tiền",       "Cổ tức đều đặn hàng quý",        "goal", "income"),
            _choice_card("goal-growth",   "📈", "Tăng trưởng tài sản", "Tích lũy dài hạn 3–10 năm",      "goal", "growth"),
            _choice_card("goal-speculate","🚀", "Lướt sóng sinh lời",  "Cơ hội ngắn hạn, linh hoạt",     "goal", "speculate"),
        ], className="choice-grid"),
        html.P(id="ips-step1-error", className="step-error"),
    ])


# ── STEP 2: Tâm lý rủi ro ────────────────────────────────────────────────────
def _step2():
    return html.Div(id="ips-step-2", className="section", children=[
        _step_eyebrow("Bước 02 / 05"),
        html.H2([
            "Nếu danh mục giảm", html.Br(),
            html.Em("20% trong 1 tháng"), ", bạn làm gì?"
        ], className="step-title"),
        html.P(
            "Đây là thước đo khẩu vị rủi ro thực sự — Willingness to Take Risk theo chuẩn CFA Level 3.",
            className="step-desc"
        ),
        html.Div([
            _choice_card("will-panic", "📉", "Bán cắt lỗ ngay",   "Không thể chịu thua lỗ",        "will", "panic"),
            _choice_card("will-worry", "☕", "Lo lắng, chờ đợi",  "Theo dõi và chờ tình hình",      "will", "worry"),
            _choice_card("will-hold",  "⚓", "Giữ vững kế hoạch", "Tin tưởng chiến lược dài hạn",   "will", "hold"),
            _choice_card("will-buy",   "🛒", "Vui mừng mua thêm", "Giảm giá = cơ hội mua vào",     "will", "buy"),
        ], className="choice-grid"),
        html.P(id="ips-step2-error", className="step-error"),
    ])


# ── STEP 3: Ràng buộc tài chính ──────────────────────────────────────────────
def _step3():
    return html.Div(id="ips-step-3", className="section", children=[
        _step_eyebrow("Bước 03 / 05"),
        html.H2([
            "Thời gian &", html.Br(),
            html.Em("ràng buộc tài chính"),
        ], className="step-title"),
        html.P(
            "Giúp VSS xác định Ability to Take Risk — yếu tố thứ hai trong mô hình IPS chuẩn CFA L3.",
            className="step-desc"
        ),

        # Time horizon
        html.P("Thời gian đầu tư dự kiến", className="section-sub-label"),
        html.Div([
            _choice_card("time-short", "⏱️", "Dưới 1 Năm", "Ngắn hạn linh hoạt",   "time", "short"),
            _choice_card("time-mid",   "📅", "1 – 3 Năm",  "Trung hạn cân bằng",   "time", "mid"),
            _choice_card("time-long",  "∞",  "Trên 3 Năm", "Dài hạn tích lũy",     "time", "long"),
        ], className="choice-grid cols-3", style={"marginBottom": "28px"}),

        # Liquidity
        html.P("Nhu cầu rút tiền đột xuất (Liquidity)", className="section-sub-label"),
        html.Div([
            _choice_card("liq-high", "💸", "Cao",         "Cần rút bất cứ lúc nào",  "liq", "high"),
            _choice_card("liq-mid",  "💧", "Trung bình",  "Thỉnh thoảng cần rút",    "liq", "mid"),
            _choice_card("liq-low",  "🔒", "Thấp",        "Có thể để dài hạn",       "liq", "low"),
        ], className="choice-grid cols-3", style={"marginBottom": "32px"}),

        # Sliders
        html.Div([
            html.Div([
                html.Span("% Thu nhập hàng tháng dành cho Chứng khoán"),
                html.Span("30%", id="savings-val", className="slider-val"),
            ], className="slider-label"),
            dcc.Slider(
                0, 100, 5, value=30, id="ips-pct-savings-slider",
                tooltip={"placement": "bottom", "always_visible": False},
                className="ips-slider",
            ),
        ], className="slider-row"),

        html.Div([
            html.Div([
                html.Span("Quỹ dự phòng khẩn cấp (số tháng chi tiêu)"),
                html.Span("4 tháng", id="emergency-val", className="slider-val"),
            ], className="slider-label"),
            dcc.Slider(
                0, 12, 1, value=4, id="ips-emergency-slider",
                tooltip={"placement": "bottom", "always_visible": False},
                className="ips-slider",
            ),
        ], className="slider-row"),

        # Checklist
        html.Div([
            html.Div([
                html.Div("✓", className="check-box checked"),
                html.Span("Ưu tiên nhận cổ tức đều đặn", className="check-item-label"),
            ], className="check-item checked", **{"data-key": "prefer_dividend"}),
            html.Div([
                html.Div("", className="check-box"),
                html.Span("Tránh mua Ngân hàng / Bất động sản", className="check-item-label"),
            ], className="check-item", **{"data-key": "avoid_bank_re"}),
            html.Div([
                html.Div("✓", className="check-box checked"),
                html.Span("Bật chế độ Người Mới (Beginner Mode)", className="check-item-label"),
            ], className="check-item checked", **{"data-key": "beginner"}),
        ], className="check-list"),

        html.P(id="ips-step3-error", className="step-error"),
    ])


# ── STEP 4: Preview profile ──────────────────────────────────────────────────
def _step4():
    return html.Div(id="ips-step-4", className="section", children=[
        _step_eyebrow("Bước 04 / 05"),
        html.H2([
            "Hồ sơ ", html.Em("đầu tư của bạn"),
        ], className="step-title"),
        html.P(
            "VSS đã tổng hợp hồ sơ IPS dựa trên câu trả lời. Xem lại và xác nhận trước khi áp dụng bộ lọc.",
            className="step-desc"
        ),

        html.Div(className="summary-card", children=[
            html.Div([
                html.Div("Investment Policy Statement", className="summary-title"),
                html.Div("Moderate Growth", id="risk-badge-text", className="risk-badge risk-moderate"),
            ], className="summary-header"),

            html.Div([
                html.Div([html.Div("Mục tiêu",         className="sum-label"), html.Div("—", id="sum-goal", className="sum-value hi")],  className="summary-cell"),
                html.Div([html.Div("Khẩu vị rủi ro",   className="sum-label"), html.Div("—", id="sum-will", className="sum-value hi")],  className="summary-cell"),
                html.Div([html.Div("Thời gian đầu tư",  className="sum-label"), html.Div("—", id="sum-time", className="sum-value")],    className="summary-cell"),
                html.Div([html.Div("Thanh khoản",        className="sum-label"), html.Div("—", id="sum-liq",  className="sum-value")],    className="summary-cell"),
                html.Div([html.Div("% Tiết kiệm / tháng",className="sum-label"),html.Div("30%", id="sum-savings", className="sum-value")],className="summary-cell"),
                html.Div([html.Div("Quỹ dự phòng",      className="sum-label"), html.Div("4 tháng", id="sum-emergency", className="sum-value")], className="summary-cell"),
            ], className="summary-grid"),

            html.Div([
                html.Div("Bộ lọc được đề xuất tự động", className="sum-filter-title"),
                html.Div([
                    html.Span("ROE ≥ 15%",          className="filter-tag"),
                    html.Span("P/E ≤ 20",           className="filter-tag"),
                    html.Span("D/E ≤ 1",            className="filter-tag"),
                    html.Span("Vốn hóa ≥ 5.000 tỷ",className="filter-tag"),
                    html.Span("Cổ tức ≥ 3%",        className="filter-tag"),
                ], id="filter-tags", className="filter-tags"),
            ], className="summary-filter-list"),
        ]),

        # Hidden stores for callbacks
        dcc.Store(id="ips-profile-preview"),
    ])


# ── STEP 5: Xác nhận & Apply ─────────────────────────────────────────────────
def _step5():
    return html.Div(id="ips-step-5", className="section", children=[
        _step_eyebrow("Bước 05 / 05"),
        html.H2([
            "Sẵn sàng", html.Br(),
            html.Em("khám phá thị trường"),
        ], className="step-title"),
        html.P(
            "Lưu hồ sơ và áp dụng bộ lọc thông minh ngay vào Screener của bạn.",
            className="step-desc"
        ),

        html.Div([
            html.Div([
                html.Div("✓", className="check-box checked"),
                html.Span("Tự động cấu hình Bộ Lọc Screener theo Hồ sơ này", className="check-item-label"),
            ], className="check-item checked", **{"data-key": "apply_filters"}),
            html.Div([
                html.Div("✓", className="check-box checked"),
                html.Span("Lưu hồ sơ vào thiết bị (localStorage)", className="check-item-label"),
            ], className="check-item checked", **{"data-key": "save_profile"}),
        ], className="check-list"),

        # Keep dbc.Checklist ẩn để callbacks vẫn hoạt động bình thường
        dbc.Checklist(
            options=[{"label": "", "value": "apply_filters"}],
            value=["apply_filters"],
            id="ips-apply-options",
            style={"display": "none"},
        ),

        html.Div([
            html.Div("⚠️", className="disclaimer-icon"),
            html.P(
                "Toàn bộ gợi ý chỉ mang tính tham khảo, không phải khuyến nghị mua/bán chứng khoán. "
                "Nhà đầu tư tự chịu trách nhiệm với quyết định của mình theo quy định pháp luật hiện hành.",
            ),
        ], className="disclaimer"),

        html.Div(id="ips-final-summary"),
        html.P(id="ips-apply-status", className="apply-status"),
    ])


# ── Onboarding JS (inline, tương tự onboarding.html) ─────────────────────────
def _onboarding_script():
    """Script xử lý navigate, validate, summary, apply — tương thích callbacks."""
    return html.Script("""
(function() {
  var currentStep = 1;
  var totalSteps  = 5;

  var state = {
    goal: null, will: null, time: null, liq: null,
    savings: 30, emergency: 4,
    checks: { prefer_dividend:true, avoid_bank_re:false, beginner:true, apply_filters:true, save_profile:true }
  };

  var LABELS = {
    goal: { preserve:'Bảo toàn vốn', income:'Tạo dòng tiền', growth:'Tăng trưởng', speculate:'Lướt sóng' },
    will: { panic:'Bán cắt lỗ', worry:'Lo lắng chờ đợi', hold:'Giữ vững kế hoạch', buy:'Mua thêm' },
    time: { short:'Dưới 1 năm', mid:'1 – 3 năm', long:'Trên 3 năm' },
    liq:  { high:'Cao', mid:'Trung bình', low:'Thấp' },
  };

  var FILTER_MAP = {
    preserve:  ['ROE ≥ 12%', 'D/E ≤ 0.5', 'Beta ≤ 0.8', 'P/B ≤ 1.5'],
    income:    ['Cổ tức ≥ 3%', 'ROE ≥ 15%', 'P/E ≤ 15', 'Dòng tiền dương'],
    growth:    ['EPS CAGR ≥ 15%', 'ROE ≥ 18%', 'P/E ≤ 25', 'Vốn hóa ≥ 5.000 tỷ'],
    speculate: ['RSI(14) 30–70', 'MACD Hist > 0', 'KL / SMA20 ≥ 1.5', 'Giá vs SMA20 > 0'],
  };

  var RISK_BADGES = {
    preserve:  { text:'Conservative',   cls:'risk-conservative' },
    income:    { text:'Income Focus',   cls:'risk-conservative' },
    growth:    { text:'Moderate Growth',cls:'risk-moderate'     },
    speculate: { text:'Aggressive',     cls:'risk-aggressive'   },
  };

  // ── Choice selection ──────────────────────────────────────────────────────
  window.selectChoice = function(card) {
    var group = card.getAttribute('data-group');
    var value = card.getAttribute('data-value');
    document.querySelectorAll('.choice-card[data-group="' + group + '"]')
      .forEach(function(c) { c.classList.remove('selected'); });
    card.classList.add('selected');
    state[group] = value;
    addRipple(card);
    var errMap = { goal:'ips-step1-error', will:'ips-step2-error', time:'ips-step3-error', liq:'ips-step3-error' };
    var errEl = document.getElementById(errMap[group]);
    if (errEl) errEl.textContent = '';
    updateSummary();
  };

  function addRipple(el) {
    var r = document.createElement('span');
    r.className = 'ripple';
    r.style.cssText = 'left:50%;top:50%;width:100px;height:100px;margin-left:-50px;margin-top:-50px;';
    el.appendChild(r);
    setTimeout(function() { r.remove(); }, 600);
  }

  // ── Checkbox toggle ───────────────────────────────────────────────────────
  window.toggleCheck = function(item) {
    var key = item.getAttribute('data-key');
    item.classList.toggle('checked');
    var checked = item.classList.contains('checked');
    var box = item.querySelector('.check-box');
    if (box) { box.textContent = checked ? '✓' : ''; box.classList.toggle('checked', checked); }
    state.checks[key] = checked;
  };

  // ── Rail rendering ────────────────────────────────────────────────────────
  function renderRail() {
    for (var i = 1; i <= totalSteps; i++) {
      var dot = document.getElementById('dot-' + i);
      var lbl = document.getElementById('lbl-' + i);
      if (!dot) continue;
      dot.className = 'rail-dot';
      lbl.className = 'rail-label';
      if (i < currentStep)       { dot.classList.add('done');   lbl.classList.add('done');   dot.textContent = '✓'; }
      else if (i === currentStep) { dot.classList.add('active'); lbl.classList.add('active'); dot.textContent = i; }
      else                        { dot.textContent = i; }
      if (i < totalSteps) {
        var line = document.getElementById('line-' + i);
        if (line) line.className = 'rail-line' + (i < currentStep ? ' done' : '');
      }
    }
    var pill = document.getElementById('step-counter');
    if (pill) pill.textContent = 'Bước ' + currentStep + ' / ' + totalSteps;
    var ipsCounter = document.getElementById('ips-step-counter');
    if (ipsCounter) ipsCounter.textContent = 'Bước ' + currentStep + ' / ' + totalSteps;
  }

  // ── Show/hide sections ────────────────────────────────────────────────────
  function showStep(step) {
    for (var i = 1; i <= totalSteps; i++) {
      var sec = document.getElementById('ips-step-' + i);
      if (!sec) continue;
      if (i === step) {
        sec.style.display = '';
        setTimeout(function(s){ return function() { s.scrollIntoView({behavior:'smooth', block:'start'}); }; }(sec), 60);
      } else {
        sec.style.display = 'none';
      }
      // Also handle dividers
      var div = document.getElementById('div-' + i);
      if (div) div.style.display = i < step ? '' : 'none';
    }
  }

  // ── Navigate ──────────────────────────────────────────────────────────────
  window.navigate = function(dir) {
    if (dir === 1) {
      if (currentStep === 1 && !state.goal) {
        showError('ips-step1-error', '⚠ Vui lòng chọn một mục tiêu đầu tư.');
        shake('ips-step-1'); return;
      }
      if (currentStep === 2 && !state.will) {
        showError('ips-step2-error', '⚠ Vui lòng chọn phản ứng của bạn.');
        shake('ips-step-2'); return;
      }
      if (currentStep === 3 && (!state.time || !state.liq)) {
        showError('ips-step3-error', '⚠ Vui lòng chọn đầy đủ thời gian và thanh khoản.');
        shake('ips-step-3'); return;
      }
      if (currentStep === 4) updateSummary();
      if (currentStep === totalSteps) { applyProfile(); return; }
    }
    var newStep = Math.max(1, Math.min(totalSteps, currentStep + dir));
    if (newStep === currentStep) return;
    currentStep = newStep;
    renderRail();
    updateNavButtons();
    showStep(currentStep);
  };

  // ── Nav button clicks (wire to Dash buttons) ──────────────────────────────
  function wireNavButtons() {
    var prevBtn = document.getElementById('ips-btn-prev');
    var nextBtn = document.getElementById('ips-btn-next');
    var prevBtn2 = document.getElementById('btn-prev');
    var nextBtn2 = document.getElementById('btn-next');

    function onPrev(e) { e.preventDefault(); navigate(-1); }
    function onNext(e) { e.preventDefault(); navigate(1); }

    if (prevBtn) prevBtn.addEventListener('click', onPrev);
    if (nextBtn) nextBtn.addEventListener('click', onNext);
    if (prevBtn2) prevBtn2.addEventListener('click', onPrev);
    if (nextBtn2) nextBtn2.addEventListener('click', onNext);
  }

  function updateNavButtons() {
    var prev = document.getElementById('ips-btn-prev') || document.getElementById('btn-prev');
    var next = document.getElementById('ips-btn-next') || document.getElementById('btn-next');
    if (prev) prev.style.visibility = currentStep === 1 ? 'hidden' : 'visible';
    if (next) {
      if (currentStep === totalSteps) {
        next.innerHTML = '🚀 Áp dụng ngay';
        next.className = (next.className || '').replace('btn-primary','') + ' btn-success';
      } else {
        next.innerHTML = 'Tiếp theo →';
        next.className = (next.className || '').replace('btn-success','') + ' btn-primary';
      }
    }
  }

  function showError(id, msg) {
    var el = document.getElementById(id);
    if (el) el.textContent = msg;
  }

  function shake(id) {
    var el = document.getElementById(id);
    if (!el) return;
    el.style.animation = 'none';
    void el.offsetWidth;
    el.style.animation = 'ipsShake 0.4s ease';
    setTimeout(function() { el.style.animation = ''; }, 400);
  }

  // ── Summary (step 4) ──────────────────────────────────────────────────────
  function updateSummary() {
    if (state.goal) {
      var gEl = document.getElementById('sum-goal');
      if (gEl) gEl.textContent = LABELS.goal[state.goal] || '—';
      var badge = RISK_BADGES[state.goal] || { text:'—', cls:'risk-moderate' };
      var badgeEl = document.getElementById('risk-badge-text');
      if (badgeEl) { badgeEl.textContent = badge.text; badgeEl.className = 'risk-badge ' + badge.cls; }
      var tags = FILTER_MAP[state.goal] || [];
      var tagsCont = document.getElementById('filter-tags');
      if (tagsCont) {
        tagsCont.innerHTML = '';
        tags.forEach(function(t, i) {
          var span = document.createElement('span');
          span.className = 'filter-tag';
          span.style.animationDelay = (i * 0.06) + 's';
          span.textContent = t;
          tagsCont.appendChild(span);
        });
      }
    }
    if (state.will) { var wEl = document.getElementById('sum-will'); if (wEl) wEl.textContent = LABELS.will[state.will] || '—'; }
    if (state.time) { var tEl = document.getElementById('sum-time'); if (tEl) tEl.textContent = LABELS.time[state.time] || '—'; }
    if (state.liq)  { var lEl = document.getElementById('sum-liq');  if (lEl) lEl.textContent = LABELS.liq[state.liq]  || '—'; }
    var sEl = document.getElementById('sum-savings');   if (sEl) sEl.textContent = state.savings + '%';
    var eEl = document.getElementById('sum-emergency'); if (eEl) eEl.textContent = state.emergency + ' tháng';
  }

  // ── Apply ─────────────────────────────────────────────────────────────────
  function applyProfile() {
    var statusEl = document.getElementById('ips-apply-status') || document.getElementById('apply-status');
    if (statusEl) statusEl.textContent = '⟳ Đang lưu hồ sơ…';
    setTimeout(function() {
      if (state.checks.save_profile) {
        try { localStorage.setItem('vss_profile', JSON.stringify(state)); } catch(e) {}
      }
      if (statusEl) statusEl.textContent = '✅ Hồ sơ đã được lưu! Đang áp dụng bộ lọc…';
      // Trigger Dash btn-next click để callback xử lý tiếp
      var dashNext = document.getElementById('ips-btn-next');
      if (dashNext) setTimeout(function() { dashNext.click(); }, 600);
    }, 700);
  }

  // ── Init ──────────────────────────────────────────────────────────────────
  function init() {
    // Inject shake keyframe
    var sEl = document.createElement('style');
    sEl.textContent = '@keyframes ipsShake{0%,100%{transform:translateX(0)}25%{transform:translateX(-8px)}75%{transform:translateX(8px)}}';
    document.head.appendChild(sEl);

    renderRail();
    showStep(1);
    updateNavButtons();
    wireNavButtons();
  }

  // Đợi DOM sẵn sàng
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
  // Dash re-renders DOM → observer lại
  var mo = new MutationObserver(function(muts) {
    var needInit = muts.some(function(m) {
      return Array.from(m.addedNodes).some(function(n) {
        return n.nodeType === 1 && (n.id === 'ips-onboarding-wrapper' || (n.querySelector && n.querySelector('#ips-step-1')));
      });
    });
    if (needInit) { setTimeout(init, 100); }
  });
  mo.observe(document.body, { childList: true, subtree: true });

})();
""")


# ── Logo + tagline header ─────────────────────────────────────────────────────
def _logo_header():
    return html.Div(className="logo-bar", children=[
        html.Div("📈", className="logo-icon"),
        html.Div("VSS Smart Screener", className="logo-name"),
    ]), html.P(
        [
            "Trước khi bắt đầu, hãy để VSS hiểu rõ hơn về bạn —",
            html.Br(),
            "chỉ mất 2 phút để thiết lập hồ sơ đầu tư cá nhân.",
        ],
        className="logo-tagline"
    )


# ── Nav bar (Quay lại / Tiếp theo) ───────────────────────────────────────────
def _nav_bar():
    return html.Div(className="nav-bar", children=[
        html.Button("← Quay lại", id="ips-btn-prev", className="btn btn-ghost",
                    style={"visibility": "hidden"}),
        html.Span("Bước 1 / 5", id="ips-step-counter", className="step-counter-pill"),
        html.Button("Tiếp theo →", id="ips-btn-next", className="btn btn-primary"),
    ])


# ─────────────────────────────────────────────────────────────────────────────
# EXPORT: layout
# ─────────────────────────────────────────────────────────────────────────────
logo_h, logo_tagline = _logo_header()

layout = html.Div(
    id="ips-onboarding-wrapper",
    children=[
        # Hero slideshow
        _hero_section(),

        # Page wrapper (giống onboarding.html .page)
        html.Div(className="page", children=[

            # Logo
            logo_h,
            logo_tagline,

            # Progress rail
            _progress_rail(),

            # Steps — hiển thị liền mạch, JS sẽ hide/show
            _step1(),
            html.Hr(id="div-1", className="divider"),
            _step2(),
            html.Hr(id="div-2", className="divider"),
            _step3(),
            html.Hr(id="div-3", className="divider"),
            _step4(),
            html.Hr(id="div-4", className="divider"),
            _step5(),

            # Nav bar cố định
            _nav_bar(),

            html.P(
                "🔒 Dữ liệu hồ sơ được lưu trên thiết bị của bạn — không gửi lên máy chủ.",
                className="footer-note"
            ),

            # Hidden stores for callbacks
            dcc.Store(id="ips-current-step",  data=1),
            dcc.Store(id="ips-goal-store",    data=None),
            dcc.Store(id="ips-will-store",    data=None),
            dcc.Store(id="ips-time-store",    data=None),
            dcc.Store(id="ips-liq-store",     data=None),

            # Hidden Dash checklist cho callbacks
            dbc.Checklist(
                options=[
                    {"label": "", "value": "prefer_dividend"},
                    {"label": "", "value": "avoid_bank_re"},
                    {"label": "", "value": "beginner"},
                ],
                value=["prefer_dividend", "beginner"],
                id="ips-unique-checklist",
                style={"display": "none"},
            ),

            # Hidden sliders for callback sync
            html.Div(style={"display": "none"}, children=[
                dcc.Slider(0, 100, 10, value=30, id="ips-pct-savings-slider-hidden"),
                dcc.Slider(0, 12, 1, value=4, id="ips-emergency-slider-hidden"),
            ]),

            # Inline onboarding script
            _onboarding_script(),
        ]),
    ],
)