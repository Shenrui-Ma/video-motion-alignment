"""Close existing R42 observation inputs, retaining the separate final-seal hold."""
import ast,hashlib,json,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[2]
P=R.parent/'h3-timing-source28289-native-r42-20261017'
OLD=R.parent/'h3-timing-auto-source51310-r40-20261017'
A=P/'analysis/postrun/captured/batch'
POSE=A/'source_pose/source_28289_video/source_28289_video.pose.json'
EXPECTED='20d6079ec8eb3e9824f599a23447bc122c49d796289f4408345eda4e3645946c'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
assert sha(POSE)==EXPECTED
pose=read(POSE);assert len(pose['frames'])==141 and pose['video']['sha256']==read(R/'configs/input_hashes.json')['source_28289_video.mp4']
assert [x['frame'] for x in pose['frames']]==list(range(141))
assert all(abs(x['time_s']-i/24)<1e-8 for i,x in enumerate(pose['frames']))
saved=R/'audit/preparation/pre_source_pose_binding';saved.mkdir()
for rel in ('PROTOCOL.DRAFT.json','configs/protocol.json','configs/PARENT_CLOSURE.json','extensions/H3AutomaticWindowRouter/transport.py'):
 dest=saved/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(R/rel,dest)
shutil.copyfile(POSE,R/'configs/source.pose.json')
shutil.copyfile(POSE.parent/'SOURCE_FILES.json',R/'configs/source_pose_files.json')
e=read(R/'configs/parent_evidence_bindings.json')
for name,src in [('source.pose.json',POSE),('source_pose_files.json',POSE.parent/'SOURCE_FILES.json')]:
 e[name]={'source':str(src),'archive_relative':str(src.relative_to(A)),'sha256':sha(src),'bytes':src.stat().st_size}
put(R/'configs/parent_evidence_bindings.json',e)
p=read(R/'configs/protocol.json');p['schema']='r44-source28289-auto-transfer-v1'
p['scope']='Source28289 green-background gestures, Elon Musk identity, seed2026101701; frozen R40 automatic policy and Full operator, bound to actual R42 Native. Full141 scan; no human action window.'
p['preparation_status']='SCIENCE_FROZEN_ACTUAL_PARENT_AND_SOURCE_BOUND'
p['observer']['source_pose_sha256']=EXPECTED
p['prefix']['availability']='Actual R42 RUN_GATE/RUNTIME_GATE/inventory attest Native0..19 plus final; actual source pose is byte-bound. Parent final media inventory must close before deployment seal.'
p['prefix']['historical_limit']='R42 did not save full processed/postaugmentation tree or packed sampler inputs. Eight actual clean-condition entities, exact noise and21 Native endpoint archive are bound; no missing historical object is inferred.'
put(R/'configs/protocol.json',p);put(R/'PROTOCOL.json',p)
put(R/'FREEZE.json',{'schema':'r44-scientific-freeze-v1','files':{'PROTOCOL.json':sha(R/'PROTOCOL.json')},'no_GPU_authorized':True})
text=(R/'extensions/H3AutomaticWindowRouter/transport.py').read_text();tree=ast.parse(text)
node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='PROTOCOL_SHA' for x in n.targets))
lines=text.splitlines(keepends=True);lines[node.lineno-1]='PROTOCOL_SHA='+repr(sha(R/'configs/protocol.json'))+'\n';(R/'extensions/H3AutomaticWindowRouter/transport.py').write_text(''.join(lines))
numbers=read(R/'audit/preparation/NUMERICAL_INHERITANCE.json')['exact_numerical_files']
assert len(numbers)==17
for rel,digest in numbers.items():assert sha(R/rel)==sha(OLD/rel)==digest,rel
spec={'schema':'r44-kernel-implementation-inheritance-v1','parent_root':'/data5/researcher/h3_runs/timing_auto_source51310_r40_20261017','parent_deploy_manifest_sha256':sha(OLD/'deploy_manifest.json'),'parent_protocol_sha256':sha(OLD/'configs/protocol.json'),'exact_numerical_files':numbers,'inherited_scope':'Numerical implementation only. R44 actual87366 layout requires a new root-run model-free kernel gate; old87361 layout does not certify this case.'}
put(R/'configs/kernel_inheritance.json',spec)
b=read(OLD/'configs/observer_bindings.json');b['schema']='r44-frozen-auto-window-bindings-v1'
b['local_files']={rel:sha(R/rel) for rel in b['local_files'] if (R/rel).is_file()}
for rel in ('configs/parent_evidence_bindings.json','configs/parent_layout.json','configs/source_pose_files.json','configs/source_input_probe.json','configs/source_selection.json'):
 b['local_files'][rel]=sha(R/rel)
put(R/'configs/observer_bindings.json',b)
c=read(R/'configs/PARENT_CLOSURE.json');c['schema']='r44-actual-parent-closure-v1';c['ready']=True;c['status']='READY';c['actual_source_pose_sha256']=EXPECTED;c['remaining_required_files']=[];c['actual_file_sha256']={rel:sha(R/rel) for rel in c['required_actual_files']};c['final_archive_ready']=False;c['final_archive_note']='Root final R42 postrun inventory/download still pending; prepare and CPU only, final bundle guard remains closed.'
put(R/'configs/PARENT_CLOSURE.json',c)
template=read(R/'configs/RESOURCE_ADMISSION_TEMPLATE.json');template.update(kernel_gate_sha256=None,protocol_sha256=sha(R/'configs/protocol.json'),inheritance_sha256=sha(R/'configs/r27_inheritance.json'),kernel_inheritance_sha256=sha(R/'configs/kernel_inheritance.json'));put(R/'configs/RESOURCE_ADMISSION_TEMPLATE.json',template)
report={'schema':'r44-source-pose-binding-v1','source_pose_sha256':EXPECTED,'source_video_sha256':pose['video']['sha256'],'frames':141,'runtime_parent_inputs_ready':True,'parent_final_media_closure_ready':False,'new_inference':0,'new_pose':0,'new_GPU':False,'new_kernel_layout':87366,'science_protocol_sha256':sha(R/'PROTOCOL.json'),'observer_bindings_sha256':sha(R/'configs/observer_bindings.json'),'numerical_files_unchanged':17}
put(R/'audit/preparation/SOURCE_POSE_BINDING.json',report)
print(json.dumps(report))
