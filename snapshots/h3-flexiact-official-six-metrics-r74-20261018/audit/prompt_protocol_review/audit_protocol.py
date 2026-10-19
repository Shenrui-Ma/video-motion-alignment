"""CPU, read-only checks against the captured actual workflow/source evidence."""
from pathlib import Path
import ast,hashlib,json,math,os
os.environ['CUDA_VISIBLE_DEVICES']=''
import torch

ROOT=Path(__file__).resolve().parent
BASE=Path('/Users/researcher/DevProjects')
LOCALS={'r72':BASE/'h3-timing-flexiact-prompt-pair-r72-20261018','r73':BASE/'h3-timing-ivebench-expanded-r73-20261018','r74':BASE/'h3-timing-flexiact-official-six-r74-20261018'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def digest(s):return hashlib.sha256(s.encode()).hexdigest()

def main():
 assert not torch.cuda.is_initialized()
 projects=[]
 for snapshot in ROOT.glob('*ACTUAL_SNAPSHOT.json'):
  for actual in read(snapshot)['roots']:
   key=next(k for k in LOCALS if '_'+k+'_' in actual['root']);local=LOCALS[key]
   assert actual['contract_sha256']==sha(local/'configs/scientific_contract.json')
   assert actual['seal_sha256']==sha(local/'deploy_manifest.json')
   pairs={};jobs=[]
   for row in actual['cases']:
    case,g=row['case'],row['graph'];run=case['run_id'];f=local/'configs/graphs'/(run+'.json')
    assert row['graph_sha256']==sha(f) and g==read(f)
    assert g['5']['inputs']['prompt']==case['prompt']
    assert g['5']['inputs']['semantic_fps']==2 and g['5']['inputs']['phase_frames']==0
    assert g['5']['inputs']['ref_video']==['23',0] and g['23']['inputs']['video']==['22',0]
    assert g['22']['inputs']['file']==case['video'] and case['geometry']['fps']==24
    assert g['13']['inputs']['fps']==24
    if key in ['r72','r74']:
     assert g['5']['inputs']['ref_image']==['21',0] and g['21']['inputs']['image']==case['portrait']
    else:
     assert 'ref_image' not in g['5']['inputs'] and '21' not in g and case['reference_image_count']==0
     for field in ['source_prompt','edit_prompt','target_prompt']:assert case['original_task'][field] in case['prompt']
    jobs.append({'run_id':run,'prompt_sha256':digest(case['prompt']),'configured_graph_sha256':row['graph_sha256'],'reference_video':case['video'],'reference_image':case.get('portrait'),'actual_status':row['actual'].get('job',{}).get('data',{}).get('status','NOT_SUBMITTED'),'actual_history_present':'history' in row['actual']})
    if 'job' in row['actual']:
     j=row['actual']['job']['data'];assert j['graph_sha256']==row['graph_sha256'] and j['case_binding']['case']['prompt']==case['prompt'] and j['name']==run
    if 'history' in row['actual']:
     h=row['actual']['history']['data'];assert h['prompt'][2]==g
    pairs.setdefault(case['source_id'],{})[case['arm']]=(g,case)
   comparisons=[]
   for name,arms in pairs.items():
    if key=='r72':
     assert set(arms)=={'p0','p1'}
     assert all(g['50']['inputs']['mode']=='native' for g,c in arms.values())
     assert arms['p0'][1]['prompt']!=arms['p1'][1]['prompt']
     comparisons.append({'pair':name,'experiment':'P0 versus P1, both native','same_prompt':False,'intentional_prompt_change':True})
    else:
     assert set(arms)=={'native','forced'}
     ng,nc=arms['native'];fg,fc=arms['forced']
     assert nc['prompt'].encode()==fc['prompt'].encode()
     assert nc['video']==fc['video'] and nc.get('portrait')==fc.get('portrait')
     assert ng['5']['inputs']==fg['5']['inputs']
     comparisons.append({'pair':name,'experiment':'native versus forced, P1','same_prompt':True,'prompt_sha256':digest(nc['prompt']),'same_reference_node_inputs':True})
   projects.append({'project':key,'snapshot':snapshot.name,'snapshot_sha256':sha(snapshot),'snapshot_time_unix':read(snapshot)['time_unix'],'planned_pair_checks':comparisons,'runs':jobs,'completed_pair_history_claim':False})

 # Execute only small position-grid helpers extracted from the actual source.
 names={'_video_t_spans','_video_t_grid','_axis_from_sqrt_area','_frame_grid','_video_grid','_ref_t_span','_audio_grid','PackedLayout'}
 positions=[];hashes=[]
 for host in ['host41','host9']:
  path=ROOT/'actual_code'/host/'comfy/ldm/minimax/model.py';tree=ast.parse(path.read_text());nodes=[]
  for node in tree.body:
   if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names:nodes.append(node)
   if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ['FRAME_PER_TOKEN','FRAME_RESCALE'] for t in node.targets):nodes.append(node)
  ns={'torch':torch,'math':math};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
  for frames in [73,90,107,124,158]:
   latent=2+(frames-5)//17*5;spans=ns['_video_t_spans'](latent);expected=[(1,4,4,4,4)[i%5] for i in range(latent)]
   assert abs(sum(spans)-frames*40/24)<1e-10
   coords=ns['_video_t_grid'](latent,11);boundaries=[sum(expected[:i]) for i in range(latent)]
   assert torch.allclose(coords-11,torch.tensor(boundaries,dtype=torch.float64)*40/24,atol=1e-12,rtol=0)
   ref={'kind':'video','latent_t':latent,'latent_h':4,'latent_w':4,'ref_audio_t':0}
   a=ns['PackedLayout'](11,latent,4,4,round(frames/24*40),refs=[ref]);b=ns['PackedLayout'](19,latent,4,4,round(frames/24*40),refs=[ref])
   for kind in ['ref_img','video']:
    x=next(s for s in a.segments if s[2]==kind);y=next(s for s in b.segments if s[2]==kind)
    aa=a.position_ids[x[0]:x[1],0];bb=b.position_ids[y[0]:y[1],0]
    assert torch.allclose(aa-aa[0],bb-bb[0],atol=1e-11,rtol=0)
   positions.append({'host':host,'frames':frames,'latent_t':latent,'first_dense_physical_bin_starts':boundaries[:8],'video_internal_time_scale':40/24,'vary_text_length_internal_grid_equal':True})
  for rel in ['comfy/ldm/minimax/model.py','comfy_extras/nodes_minimax_h3.py','comfy/text_encoders/minimax.py']:hashes.append({'host':host,'file':rel,'sha256':sha(ROOT/'actual_code'/host/rel)})
 condition=[]
 for path in ROOT.glob('*CONDITIONING_AUDITS.json'):
  for row in read(path):
   for record in row['conditioning']:
    if not record['exists']:continue
    n=record['input_video']['shape'][0];video=next(v for v in record['native_vae_calls'] if v['prepared_frames']['shape'][0]>1)
    q=next(x for x in record['qwen_presentation'] if x['type']=='video');plan=q['sampling']
    assert video['prepared_frames']['shape'][0]==n and video['latent']['shape'][2]==2+(n-5)//17*5
    assert plan['sample_indices']==list(range(0,n,12)) and plan['sample_timestamps_seconds']==[i/24 for i in range(0,n,12)]
    condition.append({'id':record['conditioning_id'],'actual_dense_RGB_frames':n,'actual_dense_VAE_latent_t':video['latent']['shape'][2],'actual_Qwen_sampled_frames':q['actual_sampled_frames']['shape'][0],'actual_source_fps':plan['source_fps'],'semantic_fps':plan['semantic_fps'],'source_audit_sha256':record['sha256']})
 assert sha(ROOT/'official/skills/h3-prompt-writing/references/ref-en.txt')==sha(LOCALS['r72']/'design/official_ref-en.txt')
 assert not torch.cuda.is_initialized()
 result={'passed':True,'projects':sorted(projects,key=lambda x:x['project']),'actual_conditioning_checks':condition,'actual_core_sources':hashes,'position_helper_checks':positions,'CUDA_initialized':False,'scope':'Read-only source/actual snapshot audit. Pending runs remain pending. Small CPU helpers check coordinate convention, not model quality.'}
 (ROOT/'CHECKS.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps({'passed':True,'planned_graphs':sum(len(p['runs']) for p in projects),'identical_P1_native_forced_pairs':sum(c.get('same_prompt') is True for p in projects for c in p['planned_pair_checks']),'actual_conditioning':condition,'position_shape_checks':len(positions),'CUDA_initialized':False},indent=2))
if __name__=='__main__':main()
