"""Optional FastAPI service wrapping the same compare pipeline."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Annotated

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from sanitycheck.engine import compare_workbook_pair
from sanitycheck.export import export_log_bytes
from sanitycheck.profiling import log_run

app = FastAPI(
    title="Feed sanity QC",
    description="Compare a test Excel workbook against a feed workbook and return a QC .xlsx.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _build_qc_bytes(
    test_bytes: bytes,
    feed_bytes: bytes,
    *,
    name_test: str,
    name_feed: str,
    filetype: str,
) -> bytes:
    wk_test = pd.read_excel(io.BytesIO(test_bytes), sheet_name=None)
    wk = pd.read_excel(io.BytesIO(feed_bytes), sheet_name=None)
    result = compare_workbook_pair(
        wk_test,
        wk,
        name_test=name_test,
        name_feed=name_feed,
        filetype=filetype,
    )
    return export_log_bytes(result)


@app.post("/compare")
async def compare_pair(
    file_test: Annotated[UploadFile, File(description="Test workbook (.xlsx) — file under QC")],
    file_feed: Annotated[UploadFile, File(description="Original baseline workbook (.xlsx)")],
    filetype: Annotated[str, Form()] = "Feed Report",
    profile_raw: Annotated[str, Form(alias="profile")] = "true",
) -> StreamingResponse:
    profile = profile_raw.strip().lower() in ("1", "true", "yes", "on")

    if not file_test.filename or not file_feed.filename:
        raise HTTPException(status_code=400, detail="Both file_test and file_feed are required.")
    for uf in (file_test, file_feed):
        if not uf.filename.lower().endswith(".xlsx"):
            raise HTTPException(
                status_code=400,
                detail=f"Only .xlsx supported via API (got {uf.filename!r}).",
            )

    test_bytes = await file_test.read()
    feed_bytes = await file_feed.read()
    label = f"api:{file_test.filename}|{file_feed.filename}"

    def run() -> bytes:
        return _build_qc_bytes(
            test_bytes,
            feed_bytes,
            name_test=file_test.filename,
            name_feed=file_feed.filename,
            filetype=filetype,
        )

    extra_headers: dict[str, str] = {}
    if profile:
        data, prof = log_run(label, run)
        extra_headers["X-QC-Seconds"] = f"{prof.seconds:.4f}"
        if prof.rss_bytes_after is not None:
            extra_headers["X-QC-RSS-Bytes"] = str(prof.rss_bytes_after)
    else:
        data = run()

    stem = Path(file_test.filename).stem.replace("Test", "") or "QC"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{stem}_Test_QCResult.xlsx"',
            **extra_headers,
        },
    )
