from pathlib import Path
import hashlib,json,os,time
R=Path('/Users/researcher/DevProjects/h3-benchmark-all-results-showcase-20261018'); A=Path(__file__).parent
H=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=R/'inventory/ivebench.json';before=H(p);assert before=='1466c6b21bfe070692a6075af0d4f288bd47632b78861c8f00fc5cbcfae62c5a'
x=json.loads(p.read_text());(A/'ivebench_before.json').write_bytes(p.read_bytes())
proof=Path('/Users/researcher/DevProjects/h3-ive-context-mf-host41-20261020/audit/RESULTS_VERIFIED.json');assert H(proof)=='a6054c8a77b8c56b80f29b6309fa3c425e61ad4511637994789d0698f08825f0'
release=proof.parent/'FINAL_RELEASE_VERIFIED.json';assert H(release)=='dcd1a41fbe39777a76fe90779c7e09b3460a9733af38629b7378dc7e3a1ee646'
y=json.loads(proof.read_text());assert y['completed_targets']==y['requested_targets']==5
changed=set()
for score in y['results']:
 for bind in score['inventory_bindings']:
  r=next(r for r in x['items'] if r['id']==bind['id']);field=bind['field'];video=r['ordinary_video_path' if field=='native' else 'guided_video_path']
  assert H(video)==score['actual_generated_video_sha256'];assert r['valid_frames']==score['valid_frames']==score['evaluation_frames'];assert score['evaluation_fps']==24
  assert H(score['result_file'])==score['result_sha256'];assert H(score['release_file'])==score['release_sha256']
  mf=r['quantitative_metrics']['motion_fidelity'];assert mf.get(field) is None
  mf[field]=score['score'];mf['status']='complete';mf['protocol']='IVEBench official MF';mf.setdefault('source_files',[]);mf.setdefault('source_sha256',{})
  for f in [proof,release,Path(score['result_file']),Path(score['release_file'])]:
   if str(f) not in mf['source_files']: mf['source_files'].append(str(f))
   mf['source_sha256'][str(f)]=H(f)
   if str(f) not in r['evidence_paths']:r['evidence_paths'].append(str(f))
   r['evidence_sha256'][str(f)]=H(f)
  changed.add(r['id'])
for r in x['items']:
 if r['id'] in changed:
  m=r['quantitative_metrics']['motion_fidelity'];m['delta']=m['guided']-m['native'] if m.get('guided') is not None else None
  m['scope']='官方IVEBench MF；同一有效帧域与预处理，视觉任务验收、事件区间和阶段持续时间分别记录。'
x['updated_unix']=time.time();assert H(p)==before;tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,p)
receipt={'before_sha256':before,'after_sha256':H(p),'changed':sorted(changed),'proof':str(proof),'proof_sha256':H(proof),'created_unix':time.time()};(A/'RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt,indent=2))
