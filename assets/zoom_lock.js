/* zoom_lock.js — Force 90% zoom, prevent user changing it */
(function () {
    /* 1. Block Ctrl +/-/0 keyboard shortcuts */
    document.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) &&
            (e.key === '+' || e.key === '-' || e.key === '=' || e.key === '0')) {
            e.preventDefault();
            e.stopPropagation();
        }
    }, true);

    /* 2. Block Ctrl+scroll zoom */
    document.addEventListener('wheel', function (e) {
        if (e.ctrlKey) e.preventDefault();
    }, { passive: false, capture: true });

    /* 3. Block pinch-zoom on touch devices */
    document.addEventListener('gesturestart', function (e) { e.preventDefault(); }, true);
    document.addEventListener('gesturechange', function (e) { e.preventDefault(); }, true);
})();