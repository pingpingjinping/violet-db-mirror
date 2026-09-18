#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunk-dir", required=True)
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()

    chunk_dir = Path(args.chunk_dir)
    out_dir = Path(args.out_dir)
    manifest_path = Path(args.manifest)
    out_dir.mkdir(parents=True, exist_ok=True)

    chunks = sorted(chunk_dir.glob("data-*.json"))
    if len(chunks) > 1:
        raise RuntimeError(f"expected at most one chunk, found {len(chunks)}")

    if chunks:
        rows = json.loads(chunks[0].read_text(encoding="utf-8"))
    else:
        rows = []

    delta_json = out_dir / f"delta-{args.run_id}.json"
    delta_zst = out_dir / f"delta-{args.run_id}.json.zst"
    delta_json.write_text(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    subprocess.run(
        ["zstd", "-q", "-f", "-5", str(delta_json), "-o", str(delta_zst)],
        check=True,
    )
    delta_json.unlink()

    before = json.loads(Path(args.before).read_text(encoding="utf-8"))
    after = json.loads(Path(args.after).read_text(encoding="utf-8"))

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {"schema": 1, "entries": []}

    entries = manifest.setdefault("entries", [])
    entries = [e for e in entries if str(e.get("run_id")) != str(args.run_id)]

    entry = {
        "run_id": str(args.run_id),
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "asset": delta_zst.name,
        "sha256": sha256(delta_zst),
        "bytes": delta_zst.stat().st_size,
        "records": len(rows),
        "before": before,
        "after": after,
    }
    entries.append(entry)

    # Keep enough history for about 30 days at four runs per day.
    manifest["entries"] = entries[-120:]
    manifest["latest_run_id"] = str(args.run_id)
    manifest["latest_after"] = after

    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(entry, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
