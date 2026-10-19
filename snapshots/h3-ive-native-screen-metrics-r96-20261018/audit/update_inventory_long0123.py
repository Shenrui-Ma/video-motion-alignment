import sys,copy,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import *
source='long_0123';p=info(source);i=ROOT/'incoming'/source;s=ROOT/'showcase'/source;decision=ROOT/'audit/actual_decisions'/f'{source}.json';review=ROOT/'audit/agent_native_first_review_long0123/REVIEW.json';ledger=ROOT/'audit/actual_decisions/SCREEN_LEDGER_after_long0123.json'
g=verify_intake(source);d=read(decision);rv=read(review);require(d['choice']=='skip' and d['root_reviewed'] is True,'actual skip required');require(d['binding']['native_gate_sha256']==sha(i/'NATIVE_RUNTIME_GATE.json') and d['binding']['video_sha256']==g['runs']['native']['video']['sha256'],'decision mismatched');require(rv['viewed_frame_indices']==list(range(144)) and rv['native_runtime_gate']['sha256']==sha(i/'NATIVE_RUNTIME_GATE.json'),'full review mismatch')
require(any(x['source_id']==source and x['status']=='native_only' and x['decision_sha256']==sha(decision) for x in read(ledger)['rows']),'ledger mismatch')
path=Path('/Users/researcher/DevProjects/h3-benchmark-all-results-showcase-20261018/inventory/ivebench.json');data=read(path);require(not any(x['id']=='r96_long_0123' for x in data['items']),'already in inventory')
a=ROOT/'audit/inventory_update_long0123';a.mkdir();(a/'PREVIOUS.json').write_bytes(path.read_bytes())
r=copy.deepcopy(next(x for x in data['items'] if x['id']=='r96_long_0047'));r={k:(v.replace('long_0047','long_0123') if isinstance(v,str) else v) for k,v in r.items()}
r.update(title='面团操作：白色面团改为红色',task=p['original_task']['edit_prompt'],display_task='将白色面团改为红色。',review_summary='全144有效帧审阅：面团改红完成，蓝色手套、袖子、桌面和箱子保留；按揉、抓起、放入箱中、搬叠箱子的动作顺序与时刻大致一致，未见明显持续延后或遗漏。已执行skip，保留普通编辑同步记录。局部接触姿态及面团形状、纹理变化另记。',valid_frames=144,generated_frames=158,original_task=p['original_task'],clip_note='IVEBench长视频派生片段；原片帧45–224（1.5–7.5秒）。',source_time_precision='原片30fps；prepared24fps按provenance对应原时刻，展示144有效帧，排除末尾14填充帧。',native_comparison_properties=read(s/'PRESENTATION.json')['videos'][0]['properties'])
r['evidence_paths']=[str(Path(config()['producer_local'])/'configs/scientific_contract.json'),str(Path(config()['producer_local'])/'configs/graphs'/f'{p["run_id"]}.json'),str(ROOT/p['provenance']['file']),str(i/'NATIVE_RUNTIME_GATE.json'),str(i/'COLLECTION.json'),str(s/'PRESENTATION.json'),str(review),str(decision),str(ledger)]
r['media_sha256']={k:sha(r[k]) for k in ['reference_video_path','ordinary_video_path','native_comparison_video_path']};r['evidence_sha256']={x:sha(x) for x in r['evidence_paths']}
data['items'].append(r);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)
save(a/'UPDATE.json',{'added':1,'modified':0,'items':len(data['items']),'unique_sources':len(set(x['source_id'] for x in data['items'])),'previous_sha256':sha(a/'PREVIOUS.json'),'inventory':bound(path),'actual_decision':bound(decision),'full_review':bound(review)})
print(json.dumps(read(a/'UPDATE.json'),ensure_ascii=False))
