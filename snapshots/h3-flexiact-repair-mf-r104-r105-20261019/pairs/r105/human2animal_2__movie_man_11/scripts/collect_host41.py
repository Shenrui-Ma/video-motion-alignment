from pathlib import Path
import json,hashlib,subprocess,shlex,tarfile
R=Path(__file__).resolve().parents[1];P=R/'host41_package';cfg=json.loads((P/'configs/RUNTIME.json').read_text());D=cfg['remote_root'];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
code='D='+repr(D)+'\n'+'''
from pathlib import Path
import json,hashlib,subprocess,tarfile,time
r=Path(D);a=r/'audit/actual_tracking_capacity4';done=json.loads((a/'COMPLETE.json').read_text());assert done['passed']
nv={int(x.split(',')[0]) for x in subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'],text=True).splitlines() if x.strip()};release=[]
for p in a.glob('*/RELEASED.json'):
 d=json.loads(p.read_text());assert d['returncode']==0 and d['process_absent'] and d['own_cuda_absent'] and not Path('/proc',str(d['pid'])).exists() and d['pid'] not in nv;release.append({'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'pid':d['pid']})
assert len(release)==3;launch=json.loads((r/'audit/SLOT_CAPACITY4_LAUNCH.json').read_text());pid=launch['identity']['pid'];assert not Path('/proc',str(pid)).exists() and pid not in nv
receipt={'passed':True,'wrapper_identity':launch['identity'],'wrapper_absent':True,'trackers':release,'all_own_allocations_absent':True,'unix':time.time()};(r/'audit/SLOT_RELEASE_RECEIPT.json').write_text(json.dumps(receipt,indent=2))
files=[]
for folder in [a,r/'controls',r/'tracks',r/'scores',r/'prepared']:
 files.extend(p for p in folder.rglob('*') if p.is_file() and p.suffix!='.mp4')
files.extend([r/'audit/SLOT_RELEASE_RECEIPT.json',r/'audit/SLOT_CAPACITY4_LAUNCH.json',r/'audit/PASSIVE_DEPLOYMENT.json',r/'runtime/official_metric/SOURCE_INPUTS.json',r/'CONSUMER_FREEZE.json']);m={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files};(r/'audit/RETURN_SHA.json').write_text(json.dumps(m,indent=2))
with tarfile.open(r/'audit/RESULTS.tar.gz','w:gz') as t:
 for p in files:t.add(p,arcname=str(p.relative_to(r)))
 t.add(r/'audit/RETURN_SHA.json',arcname='audit/RETURN_SHA.json')
print(json.dumps({'passed':True,'release':receipt,'files':len(files)}))
'''
p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','H3_SERVER_B','python3 -c '+shlex.quote(code)],capture_output=True,text=True);(R/'audit/HOST41_COLLECT_RESPONSE.json').write_text(json.dumps({'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr},indent=2));assert p.returncode==0,p.stderr
A=R/'HOST41_RESULTS.tar.gz';subprocess.run(['scp','-q','-o','BatchMode=yes','-o','ConnectTimeout=10','H3_SERVER_B:'+D+'/audit/RESULTS.tar.gz',str(A)],check=True);out=R/'actual_host41';out.mkdir(exist_ok=False)
with tarfile.open(A) as t:t.extractall(out,filter='data')
for n,h in json.loads((out/'audit/RETURN_SHA.json').read_text()).items():assert sha(out/n)==h,n
scores={k:json.loads((out/'scores'/k/'SCORE.json').read_text()) for k in ['native','guided']};reports={k:json.loads((out/'tracks'/k/'REPORT.json').read_text()) for k in ['reference','native','guided']}
for key in ['checkpoint_sha256','metric_functions_sha256','vendor_manifest_sha256','grid_size','mask','tracks_dtype','torch_version','cuda_version']:
 assert all(x[key]==reports['reference'][key] for x in reports.values()),key
receipt=out/'audit/SLOT_RELEASE_RECEIPT.json';summary={'benchmark':'FlexiAct','case':'human/human2animal_2/000','comparison_kind':'actual_paired_guidance','guidance_used':True,'score':{k:v['score'] for k,v in scores.items()},'evaluation_frames':49,'evaluation_fps':8,'source_original_sha256':'0efaab13c0a87e5d7e6292dbfdecace8daeabc4fbe0e4fe652776ca3b3d71780','full_video_valid_frames':147,'scores':{k:{'file':str(out/'scores'/k/'SCORE.json'),'sha256':sha(out/'scores'/k/'SCORE.json')} for k in scores},'release':{'file':str(receipt),'sha256':sha(receipt)},'scope':'Official author-code MF on 49 original physical timestamps. Same-source actual Native/guided comparison; visual task/event acceptance recorded separately.'};(R/'RESULT_VERIFIED.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
