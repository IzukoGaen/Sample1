"""Regression / debug: duplicate Column Header in Screen Criteria."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sanitycheck.comparisons import run_sc_factorlist, run_sc_screencriteria
from sanitycheck.models import ComparisonResult


def _screen_raw_sheet(data_rows: list[list]) -> pd.DataFrame:
    header = [
        "Category Path",
        "Column Header",
        "Not",
        "(",
        "Operator",
        "Criteria",
        ")",
        "And/Or",
    ]
    return pd.DataFrame([header] + data_rows)


def _factor_raw_sheet(data_rows: list[list]) -> pd.DataFrame:
    header = [
        "Category Path",
        "Column Header",
        "Factor Name",
        "Data Type",
    ]
    return pd.DataFrame([header] + data_rows)


class DuplicateScreenCriteriaTests(unittest.TestCase):
    def test_duplicate_header_same_newvalue_different_old_triggers_td_dedup(self) -> None:
        """Two rows share Column Header + identical FullCriteria on test; feeds differ per row."""
        dup = "DUP_FACTOR_HDR"
        # Same (Not..And/Or) on both test rows -> identical FullCriteria on test side
        same = ["", dup, "", "", "=", "SAME", "", ""]
        test_rows = [same, same]
        # Feeds must produce different Levenshtein distance to "SAME" so Td-min dedup drops a row.
        feed_rows = [
            ["", dup, "", "", "=", "ZZZZZZZZZZ", "", ""],
            ["", dup, "", "", "=", "Z", "", ""],
        ]
        wk_test = {"Screen Criteria": _screen_raw_sheet(test_rows)}
        wk_feed = {"Screen Criteria": _screen_raw_sheet(feed_rows)}
        res = ComparisonResult(name_test="t.xlsx", name_feed="f.xlsx")
        run_sc_screencriteria(wk_test, wk_feed, res)
        assert res.tbl_screening_changes is not None
        # Two paired rows differ from feed -> expect two Modified lines (Td dedup must not collapse).
        self.assertEqual(
            len(res.tbl_screening_changes),
            2,
            "Duplicate Column Header with same New value must still emit one row per sheet row",
        )

    def test_identical_workbooks_duplicate_headers_no_false_positive(self) -> None:
        dup = "DUP2"
        rows = [["", dup, "", "", ">", "1", "", ""], ["", dup, "", "", "<", "2", "", ""]]
        wk_test = {"Screen Criteria": _screen_raw_sheet(rows)}
        wk_feed = {"Screen Criteria": _screen_raw_sheet(rows)}
        res = ComparisonResult(name_test="t.xlsx", name_feed="f.xlsx")
        run_sc_screencriteria(wk_test, wk_feed, res)
        assert res.tbl_screening_changes is not None
        self.assertTrue(
            res.tbl_screening_changes.empty,
            "Identical feeds should produce no screening changes",
        )


class DuplicateFactorListTests(unittest.TestCase):
    def test_factor_list_reordered_rows_same_content_unchanged(self) -> None:
        """Instrument-style exports often reorder rows; QC must not flag Factor List as changed."""
        hdr = "SOME_HDR"
        test_rows = [
            ["", hdr, "FACT_A", "float"],
            ["", hdr, "FACT_B", "float"],
        ]
        feed_rows = [
            ["", hdr, "FACT_B", "float"],
            ["", hdr, "FACT_A", "float"],
        ]
        wk_test = {"Factor List": _factor_raw_sheet(test_rows)}
        wk_feed = {"Factor List": _factor_raw_sheet(feed_rows)}
        res = ComparisonResult(name_test="Instrumental_Test.xlsx", name_feed="Base.xlsx")
        run_sc_factorlist(wk_test, wk_feed, res)
        assert res.tbl_factor_list_merge is not None
        self.assertTrue(
            res.tbl_factor_list_merge.empty,
            "Same factor multiset per Column Header should be Unchanged despite row reorder",
        )

    def test_duplicate_column_header_inflates_merge_rows(self) -> None:
        dup = "REPEATED_HDR"
        rows = [
            ["", dup, "F1", "float"],
            ["", dup, "F2", "float"],
        ]
        wk_test = {"Factor List": _factor_raw_sheet(rows)}
        wk_feed = {"Factor List": _factor_raw_sheet(rows)}
        res = ComparisonResult(name_test="t.xlsx", name_feed="f.xlsx")
        run_sc_factorlist(wk_test, wk_feed, res)
        assert res.tbl_factor_list_merge is not None
        self.assertTrue(
            res.tbl_factor_list_merge.empty,
            "Identical factor lists should not report changes",
        )


if __name__ == "__main__":
    unittest.main()
