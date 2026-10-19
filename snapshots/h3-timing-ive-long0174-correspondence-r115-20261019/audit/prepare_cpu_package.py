from pathlib import Path
import json,hashlib,copy,shutil
P=Path(__file__).resolve().parents[1];B=P.parent;A=B/'h3-timing-ive-long0174-correspondence-r112-20261019';L=B/'h3-timing-oxygen-seed-replication-r113-20261019'
def rd(p):return json.loads(p.read_text())
def wr(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
# Rebind lifecycle code only. Frozen numerical files are overwritten from R112 below.
for folder in ['scripts','audit']:
 for p in (P/folder).glob('*.py'):
  if p.name=='prepare_cpu_package.py':continue
  p.write_text(p.read_text().replace('r113','r115').replace('R113','R115'))
(P/'scripts/r115_contract.py').unlink(missing_ok=True)
(P/'scripts/r113_contract.py').unlink(missing_ok=True)
for rel in ['extensions/H3TemporalRouter/core.py','extensions/H3TemporalRouter/correspondence.py','extensions/H3TemporalRouter/layout.py','extensions/H3X0Readout/core.py','scripts/int8_row_chunking.py','scripts/compatibility_bootstrap.py','scripts/backend_dispatch_audit.py']:
 shutil.copy2(A/rel,P/rel)
# Node wrappers call one local contract; tensor operations stay unchanged.
for p in (P/'extensions').rglob('__init__.py'):
 p.write_text(p.read_text().replace('r112_contract','r115_contract').replace("'r112_'","'r115_'"))
rt=rd(L/'configs/runtime.json');rt.update(remote_root='/home/researcher/h3_runs/timing_ive_long0174_correspondence_r115_20261019',port=8577,profile='host9_gpu0_r115_normal_reserve8',profile_scope='Two same-host correspondence controls; historical R96 Native retained as cross-host reference, environment differences recorded only.')
wr(P/'configs/runtime.json',rt)
s=rd(A/'configs/scientific_contract.json');s.update(schema='r115-two-arm-host9-correspondence-v1',scope_note='Two new same-host operators. Existing R96 Native retained with its original environment; no extra Native or environment-effect experiment.',prefix_semantics='Actual first6 AV predictions agree between new arms. Historical cross-host prefix equality is not an execution condition.')
s['continuous'].update(idle_hold_seconds=300,max_service_seconds=32400)
s['evaluation']={'valid_frames':145,'fps':24,'crop_xywh':[16,8,1280,720],'task_acceptance':'Task identity/black outfit/book/interaction/scene and event visibility reviewed independently; delay itself is not task failure. Both new results retained.','comparison':'R96 historical Native + two R115 arms; host metadata explicitly retained.'}
s['case_order']=[f'r115_long_0174_seed2026101701_{a}' for a in s['arms']]
for c,run in zip(s['cases'],s['case_order']):
 c.update(run_id=run,parent_graph='design/PARENT_GRAPH.json',pair_key='long_0174_seed2026101701',parent_semantics='R96 graph supplies frozen task and sampler; R115 same-host two-arm prefix/bank pairing. R96 output is historical reference.')
wr(P/'configs/scientific_contract.json',s);wr(P/'configs/queue.json',{'jobs':s['case_order'],'finalize':True});wr(P/'design/CASE_DEFINITIONS.json',s['cases'])
(P/'configs/prompts/long_0174.txt').write_text(s['cases'][0]['prompt'])
for c in s['cases']:
 g=rd(P/'design/PARENT_GRAPH.json');run=c['run_id'];r=Path(rt['remote_root'])
 for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=str(r/suffix)
 g['5']['inputs']['run_id']='r115_long_0174_shared';g['51']['inputs']['source_run_id']='r115_long_0174_shared'
 for node in ['6','50','51','52']:g[node]['inputs']['run_id']=run
 g['6']['inputs']['pair_id']='r115_long_0174_seed2026101701';g['14']['inputs']['filename_prefix']=run
 g['50']['inputs'].update(mode=c['arm'],alpha=1.,radius=0,time_offset=0,start_frame=0,end_frame=144,block_start=0,block_end=50,step_start=6,step_end=15)
 wr(P/'configs/graphs'/f'{run}.json',g)
for f in ['configs/readout_revision.json','configs/parent_graphs','configs/cgroup_policy.json']:
 q=P/f
 if q.is_dir():shutil.rmtree(q)
 elif q.exists():q.unlink()
wr(P/'configs/storage_policy.json',{'startup_required_free_bytes':16*1024**3,'estimated_output_bytes':8*1024**3,'note':'Two158frame outputs, full conditions/x0 and two small bank sets; raw tensors stay remote.'})
wr(P/'configs/runtime_kernel_hashes.json',{f:{'source_file':'source_snapshot/r112/'+f,'parent_sha256':sha(A/f),'current_sha256':sha(P/f),'byte_equal':sha(A/f)==sha(P/f)} for f in ['extensions/H3TemporalRouter/core.py','extensions/H3TemporalRouter/correspondence.py','extensions/H3TemporalRouter/layout.py','extensions/H3X0Readout/core.py','scripts/int8_row_chunking.py','scripts/compatibility_bootstrap.py','scripts/backend_dispatch_audit.py']})
wr(P/'design/HISTORICAL_NATIVE.json',{'run_id':'r96_long_0174_seed2026101701_native','producer_seal_sha256':sha(B/'h3-timing-ive-native-screen-r96-20261018/deploy_manifest.json'),'runtime':rd(A/'design/long_0174/PARENT_RUNTIME.json'),'actual_gate_sha256':sha(A/'design/long_0174/PARENT_ACTUAL_GATE.json'),'run':rd(A/'design/long_0174/PARENT_ACTUAL_GATE.json')['runs']['native'],'environment_comparison':'Metadata recorded. No added environment-control runs; cross-host prediction equality not required.','same_host_strict_comparison':False})
shutil.copy2(A/'design/long_0174/PARENT_ACTUAL_GATE.json',P/'design/HISTORICAL_NATIVE_GATE.json')
shutil.copy2(B/'h3-ive-long0174-spatial-marginal-metrics-r111-20261019/configs/PREREGISTERED_EVENTS.json',P/'design/PREREGISTERED_EVENTS.json')
wr(P/'design/SOURCE_SEALS.json',{'r112':sha(A/'deploy_manifest.json'),'r113_lifecycle':sha(L/'deploy_manifest.json'),'old_packages_unchanged':True})
print('prepared configs and frozen kernels')
