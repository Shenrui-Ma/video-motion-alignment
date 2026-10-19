"""Summarize actual scores with distinct benchmark protocols and task evidence."""
from pathlib import Path
import hashlib,json

r=Path(__file__).resolve().parent
base=r.parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for case in ['r100_short_0114','r96_long_0173','r99_short_0230','r99_short_0352']:
    p=r/case/'RESULT_VERIFIED.json'
    d=json.loads(p.read_text())
    assert all(x['released']['process_absent'] and x['released']['own_cuda_absent'] and x['released']['returncode']==0 for x in d['tracks'].values())
    rows.append({**{k:d[k] for k in ['case','benchmark','native','forced','delta','valid_frames','fps']},'evidence':{'file':str(p),'sha256':sha(p)},'released_pids':[x['pid'] for x in d['tracks'].values()]})
old={}
for key,rel in [('r97','audit/R97_RESULT_VERIFIED.json'),('r99_short_0210','audit/R99_0210_RESULT_VERIFIED.json')]:
    p=base/rel;old[key]={'file':str(p),'sha256':sha(p),'data':json.loads(p.read_text())}
flex=Path('/Users/researcher/DevProjects/h3-flexiact-character-repair-mf-r98-20261019/actual_host41/scores/native/SCORE.json')
out={'status':'FOUR_ACTUAL_PAIRS_SCORED_TWELVE_TRACKERS_RELEASED','IVEBench':{'official_commit':'2dcf8900ee65197f43854c76f61c66a32bb8dbfc','tracker':'grid10, offline, window60, 24fps, 1280x720, exact valid prefix','recovered_pairs':rows,'previous':old},'FlexiAct':{'official_commit':'de9fe1d536732c4d1a384577b5ae54f8fc1730d7','tracker':'grid55, 3025 points, 49 frames at 8fps','r98_native':{'score':json.loads(flex.read_text())['score'],'file':str(flex),'sha256':sha(flex)},'r101_guided':'Await actual paired media and new guided tracking'},'previous_failed_attempt':{'case':'r100_short_0114_native_only','pid':1046861,'reason':'cgroup headroom fell below 8GiB after CPU loading, before tracker CUDA forward','retained':True,'released':True},'scientific_scope':'MF values quantify the unchanged author-code trajectory metric. Task success and physical event times are separate. No combined FlexiAct/IVEBench score.'}
(r/'SUMMARY.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
text=['本轮恢复完成4组实际配对的官方IVEBench MF，12条追踪全部释放。','', '样例 | 普通编辑 | 固定时序引导 | 差值 | 有效帧']
for x in rows:text.append(f"{x['case']} | {x['native']:.9f} | {x['forced']:.9f} | {x['delta']:+.9f} | {x['valid_frames']}")
text += ['', '四组数值均下降。是否出现任务或事件时间改善，需结合各自的完整视频审阅；本表保持官方指标原公式。', 'R100篮球普通编辑仍有构图偏移，任务接受情况应标为partial。R96盒子场景已有全帧审阅，固定引导未显示清楚额外收益。', '旧R100失败attempt在CUDA前退出，已保留；本次是实际配对三角色的新追踪。', 'FlexiAct R98普通编辑MF=0.523982584476471，采用另一套官方协议，单列。R101引导评分仍待实际成片。', '', '各分数、视频SHA、轨迹SHA、PID、显存与耗时见各子目录RESULT_VERIFIED.json；汇总带证据SHA见SUMMARY.json。']
(r/'RESULTS.txt').write_text('\n'.join(text)+'\n')
print(json.dumps({'summary':str(r/'SUMMARY.json'),'sha256':sha(r/'SUMMARY.json'),'pairs':len(rows),'released_trackers':12},ensure_ascii=False))
