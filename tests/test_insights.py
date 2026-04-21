"""Tests for comparison summaries."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sanitycheck.insights import summarize_comparison_result
from sanitycheck.models import ComparisonResult


class InsightsTests(unittest.TestCase):
    def test_headline_no_changes(self) -> None:
        r = ComparisonResult(name_test="t.xlsx", name_feed="o.xlsx")
        r.paired_sheets = {"Factor List"}
        r.tbl_overall_change = pd.DataFrame(
            [{"Worksheet": "Factor List", "Status": "Unchanged"}]
        )
        s = summarize_comparison_result(r)
        self.assertIn("No worksheet-level changes", s["headline"])
        self.assertEqual(s["worksheet_counts"]["modified"], 0)

    def test_headline_modified(self) -> None:
        r = ComparisonResult(name_test="t.xlsx", name_feed="o.xlsx")
        r.paired_sheets = {"Data Feed Setup", "Factor List"}
        r.tbl_overall_change = pd.DataFrame(
            [
                {"Worksheet": "Data Feed Setup", "Status": "Modified"},
                {"Worksheet": "Factor List", "Status": "Unchanged"},
            ]
        )
        r.feed_differences = pd.DataFrame([{"a": 1}])
        s = summarize_comparison_result(r)
        self.assertEqual(s["worksheet_counts"]["modified"], 1)
        self.assertEqual(s["detail_row_counts"]["data_feed_setup_rows"], 1)


if __name__ == "__main__":
    unittest.main()
