import json,shutil,hashlib,copy
from pathlib import Path
R=Path(__file__).resolve().parents[1];P=R.parent/'h3-timing-auto-controller-r27-20261017';OLD=R.parent/'h3-timing-fixed-early-global-r34-20261017';A=P/'analysis/postrun/captured/r27_s05_normal1313_auto';D=R/'design'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
proto=read(D/'PROTOCOL.json');run=proto['planned_run_id'];seed=proto['case']['seed'];remote='/data5/researcher/h3_runs/timing_normal_early_control_r37_20261017';oldrun='r34_source40372_seed2026101701_global_full_index4'
for folder in ('scripts','extensions','tests'):
 if (R/folder).exists():raise RuntimeError('initial creation only')
 shutil.copytree(OLD/folder,R/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for folder in ('configs','inputs'): (R/folder).mkdir(exist_ok=True)
# Administrative imports/paths only; numerical core/static plan copied byte-for-byte.
for folder in ('scripts','extensions','tests'):
 for f in (R/folder).rglob('*.py'):
  if f.relative_to(R).as_posix() in ['extensions/H3StaticWindowRouter/core.py','extensions/H3StaticWindowRouter/static_plan.py']:continue
  s=f.read_text().replace('r34_contract','r37_contract').replace('timing_fixed_early_global_r34_20261017','timing_normal_early_control_r37_20261017').replace(oldrun,run).replace('r34_source_40372_shared','r37_source_05_real_megumi_shared').replace('8498','8499').replace('2026101701','2026101313').replace('actual_seed1701','actual_seed1313').replace('a4a2a5b766f4118813c561605242ece893726ec24f96a8556526e5b46ac9ad13',sha(D/'PROTOCOL.json'))
  f.write_text(s)
(R/'scripts/r34_contract.py').rename(R/'scripts/r37_contract.py')
shutil.copy2(D/'PROTOCOL.json',R/'PROTOCOL.json')
parentfiles={'parent_graph.json':P/'configs/r27_s05_normal1313_auto.json','parent_captures.json':A/'audit/x0/r27_s05_normal1313_auto/manifest.json','parent_conditioning.json':A/'audit/r27_s05_normal1313_auto_conditioning.json','parent_noise.json':A/'audit/r27_s05_normal1313_auto_noise.json','parent_file_inventory.json':A/'FILE_INVENTORY.json','parent_run_gate.json':A/'RUN_GATE.json','parent_runtime_gate.json':A/'RUNTIME_GATE.json','parent_decision_ledger.json':A/'DECISION_LEDGER.json','parent_actual_history.json':A/'logs/r27_s05_normal1313_auto_history.json','source.pose.json':P/'configs/source.pose.json','parent_core_hashes.json':P/'configs/parent_core_hashes.json','parent_runtime_provenance.json':P/'configs/parent_runtime_provenance.json','model_hashes_host9.json':P/'configs/model_hashes_host9.json','inherited_actual87592_kernel.json':P/'audit/gpu_dynamic_union_gate.json'}
for name,path in parentfiles.items():shutil.copy2(path,R/'configs'/name)
put(R/'configs/parent_actual_condition_tree.json',read(D/'COMPARABILITY.json')['parent_actual_conditioning_tree'])
inputs={proto['case']['reference_video']:proto['case']['reference_video_sha256'],proto['case']['portrait']:proto['case']['portrait_sha256']}
for name,h in inputs.items():
 src=R.parent/'h3-timing-window-location-r33-20261017/inputs'/name
 assert sha(src)==h;shutil.copy2(src,R/'inputs'/name)
put(R/'configs/input_hashes.json',inputs)
for name in ('admission.json','runtime.json','scientific_contract.json','kernel_provenance.json'):
 v=read(OLD/'configs'/name);s=json.dumps(v).replace(oldrun,run).replace('2026101701','2026101313').replace('r34-','r37-').replace('8498','8499').replace('timing_fixed_early_global_r34_20261017','timing_normal_early_control_r37_20261017').replace('a4a2a5b766f4118813c561605242ece893726ec24f96a8556526e5b46ac9ad13',sha(D/'PROTOCOL.json'));put(R/'configs'/name,json.loads(s))
put(R/'configs/queue.json',{'jobs':[run],'finalize':False})
put(R/'configs/kernel_inheritance.json',{'parent_root':'/data5/researcher/h3_runs/timing_auto_controller_r27_20261017','parent_manifest_sha256':sha(P/'audit/deploy_manifest_v2.json'),'parent_protocol_sha256':sha(P/'configs/protocol.json'),'kernel_gate_sha256':sha(P/'audit/gpu_dynamic_union_gate.json'),'scope':'Actual R27 same87592/full42bin kernel evidence with identical numerical source. No current H3 forward, memory, condition, or prefix trajectory result is inherited.'})
k=read(OLD/'configs/resource_admission_template.json');k.update(schema='r37-root-resource-admission-v1',protocol_sha256=sha(D/'PROTOCOL.json'),kernel_gate_sha256=sha(P/'audit/gpu_dynamic_union_gate.json'),kernel_inheritance_sha256=sha(R/'configs/kernel_inheritance.json'));put(R/'configs/resource_admission_template.json',k)
# Specific normal source registry; actual graph transformation is frozen and explicit.
f=R/'scripts/r37_contract.py';s=f.read_text().replace("{'source_id':'40372'}","{'source_id':'05_real_megumi'}").replace('R34','R37').replace('actual R26 parent','actual R27 normal parent');f.write_text(s)
f=R/'extensions/H3PairAudit/__init__.py';f.write_text(f.read_text().replace("'r34_source_'","'r37_source_'").replace('R34','R37'))
f=R/'scripts/prelaunch_gates.py';f.write_text(f.read_text().replace('87361','87592').replace('r34-root','r37-root'))
f=R/'tests/test_evidence.py';f.write_text(f.read_text().replace('87361','87592').replace('actual_R26','actual_R27'))
import sys
sys.path.insert(0,str(R/'scripts'));import r37_contract as c
assert c.RUN_ID==run and c.SEED==seed
new=c.expected_graph(R);put(R/'configs/graphs'/f'{run}.json',new)
put(R/'configs/job_registry.json',{'jobs':{run:{'seed':seed,'arm':'static_global','case':{'source_id':'05_real_megumi'},'graph_sha256':sha(R/'configs/graphs'/f'{run}.json')}}})
rels=['PROTOCOL.json']+[str(x.relative_to(R)) for x in D.iterdir() if x.is_file()]+['configs/'+x for x in parentfiles]+['configs/parent_actual_condition_tree.json','configs/input_hashes.json']
put(R/'configs/evidence_hashes.json',{r:sha(R/r) for r in rels})
parent=read(R/'configs/parent_graph.json');diff=[]
def walk(a,b,path=''):
 if type(a)!=type(b):diff.append({'path':path,'old':a,'new':b});return
 if isinstance(a,dict):
  for k in sorted(set(a)|set(b)):
   if k not in a or k not in b:diff.append({'path':path+'/'+k,'old':a.get(k),'new':b.get(k)})
   else:walk(a[k],b[k],path+'/'+k)
 elif a!=b:diff.append({'path':path,'old':a,'new':b})
walk(parent,new)
put(R/'configs/GRAPH_DIFF.json',{'parent_graph_sha256':sha(R/'configs/parent_graph.json'),'actual_new_graph_sha256':sha(R/'configs/graphs'/f'{run}.json'),'diff':diff,'all42bins':True,'actual_layout_seq_len':87592,'historical_prefix':'actual R27 normal Native0..4 tensor + same-input signatures','historical_unavailable':['raw packed input4 tensor entity'],'full_condition_tree':'actual R27 original+processed signature tree; exactly two corresponding UUID leaves canonicalized'})
print('prepared',run,len(diff),'graph leaf changes')
