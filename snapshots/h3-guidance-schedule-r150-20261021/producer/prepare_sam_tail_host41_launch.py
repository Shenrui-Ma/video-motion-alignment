"""Create the existing host41 launch entry with a cross-host Native receipt."""
from pathlib import Path

P = Path(__file__).resolve().parents[1]
T = P / "sam_tail_host41/cases/sam07"
text = (P / "cases/firefly06/producer/launch_case.py").read_text()
marker = "row=subprocess.run(['nvidia-smi'"
check = '''
require(str(pr)=="/data4/researcher/h3_runs/guidance_schedule_r150_20261021/cases/firefly06",
        "Sam tail requires Firefly actual release")
proof_file=ROOT/'audit/PREFIX_NATIVE_EVIDENCE.json'
proof=read(proof_file)
require(time.time()-proof['observed_unix'] < 300,'refresh cross-host Native evidence before launch')
manifest=read(ROOT/'configs/MIGRATION_MANIFEST.json')
require(proof['prefix_seal_sha256']==manifest['prefix_producer_seal_sha256'],
        'running prefix seal differs')
require(proof['prefix_manifest_sha256']==manifest['prefix_bound_manifest_sha256'],
        'running prefix partition differs')
require(proof['prefix_allowed_roles']==['native','fixed','early','late'] and
        proof['prefix_tail_runs_absent'] and proof['old_tail_never_started'] and
        proof['old_tail_launch_retired'], 'tail has another initialized execution')
import base64
files={}
for name,item in proof['files'].items():
 raw=base64.b64decode(item['base64'])
 require(hashlib.sha256(raw).hexdigest()==item['sha256'],'Native evidence bytes differ: '+name)
 files[name]=json.loads(raw)
from native_review_gate import validate_review
request=files['request'];native_review=files['review'];native_release=files['release'];gate=files['gate']
validate_review(native_review,request)
require(request['source_id']=='sam07' and
        request['run_id']=='r150_sam07_seed2026101311_native' and
        request['producer_seal_sha256']==manifest['prefix_producer_seal_sha256'],
        'Native request differs')
require(native_release['passed'] and
        native_release['request_sha256']==proof['files']['request']['sha256'] and
        native_release['review_sha256']==proof['files']['review']['sha256'] and
        request['native_gate_sha256']==proof['files']['gate']['sha256'] and
        gate['passed'] and gate['video']['sha256']==request['video_sha256'],
        'Native visual release incomplete')
'''
assert text.count(marker) == 1
text = text.replace(marker, check + "\n" + marker)
text = text.replace("'predecessor_release_verified':True,",
                    "'predecessor_release_verified':True,'Native_prefix_evidence':{'file':str(proof_file),'sha256':sha(proof_file)},")
text = text.replace("Root explicitly authorized R150 selected dance schedules with shared conditions after CPU and fresh admission",
                    "Root authorized only Sam07 split/global on GPU0 after Firefly exact release and cross-host matching-cache Native visual approval")
compile(text, "sam_tail_host41_launch.py", "exec")
(T / "producer/launch_case.py").write_text(text)
