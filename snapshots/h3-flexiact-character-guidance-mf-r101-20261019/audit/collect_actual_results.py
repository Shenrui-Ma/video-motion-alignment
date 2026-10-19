"""Fetch a completed guided tracker only after its exact process and CUDA release."""
from pathlib import Path
import hashlib,json,subprocess,tarfile
R=Path(__file__).resolve().parents[1];REMOTE='/data4/researcher/h3_runs/flexiact_character_guidance_mf_r101_20261019'
code='''
from pathlib import Path
import hashlib,json,subprocess,tarfile
r=Path(REMOTE);a=r/'audit/actual_guided_tracking_attempt1'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
complete=read(a/'COMPLETE.json');release=read(a/'guided_RELEASED.json')
assert complete['passed'] is True and complete['all_own_children_released'] is True and release['process_absent'] is True and release['own_cuda_absent'] is True and release['returncode']==0
assert not Path('/proc',str(release['pid'])).exists()
active={int(x.strip()) for x in subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True).splitlines() if x.strip()};assert release['pid'] not in active
assert complete['score']['sha256']==sha(r/'scores/guided/SCORE.json')
files=[]
for folder in [a,r/'tracks/guided',r/'scores/guided',r/'controls/guided']:
 files += [p for p in folder.rglob('*') if p.is_file()]
files += [r/'CONSUMER_FREEZE.json',r/'prepared/guided/TRACK_INPUTS.json',r/'prepared/guided/METRIC_INPUTS.json',r/'prepared/guided/MATCHED_GATE_BINDING.json',r/'audit/run_actual_guided_post_r107.py']
manifest={str(p.relative_to(r)):sha(p) for p in files};(r/'audit/ACTUAL_RETURN_SHA.json').write_text(json.dumps(manifest,indent=2))
with tarfile.open(r/'audit/ACTUAL_RESULTS.tar.gz','w:gz') as tar:
 for p in files:tar.add(p,arcname=str(p.relative_to(r)))
 tar.add(r/'audit/ACTUAL_RETURN_SHA.json',arcname='audit/ACTUAL_RETURN_SHA.json')
print(json.dumps({'passed':True,'files':len(files),'released_pid':release['pid'],'archive_sha256':sha(r/'audit/ACTUAL_RESULTS.tar.gz')}))
'''.replace('REMOTE',repr(REMOTE))
q=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','H3_SERVER_B','python3 -'],input=code,text=True,capture_output=True,check=True,timeout=120);receipt=json.loads(q.stdout);archive=R/'audit/ACTUAL_RESULTS.tar.gz';subprocess.run(['scp','-q','H3_SERVER_B:'+REMOTE+'/audit/ACTUAL_RESULTS.tar.gz',str(archive)],check=True,timeout=300)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text());assert sha(archive)==receipt['archive_sha256']
dest=R/'actual_host41';dest.mkdir(exist_ok=False)
with tarfile.open(archive) as tar:
 for m in tar.getmembers():assert m.isfile() and '..' not in Path(m.name).parts and not Path(m.name).is_absolute()
 tar.extractall(dest,filter='data')
manifest=read(dest/'audit/ACTUAL_RETURN_SHA.json');assert all(sha(dest/n)==h for n,h in manifest.items());assert sha(dest/'CONSUMER_FREEZE.json')==sha(R/'CONSUMER_FREEZE.json')
s=read(dest/'scores/guided/SCORE.json');t=read(dest/'tracks/guided/REPORT.json');release=read(dest/'audit/actual_guided_tracking_attempt1/guided_RELEASED.json');assert release['pid']==t['pid'] and s['edited_report']['sha256']==sha(dest/'tracks/guided/REPORT.json') and s['actual_gate']['sha256']==sha(R/'incoming/PAIR_RUNTIME_GATE.json') and s['cached_native_score']['sha256']==sha(R/'cache/NATIVE_SCORE.json')
value={'benchmark':'FlexiAct','case':'R101 human2animal_1/game_man_4','status':'ACTUAL_OFFICIAL_MF_COMPLETE','native':s['native_score'],'guided':s['score'],'delta':s['delta'],'score_evidence':{'file':str(dest/'scores/guided/SCORE.json'),'sha256':sha(dest/'scores/guided/SCORE.json')},'release':release,'valid_frames':147,'evaluation_frames':49,'evaluation_fps':8,'grid_size':55,'verified_returned_files':len(manifest),'task_and_timing_review':'separate root full147 review; MF alone does not establish task or event correctness'}
(R/'RESULT_VERIFIED.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value))
