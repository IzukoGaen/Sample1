"""
Local UI: upload **Original** + **Test**, run QC, download one **.xlsx** (no ZIP).

Run from project root (after ``pip install -e ".[ui]"``):

    py -m streamlit run streamlit_app.py
"""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path

# Streamlit Community Cloud may install deps via ``uv`` without resolving ``-e .``;
# ensure ``src/`` is on sys.path so ``import sanitycheck`` works from repo root.
_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if _SRC.is_dir():
    _src_str = str(_SRC)
    if _src_str not in sys.path:
        sys.path.insert(0, _src_str)

import streamlit as st

import sanitycheck.pipeline as _pipeline_mod

# Reload so Cloud picks up the repo copy of ``pipeline.py`` (not a stale bytecode / site-packages shadow).
importlib.reload(_pipeline_mod)
compare_uploaded_pair = _pipeline_mod.compare_uploaded_pair


def _run_compare_with_optional_progress(
    *,
    original_bytes: bytes,
    test_bytes: bytes,
    original_filename: str,
    test_filename: str,
    filetype: str,
    profile: bool,
    on_progress,
) -> tuple[bytes, list, dict]:
    """Call ``compare_uploaded_pair``; tolerate older deployments (no ``on_progress`` kw only)."""
    sig = inspect.signature(compare_uploaded_pair)
    kw: dict = dict(
        original_bytes=original_bytes,
        test_bytes=test_bytes,
        original_filename=original_filename,
        test_filename=test_filename,
        filetype=filetype,
        profile=profile,
    )
    if "on_progress" in sig.parameters:
        kw["on_progress"] = on_progress
    raw = compare_uploaded_pair(**kw)
    if len(raw) != 3:
        raise RuntimeError(
            "compare_uploaded_pair must return (qc_bytes, profiles, summary). "
            "Push the latest `src/sanitycheck/pipeline.py` to GitHub, then Streamlit **Manage app → Reboot**."
        )
    data, profs, summary = raw
    return data, profs, summary


def _download_filename(test_filename: str) -> str:
    stem = Path(test_filename).stem or "QC"
    safe = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in stem).strip() or "QC"
    return f"{safe[:80]}_QCResult.xlsx"


def _render_insights(summary: dict, profs: list) -> None:
    st.subheader("Insights")
    st.info(summary.get("headline", ""))

    wc = summary.get("worksheet_counts", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Worksheets modified", wc.get("modified", 0))
    c2.metric("Only in test", wc.get("added", 0))
    c3.metric("Only in original", wc.get("removed", 0))
    c4.metric("Unchanged (tracked)", wc.get("unchanged", 0))

    dc = summary.get("detail_row_counts", {})
    with st.expander("Detail row counts (QC tables)", expanded=False):
        st.caption("Rows written to the result workbook for each section (0 if not compared or empty).")
        st.dataframe(
            [
                {"Section": k.replace("_", " ").title(), "Rows": v}
                for k, v in sorted(dc.items(), key=lambda x: x[0])
            ],
            use_container_width=True,
            hide_index=True,
        )

    wo = summary.get("worksheet_overall", [])
    if wo:
        with st.expander("Worksheet status (overall)", expanded=False):
            st.dataframe(wo, use_container_width=True, hide_index=True)

    sh = summary.get("sheets", {})
    if sh.get("only_in_test") or sh.get("only_in_original"):
        with st.expander("Sheet name mismatches", expanded=False):
            st.write("**Only in test file:**", ", ".join(sh.get("only_in_test", [])) or "—")
            st.write("**Only in original file:**", ", ".join(sh.get("only_in_original", [])) or "—")

    if profs:
        p = profs[0]
        st.caption(
            f"Last run: **{p.seconds:.2f}s**"
            + (
                f", RSS **{p.rss_bytes_after / 1024 / 1024:.1f} MB**"
                if p.rss_bytes_after
                else ""
            )
        )

    with st.expander("Raw summary (JSON)", expanded=False):
        st.json(summary)


st.set_page_config(page_title="Feed sanity QC", layout="wide")
st.title("Feed sanity QC")
st.caption(
    "Upload the **original** (baseline) workbook and the **test** workbook. "
    "Names do not matter — each file has its own box. Choose the report type, run QC, then download **one** Excel result."
)

if "last_qc" not in st.session_state:
    st.session_state.last_qc = None
if "qc_just_finished" not in st.session_state:
    st.session_state.qc_just_finished = False

col_o, col_t = st.columns(2)
with col_o:
    original = st.file_uploader(
        "Original (baseline)",
        type=["xlsx"],
        help="The reference workbook you compare against.",
    )
with col_t:
    test = st.file_uploader(
        "Test (under QC)",
        type=["xlsx"],
        help="The workbook you want to validate.",
    )

with st.sidebar:
    if getattr(_pipeline_mod, "UPLOAD_QC_API_VERSION", 0) < 2:
        st.error(
            "QC backend is outdated (missing `UPLOAD_QC_API_VERSION`). "
            "Push `main` and reboot the app on Streamlit Cloud."
        )
    st.header("Report type")
    filetype = st.selectbox(
        "Used for *Data Feed Setup* columns",
        options=["Feed Report", "Fund Report"],
        index=0,
        help="Independent of file names — pick which report shape your workbooks use.",
    )
    profile = st.checkbox("Show timing / memory row", value=True)
    if st.button("Clear last QC result", help="Remove cached download and insights from this browser session."):
        st.session_state.last_qc = None
        st.session_state.qc_just_finished = False
        st.rerun()

run_disabled = original is None or test is None
if st.button("Run QC", type="primary", disabled=run_disabled):
    orig_name = original.name or "original.xlsx"
    test_name = test.name or "test.xlsx"
    orig_bytes = original.getvalue()
    test_bytes = test.getvalue()

    with st.status("Running QC…", expanded=True) as status:

        def _progress(msg: str) -> None:
            try:
                status.write(str(msg))
            except Exception:
                pass

        try:
            qc_bytes, profs, summary = _run_compare_with_optional_progress(
                original_bytes=orig_bytes,
                test_bytes=test_bytes,
                original_filename=orig_name,
                test_filename=test_name,
                filetype=filetype,
                profile=profile,
                on_progress=_progress,
            )
        except Exception:
            try:
                status.update(label="QC failed", state="error")
            except Exception:
                pass
            raise
        else:
            try:
                status.update(label="QC finished", state="complete", expanded=False)
            except TypeError:
                status.update(label="QC finished", state="complete")

    st.session_state.last_qc = {
        "bytes": qc_bytes,
        "profs": profs,
        "summary": summary,
        "test_name": test_name,
    }
    st.session_state.qc_just_finished = True
    st.rerun()

if st.session_state.last_qc is not None:
    if st.session_state.qc_just_finished:
        st.success("QC workbook ready — download below or review insights.")
        st.session_state.qc_just_finished = False
    cache = st.session_state.last_qc
    qc_bytes = cache["bytes"]
    profs = cache["profs"]
    summary = cache["summary"]
    test_name = cache["test_name"]

    st.download_button(
        label="Download QC result (.xlsx)",
        data=qc_bytes,
        file_name=_download_filename(test_name),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        key="dl_qc_xlsx",
    )

    _render_insights(summary, profs)

with st.expander("Batch mode (optional)"):
    st.markdown(
        "To compare **many** pairs from filenames in one folder, use Python: "
        "`from sanitycheck.pipeline import run_sanity_checks` with `Input files/` and `Output files/`. "
        "That flow still writes **per-pair** QC files and a pairing list (folder output, not this page)."
    )
