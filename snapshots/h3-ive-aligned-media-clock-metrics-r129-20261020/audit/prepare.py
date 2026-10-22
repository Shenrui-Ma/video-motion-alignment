from pathlib import Path
import json,hashlib,time,os
B=Path('/Users/researcher/DevProjects');R=Path(__file__).resolve().parents[1];P=B/'h3-timing-ive-aligned-media-clock-r129-20261020';OLD=B/'h3-ive-generic-retention-metrics-r122-20261020';SH=B/'h3-ive-official-prompt-metrics-r120-20261019/scripts'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def bound(p):return {'file':str(p),'sha256':sha(p)}
science=read(P/'configs/scientific_contract.json');case=science['cases'][0];prior=read(OLD/'incoming_pairs/long_0039/COLLECTION.json');assert sha(OLD/'incoming_pairs/long_0039/PAIR_RUNTIME_GATE.json')==prior['gate_sha256']
media={'source':P/'inputs'/case['video'],'native':OLD/'incoming_pairs/long_0039/native.mp4','fixed':OLD/'incoming_pairs/long_0039/forced.mp4'}
for role in ('native','fixed'):assert sha(media[role])==prior['files']['native.mp4'if role=='native'else'forced.mp4']
for rel in ['configs/scientific_contract.json','configs/runtime.json','configs/graphs/'+case['run_id']+'.json','design/r122_long_0039_shared_conditioning.json','design/r122_long_0039_seed2026101701_native_noise.json','design/R129_EVALUATION_PLAN.json','design/R122_SOURCE_EVENTS_REFINED_BEFORE_OUTPUT.json']:
 q=R/rel;q.parent.mkdir(parents=True,exist_ok=True);os.link(P/rel,q)
helpers={}
for name in ['remote.py','render_native.py','render_pair.py','full_frame_review.py']:
 p=SH/name;h=sha(p);s=f"from pathlib import Path as _P\nimport hashlib as _H\n_p=_P({str(p)!r});_b=_p.read_bytes();assert _H.sha256(_b).hexdigest()=={h!r}\n"
 if name=='full_frame_review.py':s+="_s=_b.decode().replace(\"'3.时序引导'\",\"'3.RoPE原点对齐'\")\nexec(compile(_s,str(_p),'exec'),globals())\n"
 else:s+="exec(compile(_b,str(_p),'exec'),globals())\n"
 if name=='render_pair.py':s+="LABELS=('1.参考视频','2.普通编辑','3.RoPE原点对齐')\n"
 (R/'scripts'/name).write_text(s);helpers[name]=bound(p)
(R/'scripts/paired.py').write_text('from common import verify_collection\ndef verify_pair_intake(*args):return verify_collection()\n')
c={'schema':'r129-single-aligned-consumer-v1','host':'H3_SERVER_A','producer_local':str(P),'producer_remote':read(P/'configs/runtime.json')['remote_root'],'producer_seal_sha256':sha(P/'deploy_manifest.json'),'science_sha256':sha(P/'configs/scientific_contract.json'),'runtime_sha256':sha(P/'configs/runtime.json'),'case':case,'parent_media':{k:bound(v)for k,v in media.items()},'parent_collection':bound(OLD/'incoming_pairs/long_0039/COLLECTION.json'),'parent_gate':bound(OLD/'incoming_pairs/long_0039/PAIR_RUNTIME_GATE.json'),'parent_full_frame_review':bound(OLD/'audit/full_frame_review/long_0039/paired/REVIEW.json'),'source_provenance':bound(P/'inputs'/case['provenance']),'source_original':bound(P/'inputs'/case['original_source']),'shared_helpers':helpers,'no_GPU_entry':True};save(R/'configs/contract.json',c)
print(json.dumps({'contract':str(R/'configs/contract.json'),'source':case['source_id'],'valid_frames':106,'total_frames':107,'existing_media_only':True}))
