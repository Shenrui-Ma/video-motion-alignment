"""Prepare actual R131 crop/prefix pixels with the unchanged IVE helper; CPU only."""
from pathlib import Path
import hashlib,json,os,subprocess,importlib.util
R=Path(__file__).resolve().parents[1];D=R/'audit/mf_cpu_prepared/short_0177';D.mkdir(parents=True,exist_ok=True)
MF=R/'prepared/short_0177/native/MF_INPUTS.json';m=json.loads(MF.read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
bound=lambda p:{'file':str(p),'sha256':sha(p)}
adapter=Path('/Users/researcher/DevProjects/h3-ive-bird-aligned-mf-host41-20261020/runtime/ive/metric_runtime/ive_mf_adapter.py')
s=importlib.util.spec_from_file_location('ive_pixels',adapter);a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
ff='/opt/homebrew/bin/ffmpeg';fp='/opt/homebrew/bin/ffprobe';count=m['valid_frames'];vf=f'crop=1280:720:16:8,trim=end_frame={count},setsar=1'
out={'schema':'existing-official-mf-input-manifest-v1','benchmark':'IVEBench','canonical_id':'short_0177','valid_frames':count,'evaluation_frames':count,'evaluation_fps':24,'crop_xywh':m['crop_xywh'],'source_cache':None,'selection_sha256':sha(MF),'targets':[]}
for role in ('source','native'):
 row=m['raw_videos'][role];src=Path(row['file']);assert sha(src)==row['sha256']
 full=D/('source_full.mp4' if role=='source' else 'native/full.mp4');score=D/('source_score.mp4' if role=='source' else 'native/score.mp4');full.parent.mkdir(exist_ok=True)
 if not full.exists():os.link(src,full)
 if not score.exists():subprocess.run([ff,'-v','error','-threads','2','-i',str(full),'-an','-vf',vf,'-c:v','libx264','-preset','fast','-qp','0','-pix_fmt','yuv420p','-threads','2',str(score)],check=True)
 hashes=a.frame_hashes(score,ff);assert hashes==a.frame_hashes(full,ff,vf)
 info=a.media_info(score,fp);assert info['count']==count and all(abs(t-i/24)<1e-6 for i,t in enumerate(info['pts_s']))
 if role=='source':out.update(source_full_sha256=sha(full),source_score_sha256=sha(score),source_frame_md5=hashes)
 else:out['targets'].append({'role':role,'full_file':'native/full.mp4','full_sha256':sha(full),'score_file':'native/score.mp4','score_sha256':sha(score),'score_frame_md5':hashes,'inventory_bindings':[{'id':'r131_short_0177_full_context','field':'native'}],'actual_consumer_input':bound(MF),'actual_runtime_gate':m['gate'],'evaluation_indices':list(range(count))})
p=D/'INPUTS.json';p.write_text(json.dumps(out,indent=2)+'\n')
receipt={'passed':True,'input_manifest':bound(p),'source_and_target_pixels_equal_crop_prefix':True,'source_and_target_count':count,'fps':24,'padding_excluded':list(range(60,73)),'numeric_helper':bound(adapter),'CUDA_started':False,'GPU_started':False}
(D/'CPU_READY.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
