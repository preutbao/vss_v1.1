// Đảm bảo namespace dash_clientside tồn tại
window.dash_clientside = Object.assign({}, window.dash_clientside);

window.dash_clientside.chart_utils = {
    auto_zoom_y: function(relayoutData) {
        // 1. Kiểm tra sự tồn tại của sự kiện và dữ liệu
        if (!relayoutData) return window.dash_clientside.no_update;
        if (!relayoutData['xaxis.range[0]'] && !relayoutData['xaxis.range']) {
            return window.dash_clientside.no_update;
        }

        // 2. Tìm biểu đồ Plotly
        var graphDiv = document.getElementById('main-candlestick-chart');
        if (!graphDiv) return window.dash_clientside.no_update;
        
        var plotlyElement = graphDiv.querySelector('.js-plotly-plot') || graphDiv;
        // Kiểm tra xem Plotly đã khởi tạo và có dữ liệu (data) cũng như layout chưa
        if (!plotlyElement || !plotlyElement.data || !plotlyElement.layout) return window.dash_clientside.no_update;

        // 3. Lấy dải X đang hiển thị
        var x0, x1;
        if (relayoutData['xaxis.range[0]']) {
            x0 = relayoutData['xaxis.range[0]'];
            x1 = relayoutData['xaxis.range[1]'];
        } else {
            x0 = relayoutData['xaxis.range'][0];
            x1 = relayoutData['xaxis.range'][1];
        }

        // Tính toán Index dựa trên range của trục Category (Plotly x-axis category dùng index)
        var startIndex = Math.max(0, Math.floor(x0));
        var endIndex = Math.ceil(x1);

        var y_min = Infinity;
        var y_max = -Infinity;

        // 4. Lặp qua tất cả các trace để tìm min/max
        for (var i = 0; i < plotlyElement.data.length; i++) {
            var trace = plotlyElement.data[i];
            
            // CHỈ QUAN TÂM ĐẾN CÁC TRACE NẰM TRÊN TRỤC Y CHÍNH (Nến, Đường giá, MA)
            // Trong Plotly, trục Y chính có thể là undefined, 'y', hoặc 'y1'
            if (trace.yaxis && trace.yaxis !== 'y' && trace.yaxis !== 'y1') continue;

            // KIỂM TRA TRACE LÀ CANDLESTICK
            if (trace.type === 'candlestick') {
                // Đảm bảo trace có mảng high/low
                if (!trace.high || !trace.low) continue;
                for (var j = startIndex; j <= endIndex && j < trace.high.length; j++) {
                    var h = trace.high[j];
                    var l = trace.low[j];
                    if (h !== null && typeof h !== 'undefined' && h > y_max) y_max = h;
                    if (l !== null && typeof l !== 'undefined' && l < y_min) y_min = l;
                }
            } 
            // KIỂM TRA TRACE LÀ LINE/AREA/SCATTER (Đường giá, Vùng, MA)
            else if (trace.type === 'scatter' || trace.type === 'scattergl') {
                // Đảm bảo trace có mảng y
                if (!trace.y) continue;
                for (var j = startIndex; j <= endIndex && j < trace.y.length; j++) {
                    var val = trace.y[j];
                    if (val !== null && typeof val !== 'undefined' && val > y_max) y_max = val;
                    if (val !== null && typeof val !== 'undefined' && val < y_min) y_min = val;
                }
            }
        }

        // 5. Nếu tìm thấy min/max hợp lệ, cập nhật Layout
        if (y_min !== Infinity && y_max !== -Infinity && y_min < y_max) {
            var padding = (y_max - y_min) * 0.1; // Chừa 10% khoảng trống
            var new_y_min = y_min - padding;
            var new_y_max = y_max + padding;
            
            // Sử dụng Plotly.relayout để cập nhật mượt mà
            try {
                Plotly.relayout(plotlyElement, {
                    'yaxis.range': [new_y_min, new_y_max]
                });
            } catch (e) {
                console.error("Lỗi khi auto-zoom Y:", e);
            }
        }
        
        return window.dash_clientside.no_update;
    }
};