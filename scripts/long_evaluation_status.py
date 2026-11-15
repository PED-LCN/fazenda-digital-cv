"""Read local long-evaluation progress without modifying the running job."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    result = json.loads((args.output / "job.json").read_text())
    if args.archive:
        downloaded = args.archive.stat().st_size if args.archive.exists() else 0
        result["downloaded_bytes"] = downloaded
        result["download_expected_bytes"] = 8263032538
        result["download_percent"] = round(downloaded / 8263032538 * 100, 2)
    result["progress"] = {}
    for name in ["video3", "video4"]:
        summary = args.output / f"{name}.summary.json"
        progress = args.output / f"{name}.progress.json"
        if summary.exists():
            result["progress"][name] = json.loads(summary.read_text())
        elif progress.exists():
            result["progress"][name] = json.loads(progress.read_text())
        else:
            result["progress"][name] = {"status": "waiting_for_media"}
        database = args.output / f"{name}.sqlite3"
        if database.exists():
            db = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                result["progress"][name]["committed_frames"] = db.execute(
                    "SELECT count(*) FROM frames"
                ).fetchone()[0]
            except sqlite3.OperationalError:
                result["progress"][name]["database_initializing"] = True
            finally:
                db.close()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
