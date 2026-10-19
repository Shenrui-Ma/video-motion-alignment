from pathlib import Path
import json,hashlib,copy,time,re
R=Path(__file__).resolve().parents[1];M=R.parent/'h3-flexiact-character-guidance-mf-r101-20261019';C=R.parent/'h3-flexiact-character-guidance-metrics-r101-20261019';ID='flex_r101_human2animal_1__game_man_4_fixed'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
result=M/'RESULT_VERIFIED.json';v=read(result);score=Path(v['score_evidence']['file']);assert sha(score)==v['score_evidence']['sha256']=='73e1ece058f94d117d8b2a3d9234c026e7a3104b10a3e8164ca6d3a9d0275468';s=read(score)
assert v['status']=='ACTUAL_OFFICIAL_MF_COMPLETE' and v['release']['process_absent'] and v['release']['own_cuda_absent'];assert (s['score'],s['native_score'],s['delta'])==(v['guided'],v['native'],v['delta'])
p=R/'inventory/flexiact.json';before=sha(p);doc=read(p);old=copy.deepcopy(doc['items']);row=next(x for x in doc['items'] if x['id']==ID);assert row['count_as_complete_task_success'] is False
assert row['media_sha256']['guided_video_path']==s['actual_generated_video_sha256'];assert s['actual_gate']['sha256']==sha(C/'incoming/PAIR_RUNTIME_GATE.json')
metric=row['quantitative_metrics']['motion_fidelity'];assert metric['status']=='pending'
metric.update(native=v['native'],guided=v['guided'],delta=v['delta'],status='complete',source_files=[str(result),str(score)],source_sha256={str(x):sha(x) for x in [result,score]},scope='官方FlexiAct MF：同源49帧、8fps、grid55。分数提升0.01486；全147帧审阅仍为角色外观替换完成、动作迁移不完整、无明确时序改善。',grid_size=55,verified_returned_files=22)
for f in [result,score]:
 if str(f) not in row['evidence_paths']:row['evidence_paths'].append(str(f))
 row['evidence_sha256'][str(f)]=sha(f)
assert [x for x in doc['items'] if x['id']!=ID]==[x for x in old if x['id']!=ID]
for key in ['review_summary','count_as_complete_task_success','support_for_clear_whole_event_repair','event_review']:assert row.get(key)==next(x for x in old if x['id']==ID).get(key)
a=R/'audit/r101_official_mf_20261019';a.mkdir(exist_ok=False);(a/'PREVIOUS_INVENTORY.json').write_bytes(p.read_bytes());doc['previous_inventory_sha256']=before;doc['updated_unix']=time.time();assert sha(p)==before;p.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
html=Path('/Users/researcher/Downloads/H3_R101_俯卧支撑_普通编辑与时序引导_20261019.html');text=html.read_text();(a/'HTML_BEFORE_MF.html').write_text(text)
paragraph='<p><strong>官方 Motion Fidelity：</strong>普通编辑 0.52398，时序引导 0.53884，提升 0.01486。全片审阅仍显示动作迁移不完整，当前没有明确的时序改善。</p>'
assert paragraph not in text
out=text.replace('<video',paragraph+'<video',1);assert out!=text
media=lambda s:re.findall(r'data:(?:video/mp4|image/jpeg|image/png);base64,[A-Za-z0-9+/=]+',s)
assert media(out)==media(text);html.write_text(out)
receipt={'id':ID,'before_sha256':before,'after_sha256':sha(p),'metric':metric,'other_rows_unchanged':True,'task_and_event_conclusions_unchanged':True,'html_after_sha256':sha(html),'html_media_unchanged':True};(a/'RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'after_sha256':sha(p),'native':v['native'],'guided':v['guided'],'delta':v['delta']}))
