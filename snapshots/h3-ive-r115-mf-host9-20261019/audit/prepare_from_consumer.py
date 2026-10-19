from pathlib import Path
import hashlib,json,shutil,sys,time
ROOT=Path(__file__).resolve().parents[1]
CONSUMER=ROOT.parent/'h3-ive-long0174-correspondence-metrics-r115-20261019'
sys.path.insert(0,str(CONSUMER/'scripts'))
from common import verify_collection
from media import frame_hashes,info,check_time

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n')
def copy_binding(b,dest):
 assert sha(b['file'])==b['sha256'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(b['file'],dest);assert sha(dest)==b['sha256']
mp=CONSUMER/'prepared/long_0174/MF_INPUTS.json'
if not mp.exists():print('PENDING_ACTUAL_CONSUMER');sys.exit(0)
assert not (ROOT/'SEAL.json').exists()
collection=verify_collection(CONSUMER/'incoming/long_0174');m=read(mp);assert m['valid_frames']==145 and m['fps']==24 and m['crop_xywh']==[16,8,1280,720]
cache=m['source_and_native_cache_reuse'];assert cache['native_score']==0.9424339285679327
c=ROOT/'cases/long_0174';c.mkdir(parents=True,exist_ok=True)
src=cache['roles']['source'];copy_binding(src['full_video'],c/'source_full.mp4');copy_binding(src['score_video'],c/'source_score.mp4');copy_binding(src['cached_tracks'],c/'tracks/source/tracks.npz');copy_binding(src['cached_tracker_report'],c/'tracks/source/REPORT.json')
r=read(c/'tracks/source/REPORT.json');assert r['effective_frame_count']==145 and r['tracker']=={'grid_size':10,'grid_query_frame':0,'backward_tracking':False,'offline':True,'window_len':60}
assert frame_hashes(c/'source_score.mp4')==src['frame_md5']==r['decoded_frame_md5'];check_time(info(c/'source_score.mp4'),145,1280,720)
targets=[]
for role in ['fixed_one_bin','matched_one_bin']:
 z=m['roles'][role];copy_binding(z['full_video'],c/role/'full.mp4');copy_binding(z['score_video'],c/role/'score.mp4');assert frame_hashes(c/role/'score.mp4')==z['frame_md5'];check_time(info(c/role/'score.mp4'),145,1280,720)
 targets.append({'role':role,'full_file':role+'/full.mp4','full_sha256':z['full_video']['sha256'],'score_file':role+'/score.mp4','score_sha256':z['score_video']['sha256'],'score_frame_md5':z['frame_md5'],'inventory_bindings':[{'id':'r115_long_0174_correspondence','field':role}]})
manifest={'schema':'r115-two-actual-operator-mf-v1','benchmark':'IVEBench','canonical_id':'long_0174','valid_frames':145,'evaluation_frames':145,'evaluation_fps':24,'source_full_sha256':src['full_video']['sha256'],'source_score_sha256':src['score_video']['sha256'],'source_frame_md5':src['frame_md5'],'source_cache':{'report_sha256':src['cached_tracker_report']['sha256'],'tracks_sha256':src['cached_tracks']['sha256']},'selection_sha256':r['selection_sha256'],'targets':targets,'consumer_input_sha256':sha(mp),'actual_pair_gate_sha256':m['pair_gate']['sha256'],'crop_xywh':[16,8,1280,720],'existing_native_score':cache['native_score']}
save(c/'INPUTS.json',manifest);save(ROOT/'configs/PLAN.json',{'groups':['long_0174'],'jobs':[{'case':'long_0174','role':z['role']}for z in targets]})
shutil.copy2(mp,ROOT/'configs/CONSUMER_INPUTS.json');shutil.copy2(CONSUMER/'incoming/long_0174/PAIR_RUNTIME_GATE.json',ROOT/'configs/PAIR_RUNTIME_GATE.json');shutil.copy2(CONSUMER/'incoming/long_0174/ROOT_EXIT_RECEIPT.json',ROOT/'configs/PRODUCER_RELEASE.json');shutil.copy2(CONSUMER/'incoming/long_0174/COLLECTION.json',ROOT/'configs/COLLECTION.json');save(ROOT/'configs/CACHE_REUSE.json',cache)
files={str(p.relative_to(ROOT)):sha(p)for sub in ['scripts','configs','runtime','cases','tests']for p in (ROOT/sub).rglob('*')if p.is_file() and ('__pycache__'not in p.parts or 'official_source'in p.parts)}
save(ROOT/'SEAL.json',{'schema':'r115-official-mf-host9-v1','files':files,'GPU_started':False,'official_numerical_source':'byte-identical to completed pending-MF package','root_source':str(CONSUMER),'created_unix':time.time()})
save(ROOT/'audit/PREPARE_RECEIPT.json',{'passed':True,'consumer_input':{'file':str(mp),'sha256':sha(mp)},'seal_sha256':sha(ROOT/'SEAL.json'),'generated_roles':[x['role']for x in targets],'reused_source_track_sha256':src['cached_tracks']['sha256'],'native_score':cache['native_score'],'valid_frames':145,'fps':24,'crop':[16,8,1280,720],'GPU_started':False})
print(json.dumps({'passed':True,'seal_sha256':sha(ROOT/'SEAL.json'),'files':len(files)}))
