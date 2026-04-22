/* ============================================================================
   SSI SCREENER - COMPLETE SOLUTION
   - Click criteria → Add filter with grade chips or range sliders
   - Toggle chips → Auto update filter state
   - Click "ÁP DỤNG" → Apply all filters to table
   ============================================================================ */

// ============================================================================
// GLOBAL STATE MANAGEMENT
// ============================================================================

window.FilterState = {
    activeFilters: {},
    
    // Lưu grades đã chọn cho từng filter
    setGrades: function(filterId, grades) {
        if (!this.activeFilters[filterId]) {
            this.activeFilters[filterId] = {};
        }
        this.activeFilters[filterId].grades = grades;
        this.syncToStore();
    },
    
    // Lưu range values
    setRange: function(filterId, min, max) {
        if (!this.activeFilters[filterId]) {
            this.activeFilters[filterId] = {};
        }
        this.activeFilters[filterId].range = [min, max];
        this.syncToStore();
    },
    
    // Xóa filter
    remove: function(filterId) {
        delete this.activeFilters[filterId];
        this.syncToStore();
    },
    
    // Sync state với Dash Store (để server callback có thể đọc)
    syncToStore: function() {
        // Update stores cho từng filter type
        Object.keys(this.activeFilters).forEach(filterId => {
            const filter = this.activeFilters[filterId];
            
            // Map filter ID to store ID
            const storeMap = {
                'value-score': 'filter-value-score',
                'growth-score': 'filter-growth-score',
                'momentum-score': 'filter-momentum-score',
                'vgm-score': 'filter-vgm-score',
                'price': 'filter-price',
                'volume': 'filter-volume',
                'pe': 'filter-pe',
                'roe': 'filter-roe'
            };
            
            const storeId = storeMap[filterId];
            if (storeId) {
                const storeElement = document.getElementById(storeId);
                if (storeElement) {
                    if (filter.grades) {
                        // Update grades store
                        storeElement.setAttribute('data', JSON.stringify(filter.grades));
                    } else if (filter.range) {
                        // Update range store
                        storeElement.setAttribute('data', JSON.stringify(filter.range));
                    }
                }
            }
        });
        
        console.log('📊 Filter state updated:', this.activeFilters);
    }
};

// ============================================================================
// CRITERIA CONFIGURATION
// ============================================================================

const CRITERIA_CONFIG = {
    'value-score': {
        label: 'Value (FiinTrade Score)',
        type: 'grade',
        storeId: 'filter-value-score',
        defaultGrades: ['A', 'B', 'C', 'D', 'F']
    },
    'growth-score': {
        label: 'Growth (FiinTrade Score)',
        type: 'grade',
        storeId: 'filter-growth-score',
        defaultGrades: ['A', 'B', 'C', 'D', 'F']
    },
    'momentum-score': {
        label: 'Momentum (FiinTrade Score)',
        type: 'grade',
        storeId: 'filter-momentum-score',
        defaultGrades: ['A', 'B', 'C', 'D', 'F']
    },
    'vgm-score': {
        label: 'VGM (FiinTrade Score)',
        type: 'grade',
        storeId: 'filter-vgm-score',
        defaultGrades: ['A', 'B', 'C', 'D', 'F']
    },
    'price': {
        label: 'Giá hiện tại',
        type: 'range',
        storeId: 'filter-price',
        unit: ' IDR',
        min: 0,
        max: 50000,
        step: 100,
        defaultRange: [0, 50000]
    },
    'volume': {
        label: 'Khối lượng giao dịch',
        type: 'range',
        storeId: 'filter-volume',
        unit: '',
        min: 0,
        max: 10000000,
        step: 100000,
        defaultRange: [0, 10000000]
    },
    'pe': {
        label: 'P/E Ratio',
        type: 'range',
        storeId: 'filter-pe',
        unit: '',
        min: 0,
        max: 100,
        step: 1,
        defaultRange: [0, 50]
    },
    'pb': {
        label: 'P/B Ratio',
        type: 'range',
        storeId: 'filter-pb',
        unit: '',
        min: 0,
        max: 20,
        step: 0.1,
        defaultRange: [0, 10]
    },
    'roe': {
        label: 'ROE (%)',
        type: 'range',
        storeId: 'filter-roe',
        unit: '%',
        min: -50,
        max: 100,
        step: 1,
        defaultRange: [-20, 50]
    }
};

// ============================================================================
// INITIALIZATION
// ============================================================================

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initFilterInteractions);
} else {
    initFilterInteractions();
}

