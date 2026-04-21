# Feed sanity QC

Compare the **test** workbook against the **original** (baseline) Excel workbook for MSCI-style feed reports and emit a formatted QC `.xlsx`.

When several `.xlsx` files are in the same folder (or upload), files whose names look like **outputs from this tool** (`Test QCResult`, `Test_QCResult`, or `List of paired sheets`) are **skipped** for pairing so you can keep a prior QC file next to **original + test** without it being treated as a third input.

## Install

From this directory:

```bash
python -m pip install -e .
```

With the Streamlit UI:

```bash
python -m pip install -e ".[ui]"
```

With the FastAPI service:

```bash
python -m pip install -e ".[api]"
```

## Run (folders, same as before)

```python
from pathlib import Path
from sanitycheck.pipeline import run_sanity_checks

outputs, profiles = run_sanity_checks(
    Path("Input files"),
    Path("Output files"),
    clear_output=True,
    clear_input=False,  # set True only if you want legacy “delete inputs” behavior
    profile=True,
)
```

## Run (Streamlit)

Two uploads — **Original** and **Test** — no filename pairing. You pick **Feed Report** vs **Fund Report** in the sidebar. Download is a **single `.xlsx`**, not a zip.

```bash
py -m streamlit run streamlit_app.py
```

## Run (FastAPI)

```bash
uvicorn sanitycheck.api:app --reload --host 127.0.0.1 --port 8000
```

`POST /compare` with multipart form fields: `file_test`, `file_feed`, optional `filetype` (default `Feed Report`), optional `profile` (`true` / `false`, default `true`). Response body is the QC `.xlsx`.

## Layout

- `src/sanitycheck/` — package (`comparisons`, `export`, `engine`, `pipeline`, `api`, …)
- `multiplechecks3.py` — thin wrapper around `sanitycheck.pipeline.run_sanity_checks`
- `streamlit_app.py` — local web UI

Legacy `sanityscript6.py` is removed; import `sanitycheck` instead.
