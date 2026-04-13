from __future__ import annotations

import argparse
import json
import mimetypes
import socket
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

STATIC_ROOT = Path(__file__).with_name("web_static")


def load_samples(index_path: Path) -> list[dict]:
    with index_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    records = payload if isinstance(payload, list) else payload.get("files", [])
    samples = []
    for index, record in enumerate(records):
        sample = _flatten_sample(record)
        sample["id"] = index
        sample["playable_path"] = _playable_path(sample)
        samples.append(sample)
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


def build_app(index_path: Path) -> type[BaseHTTPRequestHandler]:
    samples = load_samples(index_path)
    samples_by_id = {sample["id"]: sample for sample in samples}
    stats = summarize_by_type(samples)

    class SampleBrowserHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/index.html"}:
                self._send_static("index.html")
            elif parsed.path in {"/app.css", "/app.js"}:
                self._send_static(parsed.path.lstrip("/"))
            elif parsed.path == "/api/samples":
                self._send_json({"index_path": str(index_path), "total": len(samples), "samples": samples, "stats": stats})
            elif parsed.path == "/api/audio":
                self._send_audio(parsed.query)
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def _send_json(self, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

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
            self.wfile.write(body)

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

            path = Path(sample["playable_path"])
            if not path.exists() or not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND, "Audio file not found")
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
                while remaining > 0:
                    chunk = handle.read(min(1024 * 512, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)

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

    return {
        "file_path": file_block.get("path"),
        "name": file_block.get("name"),
        "format": file_block.get("format"),
        "duration": file_block.get("duration_sec"),
        "sample_rate": file_block.get("sample_rate"),
        "size": file_block.get("size"),
        "mtime": file_block.get("mtime"),
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
        "destination": routing.get("destination"),
        "error": routing.get("error"),
        "structured": record,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local web browser for sample-key-indexer metadata.")
    parser.add_argument("index_path", type=Path, help="Path to metadata_index.json.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    index_path = args.index_path.expanduser().resolve()
    if not index_path.exists():
        print(f"Metadata index does not exist: {index_path}")
        return 2

    handler = build_app(index_path)
    try:
        server = ThreadingHTTPServer((args.host, args.port), handler)
    except OSError as exc:
        if exc.errno == 48:
            print(f"Port {args.port} is already in use. Open http://{args.host}:{args.port} if the browser is already running, or stop the old server and run this command again.")
            return 2
        raise
    print(f"Sample browser running at http://{args.host}:{args.port}")
    print(f"Metadata: {index_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping sample browser.")
    finally:
        server.server_close()
    return 0


def _playable_path(sample: dict) -> str:
    for key in ("destination", "file_path"):
        value = sample.get(key)
        if value and Path(value).exists():
            return value
    return sample.get("destination") or sample.get("file_path") or ""


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
