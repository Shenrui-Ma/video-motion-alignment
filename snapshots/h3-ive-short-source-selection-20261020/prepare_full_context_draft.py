from pathlib import Path
import hashlib, json, time

ROOT=Path(__file__).resolve().parent
H=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
planfile=ROOT/'R122_SIX_SOURCE_INPUT_PLAN.json'
plan=json.loads(planfile.read_text())
approved=Path('/Users/researcher/DevProjects/h3-timing-ive-prompt-envelope-retention-r123-20261020/audit/FULL_FORMAT_CANDIDATE_PENDING_RETENTION.txt')
assert H(approved)=='5ea69610fb7e51081d4bdc30ba4f6ab27dff99f9bef9f0157c541cb2250acad4'
subjects={
 'long_0161':('the man in <Video 1>','the woman in <Video 1>','the grass and park scene in <Video 1>'),
 'short_0362':('the book with a blue cover in <Video 1>','the woman and man in traditional attire in <Video 1>','the surrounding scene in <Video 1>'),
 'long_0031':('the wooden cutting board in <Video 1>','the person, yellow bell pepper, and knife in <Video 1>','the kitchen scene and other ingredients and utensils in <Video 1>'),
 'long_0091':('the right hand and its pinky finger in <Video 1>','the other hand and the old-fashioned typewriter in <Video 1>','the surrounding scene in <Video 1>'),
 'long_0034':('the cucumber and the dark surface supporting it in <Video 1>','the person and knife in <Video 1>','the remaining source scene in <Video 1>'),
}
out=ROOT/'full_context_draft_20261020';out.mkdir(exist_ok=False)
rows=[]
for p in plan['pairs']:
 sid=p['source_id']
 if sid not in subjects:continue
 d=out/sid;d.mkdir()
 task=p['official_task'];a,b,c=subjects[sid]
 caption=task['source_prompt'];edit=task['edit_prompt'];target=task['target_prompt']
 text=(f'subject_definitions:\n<Video 1> is the source video for the target video edit and supplies its composition, camera, and temporal structure.\n'
       f'Source caption: {caption}\n<Subject 1> is {a}.\n<Subject 2> is {b}.\n<Subject 3> is {c}.\n\n'
       f'summary:\n[video editing] The target video is an edited version of <Video 1>.\n{edit}\n\n'
       'retention_analysis:\n'
       '<Subject 1> (appears in [Shot 1]): partially_preserved - Apply the edit requested in the summary; preserve its other source properties and actions.\n'
       '<Subject 2> (appears in [Shot 1]): fully_preserved - Preserve these source people and objects, including their appearance and actions.\n'
       '<Subject 3> (appears in [Shot 1]): fully_preserved - Preserve the remaining source scene and objects.\n'
       '<Video 1> (composition, camera, and temporal structure): fully_preserved - Preserve the source framing, camera motion, cuts, and action timing.\n\n'
       f'detailed_description:\n[Shot 1] {target}\n'
       'The edited subject is <Subject 1>; the other source people and objects are <Subject 2>, and the remaining setting is <Subject 3>, as shown in <Video 1>.\n\n'
       'overall_soundscape:\nThe benchmark specifies no audio edit.\n\n'
       'non_diegetic_music:\nThe benchmark specifies no music edit.')
 fields={}
 for name,value in [('source_prompt',caption),('edit_prompt',edit),('target_prompt',target)]:
  f=d/(name+'.txt');f.write_text(value);assert f.read_text()==task[name]
  fields[name]={'text':value,'file':str(f),'sha256':H(f)}
 f=d/'context_ir_draft.txt';f.write_text(text)
 assert 'Source caption: '+caption+'\n' in text
 assert '\n'+edit+'\n\nretention_analysis:' in text
 assert '[Shot 1] '+target+'\n' in text
 assert text.count('[video editing]')==1
 sections=['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
 assert [text.index(x+':') for x in sections]==sorted(text.index(x+':') for x in sections)
 row={'source_id':sid,'official_fields':fields,'original_task':task,'metadata_evidence':p['metadata_evidence'],
      'source_sha256':p['source']['sha256'],'source_clip':p['clip'],'evaluation_scope':p['evaluation_scope'],
      'draft':{'file':str(f),'sha256':H(f)},'subject_definitions':dict(zip(['Subject 1','Subject 2','Subject 3'],subjects[sid])),
      'added_content_scope':'Task/reference links, subject bindings and generic retention; no event times, action sequence expansion or source-derived event annotations.',
      'status':'CPU_TEXT_DRAFT_ONLY_NO_GPU_QUEUE_CHANGE'}
 if sid=='long_0034':row['binding_note']='Subject 1 groups the cucumber and its supporting surface so the added cutting board can be specified without claiming a board already exists in the source.'
 if sid=='long_0091':row['binding_note']='The leading space in the official source_prompt is retained byte-for-byte.'
 rows.append(row)
manifest={'schema':'ive-five-source-full-context-text-draft-v1','created_unix':time.time(),
 'status':'TEXT_ONLY_PENDING_FORMAT_VALIDATION_AND_ROOT_DISPATCH','plan_file':str(planfile),'plan_sha256':H(planfile),
 'approved_structure_reference':{'file':str(approved),'sha256':H(approved)},
 'template_scope':'Same six-section ordering and retention relation tags; source/edit/target captions are exact official strings. Subject identifiers adapted to each task.',
 'items':rows,'GPU_started':False,'queue_changed':False}
(out/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'path':str(out/'MANIFEST.json'),'sha256':H(out/'MANIFEST.json'),'sources':[r['source_id'] for r in rows]},ensure_ascii=False))