function initFilterInteractions() {
    console.log('🚀 Initializing SSI Filter System...');
    
    let retryCount = 0;
    const maxRetries = 10;
    
    const setupInterval = setInterval(() => {
        const criteriaItems = document.querySelectorAll('[id*="criteria-"]');
        
        if (criteriaItems.length > 0 || retryCount >= maxRetries) {
            clearInterval(setupInterval);
            
            if (criteriaItems.length > 0) {
                setupCriteriaClickHandlers();
                setupGradeChipHandlers();
                setupRemoveFilterHandlers();
                console.log('✅ Filter system ready!');
            }
        }
        
        retryCount++;
    }, 500);
}

// ============================================================================
// CRITERIA CLICK HANDLERS
// ============================================================================

function setupCriteriaClickHandlers() {
    document.addEventListener('click', function(e) {
        let target = e.target;
        let criteriaItem = null;
        
        while (target && target !== document) {
            const targetId = target.id || '';
            if (targetId.includes('criteria-') || target.classList.contains('criteria-item-hover')) {
                criteriaItem = target;
                break;
            }
            target = target.parentElement;
        }
        
        if (!criteriaItem) return;
        
        e.stopPropagation();
        
        let criteriaId = criteriaItem.id.replace('criteria-', '');
        
        console.log('🎯 Clicked criteria:', criteriaId);
        
        const config = CRITERIA_CONFIG[criteriaId];
        if (!config) {
            console.warn('⚠️ Unknown criteria:', criteriaId);
            return;
        }
        
        const existingFilter = document.getElementById(`selected-${criteriaId}`);
        if (existingFilter) {
            showToast(`ℹ️ "${config.label}" đã có trong bộ lọc`, 'info');
            highlightElement(existingFilter);
            return;
        }
        
        addFilterToUI(criteriaId, config);
        showToast(`✅ Đã thêm: ${config.label}`, 'success');
    });
}

// ============================================================================
// CREATE FILTER HTML
// ============================================================================

function addFilterToUI(filterId, config) {
    const container = document.getElementById('selected-filters-container');
    if (!container) return;
    
    let filterHtml = '';
    
    if (config.type === 'grade') {
        filterHtml = createGradeFilterHTML(filterId, config);
        // Initialize state
        window.FilterState.setGrades(filterId, config.defaultGrades);
    } else if (config.type === 'range') {
        filterHtml = createRangeFilterHTML(filterId, config);
        // Initialize state
        window.FilterState.setRange(filterId, config.defaultRange[0], config.defaultRange[1]);
    }
    
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = filterHtml;
    const filterElement = tempDiv.firstElementChild;
    
    container.appendChild(filterElement);
    
    setTimeout(() => {
        filterElement.style.opacity = '1';
        filterElement.style.transform = 'translateX(0)';
    }, 10);
    
    setupGradeChipHandlers();
    setupRemoveFilterHandlers();
    
    // Setup range slider listeners
    if (config.type === 'range') {
        setupRangeSliderHandlers(filterId);
    }
}

function createGradeFilterHTML(filterId, config) {
    const grades = config.defaultGrades || ['A', 'B', 'C', 'D', 'F'];
    
    const gradeChipsHtml = grades.map(grade => {
        const lowerGrade = grade.toLowerCase();
        return `<span class="grade-chip grade-chip-${lowerGrade} active" 
                      id="chip-${filterId}-${lowerGrade}" 
                      data-filter="${filterId}" 
                      data-grade="${grade}">
                    ${grade}
                </span>`;
    }).join('');
    
    return `
        <div id="selected-${filterId}" 
             class="filter-item"
             style="padding: 12px; 
                    background-color: #161b22; 
                    border-radius: 6px; 
                    border: 1px solid #30363d; 
                    margin-bottom: 10px;
                    opacity: 0;
                    transform: translateX(-20px);
                    transition: all 0.3s ease;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <div style="display: flex; align-items: center;">
                    <i class="fas fa-check-square" style="color: #3fb950; margin-right: 8px; font-size: 14px;"></i>
                    <span style="color: #c9d1d9; font-size: 13px; font-weight: 500;">${config.label}</span>
                </div>
                <i class="fas fa-times remove-filter-icon" 
                   data-filter="${filterId}"
                   style="color: #8b949e; cursor: pointer; font-size: 14px; transition: all 0.2s;"></i>
            </div>
            <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                ${gradeChipsHtml}
            </div>
        </div>
    `;
}

