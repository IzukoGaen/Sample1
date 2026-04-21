# Feed sanity QC

Compare the **test** workbook against the **original** (baseline) Excel workbook for MSCI-style feed reports and emit a formatted QC `.xlsx`.

**Team deployment (GitHub + Streamlit Cloud):** see [DEPLOY.md](DEPLOY.md).

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

### Deploy (Streamlit Community Cloud + GitHub)

1. Push this repo to GitHub (see **Git: first push** below if `git push` fails).
2. In [Streamlit Community Cloud](https://streamlit.io/cloud), create **New app** → pick the repo and branch.
3. **Main file path:** `streamlit_app.py` (at repo root).
4. Cloud runs `pip install -r requirements.txt` (often via **uv**). The file includes `streamlit`, `setuptools`, `wheel`, and `-e .` to install `sanitycheck`. If the editable step is skipped, [`streamlit_app.py`](streamlit_app.py) adds `src/` to `sys.path` so imports still work.

**`requirements.txt` vs `packages.txt`:** Python packages belong in `requirements.txt`. [`packages.txt`](packages.txt) is only for **Debian/apt** system libraries on Community Cloud (see [Streamlit app dependencies](https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app/app-dependencies)). This repo lists `ca-certificates` as a harmless no-op line so the file is valid if Cloud always parses it; you can clear the file or delete it if you add no apt deps (the file is optional).

**Private repo / non-public app:** use a **private** GitHub repository and set the Streamlit app to **private** + invite viewers by email—see [DEPLOY.md → Private repo and private app](DEPLOY.md#private-repo-and-private-app-non-public). For strict “data never leaves our network” policies, self-host instead of Community Cloud.

On GitHub, optional CI runs unit tests via [`.github/workflows/tests.yml`](.github/workflows/tests.yml) on pushes/PRs to `main` or `master`.

### Git: first push / `src refspec main does not match any`

That message means Git has **no local branch named `main`** (often: no commits yet, or your branch is still `master`).

- If you have not committed: `git add -A`, then `git commit -m "Initial commit"`, then `git push -u origin main`.
- If your branch is `master`: `git branch -M main` then `git push -u origin main`.
- If the remote is new and empty, `git push -u origin main` after the first commit is enough.

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
