from pathlib import Path
import json,shutil,subprocess,hashlib
A=Path(__file__).parent;O=A.parents[1];B=O/'audit/flexiact_inventory/build_inventory.py';I=O/'inventory/flexiact.json';V=O/'audit/flexiact_inventory/PATH_AND_SHA_VALIDATION.json';bk=A/'flex_display_revision';bk.mkdir(exist_ok=True)
for p in [B,I,V]:
 q=bk/(p.name+'.before');assert not q.exists();shutil.copy2(p,q)
changes={
'flex_r85_crouch__movie_man_5_fixed':{'review_status':'部分任务失败；时序接近','display_summary':'普通版身份替换不完整，引导版短发更贴目标；两版目标图白背景均未实现。下蹲起立已接近参考时序。','review_summary':'完整147帧审阅：普通版保留源人物扎发，身份替换仅部分完成；固定引导版短发更接近目标，细小侧脸不足以确认精细身份。两版仍在湖面栈桥，目标图白背景要求失败。两次下蹲起立和胸前手势保留，原本已大致同相，未见清楚的时序收益。'},
'flex_r66_fitness__game_man_4':{'review_status':'身份完成，场景失败','display_summary':'目标短黑发动漫男性及服装已替换，白背景变成山地；动作时序原本接近，固定引导无清楚收益。','review_summary':'完整49个原动作时刻和关键过渡共91帧已审阅，并补查同一目标图：短黑发、动漫男性面孔、绿披肩和棕白服装出现，源人物长发和面部未保留，主要身份外观替换完成。目标图白背景却变为山地，场景要求失败。展开、上举、接近合掌和下放序列保留，普通版已大致同相，引导无清楚时序收益；高举手部部分出画。'},
'flex_r85_one_leg__movie_man_9_fixed':{'review_status':'动作内容与时序保持失败','display_summary':'目标西装人物和场景完成；两版新增胸前合掌路径且显著晚举臂，固定引导未修复。','review_summary':'完整147帧审阅：目标人物面部、西装与图中场景保留，身份和场景迁移主要完成。两版都明显晚举臂，并插入源片没有的胸前合掌再向上举手路径，动作内容和时间保持均失败，固定引导未修复。开头构图拉远、下肢裁切影响腿部事件判断；不同举臂路径的时刻差不能当作整个动作的恒定延迟。'},
'flex_r66_human2animal_3__movie_man_11':{'review_status':'身份与场景待核验','display_summary':'已有六时刻仅确认向倒立转换，前段姿态和构图有变化；目标身份与场景尚缺明确验收，未见清楚时序收益。','review_summary':'既有固定六时刻审阅确认两版均由低支撑向倒立发展，前段肘部、身体姿态和构图与参考不同；普通版与引导版接近，未见清楚时序修复。现有记录未分别验收目标人物身份和目标图场景，这两项保留未知，不计为完整任务成功。'}}
s=B.read_text();marker='# Validate actual file availability, bind SHA, and forbid duplicate output sets.';assert s.count(marker)==1
block='display_acceptance_revision='+repr(changes)+'\nfor item in items:\n if item["id"] in display_acceptance_revision:item.update(display_acceptance_revision[item["id"]])\n'
B.write_text(s.replace(marker,block+marker));subprocess.run(['/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python',str(B)],check=True)
a=json.loads((bk/'flexiact.json.before').read_text());b=json.loads(I.read_text());aa={x['id']:x for x in a['items']};bb={x['id']:x for x in b['items']};assert set(aa)==set(bb);delta={}
for k,v in aa.items():
 diff={f:{'before':v.get(f),'after':bb[k].get(f)} for f in set(v)|set(bb[k]) if v.get(f)!=bb[k].get(f)}
 if k in changes:assert set(diff)<=set(changes[k]);delta[k]=diff
 else:assert not diff,(k,diff)
assert a['counts']==b['counts'];assert a['distinct_motion_sources']==b['distinct_motion_sources']
r={'passed':True,'only_display_fields_changed':True,'changed_items':delta,'other_items_unchanged':17,'counts_unchanged':b['counts'],'media_pairing_unchanged':True,'basis':str(A/'REVIEW.json'),'inventory_sha256':hashlib.sha256(I.read_bytes()).hexdigest()};(bk/'VALIDATION.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(r['inventory_sha256'])
