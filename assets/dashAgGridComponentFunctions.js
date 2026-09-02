var dagcomponentfuncs = window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {};

// Tạo một component tên là CustomStarRating
dagcomponentfuncs.CustomStarRating = function (props) {
    if (!props.value && !props.data) {
        return "–";
    }
    
    var score = parseInt(props.value) || 0;
    var fssRank = (props.data && props.data.FSS_Smart_Rank !== undefined && props.data.FSS_Smart_Rank !== null) 
                  ? parseFloat(props.data.FSS_Smart_Rank) 
                  : 0;
    var scoreNum = Math.round(fssRank * 100); // Scale 0.0-1.0 to 0-100
    var emptyScore = 5 - score;
    
    // Determine score color based on 0-100 scale
    var scoreColor = scoreNum >= 70 ? '#10b981' : scoreNum >= 50 ? '#f59e0b' : '#ef4444';
    var scoreBg = scoreNum >= 70 ? '#10b98120' : scoreNum >= 50 ? '#f59e0b20' : '#ef444420';
    
    return React.createElement(
        'div',
        { style: { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' } },
        // Stars
        React.createElement('span', { style: { letterSpacing: '1px' } },
            React.createElement('span', { style: { color: '#FFC107' } }, '★'.repeat(score)),
            React.createElement('span', { style: { color: '#424242' } }, '★'.repeat(emptyScore))
        ),
        // Smart Rank score with background badge
        React.createElement('span', { 
            style: { 
                fontSize: '12px', 
                fontWeight: '700',
                color: scoreColor,
                backgroundColor: scoreBg,
                padding: '3px 6px',
                borderRadius: '4px',
                minWidth: '32px',
                textAlign: 'center'
            } 
        }, scoreNum)
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