function createRangeFilterHTML(filterId, config) {
    const minVal = config.defaultRange[0];
    const maxVal = config.defaultRange[1];
    
    return `
        <div id="selected-${filterId}" 
             class="filter-item"
             style="padding: 12px; 
                    background-color: #161b22; 
                    border-radius: 6px; 
                    border: 1px solid #30363d; 
                    margin-bottom: 10px;
                    opacity: 0;
                    transform: translateX(-20px);
                    transition: all 0.3s ease;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <div style="display: flex; align-items: center;">
                    <i class="fas fa-check-square" style="color: #3fb950; margin-right: 8px; font-size: 14px;"></i>
                    <span style="color: #c9d1d9; font-size: 13px; font-weight: 500;">${config.label}</span>
                </div>
                <i class="fas fa-times remove-filter-icon" 
                   data-filter="${filterId}"
                   style="color: #8b949e; cursor: pointer; font-size: 14px; transition: all 0.2s;"></i>
            </div>
            
            <!-- Range Display -->
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                <span style="color: #58a6ff; font-size: 13px; font-weight: 600;">
                    <span id="range-min-${filterId}">${formatNumber(minVal)}</span>${config.unit}
                </span>
                <span style="color: #8b949e; font-size: 12px;">→</span>
                <span style="color: #58a6ff; font-size: 13px; font-weight: 600;">
                    <span id="range-max-${filterId}">${formatNumber(maxVal)}</span>${config.unit}
                </span>
            </div>
            
            <!-- Range Sliders -->
            <div style="position: relative; padding: 10px 0;">
                <input type="range" 
                       id="slider-min-${filterId}"
                       class="range-slider range-slider-min"
                       min="${config.min}" 
                       max="${config.max}" 
                       step="${config.step}"
                       value="${minVal}"
                       data-filter="${filterId}"
                       style="position: absolute; width: 100%; pointer-events: none; background: transparent;">
                
                <input type="range" 
                       id="slider-max-${filterId}"
                       class="range-slider range-slider-max"
                       min="${config.min}" 
                       max="${config.max}" 
                       step="${config.step}"
                       value="${maxVal}"
                       data-filter="${filterId}"
                       style="position: absolute; width: 100%; pointer-events: none; background: transparent;">
                
                <div class="slider-track" 
                     style="height: 4px; 
                            background: #30363d; 
                            border-radius: 2px; 
                            position: relative;">
                    <div id="slider-range-${filterId}"
                         class="slider-range" 
                         style="position: absolute; 
                                height: 100%; 
                                background: linear-gradient(90deg, #3b82f6, #58a6ff); 
                                border-radius: 2px;
                                left: 0%; 
                                right: 0%;"></div>
                </div>
            </div>
        </div>
    `;
}

// ============================================================================
// GRADE CHIP HANDLERS
// ============================================================================

function setupGradeChipHandlers() {
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('grade-chip')) {
            e.stopPropagation();
            
            const filterId = e.target.getAttribute('data-filter');
            const grade = e.target.getAttribute('data-grade');
            
            // Toggle active class
            e.target.classList.toggle('active');
            
            // Animation
            e.target.style.transform = 'scale(0.9)';
            setTimeout(() => {
                e.target.style.transform = '';
            }, 100);
            
            // Update state
            updateGradeState(filterId);
            
            console.log(`🎨 Toggled ${grade} for ${filterId}`);
        }
    });
}

function updateGradeState(filterId) {
    const chips = document.querySelectorAll(`[data-filter="${filterId}"].grade-chip.active`);
    const activeGrades = Array.from(chips).map(chip => chip.getAttribute('data-grade'));
    
    window.FilterState.setGrades(filterId, activeGrades);
    console.log(`📊 ${filterId} active grades:`, activeGrades);
}

// ============================================================================
// RANGE SLIDER HANDLERS
// ============================================================================

function setupRangeSliderHandlers(filterId) {
    const config = CRITERIA_CONFIG[filterId];
    if (!config) return;
    
    const minSlider = document.getElementById(`slider-min-${filterId}`);
    const maxSlider = document.getElementById(`slider-max-${filterId}`);
    const minDisplay = document.getElementById(`range-min-${filterId}`);
    const maxDisplay = document.getElementById(`range-max-${filterId}`);
    const rangeDisplay = document.getElementById(`slider-range-${filterId}`);
    
    if (!minSlider || !maxSlider) return;
    
    // Enable pointer events
    minSlider.style.pointerEvents = 'auto';
    maxSlider.style.pointerEvents = 'auto';
    
    function updateRangeDisplay() {
        let minVal = parseFloat(minSlider.value);
        let maxVal = parseFloat(maxSlider.value);
        
        // Đảm bảo min < max
        if (minVal > maxVal) {
            [minVal, maxVal] = [maxVal, minVal];
            minSlider.value = minVal;
            maxSlider.value = maxVal;
        }
        
        // Update displays
        minDisplay.textContent = formatNumber(minVal);
        maxDisplay.textContent = formatNumber(maxVal);
        
        // Update range bar
        const percent1 = ((minVal - config.min) / (config.max - config.min)) * 100;
        const percent2 = ((maxVal - config.min) / (config.max - config.min)) * 100;
        rangeDisplay.style.left = percent1 + '%';
        rangeDisplay.style.right = (100 - percent2) + '%';
        
        // Update state
        window.FilterState.setRange(filterId, minVal, maxVal);
    }
    
    minSlider.addEventListener('input', updateRangeDisplay);
    maxSlider.addEventListener('input', updateRangeDisplay);
}

