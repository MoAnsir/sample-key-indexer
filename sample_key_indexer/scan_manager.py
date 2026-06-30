"""Manages scan jobs triggered from the web UI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path


SCAN_HISTORY_FILE = Path.home() / ".sample-key-indexer" / "scan_history.json"


@dataclass
class ScanJob:
    job_id: str
    source: str
    output: str
    mode: str  # "catalog" or "organize"
    status: str = "pending"  # pending | running | completed | failed
    progress_lines: list[str] = field(default_factory=list)
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None
    pid: int | None = None
    total_files: int = 0
    processed_files: int = 0
    current_file: str = ""
    phase: str = ""
    index_path: str | None = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "source": self.source,
            "output": self.output,
            "mode": self.mode,
            "status": self.status,
            "progress_lines": self.progress_lines[-50:],
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_lines": len(self.progress_lines),
            "total_files": self.total_files,
            "processed_files": self.processed_files,
            "current_file": self.current_file,
            "phase": self.phase,
            "index_path": self.index_path,
        }


_current_job: ScanJob | None = None
_lock = threading.Lock()


def get_current_job() -> ScanJob | None:
    return _current_job


def start_scan(source: str, output: str, mode: str, options: dict | None = None) -> ScanJob:
    global _current_job

    with _lock:
        if _current_job and _current_job.status == "running":
            raise RuntimeError("A scan is already running")

    source_path = Path(source).expanduser().resolve()
    output_path = Path(output).expanduser().resolve()

    if not source_path.exists() or not source_path.is_dir():
        raise ValueError(f"Source folder does not exist: {source_path}")

    output_path.mkdir(parents=True, exist_ok=True)

    job_id = f"scan_{int(time.time())}"
    job = ScanJob(job_id=job_id, source=str(source_path), output=str(output_path), mode=mode)

    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    opts = options or {}

    # Build CLI passthrough args
    passthrough = []
    if mode == "catalog":
        passthrough.append("--catalog-only")
    if opts.get("library_id"):
        passthrough.extend(["--library-id", opts["library_id"]])
    if opts.get("library_name"):
        passthrough.extend(["--library-name", opts["library_name"]])
    if opts.get("dry_run"):
        passthrough.append("--dry-run")

    workers = opts.get("workers", 1)
    keyfinder_workers = opts.get("keyfinder_workers", 4)

    # Use kitchen-sink for full pipeline (index + KeyFinder + deep analysis)
    cmd = [
        sys.executable, "-u", "-m", "sample_key_indexer.kitchen_sink",
        str(source_path), str(output_path),
        "--keyfinder-convert-retry",
        "--keyfinder-workers", str(keyfinder_workers),
        "--workers", str(workers),
    ]
    cmd.extend(passthrough)

    def run():
        global _current_job
        job.status = "running"
        job.started_at = time.time()
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )
            job.pid = process.pid
            for raw_line in process.stdout:
                # Handle \r (tqdm overwrites) — split and process each segment
                segments = raw_line.replace("\r", "\n").split("\n")
                for segment in segments:
                    line = segment.rstrip()
                    if not line:
                        continue
                    # Parse tqdm progress: "  0%| | 0/367" or "45%|████| 167/367"
                    if "%" in line and "|" in line and "/" in line:
                        try:
                            frac_part = line.split("|")[-1].strip().split("[")[0].strip()
                            if "/" in frac_part:
                                parts = frac_part.split("/")
                                job.processed_files = int(parts[0].strip())
                                job.total_files = int(parts[1].strip())
                        except (ValueError, IndexError):
                            pass
                    # Parse discovery line
                    if "Discovered" in line and "supported audio files" in line:
                        job.phase = "discovering"
                        try:
                            count = int(line.split("Discovered")[1].split("supported")[0].strip())
                            job.total_files = count
                        except (ValueError, IndexError):
                            pass
                    if "Analysis profile" in line:
                        job.phase = "analyzing"
                    if "SQLite:" in line:
                        job.phase = "saving"
                        try:
                            job.index_path = line.split("SQLite:")[1].strip()
                        except (IndexError, ValueError):
                            pass
                    if "Metadata JSON export" in line:
                        job.phase = "saving"
                    if "Indexed" in line and "files." in line:
                        job.phase = "indexing"
                    if "Kitchen sink" in line:
                        job.phase = "complete"
                    if "KeyFinder" in line and "%" in line:
                        job.phase = "keyfinder"
                    # Store meaningful lines (skip tqdm overwrites)
                    if not line.startswith(" ") or "%" not in line:
                        job.progress_lines.append(line)
            process.wait()
            # Fallback: find index path from output directory if not parsed
            if not job.index_path:
                job.index_path = _find_index(job.output)
            if process.returncode == 0:
                job.status = "completed"
                _save_to_history(job)
            else:
                job.status = "failed"
                job.error = f"Process exited with code {process.returncode}"
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
        finally:
            job.finished_at = time.time()

    with _lock:
        _current_job = job

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return job


def _save_to_history(job: ScanJob) -> None:
    history = load_scan_history()
    entry = {
        "source": job.source,
        "output": job.output,
        "mode": job.mode,
        "scanned_at": job.finished_at,
        "index_path": _find_index(job.output),
    }
    # Remove duplicate source+output
    history = [h for h in history if not (h["source"] == entry["source"] and h["output"] == entry["output"])]
    history.insert(0, entry)
    _write_history(history)


def _find_index(output: str) -> str | None:
    output_path = Path(output)
    for name in ["metadata_index.sqlite", "metadata_index.json"]:
        candidate = output_path / name
        if candidate.exists():
            return str(candidate)
    return None


def load_scan_history() -> list[dict]:
    if not SCAN_HISTORY_FILE.exists():
        return []
    try:
        return json.loads(SCAN_HISTORY_FILE.read_text())
    except Exception:
        return []


def add_to_history(source: str, output: str, index_path: str) -> None:
    history = load_scan_history()
    entry = {
        "source": source,
        "output": output,
        "mode": "loaded",
        "scanned_at": time.time(),
        "index_path": index_path,
    }
    history = [h for h in history if h.get("index_path") != index_path]
    history.insert(0, entry)
    _write_history(history)


def remove_from_history(index_path: str) -> None:
    history = load_scan_history()
    history = [h for h in history if h.get("index_path") != index_path]
    _write_history(history)


def delete_scan_data(output: str) -> dict:
    """Delete generated index files and organized folders from a scan output directory."""
    output_path = Path(output)
    deleted = []
    errors = []

    for name in ["metadata_index.sqlite", "metadata_index.json", "analysis_run_report.json"]:
        target = output_path / name
        if target.exists():
            try:
                target.unlink()
                deleted.append(str(target))
            except Exception as e:
                errors.append(f"{target}: {e}")

    # Remove organized folders (Key/, Unsorted/) only if they look like our output
    for folder_name in ["Key", "Unsorted"]:
        target = output_path / folder_name
        if target.exists() and target.is_dir():
            try:
                shutil.rmtree(target)
                deleted.append(str(target))
            except Exception as e:
                errors.append(f"{target}: {e}")

    # Remove from history
    remove_from_history_by_output(output)

    return {"deleted": deleted, "errors": errors}


def remove_from_history_by_output(output: str) -> None:
    history = load_scan_history()
    history = [h for h in history if h.get("output") != output]
    _write_history(history)


def _write_history(history: list[dict]) -> None:
    SCAN_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    SCAN_HISTORY_FILE.write_text(json.dumps(history, indent=2))
