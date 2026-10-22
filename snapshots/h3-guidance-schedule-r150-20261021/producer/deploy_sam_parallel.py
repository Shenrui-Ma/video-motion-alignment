"""Deploy two CPU-checked queue segments without launching either GPU service."""
from pathlib import Path
import hashlib
import io
import json
import shlex
import shutil
import subprocess
import tarfile

P = Path(__file__).resolve().parents[1]
S = P / "host9/cases/sam07"
H = P / "sam_parallel_host9"
T = H / "cases/sam07"
old = json.loads((H / "PREPARED_SIX_ROLE_SOURCE/deploy_manifest.json").read_text())
deployment = json.loads((H / "MIGRATION_DEPLOYMENT.json").read_text())
prefix_seal = deployment["segments"]["prefix"]["producer_seal_sha256"]
prefix_remote = deployment["segments"]["prefix"]["remote_root"]
tail_remote = deployment["segments"]["tail"]["remote_root"]

for name in ("check_fresh_paths.py", "watch_queue.py"):
    shutil.copy2(S / "producer" / name, T / "producer" / name)
text = (S / "producer/launch_case.py").read_text()
text = text.replace("['short_0085','short_0274','musk05']]",
                    "['short_0085','short_0274','musk05']]+[" + repr(tail_remote) + "]")
text = text.replace("Sam07 six shared-condition runs", "Sam07 first four shared-condition runs")
(S / "producer/launch_case.py").write_text(text)

text = (P / "host9/cases/musk05/producer/launch_case.py").read_text()
start = text.index("peer_paths=")
end = text.index("\npeers=", start)
text = text[:start] + "peer_paths=[" + repr(prefix_remote) + "]" + text[end:]
marker = "row=subprocess.run(['nvidia-smi'"
check = '''
require(a.predecessor_root == "/home/researcher/h3_runs/guidance_schedule_r150_host9_20261021/cases/musk05",
        "tail requires actual completed Musk predecessor")
prefix=Path(PREFIX_ROOT)
require(sha(prefix/'deploy_manifest.json')==PREFIX_SEAL,'prefix seal differs')
require(read(prefix/'configs/execution_segment.json')['allowed_roles']==['native','fixed','early','late'],
        'source still permits copied tail roles')
require(read(prefix/'configs/MIGRATION_MANIFEST.json')==read(ROOT/'configs/MIGRATION_MANIFEST.json'),
        'partition differs')
native_request=read(prefix/'audit/NATIVE_VISUAL_REVIEW_REQUEST.json')
native_review=read(prefix/'audit/NATIVE_VISUAL_REVIEW.json')
native_release=read(prefix/'audit/NATIVE_VISUAL_REVIEW_RELEASE.json')
from native_review_gate import validate_review
validate_review(native_review,native_request)
require(native_request['producer_seal_sha256']==PREFIX_SEAL and
        native_release['passed'] and
        native_release['request_sha256']==sha(prefix/'audit/NATIVE_VISUAL_REVIEW_REQUEST.json') and
        native_release['review_sha256']==sha(prefix/'audit/NATIVE_VISUAL_REVIEW.json'),
        'matching-cache Native visual approval incomplete')
native_gate=Path(native_request['native_gate'])
require(sha(native_gate)==native_request['native_gate_sha256'] and
        read(native_gate)['video']['sha256']==native_request['video_sha256'],
        'Native approval video differs')
for role in ['split','global_weak']:
 run='r150_sam07_seed2026101311_'+role
 require(not any((prefix/rel).exists() for rel in [
  'logs/'+run+'_job.json','audit/router/'+run+'.json',
  'analysis/postrun/sam07/'+run+'_GATE.json']), 'source already initialized a tail role')
native_evidence={'prefix_seal':PREFIX_SEAL,'gate_sha256':sha(native_gate),
 'review_release_sha256':sha(prefix/'audit/NATIVE_VISUAL_REVIEW_RELEASE.json')}
'''.replace("PREFIX_ROOT", repr(prefix_remote)).replace("PREFIX_SEAL", repr(prefix_seal))
assert text.count(marker) == 1
text = text.replace(marker, check + "\n" + marker)
text = text.replace("'exact_R151_peers':peers,", "'exact_Sam_prefix_peers':peers,'Native_visual_approval':native_evidence,")
text = text.replace("R150 selected dance schedules with shared conditions on host9 GPU2 after CPU and fresh admission",
                    "Sam07 tail split/global on GPU2 after Musk actual release and matching-cache Native visual approval")
