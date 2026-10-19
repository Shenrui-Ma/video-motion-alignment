"""Fixed final endpoints; no online controller/producer changes or intermediate decoding."""
import os,sys,time,subprocess,random
from pathlib import Path
from contract import *
from recovery import check_pose_provenance
from evaluate_helpers import fixed_metrics,common_regions,media_and_pixels
import timing_metrics as metrics
from scan_current_pose import observe,valid_pose
OLD=Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')

def current(root,arc,p):
 run=p['cases'][0]['run_id'];history=read(arc/'logs'/f'{run}_history.json');video=output_file(arc,history,run);graph=read(arc/'configs/graphs'/f'{run}.json');sourcevideo=arc/'input'/graph['22']['inputs']['file'];source=arc/'configs/source.pose.json'
 rels={str(video.relative_to(arc)),str(sourcevideo.relative_to(arc)),'configs/source.pose.json',f'logs/{run}_history.json',f'configs/graphs/{run}.json'};dependencies=verify_phase_dependencies(root,arc,rels)
 require(sha(source)==p['source_pose_sha256'] and sha(sourcevideo)==p['source_video_sha256']==read(source)['video']['sha256'],'current source input/pose binding')
 valid_pose(source);return run,video,sourcevideo,source,dependencies

def checked_external(p):
 for path,d in p['frozen_external'].items():require(sha(path)==d,'frozen pose dependency changed '+path)

def checked_poses(root,arc,p):
 run,video,sourcevideo,source,deps=current(root,arc,p);r=validate_phase(arc,'pose');pose=phase_folder(arc,'pose')/r['metadata']['pose_relative'];require(sha(pose)==r['metadata']['pose_sha256'] and read(pose)['video']['sha256']==sha(video),'final current pose binding')
 poses={'EarlyGlobalPulse':pose};videos={'SOURCE':sourcevideo};provenance=read(pose)['provenance'];check_pose_provenance(read(source)['provenance'],provenance,sha(sourcevideo))
 for name,row in p['parents'].items():
  fp=HERE/row['pose'];vp=Path(row['video']);require(sha(fp)==row['pose_sha256'] and sha(vp)==row['video_sha256'],'historical parent changed');raw=valid_pose(fp);require(raw['video']['sha256']==row['video_sha256'] and raw['provenance']==provenance,'historical parent provenance differs');poses[name]=fp;videos[name]=vp
 auto=validate_auto_parent(read(HERE/'AUTO_PARENT_BINDING.json'),p);araw=valid_pose(auto['pose']);require(araw['provenance']==provenance,'R27 normal pose provenance differs');poses['NativeAutoOFF']=auto['pose'];videos['NativeAutoOFF']=auto['video'];videos['EarlyGlobalPulse']=video
 order=['NativeAutoOFF','EarlyGlobalPulse'];return source,{n:poses[n] for n in order},{n:videos[n] for n in ['SOURCE',*order]},auto,deps

def regions_for(auto_ledger):
 regions={'full_0_140':list(range(141)),'legacy_pre':list(range(47)),'legacy_event_bins':list(range(47,68)),'legacy_post':list(range(68,141)),'tail':list(range(112,141))}
 for a,b in ((50,65),(69,81),(80,92),(99,111)):regions[f'fixed_{a}_{b}']=list(range(a,b+1))
 for length in (16,32):
  starts=sorted(set(range(0,141-length+1,4))|{141-length})
  for start in starts:regions[f'scan_{start}_{start+length-1}']=list(range(start,start+length))
 chosen=set();bins=set()
 for row in auto_ledger['rows']:
  if row['chosen']!='full':continue
  for a,b in row['decision']['physical_intervals']:chosen.update(range(a,b+1))
  bins.update(row['decision']['latent_bins'])
 support=set();cursor=0
 for i in range(42):
  size=(1,4,4,4,4)[i%5]
  if i in bins:support.update(range(cursor,min(cursor+size,141)))
  cursor+=size
 regions.update(actual_Auto_physical_union=sorted(chosen),actual_Auto_physical_complement=sorted(set(range(141))-chosen),actual_Auto_bin_union=sorted(support),actual_Auto_bin_complement=sorted(set(range(141))-support))
 return regions

