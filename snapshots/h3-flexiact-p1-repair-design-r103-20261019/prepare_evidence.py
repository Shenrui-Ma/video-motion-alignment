from pathlib import Path
import json,hashlib,subprocess,re,time
R=Path(__file__).resolve().parent;BASE=R.parent
rd=lambda p:json.loads(p.read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bound(p):return {'file':str(p),'sha256':sha(p)}
candidates=BASE/'h3-task-repair-queue-audit-20261019/NEXT_REPAIR_CANDIDATES.json';rows=[x for x in rd(candidates)['candidates'] if x['source_id'] in ['human2animal_2__game_man_4','chest']]
official=BASE/'h3-timing-local-edit-protocol-r78-20261018/design/OFFICIAL_REF_EN.txt';r98=BASE/'h3-timing-flexiact-character-repair-r98-20261019';oldproto=rd(r98/'configs/scientific_contract.json')['cases'][0]['prompt'];(R/'R98_SUCCESSFUL_P1_REFERENCE.txt').write_text(oldproto)
items=[]
for row in rows:
 src=row['source_id'];parent=Path(row['contract']['file']).parents[1];graph=parent/'configs/graphs'/f'{row["original_run"]}.json';g=rd(graph)
 for name in ['source','target_image','contract','viewed_existing_contact_sheet']:assert sha(row[name]['file'])==row[name]['sha256'],name
 assert g['5']['inputs']['prompt']==row['original_prompt'] and g['5']['inputs']['ref_image']==['21',0] and g['5']['inputs']['ref_video']==['23',0]
 assert g['21']['inputs']['image']==Path(row['target_image']['file']).name and g['22']['inputs']['file']==Path(row['source']['file']).name
 props=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,nb_read_frames,avg_frame_rate','-of','json',row['source']['file']]))['streams'][0];assert (props['width'],props['height'],props['nb_read_frames'],props['avg_frame_rate'])==(1152,768,'158','24/1')
 key=src if src!='chest' else 'chest__game_girl_1';prompt=R/'prompts'/f'{key}_P1.txt';text=prompt.read_text();sections=re.findall(r'^(subject_definitions|summary|retention_analysis|detailed_description|overall_soundscape|non_diegetic_music):$',text,re.M);assert sections==['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music'];assert '[reference generation]' in text and '[Shot 1]' in text and '<Picture 1>' in text and '<Video 1>' in text
 (R/'prompts'/f'{key}_P0.txt').write_text(row['original_prompt']+'\n')
 items.append({'case_id':key,'source_id':src,'original_pair_scope':row['pair_scope'],'original_run':row['original_run'],'source':row['source'],'target_image':row['target_image'],'old_graph':bound(graph),'old_contract':row['contract'],'existing_fixed_frame_evidence':row['viewed_existing_contact_sheet'],'actual_graph_reference_edges':{'image_21':g['21'],'video_22':g['22'],'components_23':g['23'],'H3_reference_5':{k:g['5']['inputs'][k] for k in ['ref_image','ref_video','width','height','length','semantic_fps','phase_frames']}},'source_video_properties':props,'candidate_prompt':bound(prompt),'P0_prompt':bound(R/'prompts'/f'{key}_P0.txt'),'prompt_status':'proposal_only_no_generation','timeline':{'valid_frames':147,'total_frames':158,'fps':24,'original_motion_frames':49,'original_motion_fps':8,'evaluation_indices':list(range(0,147,3))},'scientific_diff':'P1 protocol plus explicit source roles, visible appearance and source action descriptions; source/target assets unchanged. Prompt bundle effect, not isolated syntax effect.'})
assert items[0]['target_image']['sha256']==sha(r98/'inputs/target_game_man_4.jpg')
e={'schema':'r103-task-repair-design-evidence-v1','created_unix':time.time(),'candidate_origin':bound(candidates),'official_format':{'snapshot':bound(official),'url':'https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing/references/ref-en.txt','commit':'d21241f0a4b3acbb34c97dae47fa417b7065e438'},'successful_style_reference':bound(r98/'configs/scientific_contract.json'),'items':items,'scope':'CPU text proposal and existing source/target verification only. No producer, queue, model or GPU.'}
(R/'EVIDENCE.json').write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'cases':len(items),'six_section_prompts':True,'source_and_target_sha_verified':True,'actual_graph_edges_verified':True,'EVIDENCE':bound(R/'EVIDENCE.json')}))
