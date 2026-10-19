from pathlib import Path
import json,hashlib,copy,time
R=Path(__file__).resolve().parents[1];D=R.parent;M=D/'h3-ive-followup-quantitative-r97-r99-r100-20261019/audit/recovery_20261019/r102_short_0263';ID='r102_short_0263'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
result=M/'RESULT_VERIFIED.json';v=read(result)
for x in v['scores'].values():assert sha(x['file'])==x['sha256']
assert all(x['released']['process_absent'] and x['released']['own_cuda_absent'] for x in v['tracks'].values())
p=R/'inventory/ivebench.json';before=sha(p);doc=read(p);old=copy.deepcopy(doc['items']);row=next(x for x in doc['items'] if x['id']==ID);assert row['comparison_kind']=='guided_pair'
files=[result]+[Path(x['file']) for x in v['scores'].values()];metric=row['quantitative_metrics']['motion_fidelity'];assert metric['status']=='pending';metric.update(native=v['native'],guided=v['forced'],delta=v['delta'],status='complete',source_files=[str(x) for x in files],source_sha256={str(x):sha(x) for x in files},scope='官方IVE MF，74有效帧、三组fresh轨迹均精确释放。翻书近同步、后段视线时刻UNKNOWN；整体时序结论按全帧审阅。')
for f in files:
 if str(f) not in row['evidence_paths']:row['evidence_paths'].append(str(f))
 row['evidence_sha256'][str(f)]=sha(f)
assert [x for x in doc['items'] if x['id']!=ID]==[x for x in old if x['id']!=ID]
for k in ['review_summary','review_status','event_review','support_for_clear_whole_event_repair']:assert row.get(k)==next(x for x in old if x['id']==ID).get(k)
a=R/'audit/r1020263_official_mf_20261019';a.mkdir(exist_ok=False);(a/'PREVIOUS_INVENTORY.json').write_bytes(p.read_bytes());doc['previous_inventory_sha256']=before;doc['updated_unix']=time.time();assert sha(p)==before;p.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n');receipt={'before_sha256':before,'after_sha256':sha(p),'updated':ID,'metrics':metric,'other_rows_unchanged':True,'visual_review_unchanged':True};(a/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'after_sha256':sha(p),'native':v['native'],'forced':v['forced'],'delta':v['delta']}))
