"""Packaging only: frozen source selection -> exact selected frames and provenance."""
import copy,fcntl,hashlib,json,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;R=P.parents[1];FF='/opt/homebrew/bin/ffmpeg';FP='/opt/homebrew/bin/ffprobe'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,v):
 with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def probe(p):return json.loads(subprocess.check_output([FP,'-v','error','-select_streams','v:0','-show_streams','-show_frames','-show_entries','stream=width,height,r_frame_rate,avg_frame_rate,time_base,nb_frames,duration,pix_fmt,color_range,color_space,color_transfer,color_primaries:frame=best_effort_timestamp_time','-of','json',str(p)]))
def framehash(path,fmt,flt=None):
 cmd=[FF,'-v','error','-nostdin','-threads','2','-i',str(path)]
 if flt:cmd+=['-vf',flt]
 cmd+=['-an','-pix_fmt',fmt,'-c:v','rawvideo','-threads','1','-f','framemd5','-']
 text=subprocess.check_output(cmd,text=True);rows=[line.strip().split(',')[-1].strip() for line in text.splitlines() if line and not line.startswith('#')]
 return rows,text,cmd

def main():
 lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 freeze=read(R/'configs/source_selection_freeze.json')
 for rel,d in freeze['files'].items():
  if sha(R/rel)!=d:raise ValueError('frozen selection changed '+rel)
 sources={}
 for cid in read(R/'configs/source_selection_protocol.json')['sources']:
  selpath=P/f'{cid}_SELECTION.json';selection=read(selpath);chosen=selection['selected'];start=chosen['start_frame'];end=chosen['end_frame']
  full=R/'assets/prepared'/f'{cid}_full24.mp4';fp=R/'assets/prepared'/f'{cid}_full24_provenance.json';fullmeta=read(fp)
  rawpath=P/'full_pose'/cid/f'{cid}_full24.pose.json';raw=read(rawpath)
  if sha(full)!=fullmeta['full_prepared_sha256'] or sha(rawpath)!=selection['pose_sha256']:raise ValueError('source selection binding')
  out=R/'assets/prepared'/f'{cid}_selected.mp4'
  if out.exists():raise ValueError('preserve existing export '+str(out))
  flt=f'trim=start_frame={start}:end_frame={end+1},setpts=PTS-STARTPTS'
  cmd=[FF,'-hide_banner','-nostdin','-threads','2','-i',str(full),'-vf',flt,'-an','-c:v','libx264','-qp','0','-preset','medium','-pix_fmt','yuv420p','-threads','4','-movflags','+faststart',str(out)]
  with (P/f'{cid}_selected_export.log').open('x') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
  pr=probe(out);st=pr['streams'][0];full_current_probe=probe(full)
  if len(pr['frames'])!=141 or (st['width'],st['height'],st['avg_frame_rate'])!=(1312,736,'24/1'):raise ValueError('selected frame count/geometry')
  if any(abs(float(row['best_effort_timestamp_time'])-i/24)>1e-6 for i,row in enumerate(pr['frames'])):raise ValueError('PTS')
  for k in ['color_range','color_space','color_transfer','color_primaries']:
   if st.get(k)!=full_current_probe['streams'][0].get(k):raise ValueError('color metadata changed '+k)
  checks={}
  for fmt in ['yuv420p','rgb24']:
   a,at,ac=framehash(full,fmt,flt);b,bt,bc=framehash(out,fmt)
   (P/f'{cid}_full_slice_{fmt}.framemd5').write_text(at);(P/f'{cid}_selected_{fmt}.framemd5').write_text(bt)
   if len(a)!=141 or a!=b:raise ValueError('decoded frames changed '+fmt)
   checks[fmt]={'all141_equal':True,'per_frame_md5':a,'full_command':ac,'selected_command':bc}
  frame_map=[]
  for i,old in enumerate(fullmeta['frame_map'][start:end+1]):
   item=copy.deepcopy(old);item['full_prepared_frame']=item.pop('prepared_frame');item['full_prepared_time_s']=item.pop('prepared_time_s');item.update(prepared_frame=i,prepared_time_s=i/24);frame_map.append(item)
  pose=copy.deepcopy(raw);pose['video'].update(path=str(out),sha256=sha(out),fps=24.,container_frame_count=141)
  pose['frames']=pose['frames'][start:end+1]
  for i,row in enumerate(pose['frames']):
   row['full_source_frame']=row['frame'];row['full_source_time_s']=row['time_s'];row['full_source_decoder_pos_msec']=row.get('decoder_pos_msec');row.update(frame=i,time_s=i/24,decoder_pos_msec=i/24*1000)
  pose['source_full_statistics']=pose.pop('statistics');pose['statistics']={'processed_frames':141,'missing_person_frames':sum(r['selected_person'] is None for r in pose['frames']),'multiple_person_frames':sum(len(r['persons'])>1 for r in pose['frames']),'ambiguous_selection_frames':sum(r['selection_ambiguous'] for r in pose['frames']),'note':'Derived from exact selected full-source frames; extraction costs in source_full_statistics apply to full source.'}
  pose['extraction']={'start':0,'end':141,'stride':1,'derived_full_source_start':start,'derived_full_source_end_inclusive':end,'tracking_context':'Original unchanged full-source tracker; not reinitialized at clip boundary.'}
  pose['derivation']={'full_pose_sha256':sha(rawpath),'full_video_sha256':sha(full),'selected_video_sha256':sha(out),'frame_identity_gate':'141 YUV and RGB hashes match ffmpeg full-source slice','not_fresh_clip_detection':True}
  poseout=P/f'{cid}_selected.pose.json';write(poseout,pose)
  prov={'source_id':cid,'created_unix':time.time(),'selection_freeze_sha256':sha(R/'configs/source_selection_freeze.json'),'selection_json_sha256':sha(selpath),'export_script_sha256':sha(Path(__file__)),'original_sha256':fullmeta['original_sha256'],'full_prepared_sha256':sha(full),'full_provenance_sha256':sha(fp),'prepared_sha256':sha(out),'source_frame_start':start,'source_frame_end_inclusive':end,'original_start_time_s':frame_map[0]['original_time_s'],'geometry':{'width':1312,'height':736,'frames':141,'fps':24,'duration_seconds':141/24},'ffprobe':pr,'command':cmd,'frame_identity':checks,'frame_map':frame_map,'source_pose_sha256':sha(poseout),'tracking_context':pose['extraction']['tracking_context'],'selection':chosen,'source_only':True,'visual_review_pending':True}
  provout=R/'assets/prepared'/f'{cid}_selected_provenance.json';write(provout,prov)
  sources[cid]={'source_id':cid,'prepared_path':str(out.relative_to(R)),'prepared_sha256':sha(out),'geometry':prov['geometry'],'source_frame_start':start,'source_frame_end':end,'frame_map':frame_map,'selection_status':chosen['status'],'selected_event_count':chosen['reversal_event_count'],'all_candidate_count':len(selection['all_candidate_windows']),'source_pose_path':str(poseout.relative_to(R)),'source_pose_sha256':sha(poseout),'full_source_pose_path':str(rawpath.relative_to(R)),'full_source_pose_sha256':sha(rawpath),'provenance_path':str(provout.relative_to(R)),'provenance_sha256':sha(provout),'source_selection_path':str(selpath.relative_to(R)),'source_selection_sha256':sha(selpath),'intervention_event_window':None,'visual_review_pending':True}
  print(json.dumps({'source':cid,'start':start,'end':end,'status':chosen['status'],'events':chosen['reversal_event_count'],'sha256':sha(out)}),flush=True)
 write(R/'configs/source_selection_manifest.json',{'created_unix':time.time(),'protocol_sha256':sha(R/'configs/source_selection_protocol.json'),'freeze_sha256':sha(R/'configs/source_selection_freeze.json'),'purpose':'Source-only automatic 141-frame clip selection for Native screening; no generated output or manual action window used.','sources':sources,'limitations':['Geometric direction reversals are not semantic action labels.','All three sources retained, including support UNKNOWN.','Derived pose retains original full-source tracking context.','These clips have not demonstrated a generation defect.']})
if __name__=='__main__':main()
