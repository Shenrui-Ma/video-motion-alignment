"""Read-only postrun contracts; no model import, remote process control or writes outside analysis."""
import hashlib,json,re,time
from pathlib import Path
HERE=Path(__file__).resolve().parent

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n');tmp.replace(p)
def require(v,msg):
 if not v:raise ValueError(msg)
def safe(root,rel):
 root=Path(root);r=Path(rel);require(not r.is_absolute() and '..' not in r.parts,'unsafe relative path')
 p=root/r;require(not p.is_symlink() and p.resolve().is_relative_to(root.resolve()),'symlink/outside path');return p
def relative(root,path):
 p=Path(path);require(p.is_absolute() and p.resolve().is_relative_to(root.resolve()) and not p.is_symlink(),'outside producer path');return str(p.relative_to(root))
def numeric_observer(d):return {k:v for k,v in d.items() if k!='scan_seconds'}
def output_file(root,h,run):
 rows=h.get('outputs',{}).get('14',{}).get('images',[]);require(len(rows)==1,'exactly one output')
 r=rows[0];require(r['type']=='output' and not r.get('subfolder') and re.fullmatch(re.escape(run)+r'_\d+_\.mp4',r['filename']),'output identity')
 return safe(root,'output/'+r['filename'])
def episodes(indices):
 out=[]
 for n in sorted(set(indices)):
  if out and n==out[-1][1]+1:out[-1][1]=n
  else:out.append([n,n])
 return out

def observer_summary(observer):
 rows=observer['windows'];require(observer['status'] in ('measured','unknown_visibility'),'technical error cannot become scientific UNKNOWN')
 if observer['status']=='unknown_visibility':require(rows==[],'visibility UNKNOWN contains rows')
 else:require(len(rows)==186,'full scan requires186 rows')
 counts={k:0 for k in ('delayed_candidate','advanced_candidate','aligned','unknown')};known=0;support={}
 for r in rows:
  b=r['baseline'];require(b in counts,'unknown baseline schema');counts[b]+=1;known+=b!='unknown'
  for c,d in r['measurements'].items():
   require(c in ('0.3','0.5') and len(d['curve'])==49,'49-lag/confidence inventory')
   support.setdefault(c,[]).append({'window':r['window'],'feature':r['feature'],'status':d['status'],'flags':d.get('flags'), 'reliable_lag_frames':d['reliable_lag_frames'],'same_frame':d['same_frame'],'best':d.get('best')})
 return {'scientific_status':observer['status'],'rows':len(rows),'baseline_counts':counts,'known_denominator':known,'all_denominator':len(rows),'support':support,'reasons':observer.get('reasons',[]),'overlap_warning':'rows are overlapping descriptors, not independent trials'}

def decision_ledger(audit):
 c=audit['counterfactual'];require(len(c['steps'])==len(c['measurements'])==20,'twenty completed steps required')
 rows=[];active=[];perbin={i:[] for i in range(42)};first_known=first_candidate=None
 for i,(step,m) in enumerate(zip(c['steps'],c['measurements'])):
  require(step['physical_index']==m['physical_index']==i and m['status']=='complete','current observation/step order')
  d=step['decision'];ob=m['observer'];summary=observer_summary(ob)
  require(d['chosen_full']==bool(d['latent_bins']) and d['latent_bins']==sorted(set(d['latent_bins'])) and all(0<=v<42 for v in d['latent_bins']),'latched bin union')
  if first_known is None and summary['known_denominator']:first_known=i
  if first_candidate is None and d['groups']:first_candidate=i
  if d['chosen_full']:
   active.append(i)
   for b in d['latent_bins']:perbin[b].append(i)
  flags=[]
  if ob['status']=='unknown_visibility':flags.append('UNKNOWN_visibility')
  if summary['baseline_counts']['unknown']:flags.append('some_UNKNOWN_rows')
  if summary['baseline_counts']['aligned']:flags.append('some_aligned_rows')
  if summary['baseline_counts']['advanced_candidate']:flags.append('some_advanced_rows')
  if not d['groups'] and summary['baseline_counts']['delayed_candidate']:flags.append('no_delay_passed_gain_and_support')
  if d['groups'] and not d['chosen_full']:flags.append('no_adjacent_shared_arm_persistence')
  bs=[r for r in c['branches'] if r['physical_index']==i]
  rows.append({'denoising_index':i,'legacy_physical_index':i,'sigma':c['full_grid'][i],'sigma_next':c['full_grid'][i+1],'chosen':'full' if d['chosen_full'] else 'native','nfe_indices':[r['nfe_index'] for r in bs],'native_input_signature':bs[0]['same_input'],'native_raw_stream_signatures':bs[0]['raw_stream_signatures'],'chosen_raw_stream_signatures':step['chosen_raw_stream_signatures'],'decision':d,'summary':summary,'descriptive_flags':flags,'callback_observed_once':step['callback_observed_once'],'interpretation':'Flags describe current whole scan; they do not assert one causal stop reason.'})
 require(active==c['full_physical_indices'],'ledger mask differs')
 ep=episodes(active);return {'rows':rows,'active_indices':active,'first_known':first_known,'first_candidate':first_candidate,'first_ON':active[0] if active else None,'ON_episodes_inclusive':ep,'restart_count':max(0,len(ep)-1),'stops_before_index20':[b+1 for a,b in ep if b<19],'per_bin_episodes':{str(k):episodes(v) for k,v in perbin.items()},'NFE':20+len(active),'Euler_updates':20,'full_windows_are_video_frames':True,'legacy_physical_index_is_denoising_index':True}

