from pathlib import Path
import copy,json,hashlib,time
R=Path(__file__).resolve().parents[1]
Q=R.parent/'h3-flexiact-prompt-control-mf-r90-20261019'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=R/'inventory/flexiact.json';before=sha(p);d=read(p);old=copy.deepcopy(d['items'])
row=next(x for x in d['items'] if x['id']=='flex_r90_one_leg__movie_man_9_prompt_control')
assert row['comparison_kind']=='prompt_control' and row['guided_video_path'] is None
receipt=Q/'RESULT_VERIFIED.json';v=read(receipt);inputs=Q/'prepared/MF_INPUTS.json';m=read(inputs)
assert v['guidance_used'] is False and v['evaluation_frames']==49 and v['evaluation_fps']==8
assert sha(m['source_original']['file'])==m['source_original']['sha256']==v['source_original_sha256']
scores={}
evidence=[receipt,inputs]
for method,key in [('old_native','ordinary_video_path'),('new_native','alternative_video_path')]:
    f=Path(v['scores'][method]['file']);assert sha(f)==v['scores'][method]['sha256'];s=read(f)
    assert s['actual_generated_video_sha256']==sha(row[key])==m['targets'][method]['full_sha256']
    assert s['score']==v['score'][method] and s['evaluation_frames']==49 and s['evaluation_fps']==8
    assert m['targets'][method]['indices']==list(range(0,147,3))
    scores[method]=s; evidence.append(f)
assert scores['old_native']['reference_report']==scores['new_native']['reference_report']
release=Path(v['release']['file']);assert sha(release)==v['release']['sha256'];evidence.append(release)
row['quantitative_metrics']['motion_fidelity'].update(
    native=v['score']['old_native'],alternative_native=v['score']['new_native'],guided=None,delta=None,
    prompt_delta=v['score']['new_native']-v['score']['old_native'],status='complete_prompt_control',
    evaluation_frames=49,evaluation_fps=8,reference_original_sha256=v['source_original_sha256'],
    source_files=[str(x) for x in evidence],source_sha256={str(x):sha(x) for x in evidence},
    scope='R85 P0与R90 P1普通编辑的提示词对照；两版0次引导。官方FlexiAct MF使用原始49帧8fps参考，生成视频取0,3,…144帧。可见上肢动作改善，完整单腿姿势因脚部出框仍无法核验。')
for f in evidence:
    if str(f) not in row['evidence_paths']:row['evidence_paths'].append(str(f))
    row['evidence_sha256'][str(f)]=sha(f)
for a,b in zip(old,d['items']):
    if a['id']!=row['id']:assert a==b
d['previous_inventory_sha256']=before;d['updated_unix']=time.time();assert sha(p)==before
a=R/'audit/r90_prompt_mf_20261019';a.mkdir(exist_ok=False);(a/'PREVIOUS_INVENTORY.json').write_bytes(p.read_bytes())
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
result={'before_sha256':before,'after_sha256':sha(p),'id':row['id'],'score':v['score'],'review_unchanged':True}
(a/'RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
