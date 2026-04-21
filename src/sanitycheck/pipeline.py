"""Batch runner: pair files, compare, export QC workbooks."""

from __future__ import annotations

import io
import logging
import re
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

import openpyxl as py
import pandas as pd
from openpyxl.styles import Font, NamedStyle
from openpyxl.utils.dataframe import dataframe_to_rows

from sanitycheck.engine import compare_workbook_pair
from sanitycheck.export import export_log, export_log_bytes
from sanitycheck.insights import summarize_comparison_result
from sanitycheck.models import RunProfile
from sanitycheck.pairing import list_excel_files_in_dir, pair_excel_filenames
from sanitycheck.profiling import log_run

logger = logging.getLogger(__name__)


def _clean_dir(
    dir_path: Path,
    *,
    keep_ipynb: bool = True,
) -> None:
    """Remove regular files in ``dir_path`` (non-recursive). Optionally keep ``.ipynb``."""
    if not dir_path.is_dir():
        return
    for item in dir_path.iterdir():
        if not item.is_file():
            continue
        if keep_ipynb and item.suffix.lower() == ".ipynb":
            continue
        try:
            item.unlink()
            logger.debug("Removed %s", item)
        except OSError as e:
            logger.warning("Could not remove %s: %s", item, e)
    logger.info("Cleaned directory %s", dir_path)


def _infer_filetype_from_names(names: list[str]) -> str:
    for n in names:
        if re.search(r"Feed Report", n, re.I):
            return "Feed Report"
        if re.search(r"Fund Report", n, re.I):
            return "Fund Report"
    raise ValueError(
        "At least one file name must contain 'Feed Report' or 'Fund Report' "
        "(required to choose column sets for Data Feed Setup)."
    )


def _save_pairing_workbook(name_pairs: pd.DataFrame, path: Path) -> None:
    wb_list = py.Workbook()
    dsp = NamedStyle(name="dsp")
    wb_list.add_named_style(dsp)
    ws_list = wb_list.active
    for r in dataframe_to_rows(name_pairs, index=False, header=True):
        ws_list.append(r)
    ft_header = Font(bold=True, color="000000")
    for cell in ws_list["A1:B1"][0]:
        cell.font = ft_header
    ws_list.column_dimensions["A"].width = 50
    ws_list.column_dimensions["B"].width = 50
    wb_list.save(path)


