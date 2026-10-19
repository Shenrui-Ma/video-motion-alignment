import sys,copy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
validate_static();g=verify_intake();m=read(ROOT/'showcase/PRESENTATION.json');review=ROOT/'audit/root_full_review/REVIEW.json';rv=read(review)
require(rv['reviewed_frames']==list(range(105)) and rv['gate']['sha256']==sha(ROOT/'incoming/CONTROL_RUNTIME_GATE.json'),'actual full review mismatch')
require(m['gate']['sha256']==sha(ROOT/'incoming/CONTROL_RUNTIME_GATE.json') and m['collection']['sha256']==sha(ROOT/'incoming/COLLECTION.json'),'presentation receipt mismatch')
for x in m['inputs']:require(sha(x['file'])==x['sha256'],'input media changed')
v=m['videos'][0];video=ROOT/'showcase'/v['file'];require(sha(video)==v['sha256'],'comparison video changed')
require((v['properties']['width'],v['properties']['height'],v['properties']['count'],v['properties']['avg_frame_rate'])==(5120,808,105,'24/1'),'comparison timeline changed')
path=Path('/Users/researcher/DevProjects/h3-benchmark-all-results-showcase-20261018/inventory/ivebench.json');d=read(path);require(not any(x['id']=='r97_short_0358_extended' for x in d['items']),'already present');a=ROOT/'audit/inventory_entry';(a/'PREVIOUS.json').write_bytes(path.read_bytes())
r=copy.deepcopy(next(x for x in d['items'] if x['id']=='r89_short_0358'));c=config()
r.update(id='r97_short_0358_extended',variant='R97 / P1-local-v1 / fixed guidance extended6–19',title='餐桌喝酒：延长固定引导区间',display_task='给左侧持瓶男子添加眼镜；对比普通编辑、固定6–14步与延长6–19步引导。',ordinary_video_path=m['inputs'][1]['file'],alternative_video_path=m['inputs'][2]['file'],guided_video_path=m['inputs'][3]['file'],comparison_video_path=str(video),reference_video_path=m['inputs'][0]['file'],review_summary='全105有效帧审阅：延长版眼镜任务和原场景保留；降瓶、瓶口接触和离嘴阶段与固定6–14步版接近。末次离嘴仍发生于94–97帧，参考为80–84帧；延长到6–19步未见明确额外收益。',review_status='任务完成，延长引导未见明确额外收益',review_status_code='neutral_extension',method_label='延长已知固定时序引导：6–19步（对照6–14步）',column_labels=['1.参考视频','2.普通编辑','3.固定引导6–14步','4.延长引导6–19步'],comparison_kind='guided_pair',actual_routed_blocks=700,guidance_activation='active',independent_sample=False,parent_inventory_id='r89_short_0358',sample_scope='同一0358原片、提示词、种子与实际条件的引导区间消融；计作同源对照。',comparison_properties=v['properties'])
r['evidence_paths']=[str(Path(c['producer_local'])/'configs/scientific_contract.json'),str(Path(c['producer_local'])/'configs/graphs'/f'{c["run_id"]}.json'),str(ROOT/'showcase/PRESENTATION.json'),str(ROOT/'incoming/CONTROL_RUNTIME_GATE.json'),str(ROOT/'incoming/COLLECTION.json'),str(review)]
r['evidence_sha256']={x:sha(x) for x in r['evidence_paths']};r['media_sha256']={k:sha(r[k]) for k in ['reference_video_path','ordinary_video_path','alternative_video_path','guided_video_path','comparison_video_path']}
old=r['quantitative_metrics']['motion_fidelity'];r['quantitative_metrics']={'motion_fidelity':{k:old[k] for k in ['higher_is_better','valid_frames','protocol']}}
r['quantitative_metrics']['motion_fidelity'].update(native=None,guided=None,delta=None,status='pending',source_files=[],source_sha256={},scope='此延长引导输出的正式MF正在准备；先前固定6–14步分数保留在r89_short_0358原记录。')
d['items'].append(r);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)
save(a/'UPDATE.json',{'added':1,'items':len(d['items']),'unique_sources':len({x['source_id'] for x in d['items']}),'inventory':bound(path),'prior_sha256':sha(a/'PREVIOUS.json'),'actual_full_review':bound(review),'new_independent_sources':0})
print(json.dumps(read(a/'UPDATE.json'),ensure_ascii=False))
