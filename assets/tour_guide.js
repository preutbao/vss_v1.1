// assets/tour_guide.js
// ─────────────────────────────────────────────────────────────
// FSS Tour Guide — Spotlight style
// Hiện overlay tối, khoét spotlight quanh element, tooltip cạnh đó
// ─────────────────────────────────────────────────────────────

window.VssTour = (function () {
  // 🛠 CHÈN ĐOẠN CODE TẠO HIỆU ỨNG CSS VÀO ĐÂY (NGAY ĐẦU HÀM)
  document.head.insertAdjacentHTML('beforeend', `
    <style>
      /* Hiệu ứng tỏa sáng đỏ quanh Element */
      @keyframes tourPulse { 
        0% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.8); } 
        70% { box-shadow: 0 0 0 12px rgba(220, 38, 38, 0); } 
        100% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); } 
      }
      /* Hiệu ứng chớp tắt nhè nhẹ cho dòng chữ hướng dẫn */
      @keyframes pulseText {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
      }
    </style>
  `);

  // ── CẤU HÌNH CÁC BƯỚC ────────────────────────────────────────
  // Thêm bước mới: copy 1 object vào mảng STEPS
  // target: CSS selector của element cần highlight
  // position: "bottom" | "top" | "left" | "right" — tooltip xuất hiện phía nào
  const STEPS = [
    {
      id: "welcome",
      target: null,          // null = không spotlight element nào, chỉ hiện ở giữa màn hình
      position: "center",
      title: "Chào mừng đến với FinSmartScreener! 👋",
      body: "Tôi là trợ lý VinanceAI. Chỉ mất 30 giây để tôi hướng dẫn bạn cách tìm ra cổ phiếu \"vàng\" và né bẫy rủi ro trên thị trường. Bắt đầu chứ?",
      skipBtn: "Bỏ qua",
      nextBtn: "Khám phá ngay",
    },
    
    // BƯỚC 1: Bắt click mở Tab Chiến lược
    {
      id: "strategy-tab-click",
      target: "#toolbar-tab-strategy", 
      position: "bottom", 
      title: "Mở menu Chiến lược",
      body: "Hãy click vào vùng đang nhấp nháy đỏ để mở danh sách các công cụ. (Nút Tiếp theo sẽ mở khóa sau khi bạn click).",
      skipBtn: "Bỏ qua",
      nextBtn: "Tiếp theo", 
      requireClick: true // Yêu cầu click
    },

    // BƯỚC 2: Khoanh đỏ 3 nút chức năng (Đã có sẵn ID từ sidebar.py)
    {
      id: "strategy-actions",
      // 🛠 DÙNG ĐÚNG ID CỦA PANEL CHỨA 3 NÚT TỪ FILE PYTHON
      target: "#toolbar-panel-strategy", 
      position: "bottom", // Hộp thoại hiện bên dưới
      title: "Công cụ Sàng lọc Nhanh",
      body: "Tại đây bạn có 3 tính năng: Chọn trường phái đầu tư, Tinh chỉnh Bộ lọc, và Xóa tất cả điều kiện. Bảng sẽ cập nhật realtime theo lựa chọn của bạn.",
      skipBtn: "Bỏ qua",
      nextBtn: "Tiếp theo",
      requireClick: false, 
      disableInteraction: true, // 🛠 KHOÁ CLICK VÀO 3 NÚT NÀY
      // 🛠 THÊM DÒNG NÀY VÀO: Ép chiều rộng vùng khoanh đỏ (Ví dụ: 380px)
      customW: 900, 
      
      // Nếu nó bị lệch sang trái/phải, bạn có thể bù trừ thêm bằng offsetX
      offsetX: 12,
    },
    // ==========================================
    // ── TAB TÌM KIẾM ──
    // ==========================================
    {
      id: "search-tab-click",
      target: "#toolbar-tab-search", // ID của nút Tab Tìm kiếm
      position: "bottom", 
      title: "Tìm kiếm mã cổ phiếu",
      body: "Tiếp theo, hãy click vào thẻ Tìm mã để chuyển sang công cụ tìm kiếm cụ thể.",
      skipBtn: "Bỏ qua",
      nextBtn: "Tiếp theo", 
      requireClick: true // Bắt buộc người dùng click
    },
    {
      id: "search-actions",
      target: "#toolbar-panel-search", // ID của vùng chứa thanh search
      position: "bottom",
      title: "Tìm kiếm & Mã Nổi Bật",
      body: "Tại đây, bạn có thể gõ trực tiếp tên hoặc mã cổ phiếu để xem hồ sơ. Kế bên là danh sách các mã đang 'hot' được quan tâm nhiều nhất trên thị trường.",
      skipBtn: "Bỏ qua",
      nextBtn: "Tiếp theo",
      requireClick: false, 
      disableInteraction: true, // Khóa click, đắp khiên cảnh báo
      customW: 1025, // Thanh search của bạn set minWidth 800px nên vùng này cần khá rộng, bạn có thể gia giảm số này
      offsetX: 12,
    },

    // ==========================================
    // ── TAB PHẠM VI ──
    // ==========================================
    {
      id: "scope-tab-click",
      target: "#toolbar-tab-scope", // ID của nút Tab Phạm vi
      position: "bottom", 
      title: "Lọc theo Phạm vi",
      body: "Bạn chỉ muốn chơi cổ phiếu rổ VN30 hoặc sàn HOSE? Hãy click vào thẻ Phạm vi.",
      skipBtn: "Bỏ qua",
      nextBtn: "Tiếp theo", 
      requireClick: true
    },
    {
      id: "scope-actions",
      target: "#toolbar-panel-scope", // ID của vùng chứa dropdown phạm vi
      position: "bottom",
      title: "Sàn, Ngành & Rổ Chỉ Số",
      body: "Sử dụng các menu thả xuống này để giới hạn không gian sàng lọc: Chọn Sàn giao dịch, Ngành nghề, hoặc các Rổ chỉ số lớn để kết quả cô đọng hơn.",
      skipBtn: "Bỏ qua",
      nextBtn: "Tiếp theo",
      requireClick: false, 
      disableInteraction: true,
      customW: 880, // Đủ bao trọn 4 dropdown
      offsetX: 18,
    },

    // ==========================================
    // ── TAB CÁ NHÂN ──
    // ==========================================
    {
      id: "personal-tab-click",
      target: "#toolbar-tab-personal", // ID của nút Tab Cá nhân
      position: "bottom", 
      title: "Không gian của bạn",
      body: "Cuối cùng, hãy click vào thẻ Cá nhân để xem các thiết lập riêng của bạn.",
      skipBtn: "Bỏ qua",
      nextBtn: "Tiếp theo", 
      requireClick: true
    },
    {
      id: "personal-actions",
      target: "#toolbar-panel-personal", // ID của vùng chứa nút profile
      position: "bottom",
      title: "Bộ lọc đã lưu & Hồ sơ",
      body: "Nơi đây lưu trữ các bộ lọc do chính bạn tạo ra. Bạn cũng có thể cập nhật 'Hồ sơ Nhà đầu tư' để AI của chúng tôi hiểu rõ khẩu vị rủi ro của bạn hơn.",
      skipBtn: "Bỏ qua",
      nextBtn: "Tiếp theo", 
      requireClick: false, 
      disableInteraction: true,
      customW: 363, // Vùng này chỉ có 2 thành phần nên khá ngắn
      offsetX: 12,
    },
    // ==========================================
    // ── BẢNG LỌC SCREENER VÀ POPUP CHI TIẾT ──
    // ==========================================
    
    // 1. Chỉ khoanh nút Tích Sản
    {
      id: "mode-toggle",
      target: "#mode-toggle-btn",
      position: "bottom",
      title: "Chế độ Sàng lọc",
      body: "Nút này cho phép chuyển đổi giữa 'Toàn thị trường' và 'Tích sản'. Chế độ Tích sản giúp tìm các mã có định giá rẻ phù hợp gom dài hạn.",
      skipBtn: "Bỏ qua",
      nextBtn: "Tiếp theo",
      disableInteraction: true,
      // 🛠 THÊM DÒNG NÀY ĐỂ CUỘN MÀN HÌNH XUỐNG 391px
      scrollToY: 391
    },
    
    // 2. Chỉ khoanh bảng kết quả
    {
      id: "screener-table-intro",
      target: "#screener-table",
      position: "top", // Hiện bên trên bảng
      title: "Bảng Kết quả Sàng lọc",
      body: "Đây là nơi hiển thị các siêu cổ phiếu. Cột VGM (Value-Growth-Momentum) tổng hợp sức mạnh toàn diện của doanh nghiệp thành các điểm A, B, C...",
      skipBtn: "Bỏ qua",
      nextBtn: "Tiếp theo",
      disableInteraction: true,
      customH: 250, // Ép độ cao khoanh đỏ ngắn lại để không bị chiếm hết màn hình
      noPulse: true // 🛠 THÊM MỚI: Chỉ làm nổi bật (spotlight), không hiện viền đỏ nhấp nháy
    },
    
    // 3. Bắt Double Click vào mã đầu tiên
    {
      id: "screener-first-ticker",
      // Dùng Class của AG Grid để túm chính xác dòng số 0
      target: ".ag-pinned-left-cols-container .ag-row[row-index='0']",
      position: "right",
      title: "Xem hồ sơ chi tiết",
      body: "Hãy Double-click (Nhấp đúp chuột) vào dòng cổ phiếu đầu tiên này để mở hồ sơ phân tích chuyên sâu nhé.",
      skipBtn: "Bỏ qua",
      requireDblClick: true, // Bắt buộc Double Click
      autoNextAfterClick: true, // Bấm xong tự động qua bước kế
      autoNextDelay: 1500 // Đợi 1.5s cho UI của Modal kịp Load ra
    },
    
    // 4. Khóa tương tác, đếm ngược 10 giây
    {
      id: "screener-modal-view",
      target: ".modal-content", // Khung của Popup Modal
      position: "right",
      title: "Hồ sơ Phân tích",
      body: "Popup này chứa toàn bộ biểu đồ kỹ thuật, báo cáo tài chính và sức khỏe doanh nghiệp... Bạn có thể xem lướt qua nhé! (Hệ thống sẽ tự chuyển bước sau 10s).",
      skipBtn: false, // 🛠 ĐỔI THÀNH FALSE ĐỂ ẨN NÚT
      disableInteraction: true,
      autoAdvanceDelay: 10000 // Tự động chuyển bước sau 10s
    },
    
    // 5. Bắt Click vào nút X tắt đi
    {
      id: "screener-modal-close",
      target: ".modal-header .btn-close", // Nút X của Bootstrap Modal
      position: "left",
      title: "Đóng hồ sơ",
      body: "Bạn đã xem xong! Hãy click vào nút X này để đóng cửa sổ và trở lại bảng chính.",
      skipBtn: false, // 🛠 ĐỔI THÀNH FALSE ĐỂ ẨN NÚT
      nextBtn: "Tiếp theo",
      requireClick: true, 
      autoNextAfterClick: true, 
      autoNextDelay: 800 
    },

    // 6. Bắt Click vào nút << (Mở công cụ)
    {
      id: "screener-toggle-actions",
      target: "#btn-toggle-actions",
      position: "bottom",
      title: "Mở rộng tính năng",
      body: "Bảng kết quả còn có rất nhiều tính năng ẩn. Hãy click vào nút '<<' này để mở rộng thanh công cụ nhé.",
      skipBtn: "Bỏ qua",
      nextBtn: "Tiếp theo",
      requireClick: true, 
      autoNextAfterClick: true, 
      autoNextDelay: 800,
      
      // 🛠 THÊM ĐOẠN NÀY ĐỂ FIX EDGE CASE:
      // Tự động kiểm tra và đóng thanh công cụ nếu nó đang được mở sẵn
      onBeforeShow: function() {
        const container = document.getElementById("action-buttons-container");
        const btn = document.getElementById("btn-toggle-actions");
        
        // Kiểm tra xem container có đang hiện trên màn hình không
        if (container && window.getComputedStyle(container).display !== "none") {
          // Nếu đang hiện (nghĩa là user đã mở trước đó) -> Dùng JS bấm nút ẩn nó đi
          if (btn) btn.click();
        }
      }
    },

    // 7. BƯỚC MỚI: Giới thiệu thanh công cụ
    {
      id: "screener-extended-actions",
      target: "#action-buttons-container",
      position: "bottom",
      title: "Công cụ Nâng cao",
      body: "Tại đây bạn có thể Xuất file Excel/CSV, xem Heatmap Ngành, hoặc thêm mã vào Watchlist. Các chức năng VIP (So sánh, Danh mục) sẽ được mở khoá sau khi bạn đăng nhập.",
      skipBtn: "Bỏ qua",
      nextBtn: "Tiếp theo",
      requireClick: false, 
      disableInteraction: true,
      customH: 45 // Ép chiều cao vừa vặn ôm lấy hàng nút
    },

    // 8. Bước cuối cùng: Trợ lý AI (Bubble)
    {
      id: "final-ai-bubble",
      target: "#chat-toggle-btn", // 🛠 ĐÃ SỬA ID: Chỏ đúng vào bong bóng AI
      position: "left", // Hộp thoại hiện bên trái bong bóng
      title: "Trợ lý ảo luôn đồng hành 🤖",
      body: "Tôi (VinanceAI) sẽ luôn túc trực ở góc này để hỗ trợ bạn đánh giá danh mục và ra quyết định đầu tư. Chúc bạn trải nghiệm bộ lọc vui vẻ và đầu tư thắng lợi! 🎉",
      skipBtn: "Đóng",
      nextBtn: "Hoàn tất",
      requireClick: false,
      disableInteraction: true
    }
  ]; // <-- Kết thúc mảng STEPS
  let currentStep = 0;
  let isActive = false;
  let scrollY = 0;
  let targetClickHandler = null; // 🛠 THÊM BIẾN NÀY ĐỂ LƯU SỰ KIỆN CLICK
  let stepRequirementMet = false; // 🛠 THÊM BIẾN NÀY ĐỂ MỞ KHÓA NÚT NEXT
  let shieldTimeout = null; // 🛠 THÊM BIẾN NÀY
  let autoAdvanceTimeout = null; // 🛠 THÊM BIẾN NÀY ĐỂ ĐẾM NGƯỢC THỜI GIAN

  // ── TIỆN ÍCH ────────────────────────────────────────────────
  function getRect(step) {
    if (!step || !step.target) return null;
    const el = document.querySelector(step.target);
    if (!el) return null;
    
    const r = el.getBoundingClientRect();
    let rect = { top: r.top, left: r.left, width: r.width, height: r.height, el };

    // 🛠 GHI ĐÈ KÍCH THƯỚC/VỊ TRÍ NẾU CÓ CẤU HÌNH THỦ CÔNG
    if (step.customW !== undefined) rect.width = step.customW;
    if (step.customH !== undefined) rect.height = step.customH;
    if (step.offsetX !== undefined) rect.left += step.offsetX;
    if (step.offsetY !== undefined) rect.top += step.offsetY;

    return rect;
  }

  // ── RENDER SHIELD & WARNING ──────────────────────────────────
  function showWarning(e) {
    e.preventDefault();
    e.stopPropagation();

    let warning = document.getElementById("tour-warning-msg");
    if (!warning) return;

    // Hiện warning tại vị trí gần con trỏ chuột
    warning.style.left = (e.clientX + 15) + "px";
    warning.style.top = (e.clientY - 15) + "px";
    warning.style.opacity = "1";

    if (shieldTimeout) clearTimeout(shieldTimeout);
    shieldTimeout = setTimeout(() => {
      warning.style.opacity = "0";
    }, 1000); // Ẩn sau 1s
  }

  function renderInteractionShield(step, rect) {
    let shield = document.getElementById("tour-interaction-shield");
    let warning = document.getElementById("tour-warning-msg");

    // Lần đầu chạy sẽ tự động tạo thẻ div trên body
    if (!shield) {
      // 1. Tạo khiên vô hình
      shield = document.createElement("div");
      shield.id = "tour-interaction-shield";
      shield.style.position = "fixed";
      shield.style.zIndex = "10004"; // Nằm TRÊN element đang khoanh đỏ (10002)
      shield.style.cursor = "not-allowed";
      // 🛠 THÊM DÒNG NÀY: Để khiên không chặn các phần tử con bên trong (nếu có) 
      // hoặc đảm bảo Dialogue Box nằm ngoài tầm phủ của nó
      shield.style.pointerEvents = "auto";
      
      shield.addEventListener("click", showWarning);
      document.body.appendChild(shield);

      // 2. Tạo hộp thoại Warning
      warning = document.createElement("div");
      warning.id = "tour-warning-msg";
      warning.style.position = "fixed";
      warning.style.zIndex = "10005"; // Cao nhất
      warning.style.background = "rgba(220, 38, 38, 0.95)"; // Đỏ mờ
      warning.style.color = "#ffffff";
      warning.style.padding = "6px 14px";
      warning.style.borderRadius = "6px";
      warning.style.fontSize = "13px";
      warning.style.fontWeight = "600";
      warning.style.pointerEvents = "none"; // Không bắt click
      warning.style.opacity = "0";
      warning.style.transition = "opacity 0.2s ease";
      warning.style.boxShadow = "0 4px 12px rgba(0,0,0,0.3)";
      warning.innerHTML = "⚠️ Hãy khám phá chức năng này sau khi kết thúc Tour nhé!";
      document.body.appendChild(warning);

      // 3. Gắn warning luôn cho cả vùng tối (Backdrop)
      const backdrop = document.getElementById("tour-backdrop");
      if (backdrop) backdrop.addEventListener("click", showWarning);
    }

    // Nếu bước này yêu cầu khóa tương tác -> Đắp khiên lên
    if (step.disableInteraction && rect) {
      shield.style.display = "block";
      shield.style.left = rect.left + "px";
      shield.style.top = rect.top + "px";
      shield.style.width = rect.width + "px";
      shield.style.height = rect.height + "px";
    } else {
      shield.style.display = "none";
    }
  }

  function lerp(a, b, t) { return a + (b - a) * t; }

  // ── VẼ OVERLAY SVG VỚI SPOTLIGHT ────────────────────────────
  // Dùng SVG path với "evenodd" fill-rule để khoét lỗ
  function renderBackdrop(rect, step) {
    const W = window.innerWidth;
    const H = window.innerHeight;
    const PAD = 8; // padding quanh element được highlight

    const backdrop = document.getElementById("tour-backdrop");
    if (!backdrop) return;

    if (!rect) {
      // Không có target → overlay kín toàn màn hình
      backdrop.innerHTML = `
        <svg width="${W}" height="${H}" style="position:fixed;top:0;left:0;pointer-events:all;">
          <rect width="${W}" height="${H}" fill="rgba(0,0,0,0.75)"/>
        </svg>`;
      return;
    }

    const x = rect.left - PAD;
    const y = rect.top - PAD;
    const w = rect.width + PAD * 2;
    const h = rect.height + PAD * 2;
    const r = 8; // border-radius của spotlight

    // Path: hình chữ nhật lớn che toàn màn hình, khoét hình chữ nhật bo góc ở giữa
    const spotPath =
      `M ${x+r} ${y}
       H ${x+w-r} Q ${x+w} ${y} ${x+w} ${y+r}
       V ${y+h-r} Q ${x+w} ${y+h} ${x+w-r} ${y+h}
       H ${x+r} Q ${x} ${y+h} ${x} ${y+h-r}
       V ${y+r} Q ${x} ${y} ${x+r} ${y} Z`;

    // 🛠 Nếu có cờ noPulse thì ẩn luôn viền xanh
    const strokeCode = (step && step.noPulse) 
      ? '' 
      : `<path d="${spotPath}" fill="none" stroke="rgba(0,168,255,0.7)" stroke-width="2"/>`;

    backdrop.innerHTML = `
      <svg width="${W}" height="${H}" style="position:fixed;top:0;left:0;pointer-events:all;">
        <defs>
          <mask id="tour-mask">
            <rect width="${W}" height="${H}" fill="white"/>
            <path d="${spotPath}" fill="black"/>
          </mask>
        </defs>
        <rect width="${W}" height="${H}" fill="rgba(0,0,0,0.72)" mask="url(#tour-mask)"/>
        ${strokeCode}
      </svg>`;
  }

  // ── TÍNH VỊ TRÍ TOOLTIP ──────────────────────────────────────
  function calcTooltipPos(rect, position, tooltipW, tooltipH) {
    const PAD = 16; // Khoảng cách từ tooltip đến element được highlight
    const ARROW = 12;
    const W = window.innerWidth;
    const H = window.innerHeight;

    if (!rect || position === "center") {
      return {
        left: W / 2 - tooltipW / 2,
        top: H / 2 - tooltipH / 2,
        arrowDir: null,
      };
    }

    let left, top, arrowDir;

    if (position === "bottom") {
      left = rect.left + rect.width / 2 - tooltipW / 2;
      top  = rect.top + rect.height + ARROW + PAD;
      arrowDir = "top";
    } else if (position === "top") {
      left = rect.left + rect.width / 2 - tooltipW / 2;
      top  = rect.top - tooltipH - ARROW - PAD;
      arrowDir = "bottom";
    } else if (position === "right") {
      left = rect.left + rect.width + ARROW + PAD;
      top  = rect.top + rect.height / 2 - tooltipH / 2;
      arrowDir = "left";
    } else if (position === "left") {
      left = rect.left - tooltipW - ARROW - PAD;
      top  = rect.top + rect.height / 2 - tooltipH / 2;
      arrowDir = "right";
    }

    // Clamp để không bị lọt ra ngoài màn hình
    left = Math.max(PAD, Math.min(left, W - tooltipW - PAD));
    top  = Math.max(PAD, Math.min(top, H - tooltipH - PAD));

    return { left, top, arrowDir };
  }

  // ── RENDER TOOLTIP ───────────────────────────────────────────
  function renderTooltip(step, stepIndex, total) {
    const tooltip = document.getElementById("tour-tooltip");
    const inner   = document.getElementById("tour-tooltip-inner");
    if (!tooltip || !inner) return;

    const isLast = stepIndex === total - 1;
    const isFirst = stepIndex === 0;

    const dotHTML = Array.from({ length: total - 1 }, (_, i) =>
      `<span style="
        display:inline-block; width:${i === stepIndex - 1 ? 18 : 6}px; height:5px;
        border-radius:3px; background:${i === stepIndex - 1 ? "#0090ff" : "rgba(0,0,0,0.15)"};
        transition:width 0.2s;
      "></span>`
    ).join("");

    inner.innerHTML = `
      <div style="
        background: #1e293b; /* Nền xám đậm dịu mắt */
        border: 1px solid #475569; /* Viền xám trung tính */
        border-radius: 8px; /* Bo góc vừa phải, thanh lịch */
        box-shadow: 0 10px 25px rgba(0,0,0,0.4); /* Đổ bóng mềm, không phát sáng */
        overflow: hidden;
        font-family: inherit;
        min-height: 140px; /* Giữ trục Y vừa vặn */
        display: flex;
        flex-direction: column;
      ">
        <!-- Header -->
        <div style="padding: 20px 24px 12px; display:flex; align-items:flex-start; gap:16px; flex: 1;">
          
          <!-- Icon Box: Hình vuông bo góc nhẹ, màu xanh lam tiêu chuẩn -->
          <div style="
            width:36px; height:36px; background: #0f172a;
            display:flex; align-items:center; justify-content:center; flex-shrink:0;
            border: 1px solid #334155;
            border-radius: 8px;
          ">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2">
              <path d="M12 2a7 7 0 0 1 7 7c0 4-7 13-7 13S5 13 5 9a7 7 0 0 1 7-7z"/>
              <circle cx="12" cy="9" r="2.5"/>
            </svg>
          </div>

          <div style="flex:1">
            <p style="margin:0 0 6px; font-size:15px; font-weight:600; color:#f8fafc; letter-spacing: 0.3px;">
              ${step.title}
            </p>
            <p style="margin:0; font-size:13.5px; color:#94a3b8; line-height:1.6;">
              ${step.body}
            </p>
          </div>
          
          <!-- Nút X tắt: Màu xám tĩnh -->
          <button id="tour-close-btn" style="
            background:none; border:none; cursor:pointer; color:#64748b;
            font-size:22px; padding:0; line-height:1; flex-shrink:0; margin-top:-2px; transition: color 0.2s;
          " onmouseover="this.style.color='#cbd5e1'" onmouseout="this.style.color='#64748b'">×</button>
        </div>

        <!-- Footer -->
        <div style="
          padding: 14px 24px 18px; display:flex;
          align-items:center; gap:8px;
          border-top: 1px solid #334155;
          background: #1e293b;
        ">
          <div style="flex:1; height:6px; background:#334155; border-radius:3px; overflow:hidden; position:relative; margin-right:8px;">
            <div style="width:${((stepIndex + 1) / total) * 100}%; height:100%; background:#0284c7; transition:width 0.4s cubic-bezier(0.4, 0, 0.2, 1);"></div>
          </div>

          ${!isFirst ? `
          <button id="tour-back-btn" style="
            font-size:13px; color:#cbd5e1; background:none;
            border:1px solid #475569; border-radius: 6px;
            padding:6px 12px; cursor:pointer; transition: 0.2s;
            font-weight: 500; flex-shrink: 0; white-space: nowrap;
          " onmouseover="this.style.background='#334155'; this.style.color='#f8fafc'" onmouseout="this.style.background='transparent'; this.style.color='#cbd5e1'">Trở lại</button>` : ""}

          <button id="tour-skip-btn" style="
            display: ${step.skipBtn ? 'inline-block' : 'none'}; /* 🛠 Tự động ẩn nếu skipBtn là false/rỗng */
            font-size:13px; color:#64748b; background:none;
            border:none; cursor:pointer; padding:6px 8px; transition: color 0.2s;
            font-weight: 500; flex-shrink: 0; white-space: nowrap;
          " onmouseover="this.style.color='#94a3b8'" onmouseout="this.style.color='#64748b'">
            ${step.skipBtn || "Bỏ qua"}
          </button>

          ${step.autoAdvanceDelay ? `
            <div style="font-size:13px; font-weight:600; color:#0284c7; padding:7px 10px; animation: pulseText 1.5s infinite; flex-shrink:0;">
              ⏳ Đang xem trước (${step.autoAdvanceDelay/1000}s)...
            </div>
          ` : (step.requireDblClick || step.requireClick) && step.autoNextAfterClick ? `
            <div style="font-size:13px; font-weight:600; color:#0284c7; padding:7px 10px; animation: pulseText 1.5s infinite; flex-shrink:0;">
              👆 ${step.requireDblClick ? "Double-click" : "Click"} vào mục tiêu
            </div>
          ` : `
            <button id="tour-next-btn" style="
              font-size:13px; font-weight:600; background:#0284c7; color:#ffffff;
              border:1px solid #0284c7; border-radius: 6px; padding:7px 20px; transition: all 0.2s;
              flex-shrink: 0; white-space: nowrap;
              opacity: ${(!stepRequirementMet) ? '0.4' : '1'};
              cursor: ${(!stepRequirementMet) ? 'not-allowed' : 'pointer'};
            ">
              ${isLast ? "Hoàn tất" : step.nextBtn}
            </button>
          `}
        </div>
    `;

    tooltip.style.display = "block";
    tooltip.style.width   = "400px"; // 🛠 SỬA 320 -> 400
    tooltip.style.zIndex  = "10010"; // 🛠 ÉP Z-INDEX CAO NHẤT để luôn nằm trên vùng spotlight và khiên chặn

    // Đo chiều cao thực sau khi render để tính vị trí chính xác
    const tooltipH = tooltip.offsetHeight;
    const tooltipW = 400; // 🛠 SỬA 320 -> 400

    // 🛠 SỬA TỪ: const rect = getRect(step.target);
    // THÀNH:
    const rect = getRect(step);
    const pos  = calcTooltipPos(rect, step.position, tooltipW, tooltipH);

    tooltip.style.left = pos.left + "px";
    tooltip.style.top  = pos.top  + "px";

    // Bind event listeners
    const closeBtn = document.getElementById("tour-close-btn");
    const skipBtn  = document.getElementById("tour-skip-btn");
    const nextBtn  = document.getElementById("tour-next-btn");
    const backBtn  = document.getElementById("tour-back-btn");

    if (closeBtn) closeBtn.addEventListener("click", stopTour);
    if (skipBtn)  skipBtn.addEventListener("click", stopTour);
    if (nextBtn)  nextBtn.addEventListener("click", () => {
      // 🛠 CHẶN CLICK NẾU CHƯA BẤM VÀO VÙNG KHOANH ĐỎ
      if (step.requireClick && !stepRequirementMet) return; 
      
      if (isLast) { stopTour(true); } else { goToStep(stepIndex + 1); }
    });
    if (backBtn)  backBtn.addEventListener("click", () => goToStep(stepIndex - 1));
  }

  // ── HIGHLIGHT ELEMENT ────────────────────────────────────────
  function highlightTarget(selector) {
    if (!selector) return;
    const el = document.querySelector(selector);
    if (el) {
      // Lưu lại thuộc tính gốc để trả về sau
      el.dataset.tourOrigPos = el.style.position || '';
      el.dataset.tourOrigZ = el.style.zIndex || '';
      
      const comp = window.getComputedStyle(el);
      // Chỉ đổi thành relative nếu nó chưa có position gì (static)
      if (comp.position === 'static') {
        el.style.position = 'relative';
      }
      el.style.zIndex = '10002';
    }
  }

  function unhighlightTarget(selector) {
    if (!selector) return;
    const el = document.querySelector(selector);
    if (el) {
      // Trả lại đúng thuộc tính gốc
      el.style.position = el.dataset.tourOrigPos || '';
      el.style.zIndex = el.dataset.tourOrigZ || '';
      // 🛠 FIX BUG: Xóa hiệu ứng viền đỏ nhấp nháy còn sót lại
      el.style.animation = '';
    }
  }

  // ── CHUYỂN BƯỚC ─────────────────────────────────────────────
  function goToStep(index) {
    if (index < 0) return;
    if (index >= STEPS.length) {
      stopTour(true); 
      return;
    }

    if (targetClickHandler && currentStep < STEPS.length) {
      const oldTarget = document.querySelector(STEPS[currentStep].target);
      const oldEvent = STEPS[currentStep].requireDblClick ? "dblclick" : "click";
      if (oldTarget) oldTarget.removeEventListener(oldEvent, targetClickHandler);
      targetClickHandler = null;
    }

    if (autoAdvanceTimeout) { clearTimeout(autoAdvanceTimeout); autoAdvanceTimeout = null; }

    if (currentStep < STEPS.length) unhighlightTarget(STEPS[currentStep].target);

    currentStep = index;
    const step = STEPS[index];
    highlightTarget(step.target, step.disableInteraction); 

    // 🛠 TÍNH NĂNG MỚI: Chạy logic tiền xử lý trước khi vẽ mục tiêu của bước này
    if (typeof step.onBeforeShow === 'function') {
      step.onBeforeShow();
    }

    let reqEvent = null;
    if (step.requireDblClick) reqEvent = "dblclick";
    else if (step.requireClick) reqEvent = "click";

    stepRequirementMet = !reqEvent; 

    if (reqEvent) {
      const el = document.querySelector(step.target);
      if (el) {
        if (!step.noPulse) {
          el.style.animation = "tourPulse 1.5s infinite"; 
        }
        
        targetClickHandler = () => {
          stepRequirementMet = true; 
          el.style.animation = "";   
          
          if (step.autoNextAfterClick) {
            setTimeout(() => goToStep(index + 1), step.autoNextDelay || 800);
          } else {
            const nBtn = document.getElementById("tour-next-btn");
            if (nBtn) {
              nBtn.style.opacity = "1";
              nBtn.style.cursor = "pointer";
              nBtn.style.animation = "tourPulse 1.5s infinite";
              nBtn.innerText = "Tiếp theo ->"; 
            }
          }
        };
        el.addEventListener(reqEvent, targetClickHandler);
      }
    }

    // Tự động cuộn màn hình
    if (step.scrollToY !== undefined) {
      window.scrollTo({ top: step.scrollToY, left: 0, behavior: 'smooth' });
      let startTime = Date.now();
      function followScroll() {
        if (!isActive || currentStep !== index) return;
        onResize(); 
        if (Date.now() - startTime < 800) { 
          requestAnimationFrame(followScroll);
        }
      }
      followScroll();
    }

    // Tự động đếm ngược chuyển bước
    if (step.autoAdvanceDelay) {
      autoAdvanceTimeout = setTimeout(() => goToStep(index + 1), step.autoAdvanceDelay);
    }

    const rect = getRect(step);
    // 🛠 ĐÃ FIX: Truyền thêm 'step' vào đây để nhận diện noPulse
    renderBackdrop(rect, step);
    renderInteractionShield(step, rect); 
    renderTooltip(step, index, STEPS.length);
  }

  // ── DỪNG TOUR ────────────────────────────────────────────────
  function stopTour(completed) {
    isActive = false;

    // 🛠 FIX BUG: Gỡ bỏ sự kiện click/dblclick đang chờ dở dang trên phần tử
    if (targetClickHandler && currentStep < STEPS.length && STEPS[currentStep]) {
      const oldTarget = document.querySelector(STEPS[currentStep].target);
      const oldEvent = STEPS[currentStep].requireDblClick ? "dblclick" : "click";
      if (oldTarget) oldTarget.removeEventListener(oldEvent, targetClickHandler);
      targetClickHandler = null;
    }

    // Gỡ highlight của bước hiện tại (sau khi thêm dòng bên trên vào, bước này sẽ xóa animation)
    if (STEPS[currentStep]) {
        unhighlightTarget(STEPS[currentStep].target);
    }

    const container = document.getElementById("tour-overlay-container");
    const tooltip   = document.getElementById("tour-tooltip");
    const backdrop  = document.getElementById("tour-backdrop");

    if (container) container.style.display = "none";
    if (tooltip)   tooltip.style.display   = "none";
    if (backdrop)  backdrop.innerHTML       = "";

    // Dọn dẹp khiên
    const shield = document.getElementById("tour-interaction-shield");
    if (shield) shield.style.display = "none";
    const warning = document.getElementById("tour-warning-msg");
    if (warning) warning.style.opacity = "0";
    
    // Gỡ khóa cuộn màn hình
    window.removeEventListener('wheel', preventScrollAndZoom);
    window.removeEventListener('touchmove', preventScrollAndZoom);
    window.removeEventListener('keydown', preventScrollKeys);
    window.removeEventListener("resize", onResize);

    // Ghi vào Dash Store để không hiện lại
    if (completed) {
        localStorage.setItem(
            '_dash_has-seen-tour',
            JSON.stringify({data: true})
        );
        localStorage.setItem('has-seen-tour', JSON.stringify(true));
    }
}
// Hàm khóa scroll & zoom
  function preventScrollAndZoom(e) {
    // Không cho phép hành vi mặc định của lăn chuột hoặc vuốt
    e.preventDefault();
  }

  // Khóa cuộn bằng bàn phím (Mũi tên lên, xuống, Space, PageUp, PageDown)
  function preventScrollKeys(e) {
    const keys = ["Space", "ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End"];
    if (keys.includes(e.code)) {
      e.preventDefault();
    }
  }
  // ── BẮT ĐẦU VÀ KẾT THÚC ─────────────────────────────────────
  function startTour() {
    if (isActive) return; // Nếu tour đang chạy rồi thì bỏ qua

    // 🛠 1. TỰ ĐỘNG CUỘN LÊN ĐẦU TRANG
    window.scrollTo({ top: 0, left: 0, behavior: 'smooth' });

    // 🛠 2. ĐỢI 300ms CHO MÀN HÌNH CUỘN XONG RỒI MỚI BẬT TOUR
    setTimeout(() => {
      isActive = true;
      currentStep = 0;
      stepRequirementMet = false;

      const container = document.getElementById("tour-overlay-container");
      if (container) container.style.display = "block";

      // Khóa cuộn chuột và bàn phím của người dùng
      window.addEventListener('wheel', preventScrollAndZoom, { passive: false });
      window.addEventListener('touchmove', preventScrollAndZoom, { passive: false });
      window.addEventListener('keydown', preventScrollKeys, { passive: false }); 
      
      // Chạy bước đầu tiên
      goToStep(0);

      // Bắt sự kiện resize
      window.addEventListener("resize", onResize);
    }, 300); // 300ms là đủ để màn hình trượt mượt mà lên top
  }

  function onResize() {
    if (!isActive) return;
    const step = STEPS[currentStep];
    const rect = getRect(step);
    
    // 🛠 ĐÃ FIX: Truyền thêm 'step' vào đây
    renderBackdrop(rect, step);
    
    renderInteractionShield(step, rect);
    const tooltip = document.getElementById("tour-tooltip");
    if (tooltip) {
      const tooltipH = tooltip.offsetHeight;
      const pos = calcTooltipPos(rect, step.position, 400, tooltipH); 
      tooltip.style.left = pos.left + "px";
      tooltip.style.top  = pos.top  + "px";
    }
  }

  // API public
  return { start: startTour, stop: stopTour, goTo: goToStep };

})();