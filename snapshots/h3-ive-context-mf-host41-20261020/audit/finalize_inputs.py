from pathlib import Path
import json,hashlib,os,time
R=Path(__file__).resolve().parents[1];B=R.parent;BASE=B/'h3-ive-r121-mf-host41-20261020';CON=B/'h3-ive-prompt-envelope-metrics-r123-20261020'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def link(p,q):
 q.parent.mkdir(parents=True,exist_ok=True)
 if not q.exists():os.link(p,q)
 assert sha(p)==sha(q)
assert not(R/'SEAL.json').exists();plan=read(R/'configs/PLAN.json');assert plan['unique_targets']==5 and len(plan['jobs'])==6;plan['source_cache_count']=1;plan['status']='ACTUAL_FIVE_TARGETS_READY';save(R/'configs/PLAN.json',plan)
ret=CON/'variants/generic_retention';evidence={}
for src,name in [(ret/'incoming/short_0358/NATIVE_RUNTIME_GATE.json','NATIVE_RUNTIME_GATE.json'),(ret/'incoming/short_0358/COLLECTION.json','COLLECTION.json'),(ret/'prepared/short_0358/native/MF_INPUTS.json','MF_INPUTS.json'),(ret/'audit/actual_release/ROOT_EXIT_RECEIPT.json','ROOT_EXIT_RECEIPT.json'),(ret/'audit/full_frame_review/short_0358/native/INDEPENDENT_REVIEW.json','VISUAL_REVIEW.json')]:link(src,R/'configs/short_0358/retention'/name);evidence[name]=sha(src)
for case in plan['groups']:
 m=read(R/'cases'/case/'INPUTS.json');assert len({(x['full_sha256'],tuple(x['evaluation_indices'])) for x in m['targets']})==len(m['targets'])
 for t in m['targets']:assert t['evaluation_indices']==list(range(m['valid_frames']))
files={str(p.relative_to(R)):sha(p) for sub in ['scripts','configs','cases'] for p in (R/sub).rglob('*') if p.is_file() and '__pycache__'not in p.parts}
for rel,h in read(R/'configs/ive_NUMERIC.json')['files'].items():assert sha(R/'runtime/ive'/rel)==h;files['runtime/ive/'+rel]=h
for rel in ['audit/final_release.py','audit/verify_inputs.py']:files[rel]=sha(R/rel)
value={'schema':'existing-mf-runtime-paired-context-inputs-v1','files':files,'base_seal_sha256':sha(BASE/'SEAL.json'),'official_track_and_score_byte_identical':all((R/'scripts'/n).read_bytes()==(BASE/'scripts'/n).read_bytes() for n in ['track.py','score.py']),'capacity_byte_identical':(R/'scripts/capacity.py').read_bytes()==(BASE/'scripts/capacity.py').read_bytes(),'bytecode_excluded':True,'administrative_peer_adaptation':'Existing .9 exact-peer registration adapted to .41; user8189 retained and excluded from experiment-card count.','created_unix':time.time()};assert value['official_track_and_score_byte_identical'] and value['capacity_byte_identical'];save(R/'SEAL.json',value);print(json.dumps({'seal_sha256':sha(R/'SEAL.json'),'files':len(files),'targets':5,'jobs':6,'cached_source':'short_0358'}))
