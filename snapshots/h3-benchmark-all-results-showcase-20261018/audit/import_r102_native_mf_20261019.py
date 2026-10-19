from pathlib import Path
import copy,json,hashlib,time
R=Path(__file__).resolve().parents[1]
Q=R.parent/'h3-ive-followup-quantitative-r97-r99-r100-20261019/audit/recovery_20261019/r102_short_0126_native_capacity4'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=R/'inventory/ivebench.json';before=sha(p);d=read(p);old=copy.deepcopy(d['items'])
row=next(x for x in d['items'] if x['id']=='r102_short_0126');assert row['comparison_kind']=='native_only' and row['guided_video_path'] is None
scorefile=Q/'actual_host41/cases/r102_short_0126_native/results/native.json';score=read(scorefile)
receipt=Q/'RESULT_VERIFIED.json';verified=read(receipt);release=Path(verified['release_receipt']['file'])
assert sha(release)==verified['release_receipt']['sha256']
assert score['actual_generated_video_sha256']==sha(row['ordinary_video_path'])
assert score['motion_fidelity']==verified['scores']['native'] and score['valid_frames']==109 and score['fps']==24
evidence=[scorefile,receipt,release]
row['quantitative_metrics']['motion_fidelity'].update(native=score['motion_fidelity'],guided=None,delta=None,status='complete_native_only',
    source_files=[str(x) for x in evidence],source_sha256={str(x):sha(x) for x in evidence},
    scope='109有效帧普通编辑官方MF。猫已添加，人物和动作阶段接近参考；该辅助物体添加任务按全帧审阅跳过引导。')
for f in evidence:
    if str(f) not in row['evidence_paths']:row['evidence_paths'].append(str(f))
    row['evidence_sha256'][str(f)]=sha(f)
for a,b in zip(old,d['items']):
    if a['id']!=row['id']:assert a==b
d['previous_inventory_sha256']=before;d['updated_unix']=time.time();assert sha(p)==before
a=R/'audit/r102_native_mf_20261019';a.mkdir(exist_ok=False);(a/'PREVIOUS_INVENTORY.json').write_bytes(p.read_bytes())
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
result={'before_sha256':before,'after_sha256':sha(p),'id':row['id'],'native':score['motion_fidelity'],'review_unchanged':True}
(a/'RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
