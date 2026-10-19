from pathlib import Path
from PIL import Image
import json,hashlib,time,re,shutil
R=Path(__file__).resolve().parents[1];A=R/'audit/full105_review';A.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
pres=json.loads((R/'showcase/PRESENTATION.json').read_text());pages=pres['all_frame_pages'];assert sum((p['frames'] for p in pages),[])==list(range(105))
for p in pages:assert sha(p['file'])==p['sha256']
rows=[]
for i in [0,18,36,60,84,104]:
 p=next(p for p in pages if i in p['frames']);im=Image.open(p['file']);k=p['frames'].index(i);rows.append(im.crop((0,30+k*298,1440,30+(k+1)*298)))
canvas=Image.new('RGB',(1440,30+298*6),'black');canvas.paste(Image.open(pages[0]['file']).crop((0,0,1440,30)),(0,0))
for k,row in enumerate(rows):canvas.paste(row,(0,30+k*298))
canvas.save(A/'six_times.jpg',quality=95)
Image.open(pages[0]['file']).crop((0,0,1440,328)).save(A/'frame_000.jpg',quality=95)
review={'schema':'r109-actual-full105-visual-review-v1','created_unix':time.time(),'reviewer':'recover_r99_r101','valid_frame_count':105,'fps':24,'reviewed_frames':list(range(105)),'all_valid_frames_inspected':True,'method':'Inspect all 18 physical-frame triptych sheets; fixed row times; full 16:9 content after removing only model padding.','columns':['reference','R100 six-section ordinary','R109 exact-short ordinary'],'presentation_sha256':sha(R/'showcase/PRESENTATION.json'),'actual_bindings':{n:sha(R/'incoming'/n) for n in ['source.mp4','p1.mp4','plain.mp4','gate.json','COMPLETE.json','ROOT_EXIT_RECEIPT.json','COLLECTION.json']},'task':'Replace basketball with neon-lit basketball while preserving player, dribbling, continuous shot and original composition.','short_prompt_result':{'complete_task_success':False,'player_preservation':'FAIL: player absent throughout frames 0–49; reappears at frame50 after an inserted shot cut.','ball_edit':'PARTIAL: temporary neon seams around frames10–37 in ball close-up, ordinary brown ball during late player shot50–104.','camera_composition':'FAIL: opening ball close-up replaces source low-angle player shot; frame50 switches to a higher angle and substantially different floor/person proportions.','motion_preservation':'FAIL: initial dribbling removed; late dribbling resumes in altered shot with mismatched ball visibility and phases.','timing_lag_frames':None,'timing_status':'UNKNOWN: action/shot correspondence does not support a single phase-lag measurement.'},'old_p1_result':{'complete_task_success':False,'status':'PARTIAL','ball_edit':'Neon basketball visible throughout inspected sequence.','player_motion':'Player and continuous dribbling retained, with substantial downward framing/floor-area deviation and longer head/upper-body cropping.'},'conclusion_zh':'一句话提示词未修复篮球任务。前50帧人物缺失，改成球的特写；第50帧切换镜头，后半段恢复人物但球未保持霓虹外观。六段提示词版保留了球员和运球，也完成了球外观变化，但原镜头构图偏移仍明显。','next':'R110 ordinary-only prompt explicitly binds <Video 1> and states original player/actions/framing/scene/timing preservation, with identical numerical setup and original noise.','guidance_support':False,'release_verified':True,'pages':pages,'overview_frames':[0,18,36,60,84,104]}
put(A/'REVIEW.json',review)
(A/'REPORT.txt').write_text(review['conclusion_zh']+'\n全部105有效帧已检查。动作对应关系被镜头切换打断，时延记UNKNOWN。R109实际推理已完成，精确进程及CUDA释放通过。\n')
html=Path(pres['html']);before=html.read_text();backup=A/'HTML_BEFORE_REVIEW.html'
if not backup.exists():shutil.copy2(html,backup)
needle='<video controls';paragraph='<p><strong>全片检查结果：</strong>'+review['conclusion_zh']+'</p>'
assert '<strong>全片检查结果：</strong>' not in before
new=before.replace(needle,paragraph+needle,1);assert new!=before
media=lambda s:re.findall(r'data:(?:video/mp4|image/jpeg);base64,[A-Za-z0-9+/=]+',s)
assert media(before)==media(new);html.write_text(new)
put(A/'HTML_REVIEW_UPDATE.json',{'html':str(html),'before_sha256':sha(backup),'after_sha256':sha(html),'media_unchanged':True,'review_sha256':sha(A/'REVIEW.json')})
state=Path('/Users/researcher/DevProjects/h3-timing-ive-basketball-shortprompt-r109-20261019/audit/RECOVERY_LANE_STATE.json')
put(state,{'updated_unix':time.time(),'state':'R109_COMPLETE_RELEASED_FULL105_REVIEWED','review':str(A/'REVIEW.json'),'review_sha256':sha(A/'REVIEW.json'),'task_success':False,'next':'prepare R110 explicit reference-bound ordinary prompt control, parent directed'})
print(json.dumps({'review':str(A/'REVIEW.json'),'sha256':sha(A/'REVIEW.json'),'html':str(html),'six_times':str(A/'six_times.jpg')},ensure_ascii=False))
