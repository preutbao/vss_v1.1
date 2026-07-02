var dagcomponentfuncs = window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {};

// Tạo một component tên là CustomStarRating
dagcomponentfuncs.CustomStarRating = function (props) {
    if (!props.value) {
        return "–";
    }
    
    var score = parseInt(props.value);
    var emptyScore = 5 - score;
    
    return React.createElement(
        'div',
        { style: { letterSpacing: '2px' } },
        React.createElement('span', { style: { color: '#FFC107' } }, '★'.repeat(score)),
        React.createElement('span', { style: { color: '#424242' } }, '★'.repeat(emptyScore))
    );
};

// Tạo component tên CustomSparkline — vẽ mini line-chart xu hướng giá 30 phiên
dagcomponentfuncs.CustomSparkline = function (props) {
    var data = props.value;
    if (!data || !Array.isArray(data) || data.length < 2) {
        return "–";
    }
    var w = 80, h = 26, pad = 2;
    var min = Math.min.apply(null, data);
    var max = Math.max.apply(null, data);
    var range = (max - min) || 1;
    var step = (w - pad * 2) / (data.length - 1);
    var points = data.map(function (v, i) {
        var x = pad + i * step;
        var y = h - pad - ((v - min) / range) * (h - pad * 2);
        return x + ',' + y;
    }).join(' ');
    var isUp = data[data.length - 1] >= data[0];
    var color = isUp ? '#10b981' : '#ef4444';
    return React.createElement(
        'svg',
        { width: w, height: h, viewBox: '0 0 ' + w + ' ' + h },
        React.createElement('polyline', {
            points: points,
            fill: 'none',
            stroke: color,
            strokeWidth: 1.5,
            strokeLinejoin: 'round',
            strokeLinecap: 'round',
        })
    );
};
