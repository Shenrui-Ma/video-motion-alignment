from pathlib import Path
import hashlib,json,sys
r=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
template='''subject_definitions:
<Video 1> is the source video for this video edit, providing the original camera framing, shot structure, action order, pacing and duration.
<Subject 1> is the gray-haired man in <Video 1>, wearing blue clothes and holding a small cup near his mouth. His identity, facial features, hair and visible movements come from <Video 1>.
<Subject 2> is the original room and its visible objects in <Video 1>, including the wooden furniture, window, room lighting and the small cup held by the man.
Source context: {source_prompt}

summary:
[video editing] The target video is an edited version of <Video 1>. The clothes of <Subject 1> become white while his actions and the original scene <Subject 2> follow the source video.
Requested edit: {edit_prompt}

retention_analysis:
<Subject 1> (appears in [Shot 1]): partially_preserved - change only the clothes from blue to white. Preserve the same man, his face, gray hair, clothing shape, body pose, expression, gaze, hand motion and complete sipping action with the source action order, timing and duration.
<Subject 2> (appears in [Shot 1]): fully_preserved - preserve the original room, wooden furniture, window, lighting and small cup, including their appearance, placement and visible interactions throughout the source video.
<Video 1> (cut and pacing structure): fully_preserved - preserve the source camera framing and movement, shot continuity, action order, pacing and duration.

detailed_description:
The video retains the photographic appearance, lighting and camera composition of <Video 1>.
[Shot 1] {target_prompt}
<Subject 1>, the same gray-haired man now wearing white clothes, remains in the source upper-body framing within <Subject 2>. At the opening he holds the original small cup near his mouth. His visible sipping and cup-lowering motion, facial expressions and gaze follow <Video 1> in their original order and timing. The original room, wooden furniture, window and lighting remain in their source positions as the shot continues.

overall_soundscape:
No specific soundscape is requested.

non_diegetic_music:
No specific music is requested.
'''
(r/'design/P1_TEMPLATE.txt').write_text(template)
row=read(r/'design/LOCAL_EDIT_METADATA.json')['pairs'][0]
p=template.format(**row);(r/'configs/prompts/p1.txt').write_text(p)
a=read(r/'configs/ancestors/p1_prompt_contract.json');a['5']['inputs']['prompt']=p;write(r/'configs/ancestors/p1_prompt_contract.json',a)
b=read(r/'configs/prompt_ancestry.json');b['p1']['sha256']=sha(r/b['p1']['file']);b['p1']['prompt_sha256']=sha(r/'configs/prompts/p1.txt');b['template']['sha256']=sha(r/b['template']['file']);write(r/'configs/prompt_ancestry.json',b)
s=read(r/'configs/scientific_contract.json');s['prompt_protocols']={'p0':'P0-original-official-edit-text','p1':'P1-local-v1'}
s['purpose']='Same-scene local clothing-color editing: R69 source/seed/geometry/sampling; original P0 vs full-reference P1-local-v1. Known development source.'
for c in s['cases']:
 c['prompt_protocol']=s['prompt_protocols'][c['arm']]
 if c['arm']=='p1':c['prompt']=p;c['prompt_sha256']=sha(r/c['prompt_file'])
write(r/'configs/scientific_contract.json',s)
sys.path.insert(0,str(r/'scripts'));from r78_contract import expected_graph
for c in s['cases']:write(r/'configs/graphs'/(c['run_id']+'.json'),expected_graph(r,c))
guide=Path('/Users/researcher/DevProjects/h3-flexiact-official-six-metrics-r74-20261018/audit/prompt_protocol_review/official/skills/h3-prompt-writing/references/ref-en.txt')
(r/'design/OFFICIAL_REF_EN.txt').write_bytes(guide.read_bytes())
write(r/'design/TEMPLATE_ADAPTATION.json',{'protocol':'P1-local-v1','official_guide':'https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing/references/ref-en.txt','official_local':'design/OFFICIAL_REF_EN.txt','official_sha256':sha(guide),'base_file':'design/R73_PARENT_TEMPLATE.txt','base_sha256':sha(r/'design/R73_PARENT_TEMPLATE.txt'),'previous_draft_snapshot':'audit/pre_p1_local_v1_snapshot','change':'Add visible Subject definitions with fixed retention values and an opening [Shot 1]; keep original edit/source/target text verbatim. Explicit same-man, room, furniture, cup and source action retention. No added event timestamps.','claim':'Combined prompt protocol adaptation, including structural format and explicit content constraints. This is not the original R73 P1 text or an isolated formatting experiment.','numeric_change':False})
f=r/'scripts/r78_contract.py';v=f.read_text().replace('R73-adapted local editing template/P0 relation changed','P1-local-v1 template/P0 relation changed');f.write_text(v)
f=r/'ROOT_HANDOFF.txt';v=f.read_text().replace('P1 使用 R73 六段 video editing 模板，再具体写明同一人物、房间、家具、杯子与喝水动作保留。','P1 使用完整官方 full-reference 结构 P1-local-v1，定义 Video 1、Subject 1/2、retention 和 [Shot 1]；具体保留同一人物、房间、家具、杯子与喝水动作。')
v += '\n修订：P1-local-v1 补齐官方 §2.3 可见 Subject 定义与 §5.1 [Shot 1]，与旧 R73 P1 文本有区别。旧 57 项 seal 及完整 draft 保存于 audit/pre_p1_local_v1_snapshot/。原始 edit/source/target 文本逐字保留；新增明确局部保留约束，属于 prompt bundle 对照。无数值机制改变。\n'
f.write_text(v)
print('P1',sha(r/'configs/prompts/p1.txt'))
