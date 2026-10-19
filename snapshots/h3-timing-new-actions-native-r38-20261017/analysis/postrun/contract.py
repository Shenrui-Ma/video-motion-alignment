"""Bounded CPU postrun contracts; no process control or GPU."""
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

