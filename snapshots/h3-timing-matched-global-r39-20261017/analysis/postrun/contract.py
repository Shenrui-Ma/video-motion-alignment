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

def output_file(root,h,run):
 rows=h.get('outputs',{}).get('14',{}).get('images',[]);require(len(rows)==1,'exactly one output')
 r=rows[0];require(r['type']=='output' and not r.get('subfolder') and re.fullmatch(re.escape(run)+r'_\d+_\.mp4',r['filename']),'output identity')
 return safe(root,'output/'+r['filename'])

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

def verify_producer_sources(root,manifest_sha256,all_files=False):
 """Pin executable imports per phase; full immutable inventory at boundaries."""
 manifest_path=Path(root)/'deploy_manifest.json'
 require(sha(manifest_path)==manifest_sha256,'producer manifest changed')
 entries=read(manifest_path)['files'];checked={}
 for rel,expected in entries.items():
  if not all_files and not (rel.endswith('.py') and rel.split('/')[0] in ('scripts','extensions')):continue
  p=safe(root,rel);require(p.stat().st_size==expected['bytes'] and sha(p)==expected['sha256'],'producer source changed '+rel)
  checked[rel]=expected['sha256']
 require(bool(checked),'producer dependency inventory empty')
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

def check_playback_probe(probe):
 streams=probe['streams'];require(len(streams)==1,'one video stream required');s=streams[0];frames=probe['frames']
 from fractions import Fraction
 require(s['width']==1312 and s['height']==736 and Fraction(s['r_frame_rate'])==Fraction(24) and Fraction(s['avg_frame_rate'])==Fraction(24),'playback geometry/rate')
 require(Fraction(s['time_base'])>0 and len(frames)==141,'timebase/frame count')
 times=[float(f['best_effort_timestamp_time']) for f in frames]
 require(all(abs(t-i/24)<1e-6 for i,t in enumerate(times)) and all(b>a for a,b in zip(times,times[1:])),'physical PTS not exact141x24fps')
 require(abs(float(s['duration'])-141/24)<1e-6,'container duration differs')
 return {'passed':True,'frames':141,'fps':24,'time_base':s['time_base'],'duration':s['duration'],'first_time':times[0],'last_time':times[-1],'all_timestamps_seconds':times}

PHASES=('pose','compare','media')
def phase_folder(arc,phase):
 require(phase in PHASES,'unknown analysis phase');return Path(arc)/'analysis'/phase

def validate_phase(arc,phase):
 folder=phase_folder(arc,phase);receipt=read(folder/'COMPLETE.json')
 require(receipt.get('passed') is True and receipt.get('phase')==phase,'phase receipt identity')
 files=receipt['files'];require({str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file()}==set(files)|{'COMPLETE.json'},'phase exact inventory differs')
 for rel,d in files.items():require(sha(safe(folder,rel))==d,'phase output changed '+rel)
 return receipt

def seal_phase(arc,phase,metadata):
 folder=phase_folder(arc,phase);require(not (folder/'COMPLETE.json').exists(),'phase already sealed')
 result={'passed':True,'phase':phase,'metadata':metadata,'files':{str(p.relative_to(folder)):sha(p) for p in folder.rglob('*') if p.is_file()}}
 save(folder/'COMPLETE.json',result);validate_phase(arc,phase);return result

def validate_auto_parent(binding,p):
 require(binding.get('approved') is True,'R32 actual final parent not approved')
 parent=Path(binding['parent_root']);require(str(parent)==p['auto_parent_root'] and binding['run_id']==p['auto_parent_run'],'wrong R32 parent')
 required={'RUN_GATE.json','CPU_COMPLETE.json','FILE_INVENTORY.json','DERIVED_FILES.json','DECISION_LEDGER.json'}
 require(set(binding['required_files'])==required,'parent anchor set differs')
 for rel,d in binding['required_files'].items():require(isinstance(d,str) and sha(safe(parent,rel))==d,'parent anchor changed '+rel)
 gate=read(parent/'RUN_GATE.json');done=read(parent/'CPU_COMPLETE.json');original=read(parent/'FILE_INVENTORY.json');derived=read(parent/'DERIVED_FILES.json')
 require(gate.get('passed') is True and gate.get('run_id')==p['auto_parent_run'] and done.get('passed') is True and done.get('run_id')==p['auto_parent_run'],'R32 not completed actual run')
 require(gate.get('file_inventory_sha256')==sha(parent/'FILE_INVENTORY.json'),'R32 inventory anchor')
 require(gate.get('additional_checks',{}).get('clean_condition_exact') is True and gate['additional_checks'].get('two_stream_noise_actual_exact') is True,'R32 actual parent conditions/noise not verified')
 require(original['configs/source.pose.json']['sha256']==p['source_pose_sha256'],'R32 source pose differs')
 require(derived.get('CPU_COMPLETE.json')==sha(parent/'CPU_COMPLETE.json') and derived.get('DECISION_LEDGER.json')==sha(parent/'DECISION_LEDGER.json'),'R32 completion/ledger inventory')
 pose_rel=binding['pose_relative'];video_rel=binding['video_relative'];pose=safe(parent,pose_rel);video=safe(parent,video_rel)
 require(pose_rel.startswith('final/') and pose_rel.endswith('.pose.json') and video_rel.startswith('output/') and Path(video_rel).name.startswith(p['auto_parent_run']+'_'),'parent final artifacts namespace')
 require(derived.get(pose_rel)==binding['pose_sha256']==sha(pose) and original[video_rel]['sha256']==binding['video_sha256']==sha(video),'actual R32 final media/pose binding')
 raw=read(pose);require(raw['video']['sha256']==binding['video_sha256'],'R32 pose belongs to another video')
 return {'pose':pose,'video':video,'ledger':parent/'DECISION_LEDGER.json','binding':binding}

