from __future__ import annotations

import argparse
import ipaddress
import json
import mimetypes
import os
import shutil
import socket
import subprocess
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from sample_key_indexer.index_store import MetadataIndex, SQLiteMetadataIndex, load_records
from sample_key_indexer.music_theory import build_musical_context, midi_bytes_for_progression
from sample_key_indexer.scan_manager import start_scan, get_current_job, load_scan_history, add_to_history, remove_from_history, delete_scan_data

STATIC_ROOT_LEGACY = Path(__file__).with_name("web_static")
REACT_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
STATIC_ROOT = REACT_DIST if (REACT_DIST / "index.html").exists() else STATIC_ROOT_LEGACY
BROWSER_TRANSCODE_EXTENSIONS = {".aif", ".aiff"}


def load_samples(
    index_paths: Path | list[Path],
    library_roots: dict[str, Path] | None = None,
    destination_roots: dict[str, Path] | None = None,
) -> list[dict]:
    paths = [index_paths] if isinstance(index_paths, Path) else index_paths
    samples = []
    for index_path in paths:
        if not index_path.exists():
            continue
        records = load_records(index_path)
        for record in records:
            sample = _flatten_sample(record)
            sample["index_path"] = str(index_path)
            sample["index_writable"] = is_index_writable(index_path)
            sample["id"] = len(samples)
            samples.append(_with_playback_info(sample, library_roots, destination_roots))
    return samples


