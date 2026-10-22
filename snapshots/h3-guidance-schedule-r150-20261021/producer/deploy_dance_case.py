"""Deploy an authorized new dance case and run CPU-only validation."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shlex
import subprocess
import tarfile

P = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", choices=["musk05", "firefly06", "sam07"])
    parser.add_argument("--host9", action="store_true")
    args = parser.parse_args()
    local = (P / "host9" if args.host9 else P) / "cases" / args.candidate
    runtime = json.loads((local / "configs/runtime.json").read_text())
    host = "H3_SERVER_A" if args.host9 else "H3_SERVER_B"
    remote = runtime["remote_root"]
    manifest = json.loads((local / "deploy_manifest.json").read_text())
    for rel, row in manifest["files"].items():
        assert hashlib.sha256((local / rel).read_bytes()).hexdigest() == row["sha256"], rel
    files = sorted(set(manifest["files"]) | {"deploy_manifest.json"} |
                   {str(f.relative_to(local)) for f in (local / "producer").glob("*") if f.is_file()})
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w:gz") as archive:
        for rel in files:
            archive.add(local / rel, arcname=rel, recursive=False)
    setup = """
import os, pathlib, sys, tarfile
root=pathlib.Path(sys.argv[1])
assert not root.exists(), 'deployment already exists'
root.mkdir(parents=True)
with tarfile.open(fileobj=sys.stdin.buffer, mode='r|gz') as archive:
    for member in archive:
        path=pathlib.PurePosixPath(member.name)
        assert not path.is_absolute() and '..' not in path.parts and member.isfile()
        archive.extract(member, root)
for name in ['logs','processes','input','output','temp','user','custom_nodes','audit/router','audit/x0']:
    (root/name).mkdir(parents=True,exist_ok=True)
import json
r=json.loads((root/'configs/runtime.json').read_text())
for folder in (root/'extensions').iterdir():
    if folder.is_dir(): (root/'custom_nodes'/folder.name).symlink_to(folder)
(root/'custom_nodes'/'ComfyUI-KJNodes').symlink_to(r['kj_nodes'])
print(json.dumps({'deployed':str(root)}))
"""
    subprocess.run(["ssh", host, "python3 -c " + shlex.quote(setup) + " " + shlex.quote(remote)],
                   input=payload.getvalue(), check=True)
    command = ("cd " + shlex.quote(remote) + " && CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 "
               + "PYTHONPATH=" + shlex.quote(runtime["dependencies"]) + " " + shlex.quote(runtime["python"])
               + " -m unittest discover -s tests -v && CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 "
               + "PYTHONPATH=" + shlex.quote(runtime["dependencies"]) + " " + shlex.quote(runtime["python"])
               + " scripts/remote_cpu_validate.py")
    with (local / "producer/TARGET_CPU_LOG.txt").open("xb") as log:
        result = subprocess.run(["ssh", host, command], stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"CPU validation failed; inspect {local / 'producer/TARGET_CPU_LOG.txt'}")
    for rel in ("audit/TARGET_CPU_VALIDATION.json", "audit/RUNTIME_IMPORT_SMOKE.json"):
        raw = subprocess.check_output(["ssh", host, "cat " + shlex.quote(remote + "/" + rel)])
        (local / rel).write_bytes(raw)
    print(json.dumps({"passed": True, "root": remote, "host": host,
                      "seal_sha256": hashlib.sha256((local / "deploy_manifest.json").read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
