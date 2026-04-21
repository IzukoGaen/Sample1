"""High-level compare API for one workbook pair."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sanitycheck.comparisons import (
    get_overall_change_summary,
    get_sheets_table,
    run_name_smry_table,
    run_sc_apl,
    run_sc_datafeedsetup,
    run_sc_factorlist,
    run_sc_screencriteria,
    run_sc_subsidiarymapping,
)
from sanitycheck.models import ComparisonResult

if TYPE_CHECKING:
    import pandas as pd


def compare_workbook_pair(
    wk_test: dict[str, pd.DataFrame],
    wk: dict[str, pd.DataFrame],
    *,
    name_test: str,
    name_feed: str,
    filetype: str,
) -> ComparisonResult:
    """
    Run all applicable comparisons for one **test** vs **original** workbook pair.

    ``wk`` / ``name_feed`` are the **original** (baseline); ``wk_test`` / ``name_test`` are the **test** file.

    ``filetype`` should be ``\"Feed Report\"`` or ``\"Fund Report\"`` (substring match is ok).
    """
    result = ComparisonResult(name_test=name_test, name_feed=name_feed)
    get_sheets_table(wk_test, wk, result)
    run_name_smry_table(name_test, name_feed, result)
    sheets = result.paired_sheets

    if "Data Feed Setup" in sheets:
        run_sc_datafeedsetup(wk_test, wk, filetype, result)
    if "Screen Criteria" in sheets:
        run_sc_screencriteria(wk_test, wk, result)
    if "Factor List" in sheets:
        run_sc_factorlist(wk_test, wk, result)
    if "Subsidiary Mapping" in sheets:
        run_sc_subsidiarymapping(wk_test, wk, result)
    if "APL Definition" in sheets:
        run_sc_apl(wk_test, wk, result)

    get_overall_change_summary(wk_test, wk, result)
    return result
