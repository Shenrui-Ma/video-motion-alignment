import json,hashlib,re,shutil
from fractions import Fraction
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
backup=R/'audit/preseal_clip_boundary_draft';backup.mkdir(exist_ok=False)
for rel in ['design/INPUT_PLAN.json','configs/source_selection/SELECTED_5_MANIFEST.json']:
 p=R/rel;q=backup/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
plan=read(R/'design/INPUT_PLAN.json');selection=read(R/'configs/source_selection/SELECTED_5_MANIFEST.json');sel={x['source_id']:x for x in selection['pairs']}
for row in plan['pairs']:
 s=row['pair_id'];duration=Fraction(row['clip']['end_exclusive_rational'])-Fraction(row['clip']['start_pts_rational']);n=-(-(duration*24).numerator//(duration*24).denominator)
 row['input_protocol']['effective_frame_count']=n
 row['input_protocol']['temporal_resample']='nearest original rational PTS within frozen clip bounds to clip_start+i/24; ties earlier; valid exactly i/24 < clip_end_exclusive-clip_start'
 sel[s]['input_protocol']=row['input_protocol']
write(R/'design/INPUT_PLAN.json',plan);write(R/'configs/source_selection/SELECTED_5_MANIFEST.json',selection)
for row in plan['pairs']:
 s=row['pair_id'];p=R/'inputs'/(s+'_provenance.json');shutil.copy2(p,backup/p.name);v=read(p);n=row['input_protocol']['effective_frame_count'];v['selection_sha256']=sha(R/'design/INPUT_PLAN.json');v['effective_frame_count']=n;v['evaluate_indices']=list(range(n));v['padding_indices']=list(range(n,v['frames']));write(p,v)
p=R/'scripts/prepare_inputs.py';p.write_text(re.sub(r"SELECTION_SHA = '[a-f0-9]+'","SELECTION_SHA = '"+sha(R/'design/INPUT_PLAN.json')+"'",p.read_text()))
for rel in ['scripts/input_contract.py','scripts/r88_contract.py']:
 p=R/rel;t=p.read_text();t=t.replace("(107, 97), (158, 145), (158, 145), (158, 145), (158, 145)","(107, 97), (158, 144), (158, 144), (158, 145), (158, 145)").replace("'long_0123': (158, 145)","'long_0123': (158, 144)").replace("'long_0167': (158, 145)","'long_0167': (158, 144)");p.write_text(t)
p=R/'audit/finalize_cpu_package.py';p.write_text(p.read_text().replace('97/145/145/145/145 valid','97/144/144/145/145 valid'))
write(R/'audit/CLIP_BOUNDARY_CORRECTION.json',{'scope':'preseal CPU source mapping review; no H3 run/deploy','reason':'Valid24fps timestamps must be inside the original half-open clip. Exactly6second clips have144 samples, not145.','video_bytes_changed':False,'full_original_inputs_preserved':True,'valid_frames':{x['pair_id']:x['input_protocol']['effective_frame_count'] for x in plan['pairs']}})
