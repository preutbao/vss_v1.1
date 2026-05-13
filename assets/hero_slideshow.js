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
    #hero-section {
      height: 720px !important; /* Giả sử chiều cao cũ là 720px hoặc 100vh, bạn chỉnh lại con số này */
      min-height: 720px !important;
    }
    .hero-slide {
      height: 720px !important;
    }
      .cyber-cta-container {
      margin-top: 20px;
      opacity: 0;
      transform: translateY(10px);
      transition: opacity 0.6s 0.5s ease, transform 0.6s 0.5s ease !important;
    }
    .hero-slide.active .cyber-cta-container { opacity:1 !important; transform:translateY(0) !important; }

    .cyber-btn {
      display: inline-block;
      padding: 12px 25px;
      background: rgba(0, 229, 255, 0.05);
      border: none;
      color: #00e5ff;
      font-family: 'DM Mono', monospace !important;
      font-size: 13px !important;
      font-weight: 600 !important;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      position: relative;
      cursor: pointer;
      /* Cắt góc kiểu Cyberpunk */
      clip-path: polygon(0% 0%, 90% 0%, 100% 30%, 100% 100%, 10% 100%, 0% 70%);
      transition: all 0.3s ease;
    }

    .cyber-btn:hover {
      background: #00e5ff;
      color: #080d18;
      box-shadow: 0 0 20px rgba(0, 229, 255, 0.6);
      transform: scale(1.05);
    }

    .cyber-btn::before {
      content: ">>";
      margin-right: 8px;
      font-size: 10px;
    }
    
    /* ĐÃ TRẢ VỀ NGUYÊN BẢN CỦA BẠN VÀ CHỈ KHÓA CHUYỂN ĐỘNG */
    .hero-bg {
      position: absolute;
      top: 0; left: 0; right: 0; 
      bottom: 100px !important; 
      pointer-events: none;
      z-index: 0;
      /* Giữ lại thuộc tính để hiện hình ảnh mờ */
      background-size: cover; 
      background-position: center right; 
      filter: blur(6px);
      /* Chặn đứng hiệu ứng pan/zoom */
      transform: scale(1.05) !important;
      animation: none !important;
      transition: none !important;
    }

    .hero-overlay {
      position: absolute;
      top: 0; left: 0; right: 0; 
      bottom: 75px !important; 
      pointer-events: none;
      z-index: 1;
      /* Gradient đen mờ để hiện chữ */
      background: linear-gradient(to right, rgba(0, 0, 0, 1) 0%, rgba(0, 0, 0, 0.7) 40%, rgba(0, 0, 0, 0) 100%);
    }

    /* 2. Đưa nội dung chữ lên trên lớp mờ */
    .hero-content {
      position: relative;
      z-index: 10;
      pointer-events: none; /* Để không chặn click vào các nút điều hướng bên dưới */
    }
    
    /* Cho phép các nút trong nội dung (như nút Thiết lập hồ sơ) vẫn bấm được */
    .hero-content button, .cyber-btn {
      pointer-events: auto;
    }

    /* 3. Nâng toàn bộ các nút điều khiển, số thứ tự và phím tắt lên trên cùng */
    #hero-prev, #hero-next, .hero-counter, .hero-keys, .hero-credit, #hero-progress-container {
      z-index: 100 !important;
      position: relative; /* Đảm bảo z-index có tác dụng */
    }

    /* Đảm bảo khu vực chứa Era Tabs và Timeline nằm dưới cùng không bị hình ảnh đè */
    /* Đảm bảo dải ô giai đoạn nổi lên mà KHÔNG làm vỡ vị trí gốc */
    #hero-eras, #hero-timeline, #hero-legend {
      z-index: 100 !important;
    }
    
    .era-tab {
      position: relative;
      z-index: 100 !important;
    }
    
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

  // ── DỮ LIỆU SỰ KIỆN TÀI CHÍNH VIỆT NAM (GÓC NHÌN ĐỊNH LƯỢNG - SMART SCREENER) ────────────────────────────────
  const EVENTS = [
    {
      year:'1986', era:'doi-moi', badge:'policy', badgeDate:'18/12',
      tagline:'Đổi Mới - Khởi nguồn <span class="hl-blue">dữ liệu cơ bản</span>.',
      desc:'Chuyển sang kinh tế thị trường. Đây là bước ngoặt tạo ra các doanh nghiệp tư nhân cốt lõi — nền tảng cho việc phân tích chỉ số tài chính (BCTC) sau này.',
      move:'Khởi nguyên', moveCls:'stat-neut', coverage:'Lịch sử vĩ mô · Mở cửa',
      bgColor:'#080d18', credit:'', dot:'#00e5ff', eraIdx:0,
      bgImage:'assets/slideshow_bg/slide_bg1.png',
    },
    {
      year:'1993', era:'doi-moi', badge:'policy', badgeDate:'11/07',
      tagline:'Mỹ bỏ cấm vận - Động lực <span class="hl-blue">Tăng trưởng (G)</span>.',
      desc:'FDI bùng nổ. Trong hệ thống điểm VGM, đây là giai đoạn các chỉ số Tăng trưởng (Growth) như Doanh thu & EPS bắt đầu có ý nghĩa thực tiễn.',
      move:'FDI+', moveCls:'stat-pos', coverage:'Dữ liệu tăng trưởng · Đầy đủ',
      bgColor:'#08100d', credit:'', dot:'#00e676', eraIdx:0,
      bgImage:'assets/slideshow_bg/slide_bg2.png',
    },
    {
      year:'1997', era:'khung-hoang', badge:'panic', badgeDate:'02/07',
      tagline:'Khủng hoảng châu Á - Bài học <span class="hl">Phòng thủ</span>.',
      desc:'Cú sốc tỷ giá chứng minh tầm quan trọng của chiến lược "Phòng thủ". Bộ lọc VSS sẽ đánh rớt đài (1 Sao) ngay lập tức những mã có nợ vay ngoại tệ cao.',
      move:'Rủi ro nợ', moveCls:'stat-neg', coverage:'Dữ liệu Cờ Đỏ (Red Flag)',
      bgColor:'#100a00', credit:'', dot:'#ffb703', eraIdx:1,
      bgImage:'assets/slideshow_bg/slide_bg3.png',
    },
    {
      year:'2000', era:'ttck', badge:'boom', badgeDate:'20/07',
      tagline:'HOSE khai trương - Kỷ nguyên <span class="hl-green">Dữ liệu thị trường</span>.',
      desc:'Khởi điểm của chuỗi Data chứng khoán. Nền tảng để thuật toán quét thanh khoản và xây dựng các bộ chỉ số định giá P/E, P/B trong thời gian thực.',
      move:'VNI 100', moveCls:'stat-pos', coverage:'Chuỗi Time-series · Bắt đầu',
      bgColor:'#081208', credit:'', dot:'#00e676', eraIdx:2,
      bgImage:'assets/slideshow_bg/slide_bg4.png',
    },
    {
      year:'2007', era:'ttck', badge:'mania', badgeDate:'12/03',
      tagline:'Đỉnh 1.170 - Ảo tưởng <span class="hl-purple">Lợi nhuận giấy</span>.',
      desc:'Bong bóng định giá toàn dân. Nếu VSS tồn tại lúc này, ma trận Điểm Giá Trị (Value) sẽ liên tục cảnh báo đỏ vì P/E thị trường vượt xa mức an toàn.',
      move:'P/E > 30', moveCls:'stat-pos', coverage:'Phễu định giá · Cảnh báo',
      bgColor:'#0d0a14', credit:'', dot:'#b388ff', eraIdx:2,
      bgImage:'assets/slideshow_bg/slide_bg5.png',
    },
    {
      year:'2008', era:'khung-hoang', badge:'crash', badgeDate:'28/02',
      tagline:'Vỡ bong bóng - Lưới lọc <span class="hl">Cổ phiếu rác</span>.',
      desc:'Thị trường bốc hơi 76%. Chỉ những doanh nghiệp có Dòng tiền HĐKD (CFO) dương mới sống sót. Tư duy "Tiền mặt là Vua" lên ngôi.',
      move:'−76%', moveCls:'stat-neg', coverage:'Bộ lọc Dòng tiền · Kích hoạt',
      bgColor:'#140808', credit:'', dot:'#ff3d57', eraIdx:1,
      bgImage:'assets/slideshow_bg/slide_bg6.png',
    },
    {
      year:'2012', era:'tai-co-cau', badge:'policy', badgeDate:'01/06',
      tagline:'Khủng hoảng Ngân hàng - Bóng ma <span class="hl-amber">Nợ xấu</span>.',
      desc:'Sàng lọc khắc nghiệt. Tiêu chí Chất lượng tài sản (NPL, Tỷ lệ bao phủ nợ xấu LLR) trở thành kim chỉ nam để né bẫy báo cáo tài chính tô hồng.',
      move:'Bẫy Nợ', moveCls:'stat-neut', coverage:'Chấm điểm Chất lượng · Bắt buộc',
      bgColor:'#0c0d08', credit:'', dot:'#ffb703', eraIdx:3,
      bgImage:'assets/slideshow_bg/slide_bg7.png',
    },
    {
      year:'2020', era:'covid', badge:'crash', badgeDate:'24/03',
      tagline:'Cú sốc COVID-19 - Cơ hội <span class="hl-green">Bắt đáy siêu cổ</span>.',
      desc:'Thị trường hoảng loạn rớt 33%. Thuật toán VSS lúc này sẽ giúp bạn quét ra các "viên kim cương" bị bán tháo (Điểm VGM 5-Sao) chỉ trong 30 giây.',
      move:'−33%', moveCls:'stat-neg', coverage:'Screener săn sale · Tối ưu',
      bgColor:'#080a10', credit:'', dot:'#ff3d57', eraIdx:4,
      bgImage:'assets/slideshow_bg/slide_bg8.png',
    },
    {
      year:'2021', era:'covid', badge:'boom', badgeDate:'25/11',
      tagline:'Đỉnh 1.500 - Trò chơi của <span class="hl-green">Động lượng (M)</span>.',
      desc:'Thanh khoản tỷ USD. Bộ lọc Lướt sóng & Động lượng (Momentum) của VSS phát huy sức mạnh bám theo dòng tiền lớn, tối đa hóa hiệu suất ngắn hạn.',
      move:'+68%', moveCls:'stat-pos', coverage:'Chỉ số Động lượng · Đỉnh điểm',
      bgColor:'#081208', credit:'', dot:'#00e676', eraIdx:4,
      bgImage:'assets/slideshow_bg/slide_bg9.png',
    },
    {
      year:'2026', era:'covid', badge:'policy', badgeDate:'HÔM NAY',
      tagline:'Kỷ nguyên <span class="hl-blue">AI & Đầu tư định lượng</span>.',
      desc:'Không còn dò dẫm thủ công bằng cảm xúc. Hệ thống Vietcap Smart Screener đang quét 165+ chỉ số. Xác định DNA đầu tư của bạn và để AI bốc thuốc ngay.',
      move:'LỌC NGAY', moveCls:'stat-pos', coverage:'Daily · Sẵn sàng',
      bgColor:'#040d18', credit:'', dot:'#00e5ff', eraIdx:4,
      bgImage:'assets/slideshow_bg/slide_bg10.png',
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
      <div class="hero-bg" style="background-image: url('${ev.bgImage}');"></div>
      
      <div class="hero-overlay"></div>
      
      <div class="hero-content">
        
        <div class="cyber-cta-container">
          <div class="cyber-btn" onclick="window.location.href='#learn-more'">
            TẠI SAO DÙNG VIETCAP SMART SCREENER?
          </div>
        </div>

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
              onclick="const target = document.getElementById('hero-section').nextElementSibling; if(target) { const y = target.getBoundingClientRect().top + window.scrollY - 30; window.scrollTo({top: y, behavior: 'smooth'}); }">
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