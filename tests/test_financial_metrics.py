# tests/test_financial_metrics.py
"""
Test cho Critical 3 (bản đánh giá backend):

1) P/E fallback bị đảo ngược công thức: khi thiếu cả cột EPS lẫn 'shares',
   code cũ gán Market Cap/Net Income (vốn dĩ CHÍNH LÀ P/E) vào biến tạm
   "_eps_for_pe", rồi lại chia Price cho biến đó lần nữa. Về mặt toán học,
   phép chia kép này triệt tiêu ngược lại thành Net Income/Shares (~EPS),
   KHÔNG PHẢI P/E — nhưng vẫn được gán vào cột 'P/E'.

2) Dividend Yield fallback dùng nhầm TỔNG TIỀN cổ tức (toàn công ty) làm
   DPS (cổ tức/cổ phiếu) mà không chia cho số cổ phiếu lưu hành, gây sai
   lệch đơn vị nghiêm trọng.
"""
import sys
import os
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.backend.quant_engine import calculate_financial_metrics


class TestPEFallbackFormula:
    def test_pe_fallback_equals_market_cap_over_net_income(self):
        """Khi KHÔNG có cột EPS thật và KHÔNG có cột 'shares' nào khớp
        SMART_MAPPING, P/E phải rơi vào nhánh fallback cuối và bằng đúng
        Market Cap / Net Income — không được bị đảo ngược thành ~EPS."""
        df_price = pd.DataFrame({
            "Ticker": ["AAA", "BBB", "CCC"],
            "Price Close": [50.0, 100.0, 20.0],
            "Market Cap": [1_500.0, 8_000.0, 400.0],  # đơn vị tỷ VND, tùy ý cho test
        })
        df_fin = pd.DataFrame({
            "Ticker": ["AAA", "BBB", "CCC"],
            "Date": pd.to_datetime(["2025-12-31"] * 3),
            # Chỉ cung cấp Net Income — KHÔNG cung cấp bất kỳ cột EPS hay
            # số lượng cổ phiếu nào để bắt buộc rơi vào nhánh fallback cuối.
            "Net Income after Minority Interest": [100.0, 800.0, 50.0],
        })

        result = calculate_financial_metrics(df_price, df_fin)

        expected_pe = df_price["Market Cap"] / df_fin["Net Income after Minority Interest"]
        pd.testing.assert_series_equal(
            result["P/E"].reset_index(drop=True),
            expected_pe.reset_index(drop=True),
            check_names=False,
            atol=1e-6,
        )

    def test_pe_fallback_is_not_inverted_to_eps_like_value(self):
        """Test hồi quy trực tiếp cho bug cũ: nếu ai đó vô tình đưa code về
        lại công thức đảo ngược (chia Price cho MC/NI thêm 1 lần), P/E sẽ
        bị triệt tiêu về ~Net Income/Shares thay vì Market Cap/Net Income.
        Test này phân biệt rõ 2 kết quả khác nhau đó."""
        df_price = pd.DataFrame({
            "Ticker": ["AAA"],
            "Price Close": [50.0],
            "Market Cap": [1500.0],
        })
        df_fin = pd.DataFrame({
            "Ticker": ["AAA"],
            "Date": pd.to_datetime(["2025-12-31"]),
            "Net Income after Minority Interest": [100.0],
        })
        result = calculate_financial_metrics(df_price, df_fin)

        correct_pe = 1500.0 / 100.0          # = 15.0  (Market Cap / Net Income)
        buggy_inverted_pe = 50.0 / correct_pe  # = 3.33  (công thức đảo ngược cũ)

        actual_pe = result["P/E"].iloc[0]
        assert actual_pe == pytest.approx(correct_pe, abs=1e-6), (
            f"P/E fallback phải bằng Market Cap/Net Income ({correct_pe}), "
            f"nhưng thực tế là {actual_pe} — có thể bug đảo ngược công thức cũ "
            f"đã quay lại (kết quả nghi ngờ: {buggy_inverted_pe})."
        )
        assert actual_pe != pytest.approx(buggy_inverted_pe, abs=1e-6)


