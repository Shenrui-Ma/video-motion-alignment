from pathlib import Path
import json,hashlib,copy,time,re
R=Path(__file__).resolve().parents[1];D=R.parent;M=D/'h3-ive-followup-quantitative-r97-r99-r100-20261019/audit/recovery_20261019'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=R/'inventory/ivebench.json';before=sha(p);doc=read(p);old=copy.deepcopy(doc['items']);updates=[]
for ID,case in [('r102_short_0092','r102_short_0092_native'),('r109_short_0114_promptcontrol','r109_short_0114_plain')]:
 result=M/case/'RESULT_VERIFIED.json';v=read(result);row=next(x for x in doc['items'] if x['id']==ID)
 for x in v['scores'].values():assert sha(x['file'])==x['sha256']
 assert all(x['released']['process_absent'] and x['released']['own_cuda_absent'] for x in v['tracks'].values())
 files=[result]+[Path(x['file']) for x in v['scores'].values()];metric=row['quantitative_metrics']['motion_fidelity']
 shared={'source_files':[str(x) for x in files],'source_sha256':{str(x):sha(x) for x in files},'valid_frames':v['valid_frames']}
 if ID=='r102_short_0092':
  assert row['comparison_kind']=='native_only' and row['count_as_complete_task_success'] is False
  metric.update(native=v['native'],guided=None,delta=None,status='complete_native_only',scope='58有效帧的普通编辑官方MF。植物移除仍不完整，按任务审阅跳过引导。',**shared)
 else:
  assert row['comparison_kind']=='prompt_control' and row['media_sha256']['alternative_video_path']==v['visual_review']['actual_generated_video_sha256']
  assert sha(v['visual_review']['review_file'])==v['visual_review']['review_sha256']
  metric.update(native=v['prior_six_section_ordinary_MF'],guided=None,delta=None,alternative_native=v['plain'],status='complete_prompt_control',scope='六段普通编辑0.813859，一句话普通编辑0.735928；此处比较提示词。人物与镜头任务失败结论保留。',**shared)
  row['quantitative_metrics']['task_repair_motion_fidelity']={'old_native':v['prior_six_section_ordinary_MF'],'new_native':v['plain'],'delta':v['plain_minus_six_section_MF'],'status':'complete','scope':'旧版为R100六段提示词，当前版为R109一句话提示词；MF下降0.07793。全105帧检查显示人物缺失、镜头切换及霓虹外观不稳定，任务失败。',**shared}
 for f in files:
  if str(f) not in row['evidence_paths']:row['evidence_paths'].append(str(f))
  row['evidence_sha256'][str(f)]=sha(f)
 updates.append(ID)
 for key in ['review_summary','review_status','event_review','count_as_complete_task_success','support_for_clear_whole_event_repair']:assert row.get(key)==next(x for x in old if x['id']==ID).get(key)
assert [x for x in doc['items'] if x['id'] not in updates]==[x for x in old if x['id'] not in updates]
a=R/'audit/r1020092_r109_official_mf_20261019';a.mkdir(exist_ok=False);(a/'PREVIOUS_INVENTORY.json').write_bytes(p.read_bytes());doc['previous_inventory_sha256']=before;doc['updated_unix']=time.time();assert sha(p)==before;p.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
html=Path('/Users/researcher/Downloads/H3_R109_篮球_六段提示词与简短提示词_20261019.html');text=html.read_text();(a/'R109_HTML_BEFORE_MF.html').write_text(text);paragraph='<p><strong>官方 Motion Fidelity：</strong>六段提示词普通编辑 0.813859，一句话普通编辑 0.735928，下降 0.077931。全片任务失败结论保持。</p>';assert paragraph not in text;out=text.replace('<video',paragraph+'<video',1);assert out!=text
media=lambda s:re.findall(r'data:(?:video/mp4|image/jpeg);base64,[A-Za-z0-9+/=]+',s)
assert media(text)==media(out);html.write_text(out)
receipt={'before_sha256':before,'after_sha256':sha(p),'updated':updates,'other_rows_unchanged':True,'visual_review_unchanged':True,'R109_html_sha256':sha(html),'R109_embedded_media_unchanged':True};(a/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
