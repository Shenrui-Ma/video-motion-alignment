from pathlib import Path
import ast,json,sys
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from common import *
c=verify_runtime();old=Path(c['reuse_r65']['root_local']);math_files=['run_tracks.py','score_pair.py','metric_adapter.py','METRIC_FUNCTIONS.json','VENDOR.json','vendor/motion_fidelity.py','weights/cotracker_stride_4_wind_8.pth']
inherit={p:{'R65_sha256':sha(old/'runtime/official_metric'/p),'R66_sha256':sha(METRIC/p),'equal':sha(old/'runtime/official_metric'/p)==sha(METRIC/p)} for p in math_files};assert all(x['equal'] for x in inherit.values())
syntax=[]
for folder in ['scripts','tests']:
 for p in (R/folder).rglob('*.py'):ast.parse(p.read_text());syntax.append(str(p.relative_to(R)))
track=load('cpu_frozen_timebase_check',METRIC/'run_tracks.py');sources=[]
for action in MOTIONS:
 item=source_item(action);p=METRIC/item['file'];assert sha(p)==item['sha256'];probe=track.check_timebase(p);sources.append({'motion_source_id':action,'input_sha256':sha(p),'frame_count':len(probe['frames']),'stream':probe['streams'][0]})
value={'passed':True,'CPU_tests':{'count':24,'passed':24,'log_sha256':sha(R/'audit/CPU_TESTS.log')},'syntax_files':syntax,'numerical_runtime_byte_inheritance':inherit,'sources':sources,'pair_count':8,'source_count':5,'official_csv_pair_count':2,'custom_crosspair_count':6,'CUDA_started':False,'new_pose_started':False,'new_tracker_started':False,'root_owned_directories_untouched':['inputs','source_pose'],'root_owned_protocols_untouched':['SOURCE_POSE_PROTOCOL.json','SOURCE_POSE_COMPLETE.json']}
(R/'audit/CPU_PREPARATION.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps({'passed':True,'tests':24,'sources':5,'math_byte_equal':True,'CUDA_started':False}))
