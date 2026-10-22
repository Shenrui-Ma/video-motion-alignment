"""Prepare the actual first R114 pair and a new source trajectory domain on CPU."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
CONSUMER=ROOT.parent/'h3-ive-three-source-metrics-r114-20261019'
sys.path.insert(0,str(ROOT/'runtime/ive/metric_runtime'))
from ive_mf_adapter import frame_hashes,media_info,validate_time_view,verify_vendor

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def bound(p):return {'file':str(p),'sha256':sha(p)}
def save(p,d):
 p.parent.mkdir(parents=True,exist_ok=True);assert not p.exists();p.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def copy(p,q):
 q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q);assert sha(p)==sha(q)
def validate_manifest(m):
 assert m['source_id']=='long_0081' and m['valid_frames']==120 and m['total_frames']==124
 assert m['fps']==24 and m['crop_xywh']==[16,8,1280,720] and m['evaluation_indices']==list(range(120))
 assert set(m['raw_videos'])=={'source','native','forced'} and m['reference_image_used'] is False
 assert m['evaluation_scope']=='official_source_full_extent' and len(m['input_to_original_frame'])==120

def main():
 assert not(ROOT/'SEAL.json').exists()
 mp=CONSUMER/'prepared/long_0081/paired/MF_INPUTS.json';m=read(mp);validate_manifest(m)
 gp=Path(m['gate']['file']);assert sha(gp)==m['gate']['sha256'];g=read(gp);assert g['passed'] and all(g['checks'].values())
 release=read(ROOT/'configs/PRODUCER_RELEASE.json');assert release['passed'] and release['process_absent'] and release['CUDA_allocation_absent']
 c=ROOT/'cases/long_0081';crop='crop=1280:720:16:8,trim=end_frame=120,setsar=1';md5={};files={}
 for role in ['source','native','forced']:
  row=m['raw_videos'][role];assert sha(row['file'])==row['sha256']
  if role!='source':assert g['runs'][role]['video']['sha256']==row['sha256']
  full=c/('source_full.mp4'if role=='source'else role+'/full.mp4');copy(row['file'],full)
  score=c/('source_score.mp4'if role=='source'else role+'/score.mp4')
  subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','2','-i',str(full),'-an','-vf',crop,'-vsync','0','-c:v','libx264','-qp','0','-preset','fast','-pix_fmt','yuv420p','-threads','2',str(score)],check=True)
  md5[role]=frame_hashes(score,'/opt/homebrew/bin/ffmpeg');assert md5[role]==frame_hashes(full,'/opt/homebrew/bin/ffmpeg',crop);validate_time_view(media_info(score,'/opt/homebrew/bin/ffprobe'),120);files[role]=(full,score)
 selection={'schema':'r114-mf-source-domain-v1','pair_id':'long_0081','source_prepared':m['raw_videos']['source'],'source_original':m['original_source'],'clip':m['clip'],'valid_frames':120,'fps':24,'crop_xywh':m['crop_xywh'],'source_frame_md5':md5['source'],'input_to_original_frame':m['input_to_original_frame'],'provenance':m['provenance'],'official_task':m['original_task']};save(ROOT/'configs/SELECTION.json',selection)
 targets=[{'role':role,'full_file':str(files[role][0].relative_to(c)),'full_sha256':sha(files[role][0]),'score_file':str(files[role][1].relative_to(c)),'score_sha256':sha(files[role][1]),'score_frame_md5':md5[role],'inventory_bindings':[{'id':'r114_long_0081_fixed','field':'native'if role=='native'else'guided'}]}for role in ['native','forced']]
 save(c/'INPUTS.json',{'schema':'r114-official-mf-v1','benchmark':'IVEBench','canonical_id':'long_0081','valid_frames':120,'evaluation_frames':120,'evaluation_fps':24,'crop_xywh':m['crop_xywh'],'source_full_sha256':sha(files['source'][0]),'source_score_sha256':sha(files['source'][1]),'source_frame_md5':md5['source'],'source_cache':None,'selection_sha256':sha(ROOT/'configs/SELECTION.json'),'targets':targets,'consumer_input_sha256':sha(mp),'actual_pair_gate_sha256':sha(gp)})
 save(ROOT/'configs/PLAN.json',{'groups':['long_0081'],'jobs':[{'case':'long_0081','role':role}for role in ['source','native','forced']]})
 for src,name in [(mp,'CONSUMER_INPUTS.json'),(gp,'PAIR_RUNTIME_GATE.json'),(Path(m['collection']['file']),'COLLECTION.json')]:copy(src,ROOT/'configs'/name)
 verify_vendor();sealed={str(p.relative_to(ROOT)):sha(p)for sub in ['scripts','configs','runtime','cases','tests'] for p in(ROOT/sub).rglob('*')if p.is_file()and('__pycache__'not in p.parts or'official_source'in p.parts)}
 save(ROOT/'SEAL.json',{'schema':'r114-official-mf-host9-v1','files':sealed,'GPU_started':False,'official_numerical_source':'byte-identical to completed R119/R117 IVE runtime','created_unix':time.time()})
 save(ROOT/'audit/PREPARE_RECEIPT.json',{'passed':True,'seal_sha256':sha(ROOT/'SEAL.json'),'file_count':len(sealed),'new_tracker_roles':['source','native','forced'],'source_cache_reused':False,'valid_frames':120,'fps':24,'all_pixel_domains_equal':True,'GPU_started':False})
 print(json.dumps(read(ROOT/'audit/PREPARE_RECEIPT.json')))
if __name__=='__main__':main()
