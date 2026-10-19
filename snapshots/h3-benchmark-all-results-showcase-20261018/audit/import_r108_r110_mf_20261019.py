from pathlib import Path
import copy,json,hashlib,time
R=Path(__file__).resolve().parents[1]
Q=R.parent/'h3-ive-followup-quantitative-r97-r99-r100-20261019/audit/recovery_20261019'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=R/'inventory/ivebench.json';before=sha(p);d=read(p);old=copy.deepcopy(d['items'])
protocol='IVEBench official MF; commit 2dcf8900ee65197f43854c76f61c66a32bb8dbfc; CoTracker3 offline, grid10, window60'
updates=[]
for ID,case,roles,frames in [
    ('r108_short_0392','r108_short_0392_capacity4',{'native':('r108_short_0392_capacity4/actual_host41/cases/r108_short_0392/results/native.json','ordinary_video_path'),
        'guided':('r108_short_0392_capacity4/actual_host41/cases/r108_short_0392/results/forced.json','guided_video_path')},57),
    ('r110_short_0114_promptcontrol','r110_short_0114_plain_capacity4',{'native':('r109_short_0114_plain/actual_host41/cases/r109_short_0114_plain/results/plain.json','ordinary_video_path'),
        'alternative_native':('r110_short_0114_plain_capacity4/actual_host41/cases/r110_short_0114_plain/results/plain.json','alternative_video_path')},105)]:
    row=next(x for x in d['items'] if x['id']==ID)
    files={key:Q/path for key,(path,_) in roles.items()};scores={key:read(path) for key,path in files.items()}
    for role,result in scores.items():
        assert result['actual_generated_video_sha256']==sha(row[roles[role][1]])
        assert result['valid_frames']==frames and result['fps']==24
        for key in ('source_tracks_sha256','official_vendor','checkpoint_sha256'):assert result[key]==scores['native'][key]
    receipt=Q/case/'RESULT_VERIFIED.json';verified=read(receipt)
    release=Path(verified['release_receipt']['file']);assert sha(release)==verified['release_receipt']['sha256']
    evidence=list(files.values())+[receipt,release]
    mf=row['quantitative_metrics']['motion_fidelity'];mf.update({key:score['motion_fidelity'] for key,score in scores.items()})
    mf.update(protocol=protocol,source_files=[str(x) for x in evidence],source_sha256={str(x):sha(x) for x in evidence},
        status='complete' if ID.startswith('r108') else 'complete_prompt_control')
    if ID.startswith('r108'):
        mf['delta']=mf['guided']-mf['native']
        mf['scope']='57有效帧，同源官方轨迹评分。壁炉移除两版均完成，普通0.842818、固定引导0.826313；逐帧审阅中额外时序收益不明显。'
    else:
        mf.update(guided=None,delta=None,prompt_delta=mf['alternative_native']-mf['native'])
        mf['scope']='105有效帧。一句话普通编辑0.735928、显式参考绑定普通编辑0.800568；此处比较提示词，两版均0引导。新版恢复角色、运球和霓虹球，构图仍偏移，完整任务部分完成。'
    for path in evidence:
        if str(path) not in row['evidence_paths']:row['evidence_paths'].append(str(path))
        row['evidence_sha256'][str(path)]=sha(path)
    updates.append({'id':ID,'scores':{key:score['motion_fidelity'] for key,score in scores.items()}})
for a,b in zip(old,d['items']):
    if a['id'] not in [x['id'] for x in updates]:assert a==b
d['previous_inventory_sha256']=before;d['updated_unix']=time.time();assert sha(p)==before
a=R/'audit/r108_r110_mf_20261019';a.mkdir(exist_ok=False);(a/'PREVIOUS_INVENTORY.json').write_bytes(p.read_bytes())
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
receipt={'before_sha256':before,'after_sha256':sha(p),'updates':updates,'visual_reviews_unchanged':True}
(a/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