def summarize_by_type(samples: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    for sample in samples:
        sample_type = sample.get("type") or "Unknown"
        counts[sample_type] = counts.get(sample_type, 0) + 1
    total = max(1, len(samples))
    return [
        {"type": sample_type, "count": count, "percentage": round((count / total) * 100, 2)}
        for sample_type, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def summarize_libraries(samples: list[dict]) -> list[dict]:
    libraries: dict[str, dict] = {}
    for sample in samples:
        library_id = sample.get("library_id") or "unknown"
        library = libraries.setdefault(
            library_id,
            {
                "id": library_id,
                "name": sample.get("library_name") or library_id,
                "total": 0,
                "available": 0,
                "missing": 0,
                "sources": {},
                "index_paths": set(),
            },
        )
        library["total"] += 1
        if sample.get("playback_status") == "available":
            library["available"] += 1
        else:
            library["missing"] += 1
        source = sample.get("playback_source") or "unknown"
        library["sources"][source] = library["sources"].get(source, 0) + 1
        if sample.get("index_path"):
            library["index_paths"].add(sample["index_path"])

    summaries = []
    for library in libraries.values():
        total = max(1, library["total"])
        summaries.append(
            {
                "id": library["id"],
                "name": library["name"],
                "total": library["total"],
                "available": library["available"],
                "missing": library["missing"],
                "available_percentage": round((library["available"] / total) * 100, 2),
                "sources": [
                    {"source": source, "count": count}
                    for source, count in sorted(library["sources"].items(), key=lambda item: (-item[1], item[0]))
                ],
                "index_paths": sorted(library["index_paths"]),
            }
        )
    return sorted(summaries, key=lambda item: (item["name"], item["id"]))


def build_app(
    index_paths: Path | list[Path],
    library_roots: dict[str, Path] | None = None,
    destination_roots: dict[str, Path] | None = None,
    *,
    allowed_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] | None = None,
    auth_token: str | None = None,
) -> type[BaseHTTPRequestHandler]:
    paths = [index_paths] if isinstance(index_paths, Path) else index_paths
    samples = load_samples(paths, library_roots, destination_roots)
    samples_by_id = {sample["id"]: sample for sample in samples}
    samples_by_library_id: dict[str, list[dict]] = {}
    for sample in samples:
        library_id = sample.get("library_id") or "unknown"
        samples_by_library_id.setdefault(library_id, []).append(sample)
    all_stats = summarize_by_type(samples)
    all_libraries = summarize_libraries(samples)
    library_stats = {lib["id"]: summarize_by_type(samples_by_library_id.get(lib["id"], [])) for lib in all_libraries}
    mutation_lock = threading.Lock()

    def _reload_with_new_index(new_path: Path) -> None:
        nonlocal paths, samples, samples_by_id, samples_by_library_id, all_stats, all_libraries, library_stats
        if new_path not in paths:
            paths = paths + [new_path]
        samples = load_samples(paths, library_roots, destination_roots)
        samples_by_id = {sample["id"]: sample for sample in samples}
        samples_by_library_id = {}
        for sample in samples:
            lid = sample.get("library_id") or "unknown"
            samples_by_library_id.setdefault(lid, []).append(sample)
        all_stats = summarize_by_type(samples)
        all_libraries = summarize_libraries(samples)
        library_stats = {lib["id"]: summarize_by_type(samples_by_library_id.get(lib["id"], [])) for lib in all_libraries}

    def _set_paths(new_paths: list[Path]) -> None:
        nonlocal paths, samples, samples_by_id, samples_by_library_id, all_stats, all_libraries, library_stats
        paths = new_paths
        samples = load_samples(paths, library_roots, destination_roots) if paths else []
        samples_by_id = {sample["id"]: sample for sample in samples}
        samples_by_library_id = {}
        for sample in samples:
            lid = sample.get("library_id") or "unknown"
            samples_by_library_id.setdefault(lid, []).append(sample)
        all_stats = summarize_by_type(samples)
        all_libraries = summarize_libraries(samples)
        library_stats = {lib["id"]: summarize_by_type(samples_by_library_id.get(lib["id"], [])) for lib in all_libraries}
    allowed = list(allowed_networks or [])
    expected_token = (auth_token or "").strip() or None

    class SampleBrowserHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _client_ip(self) -> str:
            try:
                return str(self.client_address[0])
            except Exception:
                return ""

        def _authorized(self) -> bool:
            if allowed:
                try:
                    addr = ipaddress.ip_address(self._client_ip())
                except ValueError:
                    return False
                if not any(addr in network for network in allowed):
                    return False

            if expected_token:
                token = self.headers.get("X-SKI-Token")
                if not token:
                    parsed = urlparse(self.path)
                    params = parse_qs(parsed.query)
                    token = (params.get("token") or [""])[0]
                if (token or "").strip() != expected_token:
                    return False

            return True

        def _reject_unauthorized(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/"):
                self._send_json({"error": "forbidden"}, status=HTTPStatus.FORBIDDEN)
                return
            self.send_response(HTTPStatus.FORBIDDEN)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Forbidden")

        def do_GET(self) -> None:
            if not self._authorized():
                self._reject_unauthorized()
                return
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/index.html"}:
                self._send_static("index.html")
            elif parsed.path in {"/app.css", "/app.js"}:
                self._send_static(parsed.path.lstrip("/"))
            elif parsed.path.startswith("/assets/"):
                self._send_static(parsed.path.lstrip("/"))
            elif parsed.path == "/api/catalog":
                self._send_json(
                    {
                        "index_paths": [str(path) for path in paths],
                        "total": len(samples),
                        "stats": all_stats,
                        "libraries": all_libraries,
                    }
                )
            elif parsed.path == "/api/sample":
                self._send_sample(parsed.query)
            elif parsed.path == "/api/sample-midi":
                self._send_sample_midi(parsed.query)
            elif parsed.path == "/api/samples":
                params = parse_qs(parsed.query)
                library_id = (params.get("library_id") or [""])[0].strip() or None
                try:
                    offset = int((params.get("offset") or ["0"])[0] or 0)
                except ValueError:
                    offset = 0
                try:
                    limit = int((params.get("limit") or ["0"])[0] or 0)
                except ValueError:
                    limit = 0
                offset = max(0, offset)
                if limit <= 0:
                    limit = 10000
                limit = min(max(1, limit), 25000)
                selected = samples if not library_id else samples_by_library_id.get(library_id, [])
                total = len(selected)
                window = selected[offset : offset + limit]
                # NOTE: playback info is already computed during load_samples(). Recomputing it here
                # is extremely expensive for large libraries (filesystem checks per row) and makes
                # library switching feel "hung", especially when audio is not mounted.
                current_samples = window
                stats = all_stats if not library_id else library_stats.get(library_id, [])
                self._send_json(
                    {
                        "index_paths": [str(path) for path in paths],
                        "total": total,
                        "offset": offset,
                        "limit": limit,
                        "returned": len(current_samples),
                        # Slim payload for huge libraries (list view + filters). Fetch full details via /api/sample on demand.
                        "samples": [list_sample(sample) for sample in current_samples],
                        "stats": stats,
                        # Libraries are stable; return the full list (small), not a per-window summary.
                        "libraries": all_libraries,
                    }
                )
            elif parsed.path == "/api/audio":
                self._send_audio(parsed.query)
            elif parsed.path == "/api/browse-folders":
                self._handle_browse_folders(parsed.query)
            elif parsed.path == "/api/scan/status":
                job = get_current_job()
                self._send_json(job.to_dict() if job else {"status": "idle"})
            elif parsed.path == "/api/scan/history":
                self._send_json({"history": load_scan_history()})
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def do_POST(self) -> None:
            if not self._authorized():
                self._reject_unauthorized()
                return
            parsed = urlparse(self.path)
            if parsed.path == "/api/review":
                self._handle_review_mutation()
                return
            if parsed.path == "/api/scan/start":
                self._handle_scan_start()
                return
            if parsed.path == "/api/reload":
                self._handle_reload()
                return
            if parsed.path == "/api/scan/add-index":
                self._handle_add_index()
                return
            if parsed.path == "/api/scan/remove":
                self._handle_remove_index()
                return
            if parsed.path == "/api/scan/delete-data":
                self._handle_delete_scan_data()
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def _send_json(self, payload: dict, *, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                return

        def _send_static(self, name: str) -> None:
            path = (STATIC_ROOT / name).resolve()
            if STATIC_ROOT.resolve() not in path.parents and path != STATIC_ROOT.resolve():
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return
            if not path.exists() or not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            body = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                return

        def _read_json_body(self) -> dict | None:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0:
                return {}
            try:
                raw = self.rfile.read(length)
            except Exception:
                return None
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                return None
            return payload if isinstance(payload, dict) else None

        def _handle_review_mutation(self) -> None:
            payload = self._read_json_body()
            if payload is None:
                self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON body")
                return
            try:
                sample_id = int(payload.get("id"))
            except Exception:
                self.send_error(HTTPStatus.BAD_REQUEST, "Missing/invalid sample id")
                return
            reviewed = bool(payload.get("reviewed"))
            sample = samples_by_id.get(sample_id)
            if not sample:
                self.send_error(HTTPStatus.NOT_FOUND, "Sample not found")
                return
            if not sample.get("index_writable"):
                self.send_error(HTTPStatus.CONFLICT, "Index is not writable (open a .sqlite index to edit review state)")
                return
            with mutation_lock:
                updated = set_sample_reviewed(sample, reviewed)
                if not updated:
                    self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Failed to update index")
                    return
                # Refresh playback fields (in case paths changed externally).
                refreshed = _with_playback_info(sample, library_roots, destination_roots)
                samples_by_id[sample_id] = refreshed
                samples[sample_id] = refreshed
                library_key = refreshed.get("library_id") or "unknown"
                bucket = samples_by_library_id.get(library_key)
                if bucket is not None:
                    for idx, existing in enumerate(bucket):
                        if existing.get("id") == sample_id:
                            bucket[idx] = refreshed
                            break
            self._send_json({"ok": True, "sample": public_sample(refreshed)})

        def _handle_browse_folders(self, query: str) -> None:
            params = parse_qs(query)
            path_str = (params.get("path") or [""])[0].strip()
            if not path_str:
                # Return root-level locations
                roots = []
                home = str(Path.home())
                roots.append({"name": "Home", "path": home})
                desktop = str(Path.home() / "Desktop")
                if Path(desktop).exists():
                    roots.append({"name": "Desktop", "path": desktop})
                # macOS volumes
                volumes = Path("/Volumes")
                if volumes.exists():
                    for v in sorted(volumes.iterdir()):
                        if v.is_dir() and not v.name.startswith("."):
                            roots.append({"name": v.name, "path": str(v)})
                # Linux media
                media = Path("/media") / (os.environ.get("USER") or "")
                if media.exists():
                    for v in sorted(media.iterdir()):
                        if v.is_dir():
                            roots.append({"name": v.name, "path": str(v)})
                self._send_json({"path": "", "folders": roots, "parent": None})
                return

            target = Path(path_str).expanduser().resolve()
            if not target.exists() or not target.is_dir():
                self._send_json({"error": f"Not a directory: {path_str}"}, status=HTTPStatus.BAD_REQUEST)
                return

            folders = []
            try:
                for entry in sorted(target.iterdir()):
                    if entry.is_dir() and not entry.name.startswith("."):
                        folders.append({"name": entry.name, "path": str(entry)})
            except PermissionError:
                pass

            parent = str(target.parent) if target.parent != target else None
            self._send_json({"path": str(target), "folders": folders, "parent": parent})

        def _handle_reload(self) -> None:
            payload = self._read_json_body()
            index_path_str = (payload or {}).get("index_path", "").strip()
            if index_path_str:
                new_path = Path(index_path_str).expanduser().resolve()
                if new_path.exists():
                    with mutation_lock:
                        _reload_with_new_index(new_path)
                    self._send_json({"ok": True, "total": len(samples), "libraries": len(all_libraries)})
                    return
                self._send_json({"error": f"Index not found: {new_path}"}, status=HTTPStatus.BAD_REQUEST)
                return
            # Full reload — rebuild from only currently-existing index paths + scan history
            with mutation_lock:
                all_known = {str(p) for p in paths if p.exists()}
                for entry in load_scan_history():
                    ip = entry.get("index_path")
                    if ip and Path(ip).exists():
                        all_known.add(ip)
                existing = [Path(pp) for pp in sorted(all_known)]
                _set_paths(existing)
            self._send_json({"ok": True, "total": len(samples), "libraries": len(all_libraries)})

        def _handle_scan_start(self) -> None:
            payload = self._read_json_body()
            if not payload:
                self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON body")
                return
            source = payload.get("source", "").strip()
            output = payload.get("output", "").strip()
            mode = payload.get("mode", "catalog").strip()
            if not source or not output:
                self._send_json({"error": "source and output are required"}, status=HTTPStatus.BAD_REQUEST)
                return
            if mode not in ("catalog", "organize"):
                self._send_json({"error": "mode must be 'catalog' or 'organize'"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                job = start_scan(source, output, mode, payload.get("options"))
                self._send_json({"ok": True, "job": job.to_dict()})
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.CONFLICT)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        def _handle_add_index(self) -> None:
            payload = self._read_json_body()
            if not payload:
                self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON body")
                return
            index_path = payload.get("index_path", "").strip()
            source = payload.get("source", "").strip()
            output = payload.get("output", "").strip()
            if not index_path:
                self._send_json({"error": "index_path is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            add_to_history(source or "", output or "", index_path)
            self._send_json({"ok": True})

        def _handle_delete_scan_data(self) -> None:
            payload = self._read_json_body()
            if not payload:
                self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON body")
                return
            output = payload.get("output", "").strip()
            if not output:
                self._send_json({"error": "output path is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            result = delete_scan_data(output)
            self._send_json({"ok": True, **result})

        def _handle_remove_index(self) -> None:
            payload = self._read_json_body()
            if not payload:
                self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON body")
                return
            index_path = payload.get("index_path", "").strip()
            if not index_path:
                self._send_json({"error": "index_path is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            remove_from_history(index_path)
            self._send_json({"ok": True})

        def _send_audio(self, query: str) -> None:
            params = parse_qs(query)
            try:
                sample_id = int(params.get("id", [""])[0])
            except ValueError:
                self.send_error(HTTPStatus.BAD_REQUEST, "Invalid sample id")
                return

            sample = samples_by_id.get(sample_id)
            if not sample:
                self.send_error(HTTPStatus.NOT_FOUND, "Sample not found")
                return

            path = Path(_playable_path(sample, library_roots, destination_roots))
            if not path.exists() or not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND, "Audio file not found")
                return

            if should_transcode_for_browser(path):
                transcoded = ffmpeg_transcode_for_browser(path)
                if transcoded is not None:
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "audio/wav")
                    self.send_header("Content-Length", str(len(transcoded)))
                    self.end_headers()
                    try:
                        self.wfile.write(transcoded)
                    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                        return
                    return

            content_type = mimetypes.guess_type(path.name)[0] or "audio/wav"
            file_size = path.stat().st_size
            start, end = _range_from_header(self.headers.get("Range"), file_size)
            status = HTTPStatus.PARTIAL_CONTENT if start or end < file_size - 1 else HTTPStatus.OK
            length = end - start + 1

            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            if status == HTTPStatus.PARTIAL_CONTENT:
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.end_headers()

            with path.open("rb") as handle:
                handle.seek(start)
                remaining = length
                try:
                    while remaining > 0:
                        chunk = handle.read(min(1024 * 512, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                    return

        def _send_sample(self, query: str) -> None:
            params = parse_qs(query)
            try:
                sample_id = int(params.get("id", [""])[0])
            except ValueError:
                self.send_error(HTTPStatus.BAD_REQUEST, "Invalid sample id")
                return
            sample = samples_by_id.get(sample_id)
            if not sample:
                self.send_error(HTTPStatus.NOT_FOUND, "Sample not found")
                return
            # Playback info is already computed at load time; don't redo filesystem probing here.
            self._send_json({"sample": public_sample(sample, include_musical_context=True)})

        def _send_sample_midi(self, query: str) -> None:
            params = parse_qs(query)
            try:
                sample_id = int(params.get("id", [""])[0])
            except ValueError:
                self.send_error(HTTPStatus.BAD_REQUEST, "Invalid sample id")
                return
            try:
                progression_index = int(params.get("progression", ["0"])[0] or 0)
            except ValueError:
                progression_index = 0
            sample = samples_by_id.get(sample_id)
            if not sample:
                self.send_error(HTTPStatus.NOT_FOUND, "Sample not found")
                return
            try:
                body = midi_bytes_for_progression(sample, progression_index)
            except RuntimeError as exc:
                message = str(exc)
                if message.startswith("missing_backend:"):
                    self.send_error(HTTPStatus.SERVICE_UNAVAILABLE, "MIDI backend not installed")
                    return
                if message == "no_progression_available":
                    self.send_error(HTTPStatus.CONFLICT, "No progression available for sample")
                    return
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Failed to generate MIDI")
                return
            filename = f"{Path(sample.get('name') or 'sample').stem}_progression_{max(0, progression_index) + 1}.mid"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "audio/midi")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                return

    return SampleBrowserHandler


def _flatten_sample(record: dict) -> dict:
    if not isinstance(record.get("file"), dict):
        return dict(record)

    file_block = record.get("file", {})
    musical = record.get("musical", {})
    features = record.get("audio_features", {})
    loudness = features.get("loudness", {})
    frequency = features.get("frequency", {})
    timbre = features.get("timbre", {})
    classification = record.get("classification", {})
    analysis = record.get("analysis", {})
    routing = record.get("routing", {})
    final = analysis.get("final_decision", {})
    programs = analysis.get("programs", {})
    deep_analysis = analysis.get("deep_analysis", {})

    return {
        "file_path": file_block.get("path"),
        "name": file_block.get("name"),
        "format": file_block.get("format"),
        "duration": file_block.get("duration_sec"),
        "sample_rate": file_block.get("sample_rate"),
        "size": file_block.get("size"),
        "mtime": file_block.get("mtime"),
        "relative_path": file_block.get("relative_path"),
        "library_id": record.get("library", {}).get("id"),
        "library_name": record.get("library", {}).get("name"),
        "library_root": record.get("library", {}).get("root"),
        "root_note": musical.get("root") or final.get("root"),
        "key": musical.get("key") or final.get("key"),
        "scale_confidence": musical.get("scale_confidence"),
        "notes": musical.get("notes", []),
        "chords": musical.get("chords", []),
        "bpm": musical.get("bpm"),
        "rms_db": loudness.get("rms"),
        "peak_db": loudness.get("peak_db"),
        "dynamic_range_db": loudness.get("dynamic_range"),
        "spectral_centroid": frequency.get("spectral_centroid"),
        "spectral_bandwidth": frequency.get("spectral_bandwidth"),
        "rolloff": frequency.get("rolloff"),
        "fundamental_freq": frequency.get("fundamental_freq"),
        "brightness": timbre.get("brightness"),
        "warmth": timbre.get("warmth"),
        "roughness": timbre.get("roughness"),
        "mfcc": timbre.get("mfcc", []),
        "category": classification.get("category"),
        "type": classification.get("type"),
        "subtype": classification.get("subtype"),
        "source": classification.get("source"),
        "confidence": classification.get("confidence") or final.get("confidence"),
        "analysis_profile": analysis.get("profile"),
        "analysis_engines": analysis.get("engines", []),
        "analysis_warnings": analysis.get("warnings", []),
        "needs_review": analysis.get("review", {}).get("needs_review", False),
        "review_reasons": analysis.get("review", {}).get("reasons", []),
        "reviewed": analysis.get("review", {}).get("reviewed", False),
        "reviewed_at": analysis.get("review", {}).get("reviewed_at"),
        "deep_review": analysis.get("deep_review", {}),
        "deep_analysis": deep_analysis,
        "deep_analysis_mode": deep_analysis.get("mode"),
        "deep_analysis_scope": deep_analysis.get("scope"),
        "deep_analysis_status": deep_analysis.get("status"),
        "deep_route_family": deep_analysis.get("source_family") or deep_analysis.get("route"),
        "deep_sample_type": deep_analysis.get("sample_type"),
        "deep_category": deep_analysis.get("category"),
        "deep_route_reason": deep_analysis.get("reason"),
        "deep_tonal_backend": deep_analysis.get("tonal_backend"),
        "deep_chord_backend": deep_analysis.get("chord_backend"),
        "deep_timing_backend": deep_analysis.get("timing_backend"),
        "deep_tuning_backend": deep_analysis.get("tuning_backend"),
        "deep_note_backend": deep_analysis.get("note_backend"),
        "deep_should_detect_chords": deep_analysis.get("should_detect_chords"),
        "deep_should_detect_tuning": deep_analysis.get("should_detect_tuning"),
        "deep_should_transcribe_notes": deep_analysis.get("should_transcribe_notes"),
        "deep_key": deep_analysis.get("deep_key"),
        "deep_root": deep_analysis.get("deep_root"),
        "deep_key_confidence": deep_analysis.get("deep_key_confidence"),
        "deep_chords": deep_analysis.get("deep_chords", []),
        "deep_chord_strengths": deep_analysis.get("deep_chord_strengths", []),
        "deep_hpcp": deep_analysis.get("deep_hpcp", []),
        "deep_tuning_hz": deep_analysis.get("deep_tuning_hz"),
        "deep_chords_key": deep_analysis.get("deep_chords_key"),
        "deep_chords_scale": deep_analysis.get("deep_chords_scale"),
        "deep_chords_changes_rate": deep_analysis.get("deep_chords_changes_rate"),
        "deep_chords_number_rate": deep_analysis.get("deep_chords_number_rate"),
        "deep_bpm": deep_analysis.get("deep_bpm"),
        "deep_bpm_confidence": deep_analysis.get("deep_bpm_confidence"),
        "deep_ticks": deep_analysis.get("deep_ticks", []),
        "deep_bpm_estimates": deep_analysis.get("deep_bpm_estimates", []),
        "deep_bpm_intervals": deep_analysis.get("deep_bpm_intervals", []),
        "deep_onsets": deep_analysis.get("deep_onsets", []),
        "deep_onset_count": deep_analysis.get("deep_onset_count"),
        "deep_timing_confidence": deep_analysis.get("deep_timing_confidence"),
        "deep_note_events": deep_analysis.get("deep_note_events", []),
        "deep_notes": deep_analysis.get("deep_notes", []),
        "deep_note_count": deep_analysis.get("deep_note_count"),
        "deep_note_confidence": deep_analysis.get("deep_note_confidence"),
        "deep_note_backend_status": deep_analysis.get("deep_note_backend_status"),
        "deep_note_backend_error": deep_analysis.get("deep_note_backend_error"),
        "deep_rhythm_status": deep_analysis.get("deep_rhythm_status"),
        "deep_rhythm_error": deep_analysis.get("deep_rhythm_error"),
        "deep_analysis_confidence": deep_analysis.get("deep_analysis_confidence"),
        "deep_analysis_confidence_breakdown": deep_analysis.get("deep_analysis_confidence_breakdown", {}),
        "deep_engines": deep_analysis.get("engines", {}),
        "librosa_key": programs.get("librosa", {}).get("key"),
        "essentia_key": programs.get("essentia", {}).get("key"),
        "filename_key": programs.get("filename", {}).get("key"),
        "destination": routing.get("destination"),
        "error": routing.get("error"),
        "structured": record,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local web browser for sample-key-indexer metadata.")
    parser.add_argument(
        "index_paths",
        nargs="+",
        type=Path,
        help=(
            "Path to one or more metadata_index.json or metadata_index.sqlite files. "
            "You can also pass a directory (for example SampleIndexes/) and the browser will auto-load every catalog under it."
        ),
    )
    parser.add_argument("--library-root", action="append", default=[], help="Playback root override as LIBRARY_ID=/Volumes/USB/Samples. Can be passed more than once.")
    parser.add_argument("--destination-root", action="append", default=[], help="Organized Key/Unsorted root override as LIBRARY_ID=/Volumes/USB/SAMPLEZ. Can be passed more than once.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind.")
    parser.add_argument("--allow-ip", action="append", default=[], help="Restrict access to a specific client IP (repeatable).")
    parser.add_argument("--allow-cidr", action="append", default=[], help="Restrict access to client IP ranges like 192.168.1.0/24 (repeatable).")
    parser.add_argument("--auth-token", default="", help="If set, require X-SKI-Token header or ?token=... on every request.")
    return parser


def parse_allowed_networks(
    allow_ip: list[str] | None,
    allow_cidr: list[str] | None,
) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    allowed_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []

    for value in list(allow_ip or []):
        value = str(value).strip()
        if not value:
            continue
        try:
            ip = ipaddress.ip_address(value)
        except ValueError as exc:
            raise ValueError(f"Invalid --allow-ip: {value}") from exc
        prefix = 32 if ip.version == 4 else 128
        network = ipaddress.ip_network(f"{ip}/{prefix}", strict=False)
        allowed_networks.append(network)

    for value in list(allow_cidr or []):
        value = str(value).strip()
        if not value:
            continue
        try:
            network = ipaddress.ip_network(value, strict=False)
        except ValueError as exc:
            raise ValueError(f"Invalid --allow-cidr: {value}") from exc
        allowed_networks.append(network)

    return allowed_networks


def is_loopback_host(host: str) -> bool:
    bind_ip = str(host or "").strip()
    return bind_ip in {"127.0.0.1", "::1", "localhost"}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    index_paths = resolve_index_paths([path.expanduser().resolve() for path in args.index_paths])

    # Auto-load known indexes from scan history
    history = load_scan_history()
    cli_path_set = {str(p) for p in index_paths}
    for entry in history:
        hist_path = entry.get("index_path")
        if hist_path and hist_path not in cli_path_set:
            p = Path(hist_path)
            if p.exists():
                index_paths.append(p)
                cli_path_set.add(hist_path)

    for index_path in index_paths:
        if not index_path.exists():
            print(f"Metadata index does not exist: {index_path}")
            return 2

    try:
        library_roots = parse_library_roots(args.library_root)
        destination_roots = parse_library_roots(args.destination_root, option_name="--destination-root")
    except ValueError as exc:
        print(str(exc))
        return 2

    try:
        allowed_networks = parse_allowed_networks(args.allow_ip, args.allow_cidr)
    except ValueError as exc:
        print(str(exc))
        return 2

    auth_token = str(args.auth_token or "").strip() or None
    is_loopback = is_loopback_host(args.host)
    if not is_loopback and not allowed_networks and not auth_token:
        print("Refusing to bind to a non-loopback host without any access controls.")
        print("Add at least one of: --allow-ip / --allow-cidr / --auth-token")
        return 2

    handler = build_app(
        index_paths,
        library_roots,
        destination_roots,
        allowed_networks=allowed_networks,
        auth_token=auth_token,
    )
    try:
        server = ThreadingHTTPServer((args.host, args.port), handler)
    except OSError as exc:
        if exc.errno == 48:
            print(f"Port {args.port} is already in use. Open http://{args.host}:{args.port} if the browser is already running, or stop the old server and run this command again.")
            return 2
        raise
    print(f"Sample browser running at http://{args.host}:{args.port}")
    print(f"Metadata ({len(index_paths)} indexes):")
    for p in index_paths:
        print(f"  {p}")
    print("Metadata:")
    for index_path in index_paths:
        print(f"  {index_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping sample browser.")
    finally:
        server.server_close()
    return 0


def resolve_index_paths(values: list[Path]) -> list[Path]:
    """Expand directories into metadata index files; prefer SQLite when both exist.

    This lets users run:
      sample-key-indexer-web /Users/.../Desktop/SampleIndexes
    and automatically load all catalogs.
    """
    expanded: list[Path] = []
    for value in values:
        if value.is_dir():
            expanded.extend(_discover_indexes_in_dir(value))
        else:
            expanded.append(value)
    # De-dupe while preserving order.
    seen: set[str] = set()
    deduped: list[Path] = []
    for path in expanded:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def _discover_indexes_in_dir(root: Path) -> list[Path]:
    sqlite_paths = list(root.rglob("metadata_index.sqlite"))
    sqlite_paths += list(root.rglob("metadata_index.sqlite3"))
    sqlite_paths += list(root.rglob("metadata_index.db"))
    json_paths = list(root.rglob("metadata_index.json"))
    # Prefer sqlite in the same directory as a json index.
    chosen: dict[str, Path] = {}
    for path in json_paths:
        chosen.setdefault(str(path.parent), path)
    for path in sqlite_paths:
        chosen[str(path.parent)] = path
    return sorted(chosen.values(), key=lambda p: str(p))


def _playable_path(
    sample: dict,
    library_roots: dict[str, Path] | None = None,
    destination_roots: dict[str, Path] | None = None,
) -> str:
    return _playback_info(sample, library_roots, destination_roots)["path"]


def _playback_info(
    sample: dict,
    library_roots: dict[str, Path] | None = None,
    destination_roots: dict[str, Path] | None = None,
) -> dict:
    destination = sample.get("destination")
    if destination and Path(destination).exists():
        return {"path": destination, "status": "available", "source": "organized_stored_path"}

    library_id = sample.get("library_id")
    destination_relative_path = organized_relative_path(destination)
    if destination_relative_path and destination_roots:
        roots: list[Path] = []
        if library_id and library_id in destination_roots:
            roots.append(destination_roots[library_id])
        if not library_id and len(destination_roots) == 1:
            roots.extend(destination_roots.values())
        for root in roots:
            candidate = root / destination_relative_path
            if candidate.exists():
                return {"path": str(candidate), "status": "available", "source": "organized_mounted_root"}

    file_path = sample.get("file_path")
    if file_path and Path(file_path).exists():
        return {"path": file_path, "status": "available", "source": "source_stored_path"}

    relative_path = sample.get("relative_path")
    if relative_path:
        roots: list[Path] = []
        if library_roots:
            if library_id and library_id in library_roots:
                roots.append(library_roots[library_id])
            if not library_id and len(library_roots) == 1:
                roots.extend(library_roots.values())
        library_root = sample.get("library_root")
        if library_root:
            roots.append(Path(library_root))
        for root in roots:
            candidate = root / relative_path
            if candidate.exists():
                source = "source_stored_library_root" if str(root) == str(sample.get("library_root")) else "source_mounted_root"
                return {"path": str(candidate), "status": "available", "source": source}
    return {"path": sample.get("destination") or sample.get("file_path") or "", "status": "missing", "source": "missing"}


def organized_relative_path(destination: str | None) -> Path | None:
    if not destination:
        return None
    path = Path(destination)
    for anchor in ("Key", "Unsorted"):
        if anchor in path.parts:
            index = path.parts.index(anchor)
            return Path(*path.parts[index:])
    return None


def _with_playback_info(
    sample: dict,
    library_roots: dict[str, Path] | None = None,
    destination_roots: dict[str, Path] | None = None,
) -> dict:
    enriched = dict(sample)
    playback = _playback_info(enriched, library_roots, destination_roots)
    enriched["playable_path"] = playback["path"]
    enriched["playback_status"] = playback["status"]
    enriched["playback_source"] = playback["source"]
    return enriched


def parse_library_roots(values: list[str], option_name: str = "--library-root") -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for value in values:
        library_id, separator, root = value.partition("=")
        if not separator or not library_id.strip() or not root.strip():
            raise ValueError(f"{option_name} must use LIBRARY_ID=/path/to/library")
        roots[library_id.strip()] = Path(root).expanduser().resolve()
    return roots


def should_transcode_for_browser(path: Path) -> bool:
    return path.suffix.lower() in BROWSER_TRANSCODE_EXTENSIONS


def ffmpeg_transcode_for_browser(path: Path) -> bytes | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    command = [
        ffmpeg,
        "-v",
        "error",
        "-i",
        str(path),
        "-f",
        "wav",
        "-acodec",
        "pcm_s16le",
        "-ac",
        "2",
        "-ar",
        "44100",
        "pipe:1",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, check=False, timeout=30)
    except Exception:
        return None
    if completed.returncode != 0 or not completed.stdout:
        return None
    return completed.stdout


def is_index_writable(index_path: Path) -> bool:
    suffix = index_path.suffix.lower()
    if suffix not in {".db", ".sqlite", ".sqlite3", ".json"}:
        return False
    try:
        return index_path.exists() and index_path.is_file() and index_path.stat().st_mode is not None and os.access(index_path, os.W_OK)
    except Exception:
        return False


def set_sample_reviewed(sample: dict, reviewed: bool) -> bool:
    index_path = Path(sample.get("index_path") or "")
    record = sample.get("structured")
    if not index_path or not record or not isinstance(record, dict):
        return False
    # Update structured record.
    analysis = record.setdefault("analysis", {})
    review = analysis.setdefault("review", {})
    review["reviewed"] = bool(reviewed)
    review["reviewed_at"] = datetime.now(timezone.utc).isoformat() if reviewed else None
    # Mirror a best-effort UX: a reviewed item shouldn't keep shouting in the queue.
    if reviewed:
        review["needs_review"] = False
        if isinstance(review.get("reasons"), list):
            review["reasons"] = list(review.get("reasons") or [])
    # Persist.
    try:
        if index_path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
            db = SQLiteMetadataIndex(index_path)
            try:
                db.upsert_record(record)
                db.write()
            finally:
                db.close()
        else:
            idx = MetadataIndex(index_path)
            idx.records[_record_path_value(record)] = record  # type: ignore[attr-defined]
            idx.write()
    except Exception:
        return False
    # Refresh flattened fields in-place.
    updated = _flatten_sample(record)
    for key, value in updated.items():
        if key == "structured":
            continue
        sample[key] = value
    sample["structured"] = record
    return True


def _record_path_value(record: dict) -> str:
    file_block = record.get("file")
    if isinstance(file_block, dict):
        return str(file_block.get("path") or "")
    return str(record.get("file_path") or "")


def public_sample(sample: dict, include_musical_context: bool = False) -> dict:
    """Return a JSON-safe sample payload for the browser (omit huge structured record)."""
    cleaned = dict(sample)
    cleaned.pop("structured", None)
    if include_musical_context:
        cleaned.update(build_musical_context(cleaned))
    return cleaned


def list_sample(sample: dict) -> dict:
    """Return a slim sample payload for list views (fast to transfer + parse)."""
    keep = {
        "id",
        "index_path",
        "index_writable",
        "library_id",
        "library_name",
        "library_root",
        "name",
        "file_path",
        "relative_path",
        "destination",
        "playable_path",
        "playback_status",
        "playback_source",
        "format",
        "duration",
        "size",
        "mtime",
        "root_note",
        "key",
        "bpm",
        "category",
        "type",
        "subtype",
        "source",
        "brightness",
        "warmth",
        "confidence",
        "needs_review",
        "review_reasons",
        "reviewed",
        "reviewed_at",
        "error",
    }
    out = {key: sample.get(key) for key in keep}
    # Ensure name is always present for sorting/display.
    out["name"] = out.get("name") or Path(out.get("file_path") or out.get("destination") or "").name
    return out


def _range_from_header(header: str | None, file_size: int) -> tuple[int, int]:
    if not header or not header.startswith("bytes="):
        return 0, file_size - 1
    value = header.removeprefix("bytes=").split(",", 1)[0]
    start_text, _, end_text = value.partition("-")
    if not start_text and end_text:
        suffix_length = min(int(end_text), file_size)
        return file_size - suffix_length, file_size - 1
    start = int(start_text or 0)
    end = int(end_text) if end_text else file_size - 1
    return max(0, start), min(file_size - 1, end)


if __name__ == "__main__":
    raise SystemExit(main())