def validate_delivery(arc,local=False):
 original=read(arc/'FILE_INVENTORY.json');expected={k:v['sha256'] for k,v in original.items() if not local or not k.endswith('.pt')}
 allowed={'FILE_INVENTORY.json'}
 if (arc/'DERIVED_FILES.json').exists():
  derived=read(arc/'DERIVED_FILES.json');done=read(arc/'CPU_COMPLETE.json');require(done.get('passed') is True and done.get('phases')==list(PHASES),'incomplete final phases')
  require(not set(expected)&set(derived),'inventory overlap');expected.update(derived);allowed.add('DERIVED_FILES.json')
  require(derived.get('CPU_COMPLETE.json')==sha(arc/'CPU_COMPLETE.json'),'completion not inventoried')
 else:
  for rel in ('RUN_GATE.json','RUNTIME_GATE.json','verify.log','ADMIN_ADMISSION_AT_ARCHIVE.json'):
   expected[rel]=sha(safe(arc,rel))
  for phase in PHASES:
   folder=phase_folder(arc,phase)
   if folder.exists():
    validate_phase(arc,phase)
    expected.update({str(f.relative_to(arc)):sha(f) for f in folder.rglob('*') if f.is_file()})
 if (arc/'ADMIN_RELEASE_ACCEPTANCE.json').exists():allowed.add('ADMIN_RELEASE_ACCEPTANCE.json')
 require({str(p.relative_to(arc)) for p in arc.rglob('*') if p.is_file()}==set(expected)|allowed,'exact archive delivery inventory differs')
 for rel,d in expected.items():require(sha(safe(arc,rel))==d,'archive delivery changed '+rel)
 return {'files_verified':len(expected),'large_PT_verified_remote':local}

def validate_completed_static_parent(row):
 """R34 parent is complete; bind its actual final, not a substitute."""
 root=Path(row['archive_root']);required={'RUN_GATE.json','CPU_COMPLETE.json','FILE_INVENTORY.json','DERIVED_FILES.json'}
 require(set(row['required_files'])==required,'static parent anchors differ')
 for rel,d in row['required_files'].items():require(sha(safe(root,rel))==d,'static parent anchor changed '+rel)
 gate=read(root/'RUN_GATE.json');done=read(root/'CPU_COMPLETE.json');original=read(root/'FILE_INVENTORY.json');derived=read(root/'DERIVED_FILES.json')
 require(gate.get('passed') is True and done.get('passed') is True and done['run_id']==gate['run_id'] and done['phases']==list(PHASES),'static parent not complete')
 require(gate['file_inventory_sha256']==sha(root/'FILE_INVENTORY.json'),'static parent inventory anchor')
 require(original['configs/source.pose.json']['sha256']==row['source_pose_sha256'],'static parent source differs')
 require(derived['CPU_COMPLETE.json']==sha(root/'CPU_COMPLETE.json') and derived[row['pose_relative']]==row['pose_sha256'],'static parent final pose inventory')
 vp=Path(row['video']);vr=relative(root,vp);require(original[vr]['sha256']==row['video_sha256']==sha(vp),'static parent actual video differs')
 require(sha(safe(root,row['pose_relative']))==row['pose_sha256'],'static parent pose changed')
 return {'run_id':done['run_id'],'anchors':row['required_files'],'pose_sha256':row['pose_sha256'],'video_sha256':row['video_sha256']}

def checked_parent_costs():
 values=read(HERE/'parents/COST_BINDINGS.json')
 require(set(values)=={'Native','GlobalFull6to14','Auto','EarlyGlobalPulse'},'cost comparison inventory')
 for name,row in values.items():
  require(row['NFE'] in (20,21,24) and row['Euler_updates']==row['callbacks']==20,'parent counters invalid')
  require(len(row['evidence'])==4,'cost evidence inventory')
  for path,d in row['evidence'].items():require(sha(path)==d,'parent cost evidence changed '+path)
 return values