def execute(phase,root,arc,p):
 require(phase!='pose','v2 only adopts registered existing pose; no extractor rerun');start=time.monotonic();folder=phase_folder(arc,phase);require(not folder.exists(),'partial phase requires reviewed recovery');folder.mkdir(parents=True)
 if phase=='pose':
  run,video,sourcevideo,source,deps=current(root,arc,p);checked_external(p)
  cmd=[sys.executable,str(OLD/'scripts/pose_probe.py'),'--video',str(video),'--output-dir',str(folder/'pose'),'--threads','4','--stride','1']
  for n in p['fixed_visual_frames']:cmd+=['--overlay-frame',str(n)]
  with (folder/'pose.log').open('x') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4'),timeout=300)
  require(r.returncode==0,'technical pose error, not scientific UNKNOWN');pose=folder/'pose'/(video.stem+'.pose.json');raw=valid_pose(pose)
  require(raw['video']['sha256']==sha(video) and raw['provenance']==read(source)['provenance'],'pose input/provenance mismatch');current(root,arc,p);checked_external(p)
  return {'pose_relative':str(pose.relative_to(folder)),'pose_sha256':sha(pose),'video_sha256':sha(video),'verified_dependencies':deps,'elapsed_seconds':time.monotonic()-start}
 source,poses,videos,auto,deps=checked_poses(root,arc,p)
 if phase=='compare':
  fixed=fixed_metrics(source,poses,p['cases'][0]['windows'],p['thresholds'],metrics);save(folder/'FIXED_WINDOWS.json',{'scope':p['scientific_endpoints']['event_status'],'results':fixed})
  scans={}
  for name,path in poses.items():
   result=observe(source,path,19);save(folder/(name+'_WHOLE_SCAN.json'),result);scans[name]=observer_summary(result)
  save(folder/'WHOLE_SCAN_SUMMARY.json',scans);regions=regions_for(read(auto['ledger']));save(folder/'REGIONS.json',regions);commons={}
  for names in p['common_support_groups']:
   key='__'.join(names);commons[key]={}
   for conf in p['thresholds']:
    d=common_regions(source,{name:poses[name] for name in names},regions,conf,metrics);save(folder/f'COMMON_{key}_{conf}.json',d);commons[key][str(conf)]={'status':d['status'],'rows':len(d['rows'])}
  save(folder/'ACTUAL_PARENT_BINDING.json',auto['binding']);save(folder/'POSE_BINDINGS.json',{name:{'file':str(path),'sha256':sha(path),'video_sha256':read(path)['video']['sha256']} for name,path in poses.items()})
  run=p['cases'][0]['run_id'];runtime=read(arc/'RUNTIME_GATE.json');audit=read(arc/'audit/counterfactual'/f'{run}.json');a=audit['counterfactual'];eff={'actual_runtime_case':runtime['cases'][0],'route_scope':'all42bins/all50blocks at denoisingindex4 only','NFE':21,'updates':20,'callbacks':20,'observations':0,'branch_observation_seconds':0,'branch_model_seconds':sum(v['model_seconds_synchronized'] for v in a['branches']),'raw_capture_seconds':sum(v['archive_and_readout_seconds'] for v in a['branches']),'scope':'record actual scopes; not speed claim'};save(folder/'EFFICIENCY.json',eff)
  summary={'run':run,'scope':p['scope'],'all_UNKNOWN_retained':True,'whole_scan':scans,'common_support':commons,'efficiency':eff,'manual_quality_review':'pending fixed blinded media','elapsed_seconds':time.monotonic()-start};save(folder/'SUMMARY.json',summary);checked_poses(root,arc,p);return {'summary_file':'SUMMARY.json','elapsed_seconds':time.monotonic()-start}
 require(phase=='media','unknown outcome phase');validate_phase(arc,'compare');require(read(phase_folder(arc,'compare')/'ACTUAL_PARENT_BINDING.json')==auto['binding'],'parent binding changed since metrics')
 pixels=media_and_pixels(videos,folder/'all_methods',p['fixed_visual_frames'],p['fixed_clip_inclusive']);media_and_pixels(videos,folder/'full141',p['fixed_visual_frames'],[0,140]);save(folder/'DIRECT_ACTUAL_PIXEL_COMPARISON.json',{'files':{n:{'file':str(v),'sha256':sha(v)} for n,v in videos.items()},'NativeAutoOFF_vs_EarlyGlobalPulse_all141_RGB_equal':pixels['RGB_frame_sha256']['NativeAutoOFF']==pixels['RGB_frame_sha256']['EarlyGlobalPulse'],'required_to_equal':False,'scope':'Direct OpenCV decoded RGB hashes of these exact actual MP4 files. No equality inferred from latent or seed; no retiming.'});pair=['NativeAutoOFF','EarlyGlobalPulse'];random.Random(p['blind_media_seed']).shuffle(pair);media_and_pixels({'VIDEO A':videos[pair[0]],'VIDEO B':videos[pair[1]]},folder/'blinded_Normal_Pulse',p['fixed_visual_frames'],p['fixed_clip_inclusive']);media_and_pixels({'VIDEO A':videos[pair[0]],'VIDEO B':videos[pair[1]]},folder/'blinded_Normal_Pulse_full141',p['fixed_visual_frames'],[0,140]);save(folder/'BLIND_KEY.json',{'seed':p['blind_media_seed'],'mapping':dict(zip(('VIDEO A','VIDEO B'),pair)),'instruction':'Review only blinded_Normal_Pulse before metrics/key; preserve UNKNOWN.'});checked_poses(root,arc,p)
 return {'fixed_frames':p['fixed_visual_frames'],'clip':p['fixed_clip_inclusive'],'fps':24,'original_frame_alignment':True,'video_sha256':{n:sha(v) for n,v in videos.items()},'elapsed_seconds':time.monotonic()-start,'quality':'pending independent blind review; pose not appearance verdict'}