def verify_source_archive(root,arc,owner,run):
 before=read(arc/'FILE_INVENTORY.json');changes=[]
 for rel,item in before.items():
  require(sha(safe(arc,rel))==item['sha256'],'archive changed '+rel)
  if sha(safe(root,rel))!=item['sha256']:changes.append(rel)
 if not changes:return None
 require(changes==['configs/queue.json'],'producer scientific files changed '+repr(changes))
 old=read(arc/'configs/queue.json');new=read(root/'configs/queue.json')
 require(old.get('finalize') is False and new.get('finalize') is True and new==dict(old,finalize=True),'not solely false->true finalize')
 gatepath=arc/'RUN_GATE.json';gate=read(gatepath);require(gate.get('passed') is True and gate.get('run_id')==run and gate.get('owner')==owner,'release gate binding')
 rpath=root/'audit/root_release_request.json';r=read(rpath)
 require(r.get('pid')==owner['pid'] and r.get('owner')==owner['identity'],'release owner binding')
 require(r.get('gate_file')==str(gatepath) and r.get('gate_sha256')==sha(gatepath),'release exact gate binding')
 require(isinstance(r.get('unix'),(float,int)) and r['unix']>=gatepath.stat().st_mtime,'release predates archive gate')
 result={'change':'queue.finalize false->true','owner':owner,'run':run,'old_queue_sha256':before['configs/queue.json']['sha256'],'new_queue_sha256':sha(root/'configs/queue.json'),'root_release_record':r,'root_release_sha256':sha(rpath),'all_other_scientific_files_unchanged':True}
 p=arc/'ADMIN_RELEASE_ACCEPTANCE.json'
 if p.exists():require(read(p)==result,'release acceptance changed')
 else:save(p,result)
 return result

def verify_phase_dependencies(root,arc,rels):
 """A phase checks its actual copied and producer dependencies, not unrelated PT."""
 inventory=read(arc/'FILE_INVENTORY.json');checked={}
 for rel in sorted(set(rels)):
  require(rel in inventory,'unregistered phase dependency '+rel)
  expected=inventory[rel]
  for base in (arc,root):
   p=safe(base,rel);require(p.stat().st_size==expected['bytes'] and sha(p)==expected['sha256'],'phase dependency changed '+rel)
  checked[rel]=expected
 return checked

def verify_archive_anchor(arc,run,owner):
 receipt=read(arc.parent.parent/'archive_receipts'/f'{run}.json')
 require(receipt['run_id']==run and receipt['owner']==owner,'archive receipt identity')
 require(sha(arc/'RUN_GATE.json')==receipt['run_gate_sha256'] and sha(arc/'FILE_INVENTORY.json')==receipt['inventory_sha256'],'archive anchor changed')
 gate=read(arc/'RUN_GATE.json')
 require(gate['passed'] is True and gate['run_id']==run and gate['owner']==owner and gate['file_inventory_sha256']==receipt['inventory_sha256'],'archive gate identity')
 return gate

def check_binding(root,b,p):
 require(str(root)==p['root_remote'] and b['remote_root']==str(root) and b['approved_for_consumer_start'] is True,'root consumer authorization/root')
 require(b['protocol_sha256']==sha(HERE/'PROTOCOL.json'),'postrun protocol binding')
 require(b['producer_manifest_sha256']==p['producer_manifest_sha256']==sha(root/'deploy_manifest.json'),'producer seal binding')
 owner=read(root/'processes/service.json');require(owner==b['service_record'],'service generation changed')
 for case in p['cases']:
  jp=root/'logs'/f'{case["run_id"]}_job.json'
  if jp.exists():
   j=read(jp);require(j['service_pid']==owner['pid'] and j['service_identity']==owner['identity'],'job generation differs')
 return owner

