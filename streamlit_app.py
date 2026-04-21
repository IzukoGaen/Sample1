"""
Local UI: upload **Original** + **Test**, run QC, download one **.xlsx** (no ZIP).

Run from project root (after ``pip install -e ".[ui]"``):

    py -m streamlit run streamlit_app.py
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from sanitycheck.pipeline import compare_uploaded_pair


def _download_filename(test_filename: str) -> str:
    stem = Path(test_filename).stem or "QC"
    safe = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in stem).strip() or "QC"
    return f"{safe[:80]}_QCResult.xlsx"


st.set_page_config(page_title="Feed sanity QC", layout="wide")
st.title("Feed sanity QC")
st.caption(
    "Upload the **original** (baseline) workbook and the **test** workbook. "
    "Names do not matter — each file has its own box. Choose the report type, run QC, then download **one** Excel result."
)

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
    st.header("Report type")
    filetype = st.selectbox(
        "Used for *Data Feed Setup* columns",
        options=["Feed Report", "Fund Report"],
        index=0,
        help="Independent of file names — pick which report shape your workbooks use.",
    )
    profile = st.checkbox("Show timing / memory row", value=True)

run_disabled = original is None or test is None
if st.button("Run QC", type="primary", disabled=run_disabled):
    orig_name = original.name or "original.xlsx"
    test_name = test.name or "test.xlsx"
    orig_bytes = original.getvalue()
    test_bytes = test.getvalue()

    with st.spinner("Running comparison…"):
        try:
            qc_bytes, profs = compare_uploaded_pair(
                original_bytes=orig_bytes,
                test_bytes=test_bytes,
                original_filename=orig_name,
                test_filename=test_name,
                filetype=filetype,
                profile=profile,
            )
        except Exception as e:
            st.exception(e)
        else:
            st.success("QC workbook ready — download below.")
            if profs:
                p = profs[0]
                st.caption(
                    f"Elapsed **{p.seconds:.2f}s**"
                    + (
                        f", RSS **{p.rss_bytes_after / 1024 / 1024:.1f} MB**"
                        if p.rss_bytes_after
                        else ""
                    )
                )
            st.download_button(
                label="Download QC result (.xlsx)",
                data=qc_bytes,
                file_name=_download_filename(test_name),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )

with st.expander("Batch mode (optional)"):
    st.markdown(
        "To compare **many** pairs from filenames in one folder, use Python: "
        "`from sanitycheck.pipeline import run_sanity_checks` with `Input files/` and `Output files/`. "
        "That flow still writes **per-pair** QC files and a pairing list (folder output, not this page)."
    )
