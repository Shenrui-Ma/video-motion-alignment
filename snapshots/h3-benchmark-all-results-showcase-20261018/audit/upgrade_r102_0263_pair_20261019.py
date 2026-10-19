from pathlib import Path
import copy,json,hashlib,time
R=Path(__file__).resolve().parents[1];C=R.parent/'h3-ive-task-repair-metrics-r102-20261019'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
path=R/'inventory/ivebench.json';previous=sha(path);v=read(path);old=copy.deepcopy(v['items']);item=next(x for x in v['items'] if x['id']=='r102_short_0263');assert item['comparison_kind']=='native_only'
a=R/'audit/r102_0263_pair_20261019';a.mkdir(exist_ok=True);(a/'PREVIOUS_INVENTORY.json').write_bytes(path.read_bytes())
pf=C/'showcase_pairs/short_0263/PRESENTATION.json';p=read(pf);gf=C/'incoming_pairs/short_0263/PAIR_RUNTIME_GATE.json';g=read(gf);rf=C/'audit/root_pair_review/short_0263/REVIEW.json';review=read(rf)
assert sha(pf)==review['presentation_sha256'] and sha(gf)==review['pair_gate_sha256'] and g['passed'] and all(g['checks'].values())
for row in p['inputs']:assert sha(row['file'])==row['sha256']
video=C/'showcase_pairs/short_0263'/p['videos'][0]['file'];assert sha(video)==p['videos'][0]['sha256']
item.update(variant='R102 / P1-local-v1 / ordinary + fixed / .9',title='躺椅读书：女人替换为小女孩（修复后的引导对照）',ordinary_video_path=p['inputs'][1]['file'],guided_video_path=p['inputs'][2]['file'],comparison_video_path=str(video),review_summary='全74有效帧审阅：两版均完成小女孩替换，蓝色躺椅、书本、植物与原镜头保持。第38–54帧翻页阶段三列均接近；后段两版的视线仍更朝下，尚不能可靠标定时差。固定引导未见明确额外时序收益。',review_status='任务完成，未见明确引导收益',review_status_code='neutral',method_label='固定时序引导（基础任务修复后的配对）',comparison_kind='guided_pair',column_labels=['1.参考视频','2.普通编辑','3.时序引导'],guidance_activation='active',actual_routed_blocks=450,comparison_properties=p['videos'][0]['properties'],event_review={'file':str(rf),'sha256':sha(rf),'events':review['motion_findings'],'scope':'root全74有效帧审阅；head/gaze时差UNKNOWN'},inference_efficiency=review['speed'])
for f in [pf,gf,C/'incoming_pairs/short_0263/COLLECTION.json',rf,rf.with_name('FRAME_LEDGER.json')]:
 if str(f) not in item['evidence_paths']:item['evidence_paths'].append(str(f))
item['evidence_sha256']={f:sha(f) for f in item['evidence_paths']}
item['media_sha256'].update({k:sha(item[k]) for k in ['ordinary_video_path','guided_video_path','comparison_video_path']})
item['quantitative_metrics']['motion_fidelity']['scope']='匹配普通/引导成片均完成，官方MF待实际评分。'
for a0,a1 in zip(old,v['items']):
 if a0['id']!='r102_short_0263':assert a0==a1
items=v['items'];v['counts'].update(guided_pairs=sum(x['comparison_kind']=='guided_pair' for x in items),activated_fixed_pairs=sum(x['comparison_kind']=='guided_pair' and x.get('guidance_activation')=='active' for x in items),native_only=sum(x['comparison_kind']=='native_only' for x in items))
v['updated_unix']=time.time();v['previous_inventory_sha256']=previous;assert sha(path)==previous;path.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
receipt={'before_sha256':previous,'after_sha256':sha(path),'upgraded':'r102_short_0263','all_other_rows_identical':True,'counts':v['counts']};(a/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
