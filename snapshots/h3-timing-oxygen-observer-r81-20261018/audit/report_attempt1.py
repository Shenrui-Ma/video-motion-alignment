"""Create a descriptive report from complete frozen R81 evidence. No inference."""
import gzip,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'audit/consumer_attempt1'
read=lambda p:json.loads(Path(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
complete=read(OUT/'COMPLETE.json')
assert complete['status']=='complete'
p=read(ROOT/'configs/PROTOCOL.json'); poses=read(ROOT/'poses/attempt1/COMPLETE.json'); decode=read(ROOT/'outputs/attempt1/RESULT.json')
assert len(poses['steps'])==len(decode['steps'])==20
versions={}; first_evidence={}
for name in ('original','visible'):
    folder=ROOT/'results/attempt1'/name
    s=read(folder/'SUMMARY.json'); assert s['status']=='complete' and len(s['steps'])==20
    versions[name]=s
    ix=s['first_persistent_ON_index']
    if ix is None:
        first_evidence[name]=None;continue
    r=s['steps'][ix]; ev=folder/r['full_evidence'];assert sha(ev)==r['full_evidence_sha256']
    with gzip.open(ev,'rt') as f: data=json.load(f)
    selections=[]
    for choice in data['decision']['selected']:
        matches=[x for x in data['observation']['windows'] if x['window']==choice['window'] and x['feature']==choice['feature']]
        assert len(matches)==1
        row=matches[0]
        selections.append({'selection':choice,'physical_interval_seconds':[f/24 for f in choice['window']],
                           'measurements':{c:{k:v for k,v in m.items() if k!='curve'} for c,m in row['measurements'].items()},
                           'comparison':row.get('comparison')})
    first_evidence[name]={'index':ix,'one_based_denoising_step':ix+1,'evidence_file':str(ev.relative_to(ROOT)),
                          'evidence_sha256':sha(ev),'selected':selections}
(OUT/'FIRST_ACTIVATION_EVIDENCE.json').write_text(json.dumps(first_evidence,indent=2)+'\n')
lines=['R81：氧气罩案例的完整20步离线观测',
       '对象：R73 short_0252 Native，画面右侧成年人；有效物理帧0–97（24fps），共98帧。',
       '用途：检查固定观察器何时获得时差候选及连续触发条件。输入为已保存的Native轨迹；当前任务没有执行在线纠正。',
       '', '结果']
for name,title in [('original','原R55观察器'),('visible','R59可见整臂观察器')]:
    s=versions[name]
    lines += [f"{title}：首个合格候选 index={s['first_qualified_candidate_index']}；首次连续触发 index={s['first_persistent_ON_index']}；全部ON indices={s['ON_indices']}。"]
    e=first_evidence[name]
    if e:
        for x in e['selected']:
            a=x['selection'];lines += [f"  首次选中物理帧{a['window']}，{a['feature']}，两置信门限lag={a['lags']}帧，min_gain={a['min_gain']:.6f}。"]
lines += ['', '逐步结果（index为0起点）','index | 原R55候选组/ON | 可见整臂候选组/ON | 选中成人的帧数（关节另过置信门）']
for i in range(20):
    a=versions['original']['steps'][i];b=versions['visible']['steps'][i];q=poses['steps'][i]
    lines += [f"{i:02d} | {a['candidate_groups']}/{int(a['active'])} | {b['candidate_groups']}/{int(b['active'])} | {q['selected_visible_frames']}/98"]
lines += ['', '候选与暂停原因',
          '两版本的全部20步窗口测量和策略决策逐项相同；这个案例中去掉躯干入口要求没有改变结果。',
          'index0：82行baseline unknown，13行共同支持不足；24行可比较，但最高min_gain=0.485388，均未超过固定0.5门限。',
          'index1：首个代表为物理帧[44,59]的右臂，lag=+11/+11帧，min_gain=0.819919；首次出现，等待连续观测。',
          'index2：相同窗口/部位与同一延后方向再次出现，lag=+15/+15帧，触发ON。原persistence没有要求跨去噪步骤lag数值差≤2。',
          'index4/8代表从右臂变成左臂，index5/9再切回右臂，导致四次awaiting_persistence。相同物理窗口仍有合格候选；暂停来自代表选择后的共有部位条件。',
          '', '解释范围',
          '源成年人的四条手臂骨段在.3/.5门限均有98/98有效帧；此统计只说明源侧可测。',
          'UNKNOWN保留为观测或对应关系不足；过大的姿态差异、低覆盖、相位歧义和搜索边界分别记录。窗口与左右臂重叠，不能计作独立实验样本。',
          '首次假设ON之后的行仍来自旧Native轨迹，只描述该轨迹下策略会作出的决定。采用纠正后的轨迹需实际在线实验验证。',
          'R59版本沿完整手臂特征，仅去掉躯干入口要求；数值阈值、signed policy与persistence全部沿冻结版本。未使用单骨段、AB门或弱全片fallback。',
          'x0由.9 Torch2.5.1生成，本次由.41 Torch2.11.0解码；VAE/Core哈希绑定一致。末步x0与sampler final存在已登记的微小FP32差异，原最终pose只作描述性终点参照。',
          '阶段图固定为source与index0/6/12/19的物理帧0/20/40/60/80/97；它用于检查图像成熟和目标人物，未决定扫描窗口。',
          '', '效率与核验',
          f"20视频SHA/107帧/24fps/逐帧PTS全部通过。总decode秒数={sum(x['decode_seconds'] for x in decode['steps']):.3f}；CPU pose总秒数={sum(x['total_seconds'] for x in poses['steps']):.3f}。",
          'root负责GPU释放；consumer调用GPU次数0。原始20视频、原始多人pose、成人筛选pose及两版本完整扫描证据均保留。',
          '', '文件',
          'results/attempt1/{original,visible}/SUMMARY.json：完整20步结果；每步json.gz保留全部代价曲线和决策。',
          'audit/consumer_attempt1/REJECTION_STAGE_DIAGNOSIS.json：原阈值拒绝阶段统计。',
          'audit/consumer_attempt1/FIRST_ACTIVATION_EVIDENCE.json：首次触发的window、lag、gain及实际代价。']
(OUT/'REPORT.txt').write_text('\n'.join(lines)+'\n')
paths=[ROOT/'configs/PROTOCOL.json',ROOT/'FREEZE.json',ROOT/'outputs/attempt1/RESULT.json',ROOT/'poses/attempt1/COMPLETE.json',OUT/'COMPLETE.json',OUT/'TRANSFER_VALIDATED.json',OUT/'SOURCE_OBSERVABILITY.json',OUT/'FIRST_ACTIVATION_EVIDENCE.json',OUT/'REJECTION_STAGE_DIAGNOSIS.json',OUT/'REPORT.txt']
paths += [ROOT/'results/attempt1'/n/'SUMMARY.json' for n in versions]
paths += list((OUT/'visual_probe').glob('*'))
paths += [OUT/'ENDPOINT_PIXEL_DESCRIPTION.json', OUT/'ROOT_RELEASED.json', OUT/'POLICY_CONTINUITY_DIAGNOSIS.json']
paths += [OUT/'R59_IMPLEMENTATION_PARITY.json', OUT/'R59_IMPLEMENTATION_PARITY.txt', ROOT/'audit/check_r59_parity.py']
(OUT/'PROOF_MANIFEST.json').write_text(json.dumps({'schema':'r81-final-evidence-v1','protocol_sha256':sha(ROOT/'configs/PROTOCOL.json'),'fixed_cases':1,'observations':20,'files':{str(f.relative_to(ROOT)):{'sha256':sha(f),'bytes':f.stat().st_size} for f in paths}},indent=2)+'\n')
print('\n'.join(lines[:10]))
