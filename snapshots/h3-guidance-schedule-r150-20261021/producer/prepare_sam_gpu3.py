"""Bind the unstarted Sam07 batch to GPU3 after the R151 MF release."""
import hashlib
import json
from pathlib import Path
import subprocess

P = Path(__file__).resolve().parents[1]
case = P / "host9/cases/sam07"
runtime_file = case / "configs/runtime.json"
runtime = json.loads(runtime_file.read_text())
runtime.update(gpu_uuid="GPU-REDACTED",
               gpu_index=3, expected_gpu_index=3)
runtime_file.write_text(json.dumps(runtime, indent=2) + "\n")
launch_file = case / "producer/launch_case.py"
text = launch_file.read_text()
text = text.replace("a=p.parse_args()", "p.add_argument('--mf-release-sha',required=True);a=p.parse_args()")
text = text.replace(
    "peer_paths=[f'/home/researcher/h3_runs/reference_feedback_r151_20261021/cases/{x}' for x in ['short_0252','short_0358','05_real_megumi_v']]",
    "peer_paths=[f'/home/researcher/h3_runs/guidance_schedule_r150_host9_20261021/cases/{x}' for x in ['short_0085','short_0274','musk05']]")
text = text.replace("'at most one R151 peer'", "'at most one R150 GPU2 peer'")
text = text.replace("['nvidia-smi','-i','2',", "['nvidia-smi','-i','3',")
text = text.replace("v[0]=='2'", "v[0]=='3'").replace("'GPU2 capacity insufficient'", "'GPU3 capacity insufficient'")
marker = "row=subprocess.run(['nvidia-smi'"
assert text.count(marker) == 1
verify = """
mf_root=Path('/home/researcher/h3_runs/reference_feedback_mf_r151_20261021')
mf_file=mf_root/'audit/FINAL_RELEASE_VERIFIED.json'
require(sha(mf_file)==a.mf_release_sha,'R151 MF release SHA differs')
mf=read(mf_file)
for key in ['passed','all_spawned_trackers_released','exact_processes_absent','exact_CUDA_allocations_absent','peer_registrations_removed']:
 require(mf.get(key) is True,'R151 MF release incomplete: '+key)
require(mf.get('completed_generated_scores')==6,'R151 six MF results required')
require(read(mf_root/'configs/RUNTIME.json')['gpu_uuid']==service.GPU,'R151 MF GPU differs')
for bound in mf['child_release_receipts']+[mf['final_complete'],mf['seal']]:
 require(sha(Path(bound['file']))==bound['sha256'],'R151 release bound evidence differs')
for old in mf['wrapper_identities']+mf['tracker_identities']:
 actual=service.external_identity(old['pid'])
 require(actual is None or (actual['uid'],str(actual['start_ticks']),actual['cmdline_sha256'])!=(old['uid'],str(old['start_ticks']),old['cmdline_sha256']),'R151 MF exact process remains')
 require(not any(x['pid']==old['pid'] for x in rows),'R151 MF CUDA allocation remains')
predecessor={'root_release_file':str(mf_file),'root_release_sha256':sha(mf_file),'completed_generated_scores':6,'actual_release_verified':True}
"""
text = text.replace(marker, verify + "\n" + marker)
text = text.replace("'exact_R151_peers':peers", "'exact_R150_peers':peers")
text = text.replace(
    "Root explicitly authorized R150 selected dance schedules with shared conditions on host9 GPU2 after CPU and fresh admission",
    "Root authorized Sam07 six shared-condition runs on host9 GPU3 after R151 six video and six MF release; one other R150 GPU2 peer permitted")
compile(text, str(launch_file), "exec")
launch_file.write_text(text)
subprocess.run(["python3", "scripts/execution_gate.py", "seal"], cwd=case, check=True)
record = {
    "reason": "Run Sam07 on GPU3 after R151 release to shorten the generation queue",
    "previous_unstarted_root": str(P / "cases/sam07"),
    "new_local_root": str(case),
    "new_remote_root": runtime["remote_root"],
    "gpu_uuid": runtime["gpu_uuid"],
    "roles": ["native", "fixed", "early", "late", "split", "global_weak"],
    "seal_sha256": hashlib.sha256((case / "deploy_manifest.json").read_bytes()).hexdigest(),
    "required_prior_release": "/home/researcher/h3_runs/reference_feedback_mf_r151_20261021/audit/FINAL_RELEASE_VERIFIED.json",
    "gpu_launch_performed": False,
}
(case / "producer/GPU3_HANDOFF.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record))
