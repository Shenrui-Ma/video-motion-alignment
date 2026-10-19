"""Prepare real completed outputs only; never generates or executes a GPU job."""
import argparse,sys
from common import *
sys.path.insert(0,str(ROOT/'runtime/metric_runtime'))
import ive_mf_adapter as a

def prepare(name,ffmpeg='ffmpeg',ffprobe='ffprobe'):
 verify_runtime();c=case_root(name);s=read(c/'SPEC.json');gate_path=c/s['gate']['file'];require(sha(gate_path)==s['gate']['sha256'],'actual gate changed');validate_gate(s,read(gate_path));count=s['valid_frames'];crop=f'crop=1280:720:16:8,trim=end_frame={count},setsar=1'
 src=s['source'];prov=read(c/src['provenance_file']);require(sha(c/src['provenance_file'])==src['provenance_sha256'],'provenance changed');require(sha(c/src['original_file'])==src['original_sha256'],'original source changed')
 require(prov['effective_frame_count']==count and prov['frames']==s['total_frames'] and prov['fps']==24 and prov['video_sha256']==src['full_sha256'] and prov['source_sha256']==src['original_sha256'],'source time/data differs')
 roles={}
 for role,r in {'source':src,**s['targets']}.items():
  full=c/r['full_file'];require(sha(full)==r['full_sha256'],'full media changed: '+role)
  if role!='source':
   h=c/r['history_file'];require(sha(h)==r['history_sha256'],'history changed');d=read(h);require(d['status'].get('completed') is True and d['status'].get('status_str')=='success','history unsuccessful')
  info=a.media_info(full,ffprobe);require((info['width'],info['height'],info['count'],info['avg_frame_rate'])==(1312,736,s['total_frames'],'24/1'),'full geometry differs');require(all(abs(t-i/24)<=1e-6 for i,t in enumerate(info['pts_s'])),'full PTS differs')
  out=c/'inputs'/f'{role}_score.mp4'
  if not out.exists():subprocess.run([ffmpeg,'-v','error','-threads','2','-i',str(full),'-vf',crop,'-an','-fps_mode','passthrough','-c:v','libx264','-qp','0','-pix_fmt','yuv420p','-threads','2',str(out)],check=True)
  a.validate_time_view(a.media_info(out,ffprobe),count);hashes=a.frame_hashes(out,ffmpeg);require(hashes==a.frame_hashes(full,ffmpeg,crop),'crop pixel mismatch')
  roles[role]={'full_file':r['full_file'],'full_sha256':sha(full),'score_file':str(out.relative_to(c)),'score_sha256':sha(out),'score_frame_md5':hashes}
 m={'schema':'ive-followup-mf-input-v1','case_id':name,'source_id':s['source_id'],'valid_frames':count,'total_frames':s['total_frames'],'fps':24,'crop_xywh':s['crop_xywh'],'gate_sha256':sha(gate_path),'spec_sha256':sha(c/'SPEC.json'),'roles':roles}
 if s.get('source_cache_reuse'):
  u=s['source_cache_reuse'];require(sha(c/u['cache_inputs_file'])==u['cache_inputs_sha256'],'original source manifest changed');validate_reuse(s,m,read(c/'tracks/source/REPORT.json'),sha(c/'tracks/source/REPORT.json'),sha(c/'tracks/source/tracks.npz'))
  m['tracking_selection_sha256']=u['selection_sha256'];save(c/'SOURCE_REUSE_RECEIPT.json',{'passed':True,'original_cache_dir':u['original_cache_dir'],'source_report':bound(c/'tracks/source/REPORT.json'),'source_tracks':bound(c/'tracks/source/tracks.npz'),'source_score':bound(c/'inputs/source_score.mp4'),'selection_scope':'original immutable source tracking selection; new targets bound separately by this case SPEC and INPUTS','selection_sha256':u['selection_sha256'],'verified_same_data_protocol_and_runtime':True})
 if (c/'INPUTS.json').exists():require(read(c/'INPUTS.json')==m,'existing prepared manifest differs; preserve prior attempt')
 else:save(c/'INPUTS.json',m)
 return {'passed':True,'case':name,'inputs':bound(c/'INPUTS.json'),'roles':list(roles),'tracking_forwards':0}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--ffprobe',default='ffprobe');a0=p.parse_args();print(json.dumps(prepare(a0.case,a0.ffmpeg,a0.ffprobe)))
