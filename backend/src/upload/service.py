import fnmatch
import json
import os
import sqlite3
import subprocess
import sys
import zipfile
from datetime import UTC, datetime

from src.database import get_connection

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
RAW_DIR = os.path.join(BASE_DIR, "data", "spotifyRaw")
PROCESSORS_DIR = os.path.join(BASE_DIR, "processors")

PROCESSOR_SCRIPTS = [
    "StreamingHistoryProcessor.py",
]

ALLOWED_PATTERNS = [
    "Streaming_History_Audio*.json",
    "StreamingHistory_music_*.json",
]
MAX_ZIP_SIZE = 100 * 1024 * 1024  # compressed, on disk
MAX_MEMBER_SIZE = 200 * 1024 * 1024  # per accepted file, uncompressed
MAX_ENTRIES = 20_000
PROCESSOR_TIMEOUT = 1800  # seconds, generous for a large streaming-history export


class InvalidZip(ValueError):
    pass


def validate_and_list_matches(zip_path: str) -> tuple[zipfile.ZipFile, list[tuple]]:
    """Reject oversized/malformed/suspicious zips before extracting anything.
    Only entries whose basename matches an expected Spotify export filename
    are ever read — everything else in the zip is ignored outright, which
    also means we never even decompress unrelated/oversized junk."""
    if os.path.getsize(zip_path) > MAX_ZIP_SIZE:
        raise InvalidZip(f"Zip file too large (max {MAX_ZIP_SIZE // (1024 * 1024)}MB)")

    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as e:
        raise InvalidZip("Not a valid zip file") from e

    infos = zf.infolist()
    if len(infos) > MAX_ENTRIES:
        zf.close()
        raise InvalidZip("Zip has too many entries")

    matches = []
    for info in infos:
        if info.is_dir():
            continue
        basename = os.path.basename(info.filename)
        if not basename:
            continue
        if any(fnmatch.fnmatch(basename, p) for p in ALLOWED_PATTERNS):
            if info.file_size > MAX_MEMBER_SIZE:
                zf.close()
                raise InvalidZip(f"{basename} is larger than expected for a Spotify export")
            matches.append((info, basename))

    if not matches:
        zf.close()
        raise InvalidZip("No recognizable Spotify export files found in the zip")

    return zf, matches


def extract_matches(zf: zipfile.ZipFile, matches: list[tuple], dest_dir: str) -> list[str]:
    """Extraction targets are built purely from the sanitized basename, never
    the zip's internal path — zip-slip is structurally impossible here."""
    os.makedirs(dest_dir, exist_ok=True)
    extracted = []
    for info, basename in matches:
        dest_path = os.path.join(dest_dir, basename)
        with zf.open(info) as src, open(dest_path, "wb") as dst:
            dst.write(src.read())
        extracted.append(basename)
    zf.close()
    return extracted


def create_job(con: sqlite3.Connection) -> int:
    now = datetime.now(UTC).isoformat()
    cur = con.execute(
        "INSERT INTO import_jobs (status, message, created_at, updated_at) VALUES (?, ?, ?, ?)",
        ("queued", None, now, now),
    )
    con.commit()
    return cur.lastrowid


def get_job(con: sqlite3.Connection, job_id: int) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM import_jobs WHERE id = ?", (job_id,)).fetchone()


def _update_job(con: sqlite3.Connection, job_id: int, **fields) -> None:
    fields["updated_at"] = datetime.now(UTC).isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    con.execute(f"UPDATE import_jobs SET {set_clause} WHERE id = ?", (*fields.values(), job_id))
    con.commit()


def _parse_summary(stdout: str) -> dict:
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {}


def process_upload(job_id: int, zip_path: str) -> None:
    """Runs as a FastAPI BackgroundTask, so it opens its own DB connection
    rather than relying on the (already-closed-by-then) request-scoped one."""
    con = get_connection()
    try:
        _update_job(con, job_id, status="extracting")
        zf, matches = validate_and_list_matches(zip_path)
        extract_matches(zf, matches, RAW_DIR)

        _update_job(con, job_id, status="processing")
        counts: dict = {}
        for script in PROCESSOR_SCRIPTS:
            result = subprocess.run(
                [sys.executable, os.path.join(PROCESSORS_DIR, script)],
                capture_output=True,
                text=True,
                cwd=BASE_DIR,
                timeout=PROCESSOR_TIMEOUT,
            )
            if result.returncode != 0:
                raise RuntimeError(f"{script} failed: {result.stderr[-2000:]}")
            counts.update(_parse_summary(result.stdout))

        _update_job(
            con,
            job_id,
            status="done",
            message="Import complete",
            new_history_rows=counts.get("new_history_rows", 0),
            new_library_tracks=counts.get("new_library_tracks", 0),
            new_library_albums=counts.get("new_library_albums", 0),
            new_library_artists=counts.get("new_library_artists", 0),
            new_playlists=counts.get("new_playlists", 0),
            new_playlist_tracks=counts.get("new_playlist_tracks", 0),
        )
    except InvalidZip as e:
        _update_job(con, job_id, status="error", message=str(e))
    except Exception as e:
        _update_job(con, job_id, status="error", message=str(e)[:2000])
    finally:
        con.close()
        if os.path.exists(zip_path):
            os.remove(zip_path)
