# tests/test_scoring_schema.py
"""
Test cho Critical 1 (bản đánh giá backend): calculate_value_score() và
calculate_growth_score() từng bị lệch tên cột — hàm tìm 'PE'/'PB'/'EV_EBITDA'
trong khi dữ liệu thật có tên 'P/E'/'P/B'/'EV/EBITDA', khiến MỌI mã đều
nhận điểm F bất kể dữ liệu tốt hay xấu.

Bộ test này đảm bảo bug không tái diễn: nếu ai đó vô tình đổi lại tên cột
sai trong quant_engine.py, test dưới đây sẽ FAIL ngay lập tức.
"""
import sys
import os
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.backend.quant_engine import calculate_value_score, calculate_growth_score


def _make_good_value_df(n=30, seed=1):
    """Dữ liệu định giá TỐT: P/E, P/B, P/S, EV/EBITDA thấp (rẻ) -> kỳ vọng điểm cao (A/B)."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "Ticker": [f"T{i:02d}" for i in range(n)],
        "P/E": rng.uniform(3, 8, n),          # rẻ
        "P/B": rng.uniform(0.3, 1.0, n),      # rẻ
        "P/S": rng.uniform(0.2, 0.8, n),      # rẻ
        "EV/EBITDA": rng.uniform(2, 5, n),    # rẻ
    })


def _make_bad_value_df(n=30, seed=2):
    """Dữ liệu định giá XẤU: P/E, P/B, P/S, EV/EBITDA rất cao (đắt) -> kỳ vọng điểm thấp (D/F)."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "Ticker": [f"T{i:02d}" for i in range(n)],
        "P/E": rng.uniform(80, 150, n),
        "P/B": rng.uniform(15, 30, n),
        "P/S": rng.uniform(20, 40, n),
        "EV/EBITDA": rng.uniform(60, 100, n),
    })


def _make_mixed_growth_df(n=30, seed=3):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "Ticker": [f"T{i:02d}" for i in range(n)],
        "EPS Growth YoY (%)": rng.uniform(-20, 50, n),
        "Revenue Growth YoY (%)": rng.uniform(-10, 40, n),
        "ROE (%)": rng.uniform(2, 25, n),
        "ROA (%)": rng.uniform(1, 15, n),
    })


class TestValueScoreSchema:
    def test_value_score_column_exists(self):
        df = calculate_value_score(_make_good_value_df())
        assert "Value Score" in df.columns

    def test_value_score_not_uniformly_F_on_good_data(self):
        """Bug cũ: MỌI mã luôn ra F do lệch tên cột. Dữ liệu rẻ phải có ít nhất
        một số mã được A/B/C, không phải 100% F."""
        df = calculate_value_score(_make_good_value_df())
        all_f = (df["Value Score"] == "F").all()
        assert not all_f, (
            "Value Score toàn bộ là F trên dữ liệu định giá TỐT — có thể bug "
            "lệch tên cột (Critical 1) đã quay lại. Kiểm tra P/E, P/B, P/S, "
            "EV/EBITDA có đúng tên cột calculate_financial_metrics() tạo ra không."
        )

    def test_value_score_valid_grades_only(self):
        df = calculate_value_score(_make_good_value_df())
        assert set(df["Value Score"].unique()).issubset({"A", "B", "C", "D", "F"})

    def test_good_valuation_scores_better_than_bad_valuation(self):
        """Dữ liệu rẻ (good) phải có điểm trung bình TỐT HƠN dữ liệu đắt (bad).

        LƯU Ý QUAN TRỌNG: scoring dùng phân vị (quantile) TÍNH TRONG CHÍNH tập
        dữ liệu được truyền vào — nghĩa là gọi hàm riêng lẻ trên 2 tập đồng
        nhất sẽ cho mỗi tập một phân bố A-F riêng, không phản ánh chất lượng
        tuyệt đối. Phải GỘP good+bad vào CÙNG một lần gọi để phân vị có ý
        nghĩa so sánh (giống cách dùng thật: chấm điểm toàn bộ thị trường
        cùng lúc, xếp hạng tương đối)."""
        good = _make_good_value_df(seed=10)
        bad = _make_bad_value_df(seed=11)
        combined = pd.concat([good, bad], ignore_index=True)
        combined["_is_good"] = [True] * len(good) + [False] * len(bad)

        result = calculate_value_score(combined)
        grade_map = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}
        result["_grade_num"] = result["Value Score"].map(grade_map)

        good_avg = result.loc[result["_is_good"], "_grade_num"].mean()
        bad_avg = result.loc[~result["_is_good"], "_grade_num"].mean()
        assert good_avg > bad_avg, (
            f"Trong cùng 1 tập xếp hạng tương đối, dữ liệu rẻ phải có điểm "
            f"trung bình cao hơn đắt, nhưng good_avg={good_avg} <= bad_avg={bad_avg}"
        )

    def test_value_pe_grade_matches_correct_column_by_name(self):
        """Test cho bug phụ: Value_PE_Grade từng bị lấy nhầm theo VỊ TRÍ trong
        list thay vì theo TÊN cột, gây lệch khi thiếu 1 metric."""
        df_full = _make_good_value_df()
        result_full = calculate_value_score(df_full.copy())

        # Xóa cột EV/EBITDA để giả lập trường hợp thiếu 1 metric đầu tiên
        df_missing_first = df_full.drop(columns=["EV/EBITDA"])
        result_missing = calculate_value_score(df_missing_first)

        assert "Value_PE_Grade" in result_missing.columns
        # Value_PE_Grade không được rỗng/toàn NaN khi thiếu EV/EBITDA
        assert result_missing["Value_PE_Grade"].notna().any()


