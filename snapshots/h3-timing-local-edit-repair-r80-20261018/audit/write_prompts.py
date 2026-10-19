from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
template='''subject_definitions:
<Video 1> is the source video for this local video edit, providing the original camera framing, shot structure, visible action sequence, pacing and duration.
<Subject 1> {subject1_definition}
<Subject 2> {subject2_definition}
Source context: {source_prompt}

summary:
[video editing] The target video is an edited version of <Video 1>. {summary}
Requested edit: {edit_prompt}

retention_analysis:
<Subject 1> (appears in [Shot 1]): partially_preserved - {subject1_retention}
<Subject 2> (appears in [Shot 1]): fully_preserved - {subject2_retention}
<Video 1> (cut and pacing structure): fully_preserved - preserve the original framing, camera movement, shot continuity, action order, pacing and duration.

detailed_description:
The target video retains the photographic appearance, lighting and camera composition of <Video 1>.
[Shot 1] {target_prompt}
{shot}

overall_soundscape:
No specific soundscape is requested.

non_diegetic_music:
No specific music is requested.
'''
rows={
'short_0230':{
'subject1_definition':'is the woman preparing food in <Video 1>, with long brown hair, a patterned red headscarf, a patterned apron and a light short-sleeved shirt. Her identity, pose, hands and food-preparation movements come from the source video.',
'subject2_definition':'is the original kitchen and its visible objects in <Video 1>, including the counter, metal food bowl, smaller bowls, green packet in the woman\'s hand, food, wooden interior and window light.',
'summary':'Change the headscarf and apron of <Subject 1> to blue within the original kitchen <Subject 2>, preserving her food-preparation action.',
'subject1_retention':'change the headscarf and apron colors to blue while preserving their shape, fabric patterns and fit. Preserve the same woman, hair, face, light shirt, body pose, hand positions and the original sequence and timing of preparing food.',
'subject2_retention':'preserve the same kitchen, counter, bowls, food and green packet, their appearance and placement, the lighting, and the original interactions between the hands and these objects.',
'shot':'<Subject 1>, the same long-haired woman now wearing a blue headscarf and blue apron over her original light shirt, occupies the source position beside the counter in <Subject 2>. She holds and tips the original green packet over the metal bowl and continues the visible hand and food-preparation movements from <Video 1> in their source order and timing. The camera, kitchen and all unedited objects follow the original shot.',
'visible_source_note':'Source six frames show a red patterned headscarf but an apron with a mostly dark patterned field and red/white trim; the official caption calls the apron red. Preserve the official instruction verbatim and edit both garment colors to blue; retain garment patterns/cut. Do not interpret the whole shirt as apron.'},
'short_0352':{
'subject1_definition':'is the seated performer in <Video 1>, originally a short-haired man in layered clothing and a scarf. The source performer supplies the visible body placement, pose, gaze and hand-gesture sequence; the target appearance is a woman wearing a modern dress.',
'subject2_definition':'is the original wooden room and its visible objects in <Video 1>, including the window panes, timber background and the thick rope-wrapped railing behind the seated performer.',
'summary':'Replace the appearance of <Subject 1> with a woman in a modern dress, keeping the original seated performance and room <Subject 2>.',
'subject1_retention':'replace the man and his clothing with a woman in a modern dress. Preserve the source screen position, seated body pose, gaze direction, expressive movement and the order, timing and duration of the visible hand gestures. The target female identity and dress replace the source male identity and attire.',
'subject2_retention':'preserve the wooden room, window panes, timber background, rope-wrapped railing, lighting and their arrangement within the original framing.',
'shot':'<Subject 1>, now a woman in a modern dress, remains seated in the original upper-body framing in <Subject 2>. Her gaze, head movements and visible hand-gesture sequence follow the seated performer in <Video 1> in the same order and timing. The original windows and rope-wrapped railing remain behind her with the source lighting and camera composition. Only the requested performer appearance and attire are replaced.',
'visible_source_note':'Six source frames show a seated short-haired man, brown layered jacket, purple scarf, wooden windows/railings and a brief raised hand. Official traditional-attire category retained as task metadata; do not ask to preserve original male facial identity or clothing in the target.'}}
(R/'design/P1_TEMPLATE.txt').write_text(template)
s=read(R/'configs/scientific_contract.json');metadata=[]
for c in s['cases']:
 source=c['source_id'];row=dict(c['original_task'],source_id=source,**rows[source]);metadata.append(row)
 prompt=template.format(**row);(R/c['prompt_file']).write_text(prompt);c.update(prompt=prompt,prompt_sha256=sha(R/c['prompt_file']))
s['prompt_template_sha256']=sha(R/'design/P1_TEMPLATE.txt')
save(R/'design/PROMPT_FIELDS.json',{'protocol':'P1-local-v1','rows':metadata});s['prompt_fields_sha256']=sha(R/'design/PROMPT_FIELDS.json');save(R/'configs/scientific_contract.json',s)
save(R/'design/SOURCE_REVIEW.json',{'source_only':True,'results_used_to_write_prompt':False,'sources':{source:{'six_frames':([0,17,34,51,68,85] if source=='short_0230' else [0,15,31,46,62,77]),'note':v['visible_source_note']} for source,v in rows.items()},'precision':'Sparse views establish visible content only; no manually timed event window or precise lag label.'})
save(R/'design/PROTOCOL.json',{'name':'P1-local-v1','guide_file':'design/OFFICIAL_REF_EN.txt','guide_sha256':sha(R/'design/OFFICIAL_REF_EN.txt'),'official_source':'https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing/references/ref-en.txt','preserved_verbatim':['source_prompt','edit_prompt','target_prompt'],'task_adaptation':'Visible Subject definitions, full scene retention and partial desired appearance change; original single shot and no invented event timestamp.','inference_claim':'Task repair under a new host profile; no isolated prompt-causal or temporal-method improvement claim.'})
