import sys,copy,json
from pathlib import Path
from fractions import Fraction
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import *
source='long_0173';p=info(source);i=ROOT/'incoming'/source;s=ROOT/'showcase'/source;decision=ROOT/'audit/actual_decisions'/f'{source}.json';review=ROOT/'audit/agent_native_first_review_long0173/REVIEW.json'
g=verify_intake(source);d=read(decision);rv=read(review)
require(d['choice']=='guide' and d['root_reviewed'] is True,'actual guide decision required')
require(d['binding']['native_gate_sha256']==sha(i/'NATIVE_RUNTIME_GATE.json') and d['binding']['video_sha256']==g['runs']['native']['video']['sha256'],'decision mismatched')
require(rv['reviewed_valid_frames']==list(range(145)) and rv['presentation']['sha256']==sha(s/'PRESENTATION.json'),'full review mismatch')
path=Path('/Users/researcher/DevProjects/h3-benchmark-all-results-showcase-20261018/inventory/ivebench.json');data=read(path);require(not any(x['id']=='r96_long_0173' for x in data['items']),'already in inventory')
a=ROOT/'audit/inventory_update_long0173';a.mkdir();(a/'PREVIOUS.json').write_bytes(path.read_bytes())
r=copy.deepcopy(next(x for x in data['items'] if x['id']=='r96_long_0167'));r={k:(v.replace('long_0167','long_0173') if isinstance(v,str) else v) for k,v in r.items()}
r.update(title='房间开盒：女人替换为老人',task=p['original_task']['edit_prompt'],display_task='将女孩身旁的女人替换为老人，保留女孩、房间和开盒互动。',review_summary='全145有效帧审阅：老人替换、女孩、房间和盒子保留；握盒、抬指、转向后柜及回头阶段接近。局部手形、接触点和末段躯干姿态不同。已选作正常时序与手物互动的引导对照，当前展示已完成的普通编辑。',review_status='任务完成，普通编辑无明确时差；引导对照生成中',review_status_code='native_valid_guide_selected',method_label='普通编辑；已选正常时序引导对照',screening_decision='guide',guidance_activation='not_applicable',valid_frames=145,generated_frames=158,original_task=p['original_task'],clip_note=f"IVEBench长视频派生片段；原片帧105–248（{float(Fraction(p['clip']['start_pts_rational'])):.5f}–{float(Fraction(p['clip']['end_exclusive_rational'])):.5f}秒，结束时刻不含）。",source_time_precision='原片24000/1001fps；prepared24fps按provenance对应原时刻，展示145有效帧，排除末尾13填充帧。',native_comparison_properties=read(s/'PRESENTATION.json')['videos'][0]['properties'])
r['evidence_paths']=[str(Path(config()['producer_local'])/'configs/scientific_contract.json'),str(Path(config()['producer_local'])/'configs/graphs'/f'{p["run_id"]}.json'),str(ROOT/p['provenance']['file']),str(i/'NATIVE_RUNTIME_GATE.json'),str(i/'COLLECTION.json'),str(s/'PRESENTATION.json'),str(review),str(decision)]
r['media_sha256']={k:sha(r[k]) for k in ['reference_video_path','ordinary_video_path','native_comparison_video_path']};r['evidence_sha256']={x:sha(x) for x in r['evidence_paths']}
r['quantitative_metrics']['motion_fidelity']['valid_frames']=145
require(r['quantitative_metrics']['motion_fidelity']['status']=='pending' and r['quantitative_metrics']['motion_fidelity']['native'] is None,'pending metric inherited incorrectly')
data['items'].append(r);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)
save(a/'UPDATE.json',{'added':1,'modified':0,'items':len(data['items']),'unique_sources':len(set(x['source_id'] for x in data['items'])),'previous_sha256':sha(a/'PREVIOUS.json'),'inventory':bound(path),'actual_decision':bound(decision),'full_review':bound(review)})
print(json.dumps(read(a/'UPDATE.json'),ensure_ascii=False))
