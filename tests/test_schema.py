# tests/test_schema.py
"""
Test cho Schema Registry (src/schema.py) — audit muc 1.

Muc dich:
1. Dam bao moi COL_* la string khong rong, khong co khoang trang thua.
2. Dam bao data_loader.FILTER_COL_MAP THUC SU duoc derive tu schema.py
   (cung object / cung gia tri), khong phai 2 ban sao doc lap co the lech nhau.
3. Neu ai do sau nay vo tinh dinh nghia lai FILTER_COL_MAP doc lap trong
   data_loader.py (quay lai hien trang truoc audit), test nay se FAIL ngay.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import src.schema as schema


def _all_col_constants():
    return {
        name: value
        for name, value in vars(schema).items()
        if name.startswith("COL_") and isinstance(value, str)
    }


def test_all_column_constants_are_nonempty_strings():
    cols = _all_col_constants()
    assert len(cols) >= 40, "Schema Registry co qua it hang so COL_* — co the bi xoa nham"
    for name, value in cols.items():
        assert isinstance(value, str) and value.strip() != "", f"{name} rong hoac khong phai string"
        assert value == value.strip(), f"{name}='{value}' co khoang trang thua o dau/cuoi"


def test_no_duplicate_column_values_by_accident():
    """Hai hang so COL_* khac ten nhung tro toi CUNG MOT chuoi cot la dau hieu
    copy-paste nham (vd COL_ROE va COL_ROA cung tro ve 'ROE (%)')."""
    cols = _all_col_constants()
    seen = {}
    dup_errors = []
    for name, value in cols.items():
        if value in seen:
            dup_errors.append((name, seen[value], value))
        seen[value] = name
    assert not dup_errors, f"Cac hang so COL_* trung gia tri (co the la loi copy-paste): {dup_errors}"


def test_filter_to_schema_col_uses_registry_values():
    """Moi gia tri trong FILTER_TO_SCHEMA_COL phai la mot trong cac COL_* da khai bao,
    khong duoc la chuoi hardcode roi (chong tai phat sinh 2 nguon su that)."""
    cols = set(_all_col_constants().values())
    for filter_id, col_name in schema.FILTER_TO_SCHEMA_COL.items():
        assert col_name in cols, (
            f"'{filter_id}' -> '{col_name}' khong khop bat ky hang so COL_* nao "
            f"trong Schema Registry — co the ai do da hardcode lai chuoi thay vi dung COL_*"
        )


def test_data_loader_filter_col_map_is_the_registry_not_a_copy():
    """data_loader.FILTER_COL_MAP phai LA (identity) hoac bang gia tri voi
    schema.FILTER_TO_SCHEMA_COL — dam bao khong co ban sao doc lap nao con sot lai."""
    from src.backend import data_loader

    assert data_loader.FILTER_COL_MAP == schema.FILTER_TO_SCHEMA_COL
    # Kiem tra vai gia tri quan trong khong bi go sai khi migrate
    assert data_loader.FILTER_COL_MAP["filter-pe"] == schema.COL_PE == "P/E"
    assert data_loader.FILTER_COL_MAP["filter-roe"] == schema.COL_ROE == "ROE (%)"
    assert data_loader.FILTER_COL_MAP["filter-ev-ebitda"] == schema.COL_EV_EBITDA == "EV/EBITDA"
