"""One real completed pair; preserve original numerical scoring inputs."""
import sys,subprocess
from common import *
sys.path.insert(0,str(ROOT/'runtime/metric_runtime'))
import ive_mf_adapter as a
CROP='crop=1280:720:16:8,trim=end_frame=105,setsar=1'
def main():
 gate=read(ROOT/'inputs/PAIR_RUNTIME_GATE.json');require(gate['passed'] is True and all(gate['checks'].values()),'actual pair gate failed')
 require(sha(ROOT/'inputs/PAIR_RUNTIME_GATE.json')=='963d11b3e95861cf55801ad037140794fbaa58159f0b5522eebdfcdccccc924c','parent gate changed')
 prov=read(ROOT/'inputs/source_provenance.json');require(prov['effective_frame_count']==105 and prov['frames']==107 and prov['fps']==24,'source timing differs')
 require(sha(ROOT/'inputs/source_full.mp4')==prov['video_sha256'] and sha(ROOT/'inputs/source_original.mp4')==prov['source_sha256'],'source bytes differ')
 values={}
 for role in ('source','native','forced'):
  full=ROOT/'inputs'/f'{role}_full.mp4';out=ROOT/'inputs'/f'{role}_score.mp4'
  if role!='source':
   require(sha(full)==gate['runs'][role]['video']['sha256'],'actual target differs')
   h=read(ROOT/'inputs'/f'{role}_history.json');require(h['status'].get('completed') and h['status'].get('status_str')=='success','history failed')
  info=a.media_info(full,'ffprobe');require((info['width'],info['height'],info['count'],info['avg_frame_rate'])==(1312,736,107,'24/1'),'full media differs')
  require(all(abs(t-i/24)<=1e-6 for i,t in enumerate(info['pts_s'])),'full PTS differs')
  if not out.exists():subprocess.run(['ffmpeg','-v','error','-threads','2','-i',str(full),'-vf',CROP,'-an','-fps_mode','passthrough','-c:v','libx264','-qp','0','-pix_fmt','yuv420p','-threads','2',str(out)],check=True)
  a.validate_time_view(a.media_info(out,'ffprobe'),105);require(a.frame_hashes(out,'ffmpeg')==a.frame_hashes(full,'ffmpeg',CROP),'crop pixels differ')
  values[role]={'full_file':str(full.relative_to(ROOT)),'full_sha256':sha(full),'score_file':str(out.relative_to(ROOT)),'score_sha256':sha(out),'score_frame_md5':a.frame_hashes(out,'ffmpeg')}
 save(ROOT/'INPUTS.json',{'schema':'quant-recovery0358-v1','source_id':'short_0358','gate_sha256':sha(ROOT/'inputs/PAIR_RUNTIME_GATE.json'),'source_provenance_sha256':sha(ROOT/'inputs/source_provenance.json'),'valid_frames':105,'total_frames':107,'fps':24,'crop_xywh':[16,8,1280,720],'roles':values})
 print('0358 three inputs: exact SHA/crop/105frames/PTS PASS')
if __name__=='__main__':main()