def canonical_sha(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()

def replay_binding(arc,root,run,index):
 require(type(index) is int and 0<=index<20,'replay index outside20')
 audit=read(arc/'audit/counterfactual'/f'{run}.json');measurement=audit['counterfactual']['measurements'][index]
 require(measurement['physical_index']==index and measurement['status']=='complete','measurement order/status')
 response_path=safe(arc,relative(root,measurement['response_file']));response=read(response_path)
 require(sha(response_path)==measurement['response_sha256'],'response binding changed')
 pose=safe(arc,relative(root,response['pose']['file']));source=arc/'configs/source.pose.json'
 require(sha(pose)==response['pose']['sha256'],'archived current pose changed')
 observer=numeric_observer(measurement['observer'])
 require(observer['physical_index']==index and observer['source_pose_sha256']==sha(source) and observer['edited_pose_sha256']==sha(pose),'observer source/current pose mismatch')
 return {'index':index,'scan_sha256':canonical_sha(observer),'source_pose_sha256':sha(source),'pose_sha256':sha(pose),'producer_observer_sha256':canonical_sha(observer),'summary':observer_summary(observer)}

def validate_replay(record,expected):
 require(record.get('passed') is True and record.get('all_numeric_values_equal') is True,'replay not passed')
 require(all(record.get(k)==v for k,v in expected.items()),'replay source/numerical/summary binding changed')
 return True

def validate_complete_inventory(arc):
 original=read(arc/'FILE_INVENTORY.json');derived=read(arc/'DERIVED_FILES.json');done=read(arc/'CPU_COMPLETE.json')
 require(done.get('passed') is True and done.get('observer_replay_indices')==list(range(20)),'incomplete CPU completion')
 mandatory={'RUN_GATE.json','RUNTIME_GATE.json','DECISION_LEDGER.json','verify.log','ADMIN_ADMISSION_AT_ARCHIVE.json','CPU_COMPLETE.json'}|{f'observer_replay/{i:03d}.json' for i in range(20)}|set(done['derived_outputs'])
 require(mandatory<=set(derived),'derived inventory omitted required output')
 require(not set(original)&set(derived),'original/derived inventories overlap')
 allowed={'FILE_INVENTORY.json','DERIVED_FILES.json'}
 if (arc/'ADMIN_RELEASE_ACCEPTANCE.json').exists():allowed.add('ADMIN_RELEASE_ACCEPTANCE.json')
 actual={str(p.relative_to(arc)) for p in arc.rglob('*') if p.is_file()}
 require(actual==set(original)|set(derived)|allowed,'archive exact file inventory differs')
 for rel,row in original.items():require(sha(safe(arc,rel))==row['sha256'],'original archive changed '+rel)
 for rel,digest in derived.items():require(sha(safe(arc,rel))==digest,'derived archive changed '+rel)
 return done

def validate_local_inventory(arc):
 original=read(arc/'FILE_INVENTORY.json');original_nonpt={k:v for k,v in original.items() if not k.endswith('.pt')}
 allowed={'FILE_INVENTORY.json'}
 if (arc/'ADMIN_RELEASE_ACCEPTANCE.json').exists():allowed.add('ADMIN_RELEASE_ACCEPTANCE.json')
 if (arc/'DERIVED_FILES.json').exists():
  derived=read(arc/'DERIVED_FILES.json');allowed.add('DERIVED_FILES.json')
  done=read(arc/'CPU_COMPLETE.json')
  required={'CPU_COMPLETE.json','RUN_GATE.json','RUNTIME_GATE.json','DECISION_LEDGER.json','verify.log','ADMIN_ADMISSION_AT_ARCHIVE.json'}|{f'observer_replay/{i:03d}.json' for i in range(20)}|set(done['derived_outputs'])
  require(done.get('passed') is True and done.get('observer_replay_indices')==list(range(20)) and required<=set(derived),'local completion omitted output')
 else:
  required={'RUN_GATE.json','RUNTIME_GATE.json','DECISION_LEDGER.json','verify.log','ADMIN_ADMISSION_AT_ARCHIVE.json'}
  derived={k:sha(safe(arc,k)) for k in required}
 require({str(p.relative_to(arc)) for p in arc.rglob('*') if p.is_file()}==set(original_nonpt)|set(derived)|allowed,'local non-PT delivery exact inventory differs')
 for rel,info in original_nonpt.items():require(sha(safe(arc,rel))==info['sha256'],'local original hash differs '+rel)
 for rel,digest in derived.items():require(sha(safe(arc,rel))==digest,'local derived hash differs '+rel)
 return {'original_non_PT':len(original_nonpt),'derived':len(derived),'all_large_PT_verified_remote':True}

def check_playback_probe(probe):
 streams=probe['streams'];require(len(streams)==1,'one video stream required');s=streams[0];frames=probe['frames']
 from fractions import Fraction
 require(s['width']==1312 and s['height']==736 and Fraction(s['r_frame_rate'])==Fraction(24) and Fraction(s['avg_frame_rate'])==Fraction(24),'playback geometry/rate')
 require(Fraction(s['time_base'])>0 and len(frames)==141,'timebase/frame count')
 times=[float(f['best_effort_timestamp_time']) for f in frames]
 require(all(abs(t-i/24)<1e-6 for i,t in enumerate(times)) and all(b>a for a,b in zip(times,times[1:])),'physical PTS not exact141x24fps')
 require(abs(float(s['duration'])-141/24)<1e-6,'container duration differs')
 return {'passed':True,'frames':141,'fps':24,'time_base':s['time_base'],'duration':s['duration'],'first_time':times[0],'last_time':times[-1],'all_timestamps_seconds':times}
