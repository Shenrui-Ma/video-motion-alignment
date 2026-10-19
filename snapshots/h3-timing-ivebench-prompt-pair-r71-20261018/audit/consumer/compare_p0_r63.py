"""Compare decoded, identically cropped P0 frames to archived lossless R63 score clip."""
import json,subprocess
from pathlib import Path
import postrun as p
out=p.HERE/'p0_preliminary';new=out/'p0.mp4';old=Path('/Users/researcher/DevProjects/h3-ivebench-forced-metrics-r63-20261018/prepared/short_0210/native_score.mp4')
assert p.sha(old)=='2d3bd7aebb38124d55a7d7e4fdb3d7183a14b0fb9da7f94ad7a41b016e4833a5'
rows={}
for key,path,crop in [('r71_p0',new,True),('r63_native_lossless_score',old,False)]:
 cmd=['ffmpeg','-v','error','-threads','1','-i',str(path),'-map','0:v:0','-an']
 if crop:cmd+=['-vf','crop=1280:720:16:8']
 cmd+=['-frames:v','87','-pix_fmt','yuv420p','-f','framemd5','-'];raw=subprocess.check_output(cmd,timeout=120).decode();(out/(key+'.framemd5')).write_text(raw)
 hashes=[s.split(',')[-1].strip() for s in raw.splitlines() if s and not s.startswith('#')];assert len(hashes)==87;rows[key]=hashes
same=[a==b for a,b in zip(*rows.values())]
p.save(out/'R63_DECODED_COMPARISON.json',{'new':p.bound(new),'old_lossless_effective_clip':p.bound(old),'scope':'first87 effective frames, yuv420p after identical crop16,8,1280,720; no alignment/interpolation','equal_frames':sum(same),'total_frames':87,'all_equal':all(same),'per_frame_equal':same,'note':'same physical media comparison; complete old-vs-new numerical trajectory/condition identity is not asserted here'})
review={'schema':'r71-p0-fixed-six-visual-v1','review_scope':'six uniform original indices; no P1 output inspected','frame_indices':[0,17,34,52,69,86],'source':'蓝幕舞台中站立演讲的女性，连续手势可见。','p0':'男性替换出现，但改为暖色室内坐姿，衣服、场景、构图与手势均有变化。','task_subject_replacement':'male subject present','unedited_scene_preservation':'FAIL','motion_content_preservation':'FAIL','time_lag_interpretation':'不能将动作与场景改变概括为纯时延；同一事件对应尚不成立。','six_times':p.bound(out/'six_times.png')};p.save(out/'HUMAN_REVIEW.json',review)
print(json.dumps({'equal_frames':sum(same),'total_frames':87}))
