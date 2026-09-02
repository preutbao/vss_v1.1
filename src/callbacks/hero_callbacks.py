# src/callbacks/hero_callbacks.py
from dash import Input, Output, State, callback_context, no_update, clientside_callback
from src.app_instance import app

# ── HERO SECTION: Scroll + Open Screener ──────────────────────────────────────
@app.callback(
    Output("fss-sticky-nav", "id", allow_duplicate=True),  # Dummy output to trigger
    [Input("hero-metrics-btn", "n_clicks"),
     Input("hero-schools-btn", "n_clicks")],
    prevent_initial_call=True,
)
def hero_scroll_to_screener(metrics_clicks, schools_clicks):
    """When clicking '193 chỉ số' or '10 trường phái',
    scroll to screener and open the filter button"""
    return no_update


# ── CLIENT-SIDE: Scroll to Screener + Click BO LOC + Open Groups ──
app.clientside_callback(
    """
    function(metrics_clicks, schools_clicks) {
        var triggered = dash_clientside.callback_context.triggered;
        if (!triggered || triggered.length === 0) {
            return dash.no_update;
        }
        
        var prop_id = triggered[0]['prop_id'];
        var is_metrics = prop_id.includes('hero-metrics-btn');
        var is_schools = prop_id.includes('hero-schools-btn');
        
        if (is_metrics || is_schools) {
            // 1. Scroll to screener section
            var anchor = document.getElementById('screener-scroll-anchor');
            if (anchor) {
                anchor.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
            
            // 2. Open BO LOC button after short delay (give scroll time)
            setTimeout(function() {
                var filterBtn = document.getElementById('toggle-filter-btn');
                if (filterBtn && filterBtn.getAttribute('aria-expanded') !== 'true') {
                    filterBtn.click();
                }
                
                // 3. After filter opens, open the appropriate groups
                setTimeout(function() {
                    // For metrics: open "Thông tin chung" (tong-quan)
                    if (is_metrics) {
                        // Find the wizard group button for "tong-quan"
                        var groupBtns = document.querySelectorAll('[id*="wizard-group-btn"]');
                        for (var i = 0; i < groupBtns.length; i++) {
                            var btn = groupBtns[i];
                            // Check if this is the tong-quan button
                            if (btn.__dash_properties__ && 
                                btn.__dash_properties__.id && 
                                btn.__dash_properties__.id.group === 'tong-quan') {
                                btn.click();
                                break;
                            }
                        }
                        // Fallback: search by group attribute in id
                        var tongQuanBtn = document.querySelector('[id*="tong-quan"]');
                        if (!tongQuanBtn) {
                            // Find first wizard-group-btn and see if we can identify it
                            var allGroupItems = document.querySelectorAll('.wizard-group-item');
                            if (allGroupItems.length > 0) {
                                allGroupItems[0].click();
                            }
                        }
                    }
                    // For schools: open strategy dropdown
                    else if (is_schools) {
                        var strategyBtn = document.getElementById('strategy-accordion-trigger');
                        if (strategyBtn) {
                            strategyBtn.click();
                        }
                    }
                }, 300);
            }, 500);
        }
        
        return dash.no_update;
    }
    """,
    Output("fss-sticky-nav", "data-hero-action", allow_duplicate=True),
    [Input("hero-metrics-btn", "n_clicks"),
     Input("hero-schools-btn", "n_clicks")],
    prevent_initial_call=True,
)


# ── HERO: Open AI Chat ────────────────────────────────────────────────────────
@app.callback(
    Output("chat-panel", "style", allow_duplicate=True),
    Input("hero-ai-chat-btn", "n_clicks"),
    State("chat-panel", "style"),
    prevent_initial_call=True,
    allow_duplicate=True,
)
def hero_open_ai_chat(ai_clicks, chat_style):
    """When clicking 'AI hỗ trợ diễn giải', open the chat panel"""
    if not ai_clicks:
        return no_update
    
    # Open chat if closed
    if chat_style and (chat_style.get("opacity", "0") in ("0", 0) or
                       chat_style.get("pointerEvents") == "none"):
        return {
            **chat_style,
            "transform": "scale(1) translateY(0)",
            "opacity": "1",
            "pointerEvents": "auto"
        }
    
    return no_update