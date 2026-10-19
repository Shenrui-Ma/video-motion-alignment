from pathlib import Path
import json,hashlib,importlib.util,sys
r=Path('/Users/researcher/DevProjects/h3-timing-matched-global-r39-20261017');f=r/'scripts/verify_completed.py';s=f.read_text();s=s.replace('actual21NFE','actual24NFE').replace("if i==4 else", "if i in (2,4,5,6) else").replace("[0]*5+[50]+[0]*15", "[50 if b=='full' else 0 for _,b in expected]").replace("[21]*50", "[24]*50").replace("[1]*50", "[4]*50").replace("len(sums)==21", "len(sums)==24").replace("mask==[4] and nfe==21", "mask==[2,4,5,6] and nfe==24")
s=s.replace("expected_nfe=[index] if index<4 else ([4,5] if index==4 else [index+1])", "start=index+sum(k<index for k in (2,4,5,6));expected_nfe=[start,start+1] if index in (2,4,5,6) else [start]")
s=s.replace("('full' if index==4 else 'native')","('full' if index in (2,4,5,6) else 'native')").replace("n<=4", "n<=2").replace("len(prefix_proofs)==5", "len(prefix_proofs)==3").replace("five actual Native prefix", "three actual Native prefix")
start=s.index("        expected_branch_names=");end=s.index("        capture=t.read_json",start)
s=s[:start]+'''        expected_branch_names=[f'step{i:03d}_native.pt' for i in range(20)]+[f'step{i:03d}_full.pt' for i in (2,4,5,6)]+[f'step{i:03d}_input_raw.pt' for i in (2,4,5,6)]+['sampler_final_raw.pt']
        t.require(sorted(p.name for p in snapshot_folder.glob('*.pt'))==sorted(expected_branch_names),'exact branch/input/final tensor inventory differs')
        t.require([x['physical_index'] for x in c['inputs']]==[2,4,5,6],'rawinput inventory differs')
        for inp in c['inputs']:
            n=inp['physical_index'];t.require(t.sha(inp['file'])==inp['file_sha256'],'input PT SHA differs')
            value=torch.load(inp['file'],map_location='cpu',weights_only=True)
            t.require(set(value)=={'packed','metadata'} and value['metadata']=={k:v for k,v in inp.items() if k not in ('file','file_sha256','archive_seconds')},'input metadata')
            t.require(value['packed'].dtype==torch.float32 and tuple(value['packed'].shape)==(1,1,24*42*46*82+32*2*235) and bool(torch.isfinite(value['packed']).all()),'packed input shape/dtype/finite')
            t.require(tensor_signature(value['packed'])==inp['packed_signature']==branches[n,'native']['same_input']==branches[n,'full']['same_input'],'same-state actual input signature differs')
            t.require(inp['full_grid']==c['full_grid'] and inp['seed']==SEED and inp['condition_sha256']==c['conditioning']['sha256'] and inp['reference_sha256']==c['reference']['sha256'],'rawinput binding differs')
''' + s[end:]
s=s.replace("canonical_condition(c['conditioning']['tree']) # current UUID correspondence only; old full tree was not archived", "t.require(canonical_condition(c['conditioning']['tree'])==canonical_condition(t.read_json(root/'configs/parent_counterfactual.json')['counterfactual']['conditioning']['tree']),'actual historical processed tree differs beyond UUIDs')")
s=s.replace('historical R26','historical R32').replace('Full4','Full2');f.write_text(s)
# Contract and graphs
sys.path.insert(0,str(r/'scripts'));import r39_contract as contract
g=contract.expected_graph();run=contract.RUN_ID;gp=r/'configs/graphs'/f'{run}.json';gp.write_text(json.dumps(g,indent=2)+'\n')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text());save=lambda p,v:p.write_text(json.dumps(v,indent=2)+'\n')
p=read(r/'PROTOCOL.json');s=read(r/'configs/scientific_contract.json');s.update(run_id=run,NFE=24,blocks=1200,route_calls=200,protocol_sha256=sha(r/'PROTOCOL.json'));s['active_indices']=[2,4,5,6];s['input_archive_indices']=[2,4,5,6];save(r/'configs/scientific_contract.json',s)
j=read(r/'configs/job_registry.json');row=next(iter(j['jobs'].values()));row['graph_sha256']=sha(gp);row['run_id']=run if 'run_id' in row else row.get('run_id',run);j['jobs']={run:row};save(r/'configs/job_registry.json',j)
# Rebind only current evidence; all scientific files listed are immutable.
evidence={}
for f in (r/'configs').glob('*.json'):
 if f.name.startswith('parent_') or f.name in ('source.pose.json','source_provenance.json','input_hashes.json','model_hashes_host9.json'):evidence[str(f.relative_to(r))]=sha(f)
evidence['PROTOCOL.json']=sha(r/'PROTOCOL.json');evidence['SCIENCE_PROTOCOL.json']=sha(r/'SCIENCE_PROTOCOL.json');save(r/'configs/evidence_hashes.json',evidence)
# Exact numerical inheritance list is refreshed only to unchanged current bytes; rejects an accidental operator change.
k=read(r/'configs/kernel_provenance.json')
for rel,row in k.items():
 assert sha(r/rel)==row['sha256'],rel
save(r/'configs/kernel_provenance.json',k)
# Actual graph diff field paths only.
parent=read(r/'configs/parent_graph.json');diff=[]
def compare(a,b,path=''):
 if type(a)!=type(b):diff.append({'path':path,'old':a,'new':b})
 elif isinstance(a,dict):
  for key in sorted(set(a)|set(b)):
   if key not in a or key not in b:diff.append({'path':path+'/'+key,'old':a.get(key),'new':b.get(key)})
   else:compare(a[key],b[key],path+'/'+key)
 elif isinstance(a,list):
  if a!=b:diff.append({'path':path,'old':a,'new':b})
 elif a!=b:diff.append({'path':path,'old':a,'new':b})
compare(parent,g);save(r/'configs/GRAPH_DIFF.json',{'parent':'actual R32 submitted graph','parent_sha256':sha(r/'configs/parent_graph.json'),'graph_sha256':sha(gp),'diff':diff,'scope':'only admin IDs/paths and automatic router node replaced by frozen static router; all source/prompt/seed/sampler/VAE/model unchanged'})
print('graph',run,len(diff),'deltas')
