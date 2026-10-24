"""Check the published H3 runtime source bundle without importing model code."""
from pathlib import Path
import ast
import hashlib
import json
import re
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "snapshots/runtime_h3_20261024"


def main():
    manifest = json.loads((BUNDLE / "EXPORT_MANIFEST.json").read_text())
    errors = []
    python_files = json_files = 0
    for row in manifest["files"]:
        path = ROOT / row["file"]
        if not path.is_file() or path.is_symlink():
            errors.append({"missing_or_symlink": row["file"]})
            continue
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != row["export_sha256"] or len(data) != row["bytes"]:
            errors.append({"hash_or_size": row["file"]})
        try:
            if path.suffix == ".py":
                ast.parse(data, filename=row["file"])
                python_files += 1
            elif path.suffix == ".json":
                json.loads(data)
                json_files += 1
        except (SyntaxError, ValueError) as exc:
            errors.append({"parse": row["file"], "error": str(exc)})
    links = 0
    for name in manifest["reading_documents"]:
        doc = ROOT / name
        for target in re.findall(r"\]\(([^)]+)\)", doc.read_text()):
            if target.startswith(("https:", "http:", "mailto:", "#")):
                continue
            target = unquote(target.split("#")[0].strip("<>"))
            links += 1
            if not (doc.parent / target).resolve().exists():
                errors.append({"broken_link": name, "target": target})
    print(json.dumps({"passed": not errors, "files": len(manifest["files"]),
                      "python_syntax_checked": python_files, "json_checked": json_files,
                      "local_links_checked": links, "errors": errors}, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
