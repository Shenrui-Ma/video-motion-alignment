"""Run the sealed collector unchanged, filtering only bulky remote telemetry."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import time

EXCLUDES = ["RESOURCE_OBSERVATIONS.json", "*.jsonl", "*.log"]


def main(batch):
    root = Path(batch).resolve()
    original = root / "audit/collect.py"
    original_sha = hashlib.sha256(original.read_bytes()).hexdigest()
    original_run = subprocess.run
    transfers = []

    def run(command, *args, **kwargs):
        if isinstance(command, list) and command[0] == "rsync":
            filtered = command[:1] + ["--itemize-changes", "--out-format=%i %n%L"]
            for pattern in EXCLUDES:
                filtered += ["--exclude", pattern]
            filtered += command[1:]
            result = original_run(filtered, *args, **kwargs)
            transfers.append(dict(
                command=filtered, returncode=result.returncode,
                copied_files=result.stdout.splitlines(), stderr=result.stderr,
            ))
            return result
        return original_run(command, *args, **kwargs)

    try:
        subprocess.run = run
        runpy.run_path(str(original), run_name="__main__")
    finally:
        subprocess.run = original_run
        assert hashlib.sha256(original.read_bytes()).hexdigest() == original_sha
        (root / "audit/COLLECTION_FILTERS.json").write_text(json.dumps(dict(
            unix=time.time(), original_collector_sha256=original_sha,
            excluded_patterns=EXCLUDES, remote_originals_preserved=True,
            transfers=transfers,
        ), ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", required=True)
    main(parser.parse_args().batch)
