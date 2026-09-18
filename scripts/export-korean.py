#!/usr/bin/env python3
import argparse
import hashlib
import os
import sqlite3
import time
from pathlib import Path


def digest(path: Path) -> bytes:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.digest()


def export_korean(source_path: Path, output_path: Path, manifest_path: Path, download_url: str):
    temp = output_path.with_name(output_path.stem + ".tmp" + output_path.suffix)
    for suffix in ("", "-journal", "-wal", "-shm"):
        Path(str(temp) + suffix).unlink(missing_ok=True)

    source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True, timeout=60)
    target = sqlite3.connect(temp)
    count = 0
    try:
        source.execute("PRAGMA cache_size=-8192")
        source.execute("BEGIN")
        target.execute("PRAGMA cache_size=-8192")

        schema = source.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type='table' AND name='HitomiColumnModel'"
        ).fetchone()
        if not schema:
            raise RuntimeError("Missing content table")

        target.execute(schema[0])

        columns = [
            row[1]
            for row in source.execute('PRAGMA table_info("HitomiColumnModel")')
        ]
        names = ", ".join(
            '"' + name.replace('"', '""') + '"' for name in columns
        )
        placeholders = ", ".join("?" for _ in columns)

        rows = source.execute(
            f"SELECT {names} FROM HitomiColumnModel "
            "WHERE lower(trim(Language)) = ?",
            ("korean",),
        )
        while True:
            batch = rows.fetchmany(1000)
            if not batch:
                break
            target.executemany(
                f"INSERT INTO HitomiColumnModel ({names}) "
                f"VALUES ({placeholders})",
                batch,
            )
            target.commit()
            count += len(batch)

        if not count:
            raise RuntimeError("No Korean articles found")

        for (sql,) in source.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type='index' "
            "AND tbl_name='HitomiColumnModel' "
            "AND sql IS NOT NULL"
        ):
            target.execute(sql)

        target.commit()
        check = target.execute("PRAGMA quick_check").fetchone()[0]
        if check != "ok":
            raise RuntimeError(f"Database validation failed: {check}")
    finally:
        target.close()
        source.close()

    changed = True
    if output_path.exists() and digest(temp) == digest(output_path):
        temp.unlink()
        changed = False
        print("Korean DB unchanged; keeping snapshot version", flush=True)
    else:
        os.replace(temp, output_path)
        manifest_tmp = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
        manifest_tmp.write_text(
            f"db {int(time.time())} {download_url}\n",
            encoding="utf-8",
        )
        os.replace(manifest_tmp, manifest_path)

    if not manifest_path.exists():
        raise RuntimeError("syncversion.txt is missing")

    version_text = manifest_path.read_text(encoding="utf-8").strip()
    print(
        f"Korean DB ready: {count:,} articles, "
        f"{output_path.stat().st_size / 1048576:.1f} MiB, "
        f"changed={changed}",
        flush=True,
    )
    print(f"syncversion: {version_text}", flush=True)

    return count, changed, version_text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--download-url", required=True)
    args = parser.parse_args()

    export_korean(
        Path(args.source),
        Path(args.output),
        Path(args.manifest),
        args.download_url,
    )


if __name__ == "__main__":
    main()
