"""Final-only four-cell comparison. Existing parents and all UNKNOWN are retained."""
import os,subprocess,sys,time
from pathlib import Path
from contract import *
from evaluate import fixed_metrics,common_regions,media_and_pixels,check_provenance
import timing_metrics as metrics
from scan_current_pose import observe,valid_pose
OLD=Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')

def interaction(common):
 out=[]
 for row in common.get('rows',[]):
  errors={k:v['same_frame_error_on_common_support'] for k,v in row['runs'].items()}
  value=None
  if row['status']=='usable_exploratory' and set(errors)=={'N','F','B','FB'} and all(v is not None for v in errors.values()):value=errors['FB']-errors['F']-errors['B']+errors['N']
  out.append({'region':row['region'],'feature':row['feature'],'status':row['status'],'common_valid_fraction':row.get('common_valid_fraction'),'errors':errors,'E_FB_minus_F_minus_B_plus_N':value,'interpretation':'descriptive common-support interaction, not population inference'})
 return out

def evaluate_joint(root,arc,case,p):
 started=time.monotonic();run=case['run_id'];dest=arc/'final'/run;require(not dest.exists(),'partial evaluation requires review');dest.mkdir(parents=True)
 for path,d in p['frozen_external'].items():require(sha(path)==d,'frozen metric/model changed '+path)
 source=HERE/case['source_pose'];require(sha(source)==case['source_pose_sha256'],'source pose changed');valid_pose(source)
 history=read(arc/'logs'/f'{run}_history.json');video=output_file(arc,history,run);graph=read(arc/'configs/graphs'/f'{run}.json');sourcevideo=arc/'input'/graph['22']['inputs']['file'];require(sha(sourcevideo)==read(source)['video']['sha256'],'source input/pose mismatch')
 poses={};videos={'SOURCE':sourcevideo};parent_prov=[]
 for name,row in p['parents'].items():
  path=HERE/row['pose'];require(sha(path)==row['pose_sha256'] and sha(row['video'])==row['video_sha256'],'parent actual video/pose hash');raw=valid_pose(path);require(raw['video']['sha256']==row['video_sha256'],'parent pose wrong video');poses[name]=path;videos[name]=Path(row['video']);parent_prov.append(raw['provenance'])
 cmd=[sys.executable,str(OLD/'scripts/pose_probe.py'),'--video',str(video),'--output-dir',str(dest/'pose'),'--threads','4','--stride','1']
 for i in p['fixed_visual_frames']:cmd+=['--overlay-frame',str(i)]
 with (dest/'pose.log').open('x') as log:proc=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',MKL_NUM_THREADS='4'),timeout=240)
 require(proc.returncode==0,'technical pose execution failure; never UNKNOWN');pose=dest/'pose'/(video.stem+'.pose.json');raw=valid_pose(pose);require(raw['video']['sha256']==sha(video),'generated pose video');provenance=check_provenance(read(source)['provenance'],raw['provenance'],parent_prov,sha(sourcevideo));poses['FB']=pose;videos['FB']=video
 fixed=fixed_metrics(source,poses,case['windows'],p['thresholds'],metrics);save(dest/'FIXED_WINDOWS.json',{'scope':case['window_scope'],'results':fixed});scans={}
 for name,path in poses.items():
  scan=observe(source,path,19);save(dest/(name+'_WHOLE_SCAN.json'),scan);scans[name]=observer_summary(scan)
 save(dest/'WHOLE_SCAN_SUMMARY.json',scans)
 regions={f'fixed_{a}_{b}':list(range(a,b+1)) for a,b in case['windows']};regions.update({f'region_{a}_{b}':list(range(a,b+1)) for a,b in p['common_regions']});save(dest/'REGIONS.json',regions)
 commons={}
 for names in p['common_support_subsets']:
  label='_'.join(names);commons[label]={}
  for conf in p['thresholds']:
   value=common_regions(source,{n:poses[n] for n in names},regions,conf,metrics);save(dest/f'COMMON_{label}_{conf}.json',value);commons[label][str(conf)]={'status':value['status'],'rows':len(value['rows'])}
   if names==['N','F','B','FB']:save(dest/f'INTERACTION_{conf}.json',interaction(value))
 media_and_pixels(videos,dest/'media',p['fixed_visual_frames'],p['fixed_clip_inclusive'])
 # A fixed hash ordering makes anonymous review reproducible, without drawing RNG.
 order=sorted(('F','FB'),key=lambda n:sha(videos[n]));anonymous={'VIDEO A':videos[order[0]],'VIDEO B':videos[order[1]]};media_and_pixels(anonymous,dest/'blinded_F_FB',p['fixed_visual_frames'],p['fixed_clip_inclusive']);save(dest/'QUALITY_REVIEW_KEY.json',{'VIDEO A':order[0],'VIDEO B':order[1],'reviewer_instruction':'Inspect blinded_F_FB only before reading this key; two independent opinions; better/UNKNOWN/worse; no extra selected timestamps.'})
 job=read(arc/'logs'/f'{run}_job.json');router=read(arc/'audit/router'/f'{run}.json');captures=read(arc/'audit/x0'/run/'manifest.json');summary={'passed':True,'run_id':run,'NFE':20,'Euler_updates':20,'F_calls':router['forward_component_calls'],'B_calls':router['reverse_component_calls'],'extra_full_Flash_calls':router['extra_full_Flash_calls'],'video_sha256':sha(video),'pose_sha256':sha(pose),'pose_provenance':provenance,'whole_scan':scans,'common_support':commons,'all_UNKNOWN_retained':True,'job_wall_seconds':job['observed_unix']-job['submitted_unix'],'sampler_wall_seconds':router['sampler_gate']['sampler_wall_seconds'],'chosen20_capture_seconds':sum(z['capture_seconds'] for z in captures['captures']),'first_attention_plus_audit_seconds':router['first_active_call']['attention_plus_audit_seconds'],'CPU_seconds':time.monotonic()-started,'quality_review':'PENDING two independent fixed media reviews; UNKNOWN permitted','scope':p['scope'],'result_is_not_automatic_quality_success':True};save(dest/'SUMMARY.json',summary);return summary
