from pathlib import Path
import hashlib, json, re, time, html
from PIL import Image

C = Path(__file__).resolve().parents[1]
P = C.parent / 'h3-timing-ive-basketball-boundprompt-r110-20261019'
A = C / 'audit/full105_review'
A.mkdir(exist_ok=True)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())
write = lambda p,d: Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
pres = read(C/'showcase/PRESENTATION.json')
pages = pres['all_frame_pages']
assert [f for page in pages for f in page['frames']] == list(range(105))
assert all(sha(page['file']) == page['sha256'] for page in pages)
assert read(C/'incoming/gate.json')['passed']
assert read(C/'incoming/ROOT_EXIT_RECEIPT.json')['passed']
conclusion = '显式绑定参考视频并要求保留内容后，球员、连续运球和霓虹篮球已恢复。构图偏差仍贯穿全片：画面朝向地面，地面占比增加，前半段人物上半身裁切更严重。完整任务判为部分完成；可对应的运球段大体接近原片时序。'
review = {
 'schema':'r110-actual-full105-visual-review-v1','created_unix':time.time(),
 'reviewer':'recover_r99_r101','valid_frame_count':105,'fps':24,
 'reviewed_frames':list(range(105)),'all_valid_frames_inspected':True,
 'method':'All 18 physical-frame triptych sheets inspected; full 16:9 content after removal of fixed model padding only.',
 'columns':['reference','R109 short ordinary','R110 reference-bound ordinary'],
 'presentation_sha256':sha(C/'showcase/PRESENTATION.json'),
 'pre_output_plan_sha256':sha(C/'audit/PRE_OUTPUT_REVIEW_PLAN.json'),
 'actual_bindings':{n:sha(C/'incoming'/n) for n in ['source.mp4','p1.mp4','plain.mp4','gate.json','COMPLETE.json','ROOT_EXIT_RECEIPT.json','COLLECTION.json']},
 'bound_prompt_result':{
  'status':'PARTIAL','complete_task_success':False,'requested_ball_edit_success':True,
  'player_preservation':'Player remains present throughout frames 0–104; same broad appearance and clothing retained.',
  'ball_edit':'Neon-coloured seams visible on the basketball throughout corresponding visible portions. Motion blur/trails and mild deformation occur around fast bounces.',
  'camera_composition':'FAIL: downward framing and increased court-floor proportion persist. Opening/early-mid sequence crops head and upper body more than source; even after the face becomes visible late, floor/sky composition remains different.',
  'motion_preservation':'Continuous dribbling and broad side-to-side ball sequence retained; no inserted shot cut. Corresponding visible phases are broadly close.',
  'camera_motion':'Broad continuing shot retained, with altered camera direction/framing across the sequence.',
  'timing_lag_frames':None,'timing_status':'No clear whole-event timing failure established. First two visible bounces show only exploratory roughly 1–2-frame differences; late ground contacts partly outside source frame.',
 },
 'short_prompt_result':{'status':'FAIL','complete_task_success':False,'summary':'Frames 0–49 omit player; frame 50 inserts cut; late brown basketball fails requested neon appearance.'},
 'conclusion_zh':conclusion,'guidance_support':False,
 'next':'Archive partial task/composition failure; skip matching timing guidance; parent directs R90 then R104.',
 'release_verified':True,'pages':pages,'overview_frames':[0,18,36,60,84,104],
}
write(A/'REVIEW.json',review)
rows=[]
for f in review['overview_frames']:
 page=next(x for x in pages if f in x['frames'])
 im=Image.open(page['file']); idx=page['frames'].index(f)
 # Consumer pages: 24px header + 294px rows, with 24px frame caption.
 row_h=(im.height-24)//len(page['frames'])
 rows.append(im.crop((0,24+idx*row_h,im.width,24+(idx+1)*row_h)))
overview=Image.new('RGB',(rows[0].width,sum(x.height for x in rows)),(0,0,0));y=0
for row in rows: overview.paste(row,(0,y));y+=row.height
overview.save(A/'six_times.jpg',quality=92)
rows[0].save(A/'frame_000.jpg',quality=94)
hp=Path(pres['html']); original=hp.read_text(); (A/'HTML_BEFORE_REVIEW.html').write_text(original)
assert 'id="full105-review"' not in original
addition='<section id="full105-review"><h2>全片检查</h2><p>'+html.escape(conclusion)+'</p><p>检查覆盖全部 105 个有效帧。三列依次为参考视频、一句话普通编辑、显式参考普通编辑；本页比较提示词设置。</p></section>'
closing='</body>' if '</body>' in original else '</html>'
assert closing in original
updated=original.replace(closing,addition+closing)
assert re.findall(r'data:video/mp4;base64,[^"\s]+',original)==re.findall(r'data:video/mp4;base64,[^"\s]+',updated)
hp.write_text(updated)
write(A/'HTML_REVIEW_UPDATE.json',{'before_sha256':sha(A/'HTML_BEFORE_REVIEW.html'),'after_sha256':sha(hp),'html':str(hp),'embedded_video_unchanged':True,'review_sha256':sha(A/'REVIEW.json')})
state=read(P/'audit/RECOVERY_LANE_STATE.json');state.update(updated_unix=time.time(),state='COMPLETE_RELEASED_FULL105_REVIEWED',gate_sha256=sha(C/'incoming/gate.json'),release_sha256=sha(C/'incoming/ROOT_EXIT_RECEIPT.json'),review=str(A/'REVIEW.json'),review_sha256=sha(A/'REVIEW.json'),conclusion=conclusion,next='R90 then R104, fresh resources/peer validation required')
write(P/'audit/RECOVERY_LANE_STATE.json',state)
(P/'CURRENT_HANDOFF.md').write_text('# R110 completed\n\n'+conclusion+'\n\nActual release and input matching passed. Review: '+str(A/'REVIEW.json')+'\n\nNext assigned queue: R90 → R104, after fresh capacity and peer checks.\n')
print(json.dumps({'review_sha256':sha(A/'REVIEW.json'),'html_sha256':sha(hp),'gate_sha256':sha(C/'incoming/gate.json')},indent=2))