// ============================================================================
// REMOVE FILTER HANDLERS
// ============================================================================

function setupRemoveFilterHandlers() {
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('remove-filter-icon')) {
            e.stopPropagation();
            
            const filterId = e.target.getAttribute('data-filter');
            const filterElement = document.getElementById(`selected-${filterId}`);
            
            if (filterElement) {
                filterElement.style.opacity = '0';
                filterElement.style.transform = 'translateX(20px)';
                
                setTimeout(() => {
                    filterElement.remove();
                    window.FilterState.remove(filterId);
                    
                    const config = CRITERIA_CONFIG[filterId];
                    const label = config ? config.label : filterId;
                    showToast(`🗑️ Đã xóa: ${label}`, 'info');
                }, 300);
            }
        }
    });
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toFixed(0);
}

function showToast(message, type = 'info') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        container.style.cssText = `
            position: fixed; top: 20px; right: 20px; z-index: 9999;
            display: flex; flex-direction: column; gap: 10px;
        `;
        document.body.appendChild(container);
    }
    
    const toast = document.createElement('div');
    let bgColor = type === 'success' ? '#10b981' : 
                  type === 'error' ? '#ef4444' : 
                  type === 'warning' ? '#f59e0b' : '#3b82f6';
    
    toast.innerHTML = message;
    toast.style.cssText = `
        background-color: ${bgColor}; color: #ffffff; padding: 12px 16px;
        border-radius: 6px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        font-size: 14px; font-weight: 600; min-width: 250px; max-width: 400px;
        opacity: 0; transform: translateX(100px); transition: all 0.3s ease;
    `;
    
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateX(0)';
    }, 10);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100px)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function highlightElement(element) {
    const originalBg = element.style.backgroundColor;
    element.style.transition = 'background-color 0.3s ease';
    element.style.backgroundColor = '#58a6ff30';
    setTimeout(() => {
        element.style.backgroundColor = originalBg;
    }, 1000);
}

console.log('🎯 SSI Screener COMPLETE - Ready to use!');

/* ── Shimmer mỗi 10 giây cho nút BỘ LỌC ── */
(function () {
    function triggerShimmer() {
        const btn = document.getElementById("btn-open-filter");
        if (!btn) return;
        btn.classList.add("play-shimmer");
        // Xóa class sau khi animation kết thúc (~700ms) để có thể chạy lại
        setTimeout(function () {
            btn.classList.remove("play-shimmer");
        }, 800);
    }

    // Chờ DOM sẵn sàng
    document.addEventListener("DOMContentLoaded", function () {
        // Lần đầu sau 1 giây
        setTimeout(triggerShimmer, 1000);
        // Sau đó mỗi 4 giây
        setInterval(triggerShimmer, 4000);
    });
})();

// Force favicon — bypass Hugging Face override
(function () {
    var FAVICON_PATH = "/assets/favicon.ico";

    function setFavicon() {
        // Xóa tất cả favicon tags không phải của mình
        document.querySelectorAll(
            "link[rel='icon'], link[rel='shortcut icon'], link[rel='apple-touch-icon']"
        ).forEach(function (el) {
            if (el.href.indexOf(FAVICON_PATH) === -1) {
                el.parentNode.removeChild(el);
            }
        });

        // Đảm bảo favicon của mình luôn tồn tại
        if (!document.querySelector("link[href='" + FAVICON_PATH + "']")) {
            var link = document.createElement("link");
            link.rel  = "icon";
            link.type = "image/x-icon";
            link.href = FAVICON_PATH;
            document.head.appendChild(link);
        }
    }

    // Chạy ngay
    setFavicon();

    // MutationObserver: react ngay khi HF inject favicon mới vào <head>
    var observer = new MutationObserver(function (mutations) {
        var needsFix = mutations.some(function (m) {
            return Array.from(m.addedNodes).some(function (node) {
                return (
                    node.nodeName === "LINK" &&
                    (node.rel === "icon" ||
                     node.rel === "shortcut icon" ||
                     node.rel === "apple-touch-icon") &&
                    node.href.indexOf(FAVICON_PATH) === -1
                );
            });
        });
        if (needsFix) setFavicon();
    });

    observer.observe(document.head, { childList: true, subtree: true });

    // Backup: poll mỗi 1s trong 30s đầu (phòng edge case)
    var polls = 0;
    var interval = setInterval(function () {
        setFavicon();
        if (++polls >= 30) clearInterval(interval);
    }, 1000);
})();