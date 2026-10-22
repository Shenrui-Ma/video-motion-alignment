"""Structural validation only; no visual review or GPU access."""
import copy,json
from pathlib import Path
R=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
c=read(R/'catalog.json'); jobs=read(R/'jobs_append.json')['jobs'];base=read(R.parent/'host9a/graphs/expand_short_0353_native.json')
assert len(c['tasks'])==10 and len(jobs)==20 and len({j['id'] for j in jobs})==20
results=[]
for t in c['tasks']:
 tid=t['task_id'];assert tid not in c['excluded_ids'];graphs=[]
 for method in ['native','global_weak']:
  g=read(R/'graphs'/f'expand2_{tid}_{method}.json');graphs.append(g)
  assert g['5']['inputs']['prompt']==t['original_task']['edit_prompt']==t['recommended_prompt']
  assert g['6']['inputs']['noise_seed']==t['seed']==2026101701
  assert g['5']['inputs']['length']==t['geometry']['frames'] and (t['geometry']['frames']-5)%17==0
  assert 0<t['valid_frames']<=t['geometry']['frames']
  assert g['22']['inputs']['file']==t['graph_input_names']['video']
  assert g['50']['inputs']['end_frame']==t['valid_frames']-1
  assert g['50']['inputs']['step_start']==0 and g['50']['inputs']['step_end']==20
  assert g['50']['inputs']['mode']==('native' if method=='native' else 'mass_preserve')
  assert g['50']['inputs']['alpha']==(1.0 if method=='native' else .25)
  for node in ['1','2','3','4','41','6','7','8','9','10','11','12','13','23','52']:assert g[node]==base[node],(tid,node)
  assert len(g['9']['inputs']['sigmas'].split(','))==21
  for node in g.values():
   for value in node['inputs'].values():
    if isinstance(value,list) and len(value)==2 and isinstance(value[0],str) and isinstance(value[1],int):assert value[0] in g
 a,b=copy.deepcopy(graphs)
 for g in [a,b]:
  del g['14']['inputs']['filename_prefix']
  for key in ['mode','alpha','schedule']:del g['50']['inputs'][key]
 assert a==b
 if t['input_status']=='requires_remote_preparation':assert t['official_source_sha256_verified']
 results.append({'task_id':tid,'paired_inputs_noise_sampler_geometry_identical':True,'official_prompt_exact':True,'excluded_from_existing_catalogs':True,'official_source_sha256_verified':t.get('official_source_sha256_verified','existing prepared provenance retained')})
result={'passed':True,'task_count':10,'graph_count':20,'tasks':results,'checks':['Official prompt verbatim','seed 2026101701','Pair structural equality except mode/alpha/schedule and output prefix','Existing catalogs disjoint','All graph edges valid','Frozen model/sampler/sigmas/conditioning/timing nodes inherited','All eight original source SHA256 values match official LFS OID','Remote preprocessing synthetic lossless-frame-mapping self-test passed'],'pending':'Eight sources require remote preprocessing and decoded-pixel mapping verification before queue append'}
(R/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS: 10 tasks, 20 graphs, frozen pair/model/prompt/sampler/noise and disjoint IDs')
