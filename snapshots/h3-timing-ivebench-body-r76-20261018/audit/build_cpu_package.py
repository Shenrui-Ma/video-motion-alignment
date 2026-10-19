"""Administrative derivation of a new frozen five-source package from R73."""
from pathlib import Path
from fractions import Fraction
import copy
import hashlib
import importlib.util
import json
import math
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent
PARENT=BASE/'h3-timing-ivebench-expanded-r73-20261018'
SELECTION=BASE/'h3-ivebench-body-candidates-20261018/CANDIDATES_MANIFEST.json'
SOURCES=['short_0131','short_0178','short_0090','short_0055','short_0321']
OLD=['short_0252','short_0344','short_0065','short_0135','short_0035']
REMOTE='/data3/researcher/h3_runs/timing_ivebench_body_r76_20261018'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def rename_text(text):
 text=text.replace('r73','r76').replace('R73','R76')
 for old,new in zip(OLD,SOURCES):text=text.replace(old,new)
 return text

def init():
 inherited=[]
 for folder in ['scripts','extensions','tests','source_snapshot']:
  for p in (PARENT/folder).rglob('*'):
   if not p.is_file() or '__pycache__' in p.parts:continue
   rel=p.relative_to(PARENT);dest=ROOT/str(rel).replace('r73_contract','r76_contract');dest.parent.mkdir(parents=True,exist_ok=True)
   data=p.read_bytes()
   if folder!='source_snapshot' and p.suffix=='.py':data=rename_text(data.decode()).encode()
   dest.write_bytes(data);inherited.append({'parent':str(p),'parent_sha256':sha(p),'relative':str(dest.relative_to(ROOT)),'new_sha256':sha(dest)})
 for p in (PARENT/'analysis/postrun').glob('*.py'):
  dest=ROOT/'analysis/postrun'/p.name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(rename_text(p.read_text()))
  inherited.append({'parent':str(p),'parent_sha256':sha(p),'relative':str(dest.relative_to(ROOT)),'new_sha256':sha(dest)})
 for name in ['runtime_kernel_hashes.json','parent_core_hashes.json','expected_checkpoint_hashes.json','storage_policy.json']:
  p=ROOT/'configs'/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PARENT/'configs'/name,p)
 (ROOT/'configs/parent_graphs').mkdir();shutil.copy2(PARENT/'configs/parent_graphs/r63_template_native.json',ROOT/'configs/parent_graphs/r63_template_native.json')
 (ROOT/'configs/R54_evidence/short_0210').mkdir(parents=True);shutil.copy2(PARENT/'configs/R54_evidence/short_0210/captures.json',ROOT/'configs/R54_evidence/short_0210/captures.json')
 for folder in ['design','configs/prompts','configs/graphs','configs/source_selection','inputs']:(ROOT/folder).mkdir(parents=True,exist_ok=True)
 template=(PARENT/'design/P1_TEMPLATE.txt').read_text()
 (ROOT/'design/P1_TEMPLATE.txt').write_text(template)
 (ROOT/'design/P1_TEMPLATE_DRAFT.txt').write_text(template)
 selected=read(SELECTION);rows={row['source_id']:row for row in selected['rows']}
 selection={'schema':'r76-source-only-selected-five-v1','selected_order':SOURCES,'selection_before_generation':True,'source_candidate_manifest_sha256':sha(SELECTION),'groups':{'clothing_color':SOURCES[:2],'style_or_prop':SOURCES[2:]},'pairs':[]}
 plan={'schema':'r76-source-input-plan-v1','selection_before_generation':True,'generated_h3_results_consulted':0,'selected_order':SOURCES,'pairs':[],'status':'ROOT_APPROVED_P1_SOURCE_ONLY_FIVE'}
 lengths=[]
 for sid in SOURCES:
  selectedrow=copy.deepcopy(rows[sid]);selectedrow['generated_h3_results_consulted']=0
  selectedrow['source_only_review']=selectedrow['source_review'];selection['pairs'].append(selectedrow)
  path=Path(selectedrow['source_file']['file']);assert sha(path)==selectedrow['source_file']['sha256']
  probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_frames','-of','json',str(path)]))
  save(ROOT/'audit'/(sid+'_original_probe.json'),probe)
  stream=probe['streams'][0];tb=Fraction(stream['time_base']);pts=[int(frame['best_effort_timestamp'])*tb for frame in probe['frames']]
  assert pts[0]==0 and all(b>a for a,b in zip(pts,pts[1:]))
  valid=math.ceil(pts[-1]*24)+1;total=max(5,math.ceil((valid-5)/17)*17+5)
  mapping=[min(range(len(pts)),key=lambda i:(abs(pts[i]-Fraction(t,24)),i)) for t in range(valid)]
  assert mapping[0]==0 and mapping[-1]==len(pts)-1
  protocol={'fps':24,'effective_frame_count':valid,'h3_frame_count':total,'input_to_original_frame':mapping+[mapping[-1]]*(total-valid),'effective_input_to_original_frame':mapping,'terminal_padding_count':total-valid,'rule':'N=ceil(last original rational PTS*24)+1; nearest original PTS for each t/24, ties earlier; repeat final frame to minimum T=17k+5; exclude padded indices from evaluation.','max_nearest_source_pts_distance_s':float(max(abs(pts[k]-Fraction(t,24)) for t,k in enumerate(mapping)))}
  task=selectedrow['official_task'];row={'pair_id':sid,**task,'source':{'file':str(path),'sha256':sha(path),'frame_count':len(pts),'actual_pts_s':[float(t) for t in pts],'actual_pts_rational':[str(t) for t in pts],'width':stream['width'],'height':stream['height'],'time_base':stream['time_base']},'input_protocol':protocol,'source_only_review':selectedrow['source_review']}
  plan['pairs'].append(row);lengths.append((total,valid))
  prompt=template.format(**{key:task[key] for key in ['source_prompt','edit_prompt','target_prompt']})
  for suffix in ['', '_DRAFT']:(ROOT/'configs/prompts'/(sid+suffix+'.txt')).write_text(prompt)
 save(ROOT/'configs/source_selection/SELECTED_5_MANIFEST.json',selection)
 shutil.copy2(SELECTION,ROOT/'configs/source_selection/CANDIDATES_MANIFEST.json')
 plan['source_selection_sha256']=sha(ROOT/'configs/source_selection/SELECTED_5_MANIFEST.json');save(ROOT/'design/INPUT_PLAN.json',plan)
 save(ROOT/'configs/source_selection_hashes.json',{p.name:sha(p) for p in (ROOT/'configs/source_selection').glob('*.json')})
 p=ROOT/'scripts/prepare_inputs.py';text=p.read_text();text=re.sub(r"SELECTION_SHA = '[a-f0-9]+'",'SELECTION_SHA = '+repr(sha(ROOT/'design/INPUT_PLAN.json')),text);p.write_text(text)
 p=ROOT/'scripts/input_contract.py';text=p.read_text();text=re.sub(r'^LENGTHS=.*$', 'LENGTHS='+repr(tuple(lengths)),text,flags=re.M);p.write_text(text)
 p=ROOT/'scripts/r76_contract.py';text=p.read_text();text=re.sub(r'^SOURCE_LENGTHS=.*$', 'SOURCE_LENGTHS='+repr(dict(zip(SOURCES,lengths))),text,flags=re.M);p.write_text(text)
 runtime=read(BASE/'h3-timing-ivebench-heldout-r64-20261018/configs/runtime.json');runtime.update(status='CPU_PREPARED_ROOT_LAUNCH_PENDING',remote_root=REMOTE,port=8543,profile='host41_gpu6_r76_normal_reserve8',profile_scope='R64 same-host runtime paths/core/checkpoint lineage; fresh R76 trajectory capacity and output quality pending.')
 save(ROOT/'configs/runtime.json',runtime)
 save(ROOT/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
 save(ROOT/'design/PROMPT_DECISION.json',{'status':'ROOT_APPROVED_AFTER_R71_ACTUAL_P1_VISUAL_REVIEW','template_sha256':sha(ROOT/'design/P1_TEMPLATE.txt'),'template_origin':str(PARENT/'design/P1_TEMPLATE.txt'),'current_scope':'Root explicitly approved these five full official clips with unchanged R73 P1 Native/forced template; no action-specific additions.'})
 save(ROOT/'audit/INITIAL_INHERITANCE.json',{'parent':str(PARENT),'files':inherited,'source_lengths':dict(zip(SOURCES,lengths))})
 print(json.dumps({'lengths':dict(zip(SOURCES,lengths)),'input_plan_sha256':sha(ROOT/'design/INPUT_PLAN.json')}))

def finalize():
 plan=read(ROOT/'design/INPUT_PLAN.json');prepared=[];inputhash={}
 for row in plan['pairs']:
  sid=row['pair_id'];files={}
  for role,suffix in [('video','video.mp4'),('original','original.mp4'),('provenance','provenance.json'),('prompt','prompt.txt')]:
   path=ROOT/'inputs'/(sid+'_'+suffix);files[role]={'file':str(path.relative_to(ROOT)),'sha256':sha(path),'bytes':path.stat().st_size};inputhash[path.name]=sha(path)
  streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(ROOT/files['video']['file'])]))['streams']
  assert len(streams)==1 and streams[0]['codec_type']=='video'
  prepared.append({'pair_id':sid,'files':files,'h3_frames':row['input_protocol']['h3_frame_count'],'valid_frames':row['input_protocol']['effective_frame_count'],'prepared_streams':streams,'latent_shape':{'video':[1,24,((row['input_protocol']['h3_frame_count']-5)//17)*5+2,46,82],'audio':[1,32,2,round(row['input_protocol']['h3_frame_count']/24*40)]}})
 save(ROOT/'PREPARED_INPUTS_MANIFEST.json',{'schema':'r76-prepared-five-full-sources-v1','input_plan_sha256':sha(ROOT/'design/INPUT_PLAN.json'),'pairs':prepared})
 save(ROOT/'configs/input_hashes.json',inputhash)
 parent=read(PARENT/'configs/scientific_contract.json');contract=copy.deepcopy(parent)
 for key in ['schema','purpose','first_pair','source_event_annotations']:contract[key]=rename_text(contract[key])
 contract['cases']=[];contract['source_ids']=SOURCES;contract['case_order']=['r76_'+sid+'_seed2026101701_'+arm for sid in SOURCES for arm in ['native','forced']]
 byid={row['pair_id']:row for row in prepared}
 selected={row['source_id']:row for row in read(ROOT/'configs/source_selection/SELECTED_5_MANIFEST.json')['pairs']}
 for row in plan['pairs']:
  sid=row['pair_id'];inputs=byid[sid]
  for arm in ['native','forced']:
   case=copy.deepcopy(parent['cases'][0]);case.update(run_id='r76_'+sid+'_seed2026101701_'+arm,source_id=sid,prompt=(ROOT/'configs/prompts'/(sid+'.txt')).read_text(),video=sid+'_video.mp4',provenance=sid+'_provenance.json',valid_frame_count=inputs['valid_frames'],original_task=selected[sid]['official_task'],video_sha256=inputs['files']['video']['sha256'],provenance_sha256=inputs['files']['provenance']['sha256'],geometry={'width':1312,'height':736,'frames':inputs['h3_frames'],'fps':24},original_source=sid+'_original.mp4',arm=arm)
   contract['cases'].append(case)
 contract.update(purpose='Five new source-only human/hand-action official tasks: clothing-color2 and style/prop3; compare same-P1 Native versus fixed routing.',prompt_template_sha256=sha(ROOT/'design/P1_TEMPLATE.txt'),input_plan_sha256=sha(ROOT/'design/INPUT_PLAN.json'),prepared_input_manifest_sha256=sha(ROOT/'PREPARED_INPUTS_MANIFEST.json'),source_selection_sha256=sha(ROOT/'configs/source_selection/SELECTED_5_MANIFEST.json'))
 contract['acceleration_axes']['runtime']='Host41 existing R64 runtime, pinned identical six numerical modules; actual paths/versions recorded at startup.'
 contract['acceleration_axes']['postprocessing']='Full official clip nearest rationalPTS to24fps; per-case legal tail padding, crop[16,8,1280,720].'
 contract['evaluation']['groups']={'clothing_color':SOURCES[:2],'style_or_prop':SOURCES[2:]}
 contract['evaluation']['visibility_policy']='short0131 both workers retain their respective motions and roles; short0321 added bouquet can validly occlude a hand. Record visible/unobservable/legally occluded events separately; never infer an omitted action solely from occlusion. All five remain in fixed denominator.'
 save(ROOT/'configs/scientific_contract.json',contract);save(ROOT/'configs/queue.json',{'jobs':contract['case_order'],'finalize':True})
 sys.path.insert(0,str(ROOT/'scripts'));import r76_contract as c
 for case in contract['cases']:save(ROOT/'configs/graphs'/(case['run_id']+'.json'),c.expected_graph(ROOT,case))
 # Preserve the fixture's small tensors while adapting the real selected source geometry.
 p=ROOT/'tests/test_pair_verifier.py';text=p.read_text().replace("'frames':73", "'frames':124").replace("'valid_frame_count':58", "'valid_frame_count':121").replace("'pixel_interval_inclusive':[0,57]", "'pixel_interval_inclusive':[0,120]").replace("['valid_frames'],58", "['valid_frames'],121")
 p.write_text(text)
 save(ROOT/'design/EVALUATION_SCOPE.json',{'fixed_sources':SOURCES,'groups':contract['evaluation']['groups'],'visibility_policy':contract['evaluation']['visibility_policy'],'source_observations_used_for_guidance':False,'both_prompts_unchanged_P1_template':True})
 print(json.dumps({'jobs':len(contract['cases']),'inputs':len(inputhash)}))

if __name__=='__main__':
 {'init':init,'finalize':finalize}[sys.argv[1]]()
