"""Unit tests for watchfolder concurrency bucket behavior."""

import asyncio
from pathlib import Path

from src.api.models import EncodingRequest, WatchfolderContext
from src.api.queue import JobQueue


def _new_queue(tmp_path: Path) -> JobQueue:
    queue = JobQueue(
        max_concurrent=4,
        db_path=tmp_path / "jobs-test.db",
        root_media=tmp_path,
    )
    queue._init_db()
    return queue


def test_watchfolder_concurrency_bucket_is_used_for_source_id(tmp_path: Path):
    queue = _new_queue(tmp_path)

    source_a = tmp_path / "a.mkv"
    source_b = tmp_path / "b.mkv"
    source_a.write_text("a")
    source_b.write_text("b")

    dest = tmp_path / "dest"
    bucket = "watchfolder:/media/source"

    request_a = EncodingRequest(
        profiles=["x265-balanced"],
        source=str(source_a),
        output_mode="destination",
        destination=str(dest),
        max_concurrent_jobs=2,
        watchfolder_context=WatchfolderContext(
            file_hash="hash-a",
            concurrency_bucket=bucket,
            keep_processed_files=True,
            disable_temp_copy=False,
        ),
    )
    request_b = EncodingRequest(
        profiles=["x265-balanced"],
        source=str(source_b),
        output_mode="destination",
        destination=str(dest),
        max_concurrent_jobs=2,
        watchfolder_context=WatchfolderContext(
            file_hash="hash-b",
            concurrency_bucket=bucket,
            keep_processed_files=True,
            disable_temp_copy=False,
        ),
    )

    asyncio.run(queue._submit_files([source_a], request_a))
    asyncio.run(queue._submit_files([source_b], request_b))

    rows = queue._conn.execute(
        "SELECT source_id FROM jobs ORDER BY created_at ASC"
    ).fetchall()
    source_ids = [row["source_id"] for row in rows]

    assert source_ids == [bucket, bucket]
    assert queue._source_limits[bucket] == 2


def test_watchfolder_file_hash_fallback_when_bucket_missing(tmp_path: Path):
    queue = _new_queue(tmp_path)

    source = tmp_path / "single.mkv"
    source.write_text("video")

    request = EncodingRequest(
        profiles=["x265-balanced"],
        source=str(source),
        output_mode="destination",
        destination=str(tmp_path / "dest"),
        max_concurrent_jobs=1,
        watchfolder_context=WatchfolderContext(
            file_hash="hash-only",
            keep_processed_files=True,
            disable_temp_copy=False,
        ),
    )

    asyncio.run(queue._submit_files([source], request))

    row = queue._conn.execute("SELECT source_id FROM jobs LIMIT 1").fetchone()
    assert row["source_id"] == "hash-only"
    assert queue._source_limits["hash-only"] == 1
