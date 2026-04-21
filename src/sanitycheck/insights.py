"""Structured summaries of a ComparisonResult for APIs and UI."""

from __future__ import annotations

from typing import Any

import pandas as pd

from sanitycheck.models import ComparisonResult


def _nrows(df: pd.DataFrame | None) -> int:
    if df is None or df.empty:
        return 0
    return int(len(df))


def summarize_comparison_result(result: ComparisonResult) -> dict[str, Any]:
    """
    Build a JSON-serializable summary (counts, sheet-level status, file names).

    Intended for Streamlit / HTTP responses; does not include full diff tables.
    """
    overall = result.tbl_overall_change
    overall_records: list[dict[str, Any]] = []
    if overall is not None and not overall.empty:
        overall_records = overall.astype(str).to_dict("records")

    status_col = "Status" if overall is not None and "Status" in overall.columns else None
    n_modified = 0
    n_added = 0
    n_removed = 0
    n_unchanged = 0
    if status_col and overall is not None:
        vc = overall[status_col].value_counts()
        n_modified = int(vc.get("Modified", 0))
        n_added = int(vc.get("Added", 0))
        n_removed = int(vc.get("Removed", 0))
        n_unchanged = int(vc.get("Unchanged", 0))

    counts = {
        "data_feed_setup_rows": _nrows(result.feed_differences),
        "screen_criteria_rows": _nrows(result.tbl_screening_changes),
        "factor_list_rows": _nrows(result.tbl_factor_list_merge),
        "subsidiary_mapping_summary_rows": _nrows(result.tbl_smry_val_comparison),
        "apl_first_rows": _nrows(result.tbl_first_apl),
        "apl_second_summary_rows": _nrows(result.tbl_second_apl_smry),
    }

    headline_parts: list[str] = []
    if n_modified:
        headline_parts.append(f"{n_modified} worksheet(s) with logic or data changes")
    if n_added:
        headline_parts.append(f"{n_added} sheet(s) only in test")
    if n_removed:
        headline_parts.append(f"{n_removed} sheet(s) only in original")
    if not headline_parts:
        headline = "No worksheet-level changes detected in compared sections."
    else:
        headline = "; ".join(headline_parts)

    return {
        "files": {"test": result.name_test, "original": result.name_feed},
        "sheets": {
            "paired": sorted(result.paired_sheets),
            "paired_count": len(result.paired_sheets),
            "only_in_test": sorted(result.additional_sheets),
            "only_in_original": sorted(result.removed_sheets),
        },
        "worksheet_overall": overall_records,
        "worksheet_counts": {
            "modified": n_modified,
            "added": n_added,
            "removed": n_removed,
            "unchanged": n_unchanged,
        },
        "detail_row_counts": counts,
        "headline": headline,
    }
