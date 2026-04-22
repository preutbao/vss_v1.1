/**
 * scroll_lock.js
 * Khóa scroll body khi bất kỳ modal/offcanvas nào của Dash mở.
 *
 * Vấn đề gốc: trang dùng zoom:90% trên <html> khiến Bootstrap's native
 * `body { overflow: hidden }` không đủ mạnh để khóa scroll.
 *
 * Giải pháp: MutationObserver theo dõi class "modal-open" trên <body>
 * (Bootstrap tự thêm/xóa khi modal mở/đóng), đồng thời cũng watch
 * trực tiếp các element .modal và .offcanvas để bắt edge case.
 */

(function () {
  "use strict";

  /* ─── Trạng thái scroll trước khi lock ───────────────────────────────── */
  var _scrollY = 0;
  var _locked  = false;

  function lockScroll() {
    if (_locked) return;
    _scrollY = window.scrollY || document.documentElement.scrollTop || 0;
    _locked  = true;

    /* Gán trực tiếp style inline — ưu tiên cao hơn bất kỳ CSS class nào */
    document.body.style.setProperty("overflow",  "hidden", "important");
    document.body.style.setProperty("position",  "fixed",  "important");
    document.body.style.setProperty("top",       "-" + _scrollY + "px", "important");
    document.body.style.setProperty("width",     "100%",   "important");

    document.documentElement.style.setProperty("overflow", "hidden", "important");
  }

  function unlockScroll() {
    if (!_locked) return;
    _locked = false;

    document.body.style.removeProperty("overflow");
    document.body.style.removeProperty("position");
    document.body.style.removeProperty("top");
    document.body.style.removeProperty("width");

    document.documentElement.style.removeProperty("overflow");

    /* Khôi phục vị trí scroll */
    window.scrollTo(0, _scrollY);
  }

  /* ─── Kiểm tra có modal/offcanvas nào đang mở không ─────────────────── */
  function anyModalOpen() {
    // Dash dbc.Modal set display:block khi is_open=True
    // KHÔNG dùng Bootstrap JS → KHÔNG có class "modal-open" trên body
    var modals = document.querySelectorAll(".modal");
    for (var i = 0; i < modals.length; i++) {
        var style = window.getComputedStyle(modals[i]);
        if (style.display !== "none") return true;
    }
    return false;
}

  function syncLock() {
    if (anyModalOpen()) {
      lockScroll();
    } else {
      unlockScroll();
    }
  }

  /* ─── MutationObserver trên body.classList ───────────────────────────── */
  var bodyObserver = new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) {
      if (mutation.type === "attributes" && mutation.attributeName === "class") {
        syncLock();
      }
    });
  });

  /* ─── MutationObserver trên DOM — bắt khi Dash render modal vào DOM ─── */
  var domObserver = new MutationObserver(function (mutations) {
    var changed = false;
    mutations.forEach(function (mutation) {
      mutation.addedNodes.forEach(function (node) {
        if (node.nodeType === 1) changed = true;
      });
      mutation.removedNodes.forEach(function (node) {
        if (node.nodeType === 1) changed = true;
      });
      if (mutation.type === "attributes") changed = true;
    });
    if (changed) syncLock();
  });

  /* ─── Khởi động sau khi DOM sẵn sàng ────────────────────────────────── */
  function init() {
    bodyObserver.observe(document.body, { attributes: true });

    /* Watch toàn bộ subtree của document để bắt Dash render modal động */
    domObserver.observe(document.body, {
    childList:     true,
    subtree:       true,
    attributes:    true,
    attributeFilter: ["class", "style", "display"],
});

    /* Chạy ngay lần đầu phòng trường hợp trang load khi modal đã mở */
    syncLock();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();