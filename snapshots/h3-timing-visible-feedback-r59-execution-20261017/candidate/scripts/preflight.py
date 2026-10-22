"""Candidate-only CPU checks. Formal execution additionally needs actual R57 closure."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions')]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def check(root=ROOT,live=False):
 root=Path(root);p=read(root/'configs/protocol.json');c=read(root/'configs/scientific_contract.json');parent=read(root/'source_snapshot/R57_scientific_contract.json')
 if c['cases']!=p['cases'] or len(c['cases'])!=20:raise ValueError('fixed four-arm registry differs')
 expected_sources={'short_0210','short_0230','short_0263','short_0352','short_0370'}
 if {x['source_id'] for x in c['cases']}!=expected_sources:raise ValueError('source set differs')
 expected_arms={'native','visible_only','visible_fallback','weak_only'}
 for pc in parent['cases']:
  rows=[x for x in c['cases'] if x['source_id']==pc['source_id']]
  if {x['arm'] for x in rows}!=expected_arms:raise ValueError('four arms incomplete')
  for x in rows:
   for k in ('prompt','prompt_sha256','video_sha256','provenance_sha256','seed','geometry','valid_frame_count'):
    if x[k]!=pc[k]:raise ValueError('P1/source scientific binding differs: '+k)
   if sha(root/x['prompt_file'])!=x['prompt_sha256'] or (root/x['prompt_file']).read_text()!=x['prompt']:raise ValueError('P1 prompt bytes differ')
   if sha(root/x['parent_planned_graph'])!=x['parent_planned_graph_sha256']:raise ValueError('planned R57 graph changed')
   if sha(root/x['source_pose_path'])!=x['source_pose_sha256']:raise ValueError('source-only pose changed')
   g=read(root/'configs/graphs'/f"{x['run_id']}.json");pg=read(root/x['parent_planned_graph'])
   for n in ('1','2','3','4','8','9','11','12','13','22','23','41'):
    if g[n]!=pg[n]:raise ValueError('frozen model/sampler/video/output node differs: '+n)
   if g['6']['inputs']['noise_seed']!=x['seed'] or g['5']['inputs']['prompt']!=x['prompt']:raise ValueError('graph seed/prompt differs')
 weak=p['weak']
 if weak['alpha']!=.25 or weak['indices']!=list(range(6,15)) or weak['bins']!=list(range(27)) or weak['blocks']!=list(range(50)):raise ValueError('weak preregistration differs')
 frozen=read(root/'audit/SOURCE_INHERITANCE.json')
 unchanged=['scripts/arm_features.py','scripts/timing_metrics.py','scripts/pairwise_gain.py','scripts/physical_tolerance.py','scripts/pose_domain.py','extensions/H3AutomaticWindowRouter/automatic_window_policy.py','extensions/H3AutomaticWindowRouter/delayed_window_policy.py','extensions/H3AutomaticWindowRouter/dynamic_support.py','extensions/H3TemporalRouter/core.py','extensions/H3TemporalRouter/mask.py','scripts/run_observer.py','scripts/decode_live_child.py','scripts/gpu_release_gate.py']
 for rel in unchanged:
  if sha(root/rel)!=frozen[rel]['sha256']:raise ValueError('inherited code changed: '+rel)
 closure=read(root/'configs/PARENT_CLOSURE.json')
 if live:
  from observer_import import t
  t.require_parent_closure(root)
  raise ValueError('R59 actual runtime/resource/binding/Comfy gate and root deployment seal are still required')
 return {'status':'CPU_CANDIDATE_PASS','sources':5,'arms':4,'graphs':20,'parent_status':closure['status'],'parent_ready':closure['ready'],'GPU_launch_authorized':False,'runtime_and_capacity':'PENDING','actual_initial_noise_reference_and_condition_pairing':'PENDING','inherited_source_hashes_checked':len(unchanged)}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');a=p.parse_args();print(json.dumps(check(live=a.live),indent=2))
