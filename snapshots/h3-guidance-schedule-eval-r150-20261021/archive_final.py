"""Archive the completed delivery over DIRECT SSH without copying source media."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile

from common import ROOT, bound, read, require, verify_record, write


def prepare():
    qa = read(ROOT / "audit/SHOWCASE_SOURCE_QA.json")
    require(qa["final"] is True and qa["embedded"] is True,
            "Build the verified final embedded showcase before archiving")
    require(qa["tasks"] == 10 and qa["independent_sources"] == 9,
            "Unexpected final task/source counts")
    verify_record(qa["html"])
    final_html = Path(qa["html"]["file"])
    require(final_html.parent == ROOT, "Final HTML must be the evaluation output")
    for record in qa["media_evidence"]:
        verify_record(record)

    files = {}
    for path in ROOT.rglob("*"):
        if (not path.is_file() or path.is_symlink()
                or "final_archive" in path.relative_to(ROOT).parts
                or path.name == "RESOURCE_OBSERVATIONS.json"):
            continue
        if path.suffix in {".py", ".js", ".css", ".json", ".md"} or path.name.endswith("_template.html"):
            files["evaluation/" + str(path.relative_to(ROOT))] = path
    files["delivery/" + final_html.name] = final_html
    # Retain the exact reused generator and old three-case records as small files.
    for old_name in ("h3-guidance-schedule-eval-r149-20261020",
                     "h3-timing-phase-combined-eval-r148-20261020"):
        old = ROOT.with_name(old_name)
        for path in old.iterdir():
            if path.is_file() and path.suffix in {".py", ".json"}:
                files["dependencies/" + old_name + "/" + path.name] = path
    for record in qa["media_evidence"]:
        path = Path(record["file"])
        if not path.is_relative_to(ROOT) and path.suffix == ".json":
            project = next(p for p in path.parents if p.parent == ROOT.parent)
            files["dependencies/" + project.name + "/" + str(path.relative_to(project))] = path

    records = [{"archive_path": name, "original_file": str(path),
                "sha256": bound(path)["sha256"], "bytes": path.stat().st_size}
               for name, path in sorted(files.items())]
    out = ROOT / "audit/final_archive" / qa["html"]["sha256"][:16]
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": "r150-final-delivery-archive-v1", "html": qa["html"],
                "qa": bound(ROOT / "audit/SHOWCASE_SOURCE_QA.json"),
                "files": records,
                "scope": "Page code, evaluation JSON and embedded final HTML; no separate video, tensor or model files."}
    manifest_path = out / "ARCHIVE_MANIFEST.json"
    if manifest_path.exists():
        require(read(manifest_path) == manifest, "Archive inputs changed after preparation")
    else:
        write(manifest_path, manifest)
    bundle = out / "delivery.tar.gz"
    if not bundle.exists():
        with tarfile.open(bundle, "w:gz") as archive:
            archive.add(manifest_path, arcname="ARCHIVE_MANIFEST.json")
            for name, path in sorted(files.items()):
                archive.add(path, arcname=name, recursive=False)
    return out, manifest, bundle


def upload(out, manifest, bundle):
    sys.path.insert(0, str(ROOT / "mf_preparation"))
    from deploy_host60_cpu import SSH, HOST, PYTHON, BASE, remote
    destination = BASE + "/delivery/" + manifest["html"]["sha256"][:16]
    remote("from pathlib import Path\nPath(" + repr(destination) +
           ").mkdir(parents=True,exist_ok=True)\n")
    subprocess.run(["rsync", "-a", "-e",
                    "ssh -o ProxyCommand=none -o BatchMode=yes",
                    str(bundle), HOST + ":" + destination + "/delivery.tar.gz"], check=True)
    code = """
import hashlib,json,tarfile
from pathlib import Path
root=Path(DESTINATION)
bundle=root/'delivery.tar.gz'
assert hashlib.sha256(bundle.read_bytes()).hexdigest()==BUNDLE_SHA
with tarfile.open(bundle) as archive:
    for item in archive.getmembers():
        assert item.isfile() and not item.issym() and not item.islnk()
        assert (root/item.name).resolve().is_relative_to(root.resolve())
    archive.extractall(root)
manifest=json.loads((root/'ARCHIVE_MANIFEST.json').read_text())
for item in manifest['files']:
    p=root/item['archive_path']
    assert p.stat().st_size==item['bytes']
    assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],item['archive_path']
receipt={'passed':True,'remote_root':str(root),'files_verified':len(manifest['files']),
         'bundle_sha256':BUNDLE_SHA,'final_html_sha256':manifest['html']['sha256'],
         'final_html':str(root/'delivery'/Path(manifest['html']['file']).name)}
(root/'ARCHIVE_VERIFIED.json').write_text(json.dumps(receipt,indent=2)+'\\n')
print(json.dumps(receipt))
""".replace("DESTINATION", repr(destination)).replace("BUNDLE_SHA", repr(bound(bundle)["sha256"]))
    receipt = json.loads(remote(code))
    write(out / "REMOTE_ARCHIVE_VERIFIED.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--upload", action="store_true")
    args = parser.parse_args()
    output, manifest, bundle = prepare()
    if args.upload:
        upload(output, manifest, bundle)
    else:
        print(json.dumps({"bundle": bound(bundle), "files": len(manifest["files"])}))
