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


def output_file(root,h,run):
 rows=h.get('outputs',{}).get('14',{}).get('images',[]);require(len(rows)==1,'exactly one output')
 r=rows[0];require(r['type']=='output' and not r.get('subfolder') and re.fullmatch(re.escape(run)+r'_\d+_\.mp4',r['filename']),'output identity')
 return safe(root,'output/'+r['filename'])


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
 require(b['protocol_sha256']==sha(HERE/'PROTOCOL.json') and b['consumer_freeze_sha256']==sha(HERE/'FREEZE.json'),'postrun protocol/code binding')
 require(b['producer_manifest_sha256']==p['producer_manifest_sha256']==sha(root/'deploy_manifest.json'),'producer seal binding')
 check_declared_cases(p,read(root/'configs/scientific_contract.json'))
 owner=read(root/'processes/service.json');require(owner==b['service_record'],'service generation changed')
 for case in p['cases']:
  jp=root/'logs'/f'{case["run_id"]}_job.json'
  if jp.exists():
   j=read(jp);require(j['service_pid']==owner['pid'] and j['service_identity']==owner['identity'],'job generation differs')
 return owner


def check_declared_cases(protocol,producer):
 fields=('run_id','source_id','seed','prompt','video','video_sha256','provenance','provenance_sha256','original_source','reference_image_count','reference_video_count','valid_frame_count','original_task','geometry','evaluation_crop_xywh')
 planned=protocol['cases'];actual=producer['cases']
 require(len(planned)==len(actual)==5,'five declared cases required')
 require([c['run_id'] for c in planned]==producer['case_order'],'producer case order differs')
 for case,source in zip(planned,actual):
  require(all(case[k]==source[k] for k in fields),'source/task/input binding differs')
  require(case['reference_image_count']==0 and case['reference_video_count']==1,'single-video task differs')
  require(case['prompt']==case['original_task']['edit_prompt'],'original editing task differs')
  require(case['geometry']==protocol['geometry'] and case['evaluation_crop_xywh']==[16,8,1280,720],'case geometry differs')
 require(protocol['geometry']==producer['geometry']=={'width':1312,'height':736,'frames':90,'fps':24},'geometry differs')
 require([c['valid_frame_count'] for c in planned]==[87,86,74,78,89],'valid score prefixes differ')
 return True


def check_case_summary(summary,case):
 require(summary.get('passed') is True,'case incomplete')
 for field in ('run_id','source_id','seed'):
  require(summary.get(field)==case[field],'case result identity differs '+field)
 require(summary.get('source_video_sha256')==case['video_sha256'],'case source video differs')
 mask=summary.get('active_denoising_indices',[])
 require(type(mask) is list and mask==sorted(set(mask)) and all(type(i) is int and 1<=i<20 for i in mask),'invalid intervention steps')
 require(summary.get('NFE')==20+len(mask) and summary.get('actual_routed_blocks')==50*len(mask) and summary.get('observations_replayed')==20,'automatic counts/replays differ')
 require(summary.get('padding_evaluated') is False and summary.get('decoded_frame_md5_equal') is True and summary.get('score_frame_indices')==list(range(case['valid_frame_count'])),'valid-prefix contract differs')
 return True


def canonical_sha(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()


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



def numeric_observer(d):return {k:v for k,v in d.items() if k!='scan_seconds'}

def episodes(indices):
 out=[]
 for n in sorted(set(indices)):
  if out and n==out[-1][1]+1:out[-1][1]=n
  else:out.append([n,n])
 return out

def observer_summary(observer,case):
 rows=observer['windows'];require(observer['status'] in ('measured','unknown_visibility'),'technical error cannot become scientific UNKNOWN')
 if observer['status']=='unknown_visibility':require(rows==[],'visibility UNKNOWN contains rows')
 else:
  n=case['valid_frame_count'];windows=[(start,start+length-1) for length in (16,32) for start in sorted(set(range(0,n-length+1,4))|{n-length})]
  expected=[(list(w),f) for w in windows for f in ('arm_direction','left_arm_direction','right_arm_direction')]
  require([(r['window'],r['feature']) for r in rows]==expected,'full scan valid-prefix windows differ')
 counts={k:0 for k in ('delayed_candidate','advanced_candidate','aligned','unknown')};known=0;support={}
 for r in rows:
  b=r['baseline'];require(b in counts,'unknown baseline schema');counts[b]+=1;known+=b!='unknown'
  for c,d in r['measurements'].items():
   require(c in ('0.3','0.5') and len(d['curve'])==49,'49-lag/confidence inventory')
   support.setdefault(c,[]).append({'window':r['window'],'feature':r['feature'],'status':d['status'],'flags':d.get('flags'), 'reliable_lag_frames':d['reliable_lag_frames'],'same_frame':d['same_frame'],'best':d.get('best')})
 return {'scientific_status':observer['status'],'rows':len(rows),'baseline_counts':counts,'known_denominator':known,'all_denominator':len(rows),'support':support,'reasons':observer.get('reasons',[]),'overlap_warning':'rows are overlapping descriptors, not independent trials'}

def decision_ledger(audit,case):
 c=audit['counterfactual'];require(len(c['steps'])==len(c['measurements'])==20,'twenty completed steps required')
 rows=[];active=[];perbin={i:[] for i in range(27)};first_known=first_candidate=None
 for i,(step,m) in enumerate(zip(c['steps'],c['measurements'])):
  require(step['physical_index']==m['physical_index']==i and m['status']=='complete','current observation/step order')
  d=step['decision'];ob=m['observer'];summary=observer_summary(ob,case)
  require(d['chosen_full']==bool(d['latent_bins']) and d['latent_bins']==sorted(set(d['latent_bins'])) and all(0<=v<27 for v in d['latent_bins']),'latched bin union')
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
  if not d['groups'] and (summary['baseline_counts']['delayed_candidate'] or summary['baseline_counts']['advanced_candidate']):flags.append('no_candidate_passed_gain_and_support')
  if d['groups'] and not d['chosen_full']:flags.append('no_adjacent_shared_arm_persistence')
  bs=[r for r in c['branches'] if r['physical_index']==i]
  rows.append({'denoising_index':i,'legacy_physical_index':i,'sigma':c['full_grid'][i],'sigma_next':c['full_grid'][i+1],'chosen':'full' if d['chosen_full'] else 'native','nfe_indices':[r['nfe_index'] for r in bs],'native_input_signature':bs[0]['same_input'],'native_raw_stream_signatures':bs[0]['raw_stream_signatures'],'chosen_raw_stream_signatures':step['chosen_raw_stream_signatures'],'decision':d,'summary':summary,'descriptive_flags':flags,'callback_observed_once':step['callback_observed_once'],'interpretation':'Flags describe current whole scan; they do not assert one causal stop reason.'})
 require(active==c['full_physical_indices'],'ledger mask differs')
 ep=episodes(active);return {'rows':rows,'active_indices':active,'first_known':first_known,'first_candidate':first_candidate,'first_ON':active[0] if active else None,'ON_episodes_inclusive':ep,'restart_count':max(0,len(ep)-1),'stops_before_index20':[b+1 for a,b in ep if b<19],'per_bin_episodes':{str(k):episodes(v) for k,v in perbin.items()},'NFE':20+len(active),'Euler_updates':20,'full_windows_are_video_frames':True,'legacy_physical_index_is_denoising_index':True}
