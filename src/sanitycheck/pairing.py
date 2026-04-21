"""Pair test/feed Excel filenames using Levenshtein distance (legacy algorithm)."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import textdistance as td

from sanitycheck.models import PairingResult

logger = logging.getLogger(__name__)


def is_tool_output_filename(name: str) -> bool:
    """
    Return True if ``name`` looks like an output from this QC tool (not an input workbook).

    These files are skipped when pairing so you can upload **original + test + prior QC**
    without the result workbook being matched as a third input.
    """
    base = Path(name).name.lower()
    markers = (
        "test qcresult",  # batch output: ``*_Test QCResult.xlsx``
        "test_qcresult",  # API download variant
        "list of paired sheets",  # pairing list from batch mode
    )
    return any(m in base for m in markers)


def pair_excel_filenames(
    filenames: list[str],
    *,
    exclude_tool_outputs: bool = True,
) -> PairingResult:
    """
    Given a list of file names (not full paths), return best **original / test** pairs.

    The **original** file is the baseline (legacy code called this "feed"); the **test** file
    is what you are validating. Pairing uses the legacy rule: self-merge on names,
    min non-zero Levenshtein distance per name,
    tie-break with lower ASCII sum of characters in the ``Name`` column.

    When ``exclude_tool_outputs`` is True (default), names matching :func:`is_tool_output_filename`
    are removed before pairing.
    """
    if exclude_tool_outputs:
        skipped = [f for f in filenames if is_tool_output_filename(f)]
        if skipped:
            logger.info("Skipping tool output files (not used as compare inputs): %s", skipped)
        filenames = [f for f in filenames if not is_tool_output_filename(f)]

    if not filenames:
        return PairingResult(
            name_pairs=pd.DataFrame(columns=["Original_FileName", "Test_FileName"]),
            test_names=[],
            feed_names=[],
        )

    s = pd.Series(filenames)
    clean_files = s[s.str.contains(r"\.xlsx$|\.csv$", case=False, regex=True)]
    if clean_files.empty:
        return PairingResult(
            name_pairs=pd.DataFrame(columns=["Original_FileName", "Test_FileName"]),
            test_names=[],
            feed_names=[],
        )

    ints = list(
        map(
            lambda x: sum(map(ord, x)),
            clean_files.apply(lambda x: list(x)),
        )
    )
    feeds = clean_files.to_frame("Name")
    feeds["chrVal"] = ints
    feeds.index = len(feeds.index.values) * [1]
    name_distance = (
        feeds.merge(feeds, left_index=True, right_index=True, how="left", suffixes=("", "2"))
        .reset_index(drop=True)
    )
    name_distance["LevDistance"] = list(
        map(
            lambda x: td.levenshtein(x[0], x[1]),
            zip(name_distance["Name"], name_distance["Name2"]),
        )
    )
    mins = name_distance[name_distance["LevDistance"] != 0].groupby("Name")["LevDistance"].min()
    mins.name = "MinLev"
    name_pairs = (
        name_distance.merge(mins, left_on="Name", right_index=True)
        .where(lambda x: x["LevDistance"] == x["MinLev"])
        .where(lambda x: x["chrVal"] < x["chrVal2"])
        .dropna()
        .reset_index(drop=True)
    )
    feed_list = name_pairs["Name"].to_list()
    test_list = name_pairs["Name2"].to_list()
    name_pairs_exp = name_pairs.rename(
        columns={"Name": "Original_FileName", "Name2": "Test_FileName"}
    )[["Original_FileName", "Test_FileName"]]
    return PairingResult(
        name_pairs=name_pairs_exp,
        test_names=test_list,
        feed_names=feed_list,
    )


def list_excel_files_in_dir(input_dir: str | Path) -> list[str]:
    """Return base names of .xlsx/.csv files in a directory."""
    p = Path(input_dir)
    if not p.is_dir():
        logger.warning("Not a directory: %s", p)
        return []
    out: list[str] = []
    for child in p.iterdir():
        if child.is_file() and child.suffix.lower() in (".xlsx", ".csv"):
            out.append(child.name)
    return sorted(out)
