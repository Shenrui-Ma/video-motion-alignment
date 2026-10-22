"""Freeze sparse source-only human-evaluation checkpoints, separate from inference."""
import datetime,hashlib,json
from pathlib import Path
B=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((B/'SELECTED_4_MANIFEST.json').read_text())
labels={
'short_0092':[(16,'手掌仍举在胸外侧，处于挥手姿态。'),(27,'同一只手已经移到上胸前并贴近衣领。')],
'short_0114':[(35,'球位于双腿之间低处，手正向下运球。'),(49,'球已移至画面右侧，另一只手在该侧控球。')],
'short_0126':[(20,'双肘弯曲，双手在头侧附近。'),(41,'双手合在头顶上方，双臂向上伸展。')],
'short_0392':[(20,'前伸的指向手下摆，手腕处于较低位置。'),(40,'同一只手再次抬高，手指仍向镜头方向。')],
}
risks={
'short_0092':'后段前景相机遮挡，用这两个可见检查点核对挥手→手到胸前的顺序。',
'short_0114':'周期运球存在多个相似瞬间，同时核对手、球的左右侧与换手顺序。',
'short_0126':'抬臂后保持较久，先核对弯肘→向上伸展的转变，避免把静态保持误当已同步。',
'short_0392':'低照度、透视缩短且有身体运动；检查手相对肩/胸的位置，不能只看全画面像素位移。',
}
rows=[]
for r in m['pairs']:
 id=r['pair_id'];p=r['input_protocol'];check=[]
 for i,label in labels[id]:
  ids=[j for j,k in enumerate(p['input_to_original_frame'][:p['effective_frame_count']]) if k==i]
  assert ids
  j=min(ids,key=lambda j:abs(j/24-r['source']['actual_pts_s'][i]))
  check.append({'source_frame':i,'source_time_s':r['source']['actual_pts_s'][i],'prepared_frame':j,'prepared_time_s':j/24,'same_original_frame':True,'visible_state':label})
 rows.append({'pair_id':id,'source_sha256':r['source']['sha256'],'checkpoints':check,'inspection_note':risks[id],'source_contact_sheet':str(B/'source_event_review'/f'{id}.jpg'),'source_contact_sheet_sha256':sha(B/'source_event_review'/f'{id}.jpg')})
record={'schema':'r64-source-only-evaluation-checkpoints-v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'usage':'evaluation_only; do not feed to model prompts, intervention window selection, controller, or sampler','annotation_scope':'Sparse directly viewed states and transitions; not dense onset/offset labels and not a claim of exact extrema. Check matching physical prepared frames in completed videos, then inspect a surrounding short clip.','new_h3_outputs_consulted':0,'selection_sha256':sha(B/'SELECTED_4_MANIFEST.json'),'prepared_inputs_manifest_sha256':sha(B/'PREPARED_INPUTS_MANIFEST.json'),'pairs':rows}
path=B/'SOURCE_ONLY_EVALUATION_CHECKPOINTS.json';assert not path.exists();path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
lines=['仅源人工复核检查点（只用于评估）','', '成片按 prepared frame 同帧检查；原source frame用于追溯。每条两点对应可见状态，未作密集起止标注。','']
for r in rows:
 lines.append(r['pair_id'])
 for c in r['checkpoints']:
  lines.append(f"  原帧{c['source_frame']} / {c['source_time_s']:.6f}s → 输入帧{c['prepared_frame']} / {c['prepared_time_s']:.6f}s：{c['visible_state']}")
 lines.append('  '+r['inspection_note']);lines.append('')
(B/'SOURCE_ONLY_EVALUATION_CHECKPOINTS.txt').write_text('\n'.join(lines)+'\n')
paths=[path,B/'SOURCE_ONLY_EVALUATION_CHECKPOINTS.txt',B/'scripts/freeze_evaluation_checkpoints.py',B/'scripts/make_event_review.py',B/'source_event_review/FRAMES.json']+[B/'source_event_review'/f"{x['pair_id']}.jpg" for x in rows]
(B/'EVALUATION_CHECKPOINT_FREEZE.json').write_text(json.dumps({'files':[{'file':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in paths]},ensure_ascii=False,indent=2)+'\n')
print('\n'.join(lines));print('checkpoint SHA',sha(path))
