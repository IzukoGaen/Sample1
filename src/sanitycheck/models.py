from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd


@dataclass
class ComparisonResult:
    """Outputs from comparing one test workbook against one feed workbook."""

    name_test: str
    name_feed: str
    tbl_filenames: Optional[pd.DataFrame] = None
    tbl_avail_sheets: Optional[pd.DataFrame] = None
    feed_differences: Optional[pd.DataFrame] = None
    tbl_screening_changes: Optional[pd.DataFrame] = None
    tbl_factor_list_merge: Optional[pd.DataFrame] = None
    tbl_smry_val_comparison: Optional[pd.DataFrame] = None
    tbl_first_apl: Optional[pd.DataFrame] = None
    tbl_second_apl_smry: Optional[pd.DataFrame] = None
    tbl_overall_change: Optional[pd.DataFrame] = None
    paired_sheets: set[str] = field(default_factory=set)
    additional_sheets: set[str] = field(default_factory=set)
    removed_sheets: set[str] = field(default_factory=set)


@dataclass
class RunProfile:
    """Timing and memory snapshot for one pair or full batch."""

    label: str
    seconds: float
    rss_bytes_after: Optional[int] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PairingResult:
    """Detected original + test filename pairs (for QC)."""

    name_pairs: pd.DataFrame
    test_names: list[str]
    feed_names: list[str]  # original (baseline) file names, same order as test_names