class TestDividendYieldFallback:
    def test_dividend_yield_uses_dps_not_total_dividends(self):
        """Khi KHÔNG có cột DPS trực tiếp, fallback phải tự tính
        DPS = Tổng cổ tức đã trả / Số cổ phiếu lưu hành — KHÔNG được dùng
        thẳng tổng tiền cổ tức (đơn vị hoàn toàn khác DPS).

        LƯU Ý QUY ƯỚC ĐƠN VỊ: toàn bộ codebase (vd: EPS = net_income/shares
        ở dòng ~1027, KHÔNG nhân hệ số quy đổi nào) giả định các trường tài
        chính thô (net_income, dividends...) đã cùng đơn vị VNĐ gốc với
        Price Close và shares — tức chia trực tiếp là đúng quy ước, không
        cần nhân thêm hệ số tỷ/triệu."""
        shares = 100_000_000  # 100 triệu cổ phiếu
        price = 25_000        # VNĐ/cổ phiếu
        total_dividends_paid = 5_000_000_000.0  # tổng tiền cổ tức, đơn vị VNĐ gốc

        df_price = pd.DataFrame({
            "Ticker": ["AAA"],
            "Price Close": [price],
        })
        df_fin = pd.DataFrame({
            "Ticker": ["AAA"],
            "Date": pd.to_datetime(["2025-12-31"]),
            "Common Shares - Outstanding - Total": [shares],
            "Net Income after Minority Interest": [100.0],
            # Không có cột DPS trực tiếp — chỉ có tổng tiền cổ tức đã trả
            "Dividends Provided/Paid - Common": [total_dividends_paid],
        })

        result = calculate_financial_metrics(df_price, df_fin)

        expected_dps = total_dividends_paid / shares   # = 50 VNĐ/cổ phiếu
        expected_yield = expected_dps / price * 100     # = 0.2%

        actual_yield = result["Dividend Yield (%)"].iloc[0]

        # Bug cũ: dùng thẳng total_dividends_paid (chưa chia cho shares)
        # làm dps, tức Dividend Yield = 5_000_000_000 / 25000 * 100 — một
        # con số phần trăm khổng lồ vô lý.
        buggy_yield = total_dividends_paid / price * 100

        assert actual_yield == pytest.approx(expected_yield, rel=1e-6), (
            f"Dividend Yield phải tính từ DPS = tổng cổ tức/số CP "
            f"({expected_yield:.4f}%), nhưng thực tế là {actual_yield}% "
            f"(nghi ngờ dùng thẳng tổng tiền cổ tức chưa chia: {buggy_yield}%)"
        )
        assert actual_yield < 100, (
            "Dividend Yield vượt quá 100% — dấu hiệu bug dùng nhầm tổng tiền "
            "cổ tức chưa chia cho số cổ phiếu lưu hành."
        )

    def test_dividend_yield_zero_when_no_dividend_data(self):
        """Không có dữ liệu cổ tức nào -> không được crash, và không được
        ra một con số dương giả (như bug cũ dùng nhầm tổng tiền cổ tức).

        LƯU Ý: codebase có chủ đích đổi 0 -> NaN cho các cột tỷ suất
        (P/E, ROE, Dividend Yield...) để phân biệt "thiếu dữ liệu" với
        "giá trị 0 do nhánh fallback mặc định" (xem dòng ~453-459). Vì vậy
        kết quả đúng ở đây là NaN (hiển thị "–" trên UI), không phải số 0
        hay lỗi crash — đây không phải phạm vi bug đang test (unit/giá
        trị Dividend Yield khi có dữ liệu), test này chỉ đảm bảo không
        crash và không trả về một con số dương giả."""
        df_price = pd.DataFrame({"Ticker": ["AAA"], "Price Close": [25000.0]})
        df_fin = pd.DataFrame({
            "Ticker": ["AAA"],
            "Date": pd.to_datetime(["2025-12-31"]),
            "Net Income after Minority Interest": [100.0],
        })
        result = calculate_financial_metrics(df_price, df_fin)
        yield_val = result["Dividend Yield (%)"].iloc[0]
        assert pd.isna(yield_val) or yield_val == 0, (
            f"Không có dữ liệu cổ tức phải cho NaN hoặc 0, không phải "
            f"{yield_val} (nghi ngờ tính sai từ dữ liệu rỗng)."
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
