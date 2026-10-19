"""Additive outer binding only. Call after both second-seed Native CPU gates pass."""
import copy,difflib,hashlib,json,time
from pathlib import Path
P=Path(__file__).resolve().parent
R=P.parent/'postrun'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write_new(p,s):
 with p.open('x') as f:f.write(s)
seed=2026101611
protocol=copy.deepcopy(read(P/'PROTOCOL.json'))
protocol['frozen_unix']=time.time()
protocol['scope']='R24 second-seed native005 coarse readout; additive binding; both preselected sources and all original windows, primitives and thresholds retained.'
protocol['parent_protocol_sha256']=sha(P/'PROTOCOL.json')
protocol['analysis_comparison']='Record accepted lag>=4 as would-trigger-coarse-start. Final pose is descriptive endpoint context, not independent native005 truth; include both sources regardless of final timing.'
for cid,cp in protocol['cases'].items():
 run=f'r24_{cid}_seed{seed}_native';arc=R/'captured'/run
 if not read(arc/'RUN_GATE.json')['passed'] or not read(arc/'CPU_COMPLETE.json')['passed']:raise RuntimeError('Actual Native CPU gate incomplete: '+run)
 inv=read(arc/'FILE_INVENTORY.json');condpath=arc/'audit'/f'{run}_conditioning.json';cond=read(condpath)
 v=cond['native_vae_calls'][1]['latent'];ref='audit/'+v['tensor_file'];snapshot=f'audit/x0/{run}/x0_step005.pt'
 cp.update(run_id=run,run_gate_sha256=sha(arc/'RUN_GATE.json'),CPU_COMPLETE_sha256=sha(arc/'CPU_COMPLETE.json'),inventory_sha256=sha(arc/'FILE_INVENTORY.json'),condition_sha256=sha(condpath),snapshot_path=snapshot,snapshot_file_sha256=inv[snapshot]['sha256'],reference_path=ref,reference_file_sha256=inv[ref]['sha256'],reference_tensor={k:v[k] for k in ['shape','dtype','sha256']})
 cp.pop('normal_final_motion_status',None)
 if read(arc/'RUN_GATE.json')['case']['video_sha256']!=cp['source_video_sha256']:raise RuntimeError('source changed')
# Only output/config filenames change in the previously reviewed wrapper.
original=(P/'evaluate.py').read_text();derived=original
for old,new in [('RESULTS.json','RESULTS_seed2026101611.json'),('PROTOCOL.json','PROTOCOL_seed2026101611.json'),('FREEZE.json','FREEZE_seed2026101611.json')]:derived=derived.replace(old,new)
compile(derived,'evaluate_seed2026101611.py','exec')
files={'PROTOCOL_seed2026101611.json':json.dumps(protocol,indent=2)+'\n','evaluate_seed2026101611.py':derived,'wrapper_seed2026101611.diff':''.join(difflib.unified_diff(original.splitlines(True),derived.splitlines(True),fromfile='evaluate.py',tofile='evaluate_seed2026101611.py'))}
for n,s in files.items():write_new(P/n,s)
frozen={'frozen_unix':time.time(),'files':{n:sha(P/n) for n in ['PROTOCOL_seed2026101611.json','observer_frozen.py','observer_protocol.json','evaluate_seed2026101611.py']},'parent_freeze_sha256':sha(P/'FREEZE.json'),'change':'Only current actual second-seed case/input binding and artifact filenames. All five pure primitives, reject rules, windows and lag range are unchanged. Inputs selected by fixed queue, not generated outcome.'}
write_new(P/'FREEZE_seed2026101611.json',json.dumps(frozen,indent=2)+'\n')
print(json.dumps({'protocol_sha256':sha(P/'PROTOCOL_seed2026101611.json'),'freeze_sha256':sha(P/'FREEZE_seed2026101611.json'),'script_sha256':sha(P/'evaluate_seed2026101611.py')}))