def run_sanity_checks(
    input_dir: str | Path,
    output_dir: str | Path,
    *,
    clear_output: bool = True,
    clear_input: bool = False,
    profile: bool = True,
) -> tuple[list[str], list[RunProfile]]:
    """
    Pair Excel files in ``input_dir``, run comparisons, write QC workbooks to ``output_dir``.

    Parameters
    ----------
    clear_output :
        If True, delete existing files in ``output_dir`` before writing (except ``.ipynb``).
    clear_input :
        If True, delete processed input files after a successful run (legacy behavior).
        Default False — inputs are preserved.
    profile :
        If True, log elapsed time and RSS after each pair (requires ``psutil`` for RSS).
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if clear_output:
        _clean_dir(output_path)

    names = list_excel_files_in_dir(input_path)
    pairing = pair_excel_filenames(names)
    if pairing.name_pairs.empty:
        logger.warning("No .xlsx/.csv files found in %s", input_path)
        return [], []

    list_path = output_path / "List of paired sheets.xlsx"
    _save_pairing_workbook(pairing.name_pairs, list_path)

    filetype = _infer_filetype_from_names(pairing.test_names + pairing.feed_names)
    profiles: list[RunProfile] = []
    output_paths: list[str] = []

    for name_test, name_feed in zip(pairing.test_names, pairing.feed_names):
        label = f"pair:{name_test}|{name_feed}"

        def run_one(
            name_test: str = name_test,
            name_feed: str = name_feed,
        ) -> str:
            wk_test = pd.read_excel(input_path / name_test, sheet_name=None)
            wk = pd.read_excel(input_path / name_feed, sheet_name=None)
            result = compare_workbook_pair(
                wk_test,
                wk,
                name_test=name_test,
                name_feed=name_feed,
                filetype=filetype,
            )
            stem = name_test.split(" ")[0].replace("Test", "")
            log_path = output_path / f"{stem}_Test QCResult.xlsx"
            export_log(result, str(log_path))
            return str(log_path)

        if profile:
            path, prof = log_run(label, run_one)
            profiles.append(prof)
        else:
            path = run_one()
        output_paths.append(path)
        logger.info("%s — QC written", name_test)

    if clear_input:
        _clean_dir(input_path)

    return output_paths, profiles


def compare_uploaded_pair(
    *,
    original_bytes: bytes,
    test_bytes: bytes,
    original_filename: str = "original.xlsx",
    test_filename: str = "test.xlsx",
    filetype: str = "Feed Report",
    profile: bool = True,
    on_progress: Callable[[str], None] | None = None,
) -> tuple[bytes, list[RunProfile], dict]:
    """
    Compare one **test** workbook (bytes) to one **original** (bytes); return QC ``.xlsx`` bytes,
    profiling rows, and a JSON-serializable **insights** dict (see ``summarize_comparison_result``).

    Does not use filename pairing — roles are explicit. ``filetype`` must be
    ``\"Feed Report\"`` or ``\"Fund Report\"`` for *Data Feed Setup* column logic.

    ``on_progress`` is invoked with short status strings during load, compare, and export.
    """
    if on_progress is not None:
        on_progress("Reading **original** workbook from upload…")
    wk_orig = pd.read_excel(io.BytesIO(original_bytes), sheet_name=None)
    if on_progress is not None:
        on_progress("Reading **test** workbook from upload…")
    wk_test = pd.read_excel(io.BytesIO(test_bytes), sheet_name=None)

    def _run() -> tuple[bytes, dict]:
        res = compare_workbook_pair(
            wk_test,
            wk_orig,
            name_test=test_filename,
            name_feed=original_filename,
            filetype=filetype,
            on_progress=on_progress,
        )
        if on_progress is not None:
            on_progress("Writing QC Excel to memory…")
        blob = export_log_bytes(res)
        return blob, summarize_comparison_result(res)

    if profile:
        (data, summary), prof = log_run("compare_uploaded_pair", _run)
        return data, [prof], summary
    data, summary = _run()
    return data, [], summary


def run_sanity_checks_from_uploads(
    files: list[tuple[str, BinaryIO]],
    *,
    profile: bool = True,
) -> tuple[bytes, list[str], list[RunProfile]]:
    """
    Run QC on in-memory uploads; return zip bytes, output paths, and RunProfile rows.

    ``files`` is a list of ``(filename, fileobj)`` opened in binary mode.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        for name, fh in files:
            safe = Path(name).name
            dest = tdir / safe
            data = fh.read() if hasattr(fh, "read") else fh
            if isinstance(data, bytes):
                dest.write_bytes(data)
            else:
                dest.write_bytes(bytes(data))

        out_dir = tdir / "out"
        out_dir.mkdir()
        paths, profs = run_sanity_checks(
            tdir,
            out_dir,
            clear_output=False,
            clear_input=False,
            profile=profile,
        )
        prof_lines = [
            f"{p.label}: {p.seconds:.2f}s"
            + (
                f", RSS_after={p.rss_bytes_after / 1024 / 1024:.1f} MB"
                if p.rss_bytes_after
                else ""
            )
            for p in profs
        ]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in out_dir.iterdir():
                if p.is_file():
                    zf.write(p, arcname=p.name)
        buf.seek(0)
        return buf.read(), paths, profs


def extract_zip_upload(zip_bytes: bytes, dest: Path) -> list[str]:
    """Extract a zip into ``dest`` and return list of extracted file names (top-level only)."""
    dest.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            name = Path(member.filename).name
            if not name.lower().endswith((".xlsx", ".csv")):
                continue
            target = dest / name
            target.write_bytes(zf.read(member))
            names.append(name)
    return names
