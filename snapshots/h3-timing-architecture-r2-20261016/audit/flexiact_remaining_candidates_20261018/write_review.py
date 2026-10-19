from pathlib import Path
import json,hashlib
from PIL import Image,ImageDraw,ImageFont,ImageOps
r=Path(__file__).resolve().parent
old=Path('/Users/researcher/DevProjects/h3-ivebench-remaining-metrics-r69-20261018/audit/flex_official_inventory/FIXED_8_CANDIDATES.json')
rows=json.loads(old.read_text())['pairs'];by={p['source']+'__'+Path(p['target']).stem:p for p in rows}
notes=[('crouch__movie_man_9','priority','两次下蹲—低位—站起；约1.5–2.0秒及4.5–5.0秒在低位，3.0和6.0秒回高位。全身、膝髋和脚均可见。目标为完整西装人体，白色廊柱场景有平整地面；深色裤装可能限制关节检测。官方此行正确写squats，旧候选的器械caption警告误贴到此行。'),('rotate__game_man_4','priority','合手在胸前，连续左右转体并回中；可核方向顺序及回中时间。源与目标全身可见，目标为正常人体比例动漫人物，绿色斗篷与腿部装具提供身份特征；斗篷可能遮肘。白底场景适合原地转体。官方brown coat文字与图中主要灰衣/绿斗篷有差别，动作caption一致。'),('chest__movie_man_7','priority','两轮手臂展开—收至身体前下方—再展开，约1.5–2.0及4.5–5.0秒收至低位。目标躯干和手臂裸露、正常人体比例；腿部不全，不能记全身。源手部会出边界，后段构图移动。目标水边缺少源片器械，保持持索接触关系需额外场景适配，风险较高。'),('rotate__game_man_1','reserve','与rotate/game4完全相同原片。红帽、蓝背带裤、白手套、浅底场景让身份容易辨认；短肢和较大头身比增加运动几何迁移难度。仅作为额外身份/跨比例测试，不新增动作源。')]
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',25);out=[]
for i,(key,decision,note) in enumerate(notes):
 p=by[key];sheet=Image.open(r/(p['source']+'_source_13_times.png')).convert('RGB');canvas=Image.new('RGB',(1440,1150),'black');d=ImageDraw.Draw(canvas)
 target=ImageOps.contain(Image.open(p['target_asset']['path']).convert('RGB'),(600,280));canvas.paste(target,(20,40))
 for y,s in [(70,key),(110,'Official target image + original motion'),(150,f'Priority {i+1} | CSV row {p["csv_row_zero_based"]+1}')]:d.text((650,y),s,font=font,fill='white')
 canvas.paste(sheet,(0,320));path=r/(key+'_source_target.png');canvas.save(path)
 out.append({'priority':i+1,'pair_key':key,'decision':decision,'notes':note,'official_csv_row_zero_based':p['csv_row_zero_based'],'source':p['source_asset'],'target':p['target_asset'],'contact_sheet':str(path),'existing_motion':True,'actual_native_generated_for_this_pair':False})
receipt={'dataset_revision':json.loads(old.read_text())['dataset_revision'],'original_candidate_pairs':8,'in_r85_original_fixed8':2,'remaining':6,'remaining_actual_previously_generated':2,'new_pair_candidates':4,'priority_candidates':3,'reserve_candidates':1,'distinct_motion_sources_in_new_pairs':3,'new_original_motion_sources':0,'selection_basis':'original videos and target images; prior actual-run records separately labelled','ranked_candidates':out,'existing_pairs_not_new':{'fitness__game_man_5':'R72 actual P0/P1 completed; major motion and target identity succeeded; R84 fixed already prepared.','chest__game_man_5':'R74 actual Native completed; target identity failed; retain old failure.'},'asset_and_csv_verification':'SOURCE_SHEET_RECEIPT.json','sampling':'original frames0,4,...,48 at8fps, exactPTS; approximate stage observations, not precise event ground truth','GPU_started':False}
(r/'CANDIDATE_REVIEW.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
lines=['旧8条FlexiAct候选：源片与目标图审查','','优先3条：crouch/movie9、rotate/game4、chest/movie7。备用1条：rotate/game1。四对共3种已经使用过的原片，新增原片数为0。它们是有清晰阶段的循环练习，不能记为密集的不同动作序列。','','原8条中R85包含crouch/movie5与one_leg/movie9；R85的rotate/gamegirl1不在旧8条中。余6条中fitness/game5和chest/game5已有实际成片，因此未生成配对仅4条。目标图可见性/人体比例用于挑输入，身份保持成功仍由实际Native验证。']
for p in out:lines+=['',f'{p["priority"]}. {p["pair_key"]} ({p["decision"]})',p['notes'],'图：'+p['contact_sheet']]
lines+=['','每张原片图取0,4,...,48帧，共13时刻，8fps；总49帧，末帧PTS6.000秒。所有8行CSV及素材SHA已实际核对。保留旧样本失败；未新建推理队列。']
(r/'REPORT.txt').write_text('\n'.join(lines)+'\n')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(r/'REVIEW_ARTIFACTS.json').write_text(json.dumps({p.name:{'sha256':sha(p),'bytes':p.stat().st_size}for p in r.iterdir()if p.is_file()and p.name!='REVIEW_ARTIFACTS.json'},indent=2)+'\n')
print(r/'REPORT.txt')
