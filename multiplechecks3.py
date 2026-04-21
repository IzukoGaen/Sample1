"""Backward-compatible batch entrypoint — delegates to ``sanitycheck``."""

from __future__ import annotations

from pathlib import Path

from sanitycheck.pipeline import run_sanity_checks as _run_sanity_checks


def run_sanity_checks(
    input_dir: str | Path,
    output_dir: str | Path,
    *,
    clear_output: bool = True,
    clear_input: bool = False,
    profile: bool = True,
):
    """
    Pair spreadsheets in ``input_dir``, write QC workbooks under ``output_dir``.

    Returns ``(output_paths, profiles)`` — see ``sanitycheck.pipeline.run_sanity_checks``.

    ``clear_input`` defaults to ``False`` so your source files are not deleted (legacy
    behavior deleted the input folder after a run).
    """
    return _run_sanity_checks(
        Path(input_dir),
        Path(output_dir),
        clear_output=clear_output,
        clear_input=clear_input,
        profile=profile,
    )