compile(text, "tail_launch_case.py", "exec")
(T / "producer/launch_case.py").write_text(text)

for root, name in ((S, "prefix"), (T, "tail")):
    runtime = json.loads((root / "configs/runtime.json").read_text())
    remote = runtime["remote_root"]
    manifest = json.loads((root / "deploy_manifest.json").read_text())
    if name == "prefix":
        changed = {p for p in manifest["files"] if old["files"].get(p) != manifest["files"][p]}
        files = sorted(changed | {"deploy_manifest.json", "producer/launch_case.py"})
    else:
        files = sorted(set(manifest["files"]) | {"deploy_manifest.json"} |
                       {str(p.relative_to(root)) for p in (root / "producer").glob("*") if p.is_file()})
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w:gz") as archive:
        for rel in files:
            archive.add(root / rel, arcname=rel, recursive=False)
    setup = '''
import hashlib,json,pathlib,sys,tarfile
root=pathlib.Path(sys.argv[1]);mode=sys.argv[2]
if mode=='prefix':
 assert hashlib.sha256((root/'deploy_manifest.json').read_bytes()).hexdigest()=='ebd1cf87931a379cac0a0bbfd3c152257fec8361022813547c123604b4a166a3'
 assert not (root/'processes/service.json').exists()
 assert not list((root/'audit/x0').glob('*'))
 archive=root/'audit/PRE_PLANNED_PARTITION';archive.mkdir(exist_ok=False)
else:
 root.mkdir(parents=True,exist_ok=False)
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|gz') as tar:
 for member in tar:
  rel=pathlib.PurePosixPath(member.name)
  assert not rel.is_absolute() and '..' not in rel.parts and member.isfile()
  old=root/str(rel)
  if mode=='prefix' and old.exists():
   saved=archive/str(rel);saved.parent.mkdir(parents=True,exist_ok=True);old.rename(saved)
  tar.extract(member,root)
if mode=='prefix':
 for rel in ['audit/TARGET_CPU_VALIDATION.json','audit/RUNTIME_IMPORT_SMOKE.json']:
  p=root/rel
  if p.exists():q=archive/rel;q.parent.mkdir(parents=True,exist_ok=True);p.rename(q)
else:
 for rel in ['logs','processes','input','output','temp','user','custom_nodes','audit/router','audit/x0']:
  (root/rel).mkdir(parents=True,exist_ok=True)
 r=json.loads((root/'configs/runtime.json').read_text())
 for p in (root/'extensions').iterdir():
  if p.is_dir():(root/'custom_nodes'/p.name).symlink_to(p)
 (root/'custom_nodes/ComfyUI-KJNodes').symlink_to(r['kj_nodes'])
print(json.dumps({'root':str(root),'seal':hashlib.sha256((root/'deploy_manifest.json').read_bytes()).hexdigest()}))
'''
    subprocess.run(["ssh", runtime["host"], "python3 -c " + shlex.quote(setup) + " " +
                    shlex.quote(remote) + " " + name], input=payload.getvalue(), check=True)
    env = "CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=" + shlex.quote(runtime["dependencies"])
    command = ("cd " + shlex.quote(remote) + " && " + env + " " +
               shlex.quote(runtime["python"]) + " -m unittest discover -s tests -v && " +
               env + " " + shlex.quote(runtime["python"]) + " scripts/remote_cpu_validate.py")
    with (root / "producer/PARALLEL_CPU_LOG.txt").open("x") as log:
        subprocess.run(["ssh", runtime["host"], command], stdout=log, stderr=subprocess.STDOUT, check=True)
    for rel in ("audit/TARGET_CPU_VALIDATION.json", "audit/RUNTIME_IMPORT_SMOKE.json"):
        (root / rel).write_bytes(subprocess.check_output(
            ["ssh", runtime["host"], "cat " + shlex.quote(remote + "/" + rel)]))
    print(json.dumps({"CPU_passed": True, "segment": name,
                      "seal": hashlib.sha256((root / "deploy_manifest.json").read_bytes()).hexdigest()}),
          flush=True)
