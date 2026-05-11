// assets/hero_slideshow.js — VSS Smart Screener
// Cập nhật: sự kiện tài chính Việt Nam + typography nâng cấp

(function initHero() {
  if (!document.getElementById('hero-section')) {
    setTimeout(initHero, 200);
    return;
  }

  // ── Inject font DM Sans + Syne nếu chưa có ──────────────────────────────
  if (!document.querySelector('link[href*="Syne"]')) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap';
    document.head.appendChild(link);
  }

  // ── Inject enhanced hero typography styles ───────────────────────────────
  const heroStyle = document.createElement('style');
  heroStyle.textContent = `
    .hero-year {
      font-family: 'Syne', 'Montserrat', sans-serif !important;
      font-size: clamp(88px, 13vw, 168px) !important;
      font-weight: 800 !important;
      line-height: 0.85 !important;
      letter-spacing: -5px !important;
      color: #ffffff !important;
      margin-bottom: 20px !important;
      text-shadow: 0 0 120px rgba(255,255,255,0.06) !important;
      opacity: 0;
      transform: translateY(24px);
      transition: opacity 0.7s 0.08s cubic-bezier(0.22,1,0.36,1),
                  transform 0.7s 0.08s cubic-bezier(0.22,1,0.36,1) !important;
    }
    .hero-slide.active .hero-year { opacity:1 !important; transform:translateY(0) !important; }

    .hero-tagline {
      font-family: 'Syne', 'Montserrat', sans-serif !important;
      font-size: clamp(20px, 2.8vw, 34px) !important;
      font-weight: 700 !important;
      color: #e8f4ff !important;
      line-height: 1.18 !important;
      letter-spacing: -0.3px !important;
      margin-bottom: 16px !important;
      max-width: 580px !important;
      opacity: 0;
      transform: translateY(16px);
      transition: opacity 0.65s 0.22s cubic-bezier(0.22,1,0.36,1),
                  transform 0.65s 0.22s cubic-bezier(0.22,1,0.36,1) !important;
    }
    .hero-slide.active .hero-tagline { opacity:1 !important; transform:translateY(0) !important; }

    .hero-desc {
      font-family: 'DM Sans', 'Inter', sans-serif !important;
      font-size: 14.5px !important;
      font-weight: 400 !important;
      color: rgba(200,220,240,0.62) !important;
      line-height: 1.75 !important;
      max-width: 500px !important;
      margin-bottom: 30px !important;
      letter-spacing: 0.1px !important;
      opacity: 0;
      transform: translateY(10px);
      transition: opacity 0.6s 0.36s ease, transform 0.6s 0.36s ease !important;
    }
    .hero-slide.active .hero-desc { opacity:1 !important; transform:translateY(0) !important; }

    .hero-badge {
      font-family: 'DM Mono', 'JetBrains Mono', monospace !important;
      font-size: 10.5px !important; font-weight:500 !important;
      letter-spacing: 2px !important; border-radius: 3px !important;
      padding: 4px 11px !important; margin-bottom: 18px !important;
    }
    .stat-label {
      font-family: 'DM Mono', monospace !important;
      font-size: 9px !important; color: rgba(200,220,240,0.32) !important;
      letter-spacing: 1.8px !important; text-transform: uppercase !important;
    }
    .stat-value {
      font-family: 'DM Mono', monospace !important;
      font-size: 17px !important; font-weight: 500 !important; letter-spacing: -0.5px !important;
    }
    .hero-stats { opacity:0; transition:opacity 0.5s 0.5s ease !important; }
    .hero-slide.active .hero-stats { opacity:1 !important; }

    .hero-enter {
      font-family: 'Syne', sans-serif !important;
      font-size: 12px !important; font-weight: 800 !important; letter-spacing: 0.8px !important;
    }
    .hero-counter { font-family:'DM Mono',monospace !important; font-size:11px !important; color:rgba(200,220,240,0.28) !important; letter-spacing:1px !important; }
    .hero-keys { font-family:'DM Mono',monospace !important; font-size:10px !important; color:rgba(200,220,240,0.18) !important; }
    .era-tab { font-family:'DM Mono',monospace !important; font-size:9.5px !important; letter-spacing:1.4px !important; }
    .tl-tick-label { font-family:'DM Mono',monospace !important; font-size:8.5px !important; color:rgba(200,220,240,0.18) !important; }
    .legend-dot-item { font-family:'DM Mono',monospace !important; font-size:9.5px !important; letter-spacing:1px !important; }
    .hero-credit { font-family:'DM Mono',monospace !important; font-size:9px !important; color:rgba(200,220,240,0.16) !important; }

    .era-doi-moi     { color:#3a6eb3 !important; }
    .era-khung-hoang { color:#b33a3a !important; }
    .era-ttck        { color:#8b3ab3 !important; }
    .era-tai-co-cau  { color:#b37a3a !important; }
    .era-covid       { color:#3ab36e !important; }
  `;
  document.head.appendChild(heroStyle);

  // ── DỮ LIỆU SỰ KIỆN TÀI CHÍNH VIỆT NAM ────────────────────────────────
  const EVENTS = [
    {
      year:'1986', era:'doi-moi', badge:'policy', badgeDate:'18/12',
      tagline:'Đổi Mới — Việt Nam <span class="hl-blue">mở cửa</span> nền kinh tế.',
      desc:'Đại hội VI quyết định chuyển từ kinh tế kế hoạch hoá sang kinh tế thị trường định hướng XHCN. Nền tảng cho toàn bộ thị trường vốn sau này.',
      move:'Reform', moveCls:'stat-neut', coverage:'Lưu trữ hàng tháng · Một phần',
      bgColor:'#080d18', credit:'', dot:'#00e5ff', eraIdx:0,
    },
    {
      year:'1993', era:'doi-moi', badge:'policy', badgeDate:'11/07',
      tagline:'Mỹ <span class="hl-blue">bỏ cấm vận</span>. Dòng vốn ngoại bắt đầu chảy vào.',
      desc:'Mỹ bình thường hoá quan hệ và dỡ lệnh cấm vận 18 năm. FDI tăng đột biến, kỷ nguyên hội nhập kinh tế mới bắt đầu.',
      move:'FDI+', moveCls:'stat-pos', coverage:'Lưu trữ hàng tháng · Đầy đủ',
      bgColor:'#08100d', credit:'', dot:'#00e676', eraIdx:0,
    },
    {
      year:'1997', era:'khung-hoang', badge:'panic', badgeDate:'02/07',
      tagline:'Khủng hoảng châu Á — <span class="hl">đồng tiền</span> Đông Nam Á sụp đổ.',
      desc:'Đồng baht Thái phá giá kéo theo làn sóng tháo chạy vốn khắp khu vực. Việt Nam chịu tác động gián tiếp nhưng tránh thảm hoạ nhờ kiểm soát vốn chặt.',
      move:'−40%', moveCls:'stat-neg', coverage:'Lưu trữ hàng ngày · Một phần',
      bgColor:'#100a00', credit:'', dot:'#ffb703', eraIdx:1,
    },
    {
      year:'2000', era:'ttck', badge:'boom', badgeDate:'20/07',
      tagline:'HOSE khai trương — <span class="hl-green">chứng khoán</span> Việt Nam ra đời.',
      desc:'Trung tâm Giao dịch Chứng khoán TP.HCM mở phiên giao dịch đầu tiên với 2 mã REE và SAM. VNIndex khởi đầu tại mốc 100 điểm.',
      move:'VNI 100', moveCls:'stat-pos', coverage:'Dữ liệu phiên · Đầy đủ',
      bgColor:'#081208', credit:'', dot:'#00e676', eraIdx:2,
    },
    {
      year:'2007', era:'ttck', badge:'mania', badgeDate:'12/03',
      tagline:'VNIndex <span class="hl-purple">lên đỉnh</span> 1.170 điểm. Cơn sốt chứng khoán toàn dân.',
      desc:'Sau khi gia nhập WTO, hàng triệu tài khoản mở mới chỉ trong vài tháng. VNIndex tăng 145% từ đầu năm, tạo bong bóng lịch sử.',
      move:'+145%', moveCls:'stat-pos', coverage:'Dữ liệu 1 phút · Đầy đủ',
      bgColor:'#0d0a14', credit:'', dot:'#b388ff', eraIdx:2,
    },
    {
      year:'2008', era:'khung-hoang', badge:'crash', badgeDate:'28/02',
      tagline:'VNIndex <span class="hl">rơi tự do</span> về 286 điểm. Bong bóng vỡ.',
      desc:'Từ đỉnh 1.170 xuống đáy 286 điểm, mất gần 76% trong 12 tháng. Lạm phát phi mã 23%, tín dụng bị siết, hàng vạn nhà đầu tư thua lỗ nặng.',
      move:'−76%', moveCls:'stat-neg', coverage:'Dữ liệu 1 phút · Đầy đủ',
      bgColor:'#140808', credit:'', dot:'#ff3d57', eraIdx:1,
    },
    {
      year:'2012', era:'tai-co-cau', badge:'policy', badgeDate:'01/06',
      tagline:'Tái cơ cấu ngân hàng — <span class="hl-amber">nợ xấu</span> phủ bóng thị trường.',
      desc:'NHNN khởi động hợp nhất, sáp nhập ngân hàng. VAMC ra đời mua nợ xấu. VNIndex lình xình vùng 350–470 điểm suốt 3 năm, thanh khoản sụt giảm mạnh.',
      move:'Sideways', moveCls:'stat-neut', coverage:'Dữ liệu 1 phút · Đầy đủ',
      bgColor:'#0c0d08', credit:'', dot:'#ffb703', eraIdx:3,
    },
    {
      year:'2020', era:'covid', badge:'crash', badgeDate:'24/03',
      tagline:'COVID-19 — VNIndex <span class="hl">mất 33%</span> trong 5 tuần.',
      desc:'Từ đỉnh 940 điểm xuống đáy 629 điểm khi cả nước giãn cách. Nhưng nhà đầu tư F0 ào ạt mở tài khoản — thanh khoản bùng nổ kỷ lục.',
      move:'−33%', moveCls:'stat-neg', coverage:'Dữ liệu 1 phút · Đầy đủ',
      bgColor:'#080a10', credit:'', dot:'#ff3d57', eraIdx:4,
    },
    {
      year:'2021', era:'covid', badge:'boom', badgeDate:'25/11',
      tagline:'VNIndex <span class="hl-green">chinh phục</span> đỉnh lịch sử 1.500 điểm.',
      desc:'Hơn 1,5 triệu tài khoản mở mới trong năm 2021 — kỷ lục mọi thời đại. Thanh khoản đạt 30.000–40.000 tỷ đồng mỗi phiên, gấp đôi năm 2020.',
      move:'+68%', moveCls:'stat-pos', coverage:'Dữ liệu 1 phút · Đầy đủ',
      bgColor:'#081208', credit:'', dot:'#00e676', eraIdx:4,
    },
    {
      year:'2026', era:'covid', badge:'policy', badgeDate:'HÔM NAY',
      tagline:'Bạn đang <span class="hl-green">giao dịch</span> TTCK Việt Nam trực tiếp.',
      desc:'Dữ liệu real-time đang streaming. Hệ thống KRX vận hành — thanh toán T+1.5. Mở biểu đồ và bắt đầu giao dịch ngay bây giờ.',
      move:'LIVE', moveCls:'stat-neut', coverage:'Live · Streaming now',
      bgColor:'#040d18', credit:'', dot:'#00e5ff', eraIdx:4,
    },
  ];

  const ERAS = [
    { id:'doi-moi',     label:'Đổi Mới',       color:'#3a6eb3' },
    { id:'khung-hoang', label:'Khủng Hoảng',   color:'#b33a3a' },
    { id:'ttck',        label:'TTCK Ra Đời',   color:'#8b3ab3' },
    { id:'tai-co-cau',  label:'Tái Cơ Cấu',   color:'#b37a3a' },
    { id:'covid',       label:'COVID / Bùng Nổ',color:'#3ab36e' },
  ];

  const ERA_ID_MAP = ['doi-moi','khung-hoang','ttck','tai-co-cau','covid'];
  const TYPE_COLORS = { crash:'#ff3d57', collapse:'#ff8c42', panic:'#ffb703', mania:'#b388ff', boom:'#00e676', policy:'#00e5ff' };
  const YEAR_RANGE = { min:1985, max:2027 };
  let currentIdx = 0;
  let autoTimer = null;
  const AUTO_INTERVAL = 7000;

  // ── Build slides ────────────────────────────────────────────────────────
  const container = document.getElementById('hero-slides-container');
  EVENTS.forEach((ev, i) => {
    const slide = document.createElement('div');
    slide.className = 'hero-slide' + (i === 0 ? ' active' : '');
    slide.dataset.index = i;
    const isLast = i === EVENTS.length - 1;
    slide.innerHTML = `
      <div class="hero-bg" style="background-color:${ev.bgColor}"></div>
      <div class="hero-overlay"></div>
      <div class="hero-content">
        <div class="hero-badge badge-${ev.badge}">${ev.badge.toUpperCase()} &nbsp;·&nbsp; ${ev.badgeDate}</div>
        <div class="hero-year">${ev.year}</div>
        <div class="hero-tagline">${ev.tagline}</div>
        <div class="hero-desc">${ev.desc}</div>
        <div class="hero-stats">
          <div class="hero-stat-group">
            <div class="stat-label">Biến động</div>
            <div class="stat-value ${ev.moveCls}">${ev.move}</div>
          </div>
          <div class="stat-divider"></div>
          <div class="hero-stat-group">
            <div class="stat-label">Dữ liệu</div>
            <div class="stat-value stat-neut" style="font-size:13px;letter-spacing:0.5px">${ev.coverage}</div>
          </div>
          ${isLast ? `
          <div class="stat-divider"></div>
          <div class="hero-stat-group">
            <button class="hero-enter"
              onclick="document.querySelector('.page, #ips-onboarding-wrapper').scrollIntoView({behavior:'smooth'})">
              Thiết lập Hồ sơ &nbsp;↓
            </button>
          </div>` : ''}
        </div>
      </div>`;
    container.appendChild(slide);
  });

  // ── Build era tabs ──────────────────────────────────────────────────────
  const erasEl = document.getElementById('hero-eras');
  ERAS.forEach((era) => {
    const tab = document.createElement('div');
    tab.className = `era-tab era-${era.id}`;
    tab.textContent = era.label;
    tab.style.borderBottomColor = era.color;
    tab.addEventListener('click', () => {
      const t = EVENTS.findIndex(e => ERA_ID_MAP[e.eraIdx] === era.id);
      if (t >= 0) goTo(t);
    });
    erasEl.appendChild(tab);
  });

  // ── Build legend ────────────────────────────────────────────────────────
  const legendEl = document.getElementById('hero-legend');
  Object.entries(TYPE_COLORS).forEach(([type, color]) => {
    const item = document.createElement('div');
    item.className = 'legend-dot-item';
    item.innerHTML = `<div class="legend-dot" style="background:${color}"></div>${type.toUpperCase()}`;
    legendEl.appendChild(item);
  });

  // ── Build timeline ──────────────────────────────────────────────────────
  const tlInner = document.getElementById('tl-inner');
  const { min, max } = YEAR_RANGE;
  for (let y = Math.ceil(min / 5) * 5; y <= max; y += 5) {
    const pct = ((y - min) / (max - min)) * 100;
    const lbl = document.createElement('div');
    lbl.className = 'tl-tick-label';
    lbl.style.left = pct + '%';
    lbl.textContent = "'" + String(y).slice(2);
    tlInner.appendChild(lbl);
  }
  EVENTS.forEach((ev, i) => {
    const year = parseInt(ev.year);
    const pct = ((year - min) / (max - min)) * 100;
    const dot = document.createElement('div');
    dot.className = 'tl-event-dot' + (i === 0 ? ' active' : '');
    dot.style.left = pct + '%';
    dot.style.background = TYPE_COLORS[ev.badge] || '#fff';
    dot.dataset.index = i;
    dot.title = ev.year;
    dot.addEventListener('click', () => goTo(i));
    tlInner.appendChild(dot);
  });

  // ── GoTo ────────────────────────────────────────────────────────────────
  function goTo(idx) {
    document.querySelectorAll('.hero-slide')[currentIdx]?.classList.remove('active');
    document.querySelectorAll('.tl-event-dot')[currentIdx]?.classList.remove('active');
    currentIdx = (idx + EVENTS.length) % EVENTS.length;
    document.querySelectorAll('.hero-slide')[currentIdx]?.classList.add('active');
    document.querySelectorAll('.tl-event-dot')[currentIdx]?.classList.add('active');
    document.querySelectorAll('.era-tab').forEach((t, i) => {
      t.classList.toggle('active', ERAS[i] && ERAS[i].id === ERA_ID_MAP[EVENTS[currentIdx].eraIdx]);
    });
    const creditEl = document.getElementById('hero-credit');
    if (creditEl) creditEl.textContent = EVENTS[currentIdx].credit || '';
    const counterEl = document.getElementById('hero-counter');
    if (counterEl) counterEl.textContent =
      String(currentIdx + 1).padStart(2, '0') + ' / ' + String(EVENTS.length).padStart(2, '0');
    resetAuto();
    startProgress();
  }

  // ── Progress bar ────────────────────────────────────────────────────────
  let raf = null, pStart = null;
  function startProgress() {
    const bar = document.getElementById('hero-progress');
    if (!bar) return;
    if (raf) cancelAnimationFrame(raf);
    pStart = performance.now();
    function step(now) {
      const p = Math.min(((now - pStart) / AUTO_INTERVAL) * 100, 100);
      bar.style.width = p + '%';
      if (p < 100) raf = requestAnimationFrame(step);
    }
    raf = requestAnimationFrame(step);
  }
  function resetAuto() {
    if (autoTimer) clearInterval(autoTimer);
    autoTimer = setInterval(() => goTo(currentIdx + 1), AUTO_INTERVAL);
  }

  // ── Controls ────────────────────────────────────────────────────────────
  document.getElementById('hero-prev')?.addEventListener('click', () => goTo(currentIdx - 1));
  document.getElementById('hero-next')?.addEventListener('click', () => goTo(currentIdx + 1));
  document.addEventListener('keydown', e => {
    const hero = document.getElementById('hero-section');
    if (!hero) return;
    const rect = hero.getBoundingClientRect();
    if (rect.bottom < 0) return;
    if (e.key === 'ArrowLeft') goTo(currentIdx - 1);
    if (e.key === 'ArrowRight') goTo(currentIdx + 1);
  });
  const heroEl = document.getElementById('hero-section');
  heroEl?.addEventListener('mouseenter', () => { clearInterval(autoTimer); cancelAnimationFrame(raf); });
  heroEl?.addEventListener('mouseleave', () => { resetAuto(); startProgress(); });

  // ── Init ─────────────────────────────────────────────────────────────────
  const firstEraId = ERA_ID_MAP[EVENTS[0].eraIdx];
  document.querySelectorAll('.era-tab').forEach((t, i) => {
    if (ERAS[i] && ERAS[i].id === firstEraId) t.classList.add('active');
  });
  const counterEl = document.getElementById('hero-counter');
  if (counterEl) counterEl.textContent = '01 / ' + String(EVENTS.length).padStart(2, '0');
  resetAuto();
  startProgress();
})();