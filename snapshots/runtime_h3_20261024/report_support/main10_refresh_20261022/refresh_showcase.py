"""Update the portable R150 display with frozen main-ten metric/video evidence."""
from pathlib import Path
import json,re,base64,hashlib
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent
REPORT=Path('/workspace/research-user/DevProjects/video-motion-alignment/reports/R150_十组引导区间对照_单文件.html')
EXE=Path('/workspace/research-user/DevProjects/video-motion-alignment/execution-20261022')
if (EXE/'supervision/interval_short0177_20261024/report/PUBLISHED.json').exists():
    raise SystemExit('IVEBench10 report is now maintained by execution-20261022/supervision/interval_short0177_20261024/report/build_reports.py; use its --input and --publish options.')
ROLES=['source','native','early','fixed','late','split','global_weak']
NEW=['short_0343','short_0114','crouch__movie_man_4','long_0167']
ORDER=['short_0252','short_0358','long_0039','long_0059']+NEW+['short_0085','short_0274','05_real_megumi_v','musk05','firefly06','sam07']
TITLES={'short_0343':'角色替换 — 浴室照镜子的女子替换为医生','short_0114':'物体替换 — 篮球替换为霓虹发光球','crouch__movie_man_4':'动作迁移 — 参考图男子做两次蹲起','long_0167':'外观编辑 — 三名动画角色的衣服改为白色'}
def url(p,mime):return f'data:{mime};base64,'+base64.b64encode(p.read_bytes()).decode()
source=REPORT.read_text();data=json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>',source,re.S).group(1))
cases={c['source_id']:c for c in data['cases']}
manifest=json.loads((ROOT/'new4_manifest.json').read_text());catalog=json.loads((EXE/'innovation/pilot_ten/manifest_preparation/catalog.json').read_text())['cases']
for sid in NEW:
 jobs={j['method']:j for j in manifest['jobs'] if j['task_id']==sid};cat=next(c for c in catalog if c['task_id']==sid);p=ROOT/sid;receipt=json.loads((p/'PRESENTATION.json').read_text())
 for name,digest in receipt['files'].items():assert hashlib.sha256((p/name).read_bytes()).hexdigest()==digest
 c=dict(id=sid,source_id=sid,title=TITLES[sid],dataset=cat['dataset'],geometry=cat['geometry'],seed=cat['seed'],prompt=cat['prompt'],prompt_source_label='本轮实际简单提示词',reference_image=bool(cat['reference_image']),events=[],old_MF={},control_verdicts={},control_reviews={},arms={r:{} for r in ROLES if r not in ['source','native','fixed']},pending=False,preservation=False,source_MF=1,arm_offsets={r:None for r in ROLES},mean_absolute_offset={r:None for r in ROLES},event_offsets={},display_summary='六种编辑均已生成；九项数值指标已完成。动作时间偏移暂未测。',new_batch=True)
 c['overview']={'video':url(p/'comparison.mp4','video/mp4'),'default_frame':receipt['screenshot_frame'],'frames':[{'frame':receipt['screenshot_frame'],'url':url(p/'same_frame.jpg','image/jpeg')}]}
 cases[sid]=c
rows=json.loads((ROOT/'metrics_snapshot.json').read_text())['rows']
for sid in ORDER:
 c=cases[sid];c['main_cohort']=sid in ORDER[:10];c['official_metrics']={}
 if c['main_cohort']:
  for role in ROLES:
   rs=[r for r in rows if r['task_id']==sid and r.get('cohort','main')=='main' and r['method']==role]
   c['official_metrics'][role]={r['metric']:{'status':r['status'],'score':r.get('score')} for r in rs}
  for role in ROLES:
   mf=c['official_metrics'][role]['motion_fidelity']['score'];assert mf is not None
   if role=='source':c['source_MF']=mf
   elif role in ['native','fixed']:c['old_MF'][role]=mf
   else:c['arms'][role]['score']=mf
 data['cases']=[cases[sid] for sid in ORDER]
from action_offsets import apply_annotations
timing_audit=apply_annotations(cases)
data['title']='引导步区间对照';data['tasks']=10;data['independent_sources']=10;data.pop('ranking',None)
data['metric_scopes']={k: v['methods'] for k,v in json.loads((EXE/'summaries/main10_20261022/snapshot.json').read_text())['metrics']['means'].items() if k in ['main_all','main_IVEBench']}
data['metric_means']=data['metric_scopes']['main_all']
template=(ROOT/'showcase_template.html').read_text()
from published_results import render_published_results
published_path=EXE/'literature/ivebench_published_scores.json'
published=json.loads(published_path.read_text())
data['published_results']=published
published_html=render_published_results(published,data['metric_scopes']['main_IVEBench'])
template=template.replace('<section class="intro" id="paper-comparison"><h2>公开论文结果</h2><p class="muted">文献对照整理中。</p></section>',published_html)
svg=re.search(r'<div class="diagram scroll">(.*?)</div>',source,re.S).group(1)
output=template.replace('__DATA__',json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')).replace('__SCHEDULE_SVG__',svg)
assert len(data['cases'])==14 and len({c['source_id'] for c in data['cases']})==14
assert all(c['overview']['video'].startswith('data:video/mp4;base64,') for c in data['cases'])
assert all(c['overview']['default_frame']>0 for c in data['cases'])
for sid in ORDER[:10]:
 for role in ROLES:assert sum(v['score'] is not None for v in cases[sid]['official_metrics'][role].values())==9
REPORT.write_text(output)
(PROJECT/'index.html').write_text(output)
# Existing portable source link follows the same updated document, without another media copy.
p=PROJECT/'R150_十组引导区间对照_单文件.html'
if p.exists() or p.is_symlink():p.unlink()
p.symlink_to(REPORT)
proof={'report':str(REPORT),'source_index':str(PROJECT/'index.html'),'bytes':REPORT.stat().st_size,'sha256':hashlib.sha256(REPORT.read_bytes()).hexdigest(),'main10_order':ORDER[:10],'historical_order':ORDER[10:],'videos':14,'native_controls':True,'new4_media_full_decode':'4/4','numeric_metrics_main10':'630/630','QA':'N/A','IS_CF':'pending Qwen72B resources','action_offset_audit':timing_audit['scopes'],'action_annotation':'AI visual frame annotation'}
(ROOT/'STRUCTURE_VALIDATION.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2));print(json.dumps(proof,ensure_ascii=False,indent=2))
