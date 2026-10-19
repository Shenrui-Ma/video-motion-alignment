"""Read-only normal-case graph, model/core and bundle preflight; no GPU imports."""
import argparse,json
from pathlib import Path
from observer_import import t,ROOT
RUN='r21_s05_seed1313_coarse_pose'
REMOTE='/data5/researcher/h3_runs/timing_coarse_to_pose_r21_20261016'
PARENT_SHA='1bda0c7effff01c6e8e7452f149da9394c797dc30beea0b24052f17f744a6b96'
def expected_graph(parent):
 g=json.loads(json.dumps(parent).replace('/data5/researcher/h3_runs/timing_native_screen_r14_host9_20261016',REMOTE).replace('r14_s05_seed1313_native_host9',RUN))
 g['50']={'class_type':'H3CoarsePoseObserverRouter','inputs':{'model':['41',0],'positive':['51',0],'run_id':RUN,'audit_dir':REMOTE+'/audit/counterfactual','policy':'coarse_pose_observer','fixed_indices':''}}
 return g
def check(root=ROOT,metadata_only=False):
 root=Path(root);t.bindings();t.admission_document(approved=not metadata_only)
 parent=root/'configs/parent_native_graph.json';t.require(t.sha(parent)==PARENT_SHA,'actual R14 graph changed')
 history=t.read_json(root/'configs/parent_native_history.json')
 t.require(history['status']['completed'] and history['status']['status_str']=='success' and history['prompt'][2]==t.read_json(parent),'actual R14 executed graph differs')
 g=t.read_json(root/'configs'/f'{RUN}.json');t.require(g==expected_graph(t.read_json(parent)),'unauthorized graph difference')
 t.require(t.read_json(root/'configs/queue.json')=={'jobs':[RUN],'sealed':True},'queue differs')
 for rel,record in t.read_json(root/'configs/unchanged_runtime_sources.json').items():t.require(t.sha(root/rel)==record['sha256'],'frozen original operator/runtime changed: '+rel)
 if not metadata_only:
  for name,sha in t.read_json(root/'configs/input_hashes.json').items():t.require(t.sha(root/'inputs'/name)==sha,'input file differs: '+name)
  b=t.bindings(external=True)
  for rel,sha in t.read_json(root/'configs/parent_core_hashes.json').items():t.require(t.sha(Path(b['comfy'])/rel)==sha,'actual Comfy core differs: '+rel)
  old=Path('/data5/researcher/h3_runs/timing_native_screen_r14_host9_20261016/audit/x0/r14_s05_seed1313_native_host9')
  captures=t.read_json(root/'configs/parent_r14_captures.json')
  for row in captures['captures']+[captures['final_sampler_result']]:t.require((old/row['file']).is_file(),'historical tensor absent: '+row['file'])
  manifest=t.read_json(root/'deploy_manifest_v1.json')
  for rel,row in manifest['files'].items():t.require(t.sha(root/rel)==row['sha256'],'sealed runtime differs: '+rel)
 return {'passed':True,'scope':'static normal-case config; live numerical bridges pending','graph_sha256':t.sha(root/'configs'/f'{RUN}.json'),'planned_NFE_bounds':[20,34],'Euler_updates':20,'external_observations':10,'historical_post_augmentation_tensor_available':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',default=str(ROOT));p.add_argument('--metadata-only',action='store_true');a=p.parse_args();print(json.dumps(check(a.root,a.metadata_only),indent=2))
