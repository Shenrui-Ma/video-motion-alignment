"""Read-only protocol, graph, model/core and bundle preflight; no GPU imports."""
import argparse,hashlib,json
from pathlib import Path
from observer_import import t,ROOT
RUN='r19_s05_pose_observer'
REMOTE='/data5/researcher/h3_runs/timing_pose_feedback_r19_20261016'
def expected_graph(parent):
 g=json.loads(json.dumps(parent).replace('/data5/researcher/h3_runs/timing_spatial_r3_20261016',REMOTE).replace('r3_s05_full_6to14',RUN))
 g['50']={'class_type':'H3PoseObserverRouter','inputs':{'model':['41',0],'positive':['51',0],'run_id':RUN,'audit_dir':REMOTE+'/audit/counterfactual','policy':'pose_observer','fixed_indices':''}}
 return g
def check(root=ROOT,metadata_only=False):
 root=Path(root);t.bindings();t.admission_document(approved=not metadata_only)
 parent=root/'configs/parent_full_graph.json'
 t.require(t.sha(parent)=='83dec6024bdad01a02dd762dbce94fce93b21611d36cceb67df579a6757e57fe','parent graph changed')
 g=t.read_json(root/'configs'/f'{RUN}.json');t.require(g==expected_graph(t.read_json(parent)),'unauthorized graph difference')
 t.require(t.read_json(root/'configs/queue.json')=={'jobs':[RUN],'sealed':True},'queue differs')
 for rel,record in t.read_json(root/'configs/unchanged_runtime_sources.json').items():t.require(t.sha(root/rel)==record['sha256'],'frozen original operator/runtime changed: '+rel)
 if not metadata_only:
  for name,sha in t.read_json(root/'configs/input_hashes.json').items():t.require(t.sha(root/'inputs'/name)==sha,'input file differs: '+name)
  b=t.bindings(external=True)
  for rel,sha in t.read_json(root/'configs/parent_core_hashes.json').items():t.require(t.sha(Path(b['comfy'])/rel)==sha,'actual Comfy core differs: '+rel)
  manifest=t.read_json(root/'deploy_manifest_v1.json')
  for rel,row in manifest['files'].items():t.require(t.sha(root/rel)==row['sha256'],'sealed runtime differs: '+rel)
 return {'passed':True,'scope':'static configuration; actual G1/G2/G3 pending','graph_sha256':t.sha(root/'configs'/f'{RUN}.json'),'planned_NFE_bounds':[24,34],'Euler_updates':20,'external_observations':10}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',default=str(ROOT));p.add_argument('--metadata-only',action='store_true');a=p.parse_args();print(json.dumps(check(a.root,a.metadata_only),indent=2))