class TestGrowthScoreSchema:
    def test_growth_score_column_exists(self):
        df = calculate_growth_score(_make_mixed_growth_df())
        assert "Growth Score" in df.columns

    def test_growth_score_not_uniformly_F(self):
        df = calculate_growth_score(_make_mixed_growth_df())
        all_f = (df["Growth Score"] == "F").all()
        assert not all_f, (
            "Growth Score toàn bộ là F — có thể bug lệch tên cột (Critical 1) "
            "đã quay lại. Kiểm tra 'EPS Growth YoY (%)', 'Revenue Growth YoY (%)', "
            "'ROE (%)', 'ROA (%)' có đúng tên cột thật không."
        )

    def test_growth_score_valid_grades_only(self):
        df = calculate_growth_score(_make_mixed_growth_df())
        assert set(df["Growth Score"].unique()).issubset({"A", "B", "C", "D", "F"})

    def test_high_growth_scores_better_than_negative_growth(self):
        """LƯU Ý: dùng giá trị ĐỒNG NHẤT (np.full) trong 1 nhóm sẽ không tạo
        được phân vị (mọi dòng y hệt nhau -> mọi dòng cùng 1 hạng), nên phải
        (1) thêm nhiễu nhỏ để có phân bố thật, và (2) gộp good+bad vào cùng
        một lần gọi để phân vị so sánh có ý nghĩa (xem lý do ở test tương ứng
        của Value Score phía trên)."""
        grade_map = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}
        n = 30
        rng = np.random.default_rng(42)
        good = pd.DataFrame({
            "Ticker": [f"G{i:02d}" for i in range(n)],
            "EPS Growth YoY (%)": rng.normal(45, 3, n),
            "Revenue Growth YoY (%)": rng.normal(35, 3, n),
            "ROE (%)": rng.normal(22, 1, n),
            "ROA (%)": rng.normal(12, 1, n),
        })
        bad = pd.DataFrame({
            "Ticker": [f"B{i:02d}" for i in range(n)],
            "EPS Growth YoY (%)": rng.normal(-30, 3, n),
            "Revenue Growth YoY (%)": rng.normal(-20, 3, n),
            "ROE (%)": rng.normal(1, 0.3, n),
            "ROA (%)": rng.normal(0.5, 0.2, n),
        })
        combined = pd.concat([good, bad], ignore_index=True)
        combined["_is_good"] = [True] * n + [False] * n

        result = calculate_growth_score(combined)
        result["_grade_num"] = result["Growth Score"].map(grade_map)
        good_avg = result.loc[result["_is_good"], "_grade_num"].mean()
        bad_avg = result.loc[~result["_is_good"], "_grade_num"].mean()
        assert good_avg > bad_avg


class TestMissingDataHandling:
    def test_missing_all_value_columns_does_not_crash(self):
        """Thiếu dữ liệu không được làm hàm crash, và không mặc định vô lý."""
        df = pd.DataFrame({"Ticker": ["AAA", "BBB"]})
        result = calculate_value_score(df)
        assert "Value Score" in result.columns

    def test_missing_all_growth_columns_does_not_crash(self):
        df = pd.DataFrame({"Ticker": ["AAA", "BBB"]})
        result = calculate_growth_score(df)
        assert "Growth Score" in result.columns


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
