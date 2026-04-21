"""High-level compare API for one workbook pair."""

from __future__ import annotations

from collections.abc import Callable
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
    on_progress: Callable[[str], None] | None = None,
) -> ComparisonResult:
    """
    Run all applicable comparisons for one **test** vs **original** workbook pair.

    ``wk`` / ``name_feed`` are the **original** (baseline); ``wk_test`` / ``name_test`` are the **test** file.

    ``filetype`` should be ``\"Feed Report\"`` or ``\"Fund Report\"`` (substring match is ok).

    ``on_progress`` receives short English status lines for UIs (e.g. Streamlit ``st.status``).
    """
    def _p(msg: str) -> None:
        if on_progress is not None:
            on_progress(msg)

    result = ComparisonResult(name_test=name_test, name_feed=name_feed)
    _p("Listing worksheets and pairing sheets…")
    get_sheets_table(wk_test, wk, result)
    run_name_smry_table(name_test, name_feed, result)
    sheets = result.paired_sheets

    if "Data Feed Setup" in sheets:
        _p("Comparing **Data Feed Setup**…")
        run_sc_datafeedsetup(wk_test, wk, filetype, result)
    if "Screen Criteria" in sheets:
        _p("Comparing **Screen Criteria**…")
        run_sc_screencriteria(wk_test, wk, result)
    if "Factor List" in sheets:
        _p("Comparing **Factor List**…")
        run_sc_factorlist(wk_test, wk, result)
    if "Subsidiary Mapping" in sheets:
        _p("Comparing **Subsidiary Mapping**…")
        run_sc_subsidiarymapping(wk_test, wk, result)
    if "APL Definition" in sheets:
        _p("Comparing **APL Definition**…")
        run_sc_apl(wk_test, wk, result)

    _p("Building overall change summary…")
    get_overall_change_summary(wk_test, wk, result)
    return result
