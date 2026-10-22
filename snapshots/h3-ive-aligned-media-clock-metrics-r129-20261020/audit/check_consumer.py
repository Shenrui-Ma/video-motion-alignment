"""CPU binding checks; fixtures are schema tests, never actual results."""
from pathlib import Path
import json,sys,copy
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from common import *
from render_native import media_info,check_time
from render_pair import command
c=validate_static();runtime=read(R/'configs/runtime.json');case=c['case'];parent=read(R/'design/r122_long_0039_shared_conditioning.json');position=parent['packed_layout']['position_ids']['sha256']
for b in c['parent_media'].values():check_time(media_info(b['file'],'/opt/homebrew/bin/ffprobe'),107,1312,736)
owner={'pid':1,'gpu_uuid':runtime['gpu_uuid'],'port':runtime['port'],'identity':{'uid':runtime['uid'],'start_ticks':'1','cmdline':str(Path(c['producer_remote'])/'scripts/service_entry.py')}}
layout={'original_position_sha256':position,'aligned_position_sha256':'synthetic_derived_digest','reference_origin':4839,'aligned_target_origin':4839,'target_time_displacement':-178.33333333333334,**{k:True for k in ('reference_text_unchanged','spatial_unchanged','target_video_matches_reference_all_coordinates','target_audio_video_common_origin')}}
a={'run_id':case['run_id'],'enabled':True,'status':'complete','completed_calls':1000,'completed_sampling_steps':20,'calls_by_block':[20]*50,'calls_by_forward':[50]*20,'rotation_table_builds':1,'layout':layout}
r={'run_id':case['run_id'],'valid_frames':106,'evaluation_crop_xywh':[16,8,1280,720],'NFE':20,'Euler_updates':20,'routed_blocks':0,'aligned_blocks':1000,'video':{'file':str(Path(c['producer_remote'])/'output/fixture_only.mp4')}}
g={'schema':'r129-aligned-runtime-gate-v1','source_id':'long_0039','passed':True,'checks':{k:True for k in REQUIRED_CHECKS},'producer_seal_sha256':c['producer_seal_sha256'],'runtime_profile_sha256':c['runtime_sha256'],'runtime_profile':runtime,'service_owner':owner,'runs':{'aligned':r},'first_six_prediction_equality_required':False,'alignment':a,'evaluation_plan_sha256':sha(R/'design/R129_EVALUATION_PLAN.json')}
s={'owner':owner};co={'schema':'r129-one-output-completion-v1','passed':True,'GPU_released':True,'jobs':[case['run_id']],'remaining':[],'service_owner':owner};re={'owner':owner,'passed':True,'process_absent':True,'CUDA_allocation_absent':True};verify_gate(g,s,co,re)
checks=[]
mutations=[('missing_condition_gate',lambda x:x['checks'].pop('all_six_original_conditions_equal_R122')),('condition_mismatch',lambda x:x['checks'].__setitem__('all_six_original_conditions_equal_R122',False)),('partial_blocks',lambda x:x['alignment'].__setitem__('completed_calls',999)),('router_on',lambda x:x['runs']['aligned'].__setitem__('routed_blocks',450)),('wrong_origin',lambda x:x['alignment']['layout'].__setitem__('target_time_displacement',0)),('owner_mismatch',lambda x:x.__setitem__('service_owner',{})),('prefix_equality',lambda x:x.__setitem__('first_six_prediction_equality_required',True)),('unexpected_arm',lambda x:x['runs'].__setitem__('forced',{}))]
for label,fn in mutations:
 x=copy.deepcopy(g);fn(x)
 try:verify_gate(x,s,co,re)
 except (ValueError,KeyError):checks.append(label)
 else:raise AssertionError('accepted '+label)
cmd=command([Path('a'),Path('b'),Path('c')],Path('caption'),Path('out'),106,'ffmpeg');f=cmd[cmd.index('-filter_complex')+1];assert f.count('crop=1280:720:16:8')==3 and f.count('trim=start_frame=0:end_frame=106')==3 and 'setpts=PTS-STARTPTS'in f
save(R/'audit/CPU_CHECK.json',{'passed':True,'consumer_freeze':bound(R/'CONSUMER_FREEZE.json'),'producer_files':57,'existing_media_all107_PTS_verified':True,'valid_frames':106,'crop_xywh':[16,8,1280,720],'targeted_rejections':checks,'three_columns_same_frame_render_checked':True,'fixtures_are_not_actual_results':True,'actual_output_present':(R/'incoming').exists(),'CUDA_started':False});print(json.dumps(bound(R/'audit/CPU_CHECK.json')))
