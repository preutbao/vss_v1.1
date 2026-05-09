var dagcomponentfuncs = window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {};

// Tạo một component tên là CustomStarRating
dagcomponentfuncs.CustomStarRating = function (props) {
    if (!props.value) {
        return "–";
    }
    
    var score = parseInt(props.value);
    var emptyScore = 5 - score;
    
    // Dùng React.createElement để render HTML trực tiếp trong Dash
    // Sao sáng màu vàng (#FFC107), sao tối màu xám tro (#424242 hoặc tùy nền web)
    return React.createElement(
        'div',
        { style: { letterSpacing: '2px' } }, // Tạo khoảng cách giữa các sao cho thoáng
        React.createElement('span', { style: { color: '#FFC107' } }, '★'.repeat(score)),
        React.createElement('span', { style: { color: '#424242' } }, '★'.repeat(emptyScore))
    );
};4