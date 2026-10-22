from pathlib import Path
import json,hashlib,datetime
B=Path('/Users/researcher/DevProjects');O=Path(__file__).parent
def bind(p):
 p=Path(p);return {'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
inv={bn:json.loads((B/f'h3-benchmark-all-results-showcase-20261018/inventory/{bn}.json').read_text()) for bn in ['ivebench','flexiact']};rows={x['id']:x for x in inv['ivebench']['items']}
spec=[('R73','r73_short_0252','h3-timing-ivebench-expanded-r73-20261018/configs/graphs','r73_short_0252_seed2026101701_'),('R89','r89_short_0358','h3-timing-ive-subject-capacity-r89-20261018/configs/graphs','r89_short_0358_seed2026101701_'),('R115','r115_long_0174_matched_one_bin','h3-ive-long0174-correspondence-metrics-r115-20261019/configs','graph_'),('R113_seed1702','r113_short_0252_seed2026101702_fixed','h3-oxygen-seed-replication-metrics-r113-host41-20261019/incoming/actual','r113_short_0252_seed2026101702_'),('R113_seed1703','r113_short_0252_seed2026101703_fixed','h3-oxygen-seed-replication-metrics-r113-host41-20261019/incoming/actual','r113_short_0252_seed2026101703_')]
out=[]
for label,i,dirn,prefix in spec:
 ps=sorted((B/dirn).glob(prefix+'*.json'))
 if label.startswith('R113'):ps=[p for p in ps if p.name.endswith('_graph.json')]
 if label=='R115':ps=[p for p in ps if p.name in ['graph_fixed_one_bin.json','graph_matched_one_bin.json']]
 gs=[json.loads(p.read_text()) for p in ps];assert len(gs)==2,(label,ps)
 prompts=[g['5']['inputs']['prompt'] for g in gs];assert prompts[0]==prompts[1]
 image_loaders=[v for g in gs for v in g.values() if isinstance(v,dict) and v.get('class_type') in ['LoadImage','LoadImageMask']]
 assert not image_loaders,(label,image_loaders)
 assert all(not any('image' in k.lower() for k in g['5']['inputs']) for g in gs)
 x=rows[i];assert x.get('reference_image_used') is False
 mf=x.get('quantitative_metrics',{}).get('motion_fidelity',{})
 out.append({'label':label,'inventory_id':i,'source_id':x['source_id'],'official_edit_prompt':x.get('original_task',{}).get('edit_prompt',x['task']),'actual_prompt':prompts[0],'prompt_format':'six-section structured adaptation','native_and_guided_prompt_equal':None if label=='R115' else True,'prompt_equality_scope':'two new operators' if label=='R115' else 'native and guided','reference_image_used':False,'reference_video_count':1,'evidence_graphs':[bind(p) for p in ps],'graph_reference_node':{'class_type':gs[0]['5']['class_type'],'ref_video':gs[0]['5']['inputs']['ref_video'],'image_input_present':False},'scores':{k:mf[k] for k in ['native','guided','delta'] if k in mf},'score_evidence':[bind(p) for p in mf.get('source_files',[]) if Path(p).is_file() and ('results/' in p or 'RESULTS_VERIFIED' in p)]})
flex=B/'h3-flexiact-r116-mf-host9-20261019/runtime/flex';ive=B/'h3-ive-r118-mf-host41-20261019/runtime/ive'
summary=[]
for bn,d in inv.items():
 numeric=[];unofficial=[];missing=[]
 for x in d['items']:
  q=x.get('quantitative_metrics',{});m=q.get('task_repair_motion_fidelity',q.get('motion_fidelity',{}));vals={k:v for k,v in m.items() if isinstance(v,(float,int)) and not isinstance(v,bool) and k not in ['valid_frames','evaluation_frames','evaluation_fps','fps']};tag=m.get('protocol',m.get('implementation',q.get('motion_fidelity',{}).get('protocol','')))
  if vals:
   numeric.append(x['id'])
   if 'official' not in tag.lower():unofficial.append(x['id'])
  else:missing.append(x['id'])
 summary.append({'benchmark':bn,'inventory':bind(B/f'h3-benchmark-all-results-showcase-20261018/inventory/{bn}.json'),'version_count':len(d['items']),'versions_with_numeric_mf':len(numeric),'numeric_without_official_tag':unofficial,'unscored_versions':missing})
report={'schema':'paper-prompt-and-metric-provenance-v1','created':datetime.datetime.now().isoformat(),'short_statement_zh':'IVEBench 样例采用 IVEBench 官方 MF；FlexiAct 样例采用 FlexiAct 官方 MF。两种实现及采样协议分别记录，分数分开报告。','metric_implementations':{'IVEBench':{'repo':'https://github.com/RyanChenYN/IVEBench','commit':'2dcf8900ee65197f43854c76f61c66a32bb8dbfc','code':bind(ive/'official_source/metrics/fidelity/motion_fidelity.py'),'code_url':'https://github.com/RyanChenYN/IVEBench/blob/2dcf8900ee65197f43854c76f61c66a32bb8dbfc/metrics/fidelity/motion_fidelity.py','protocol':'CoTracker3 offline; grid10; window60; physical24fps effective frames after removing input pad; no foreground mask','meaning_zh':'可见轨迹重采样后，比较归一化位置与速度，权重0.7/0.3，再做Hungarian匹配。可见帧重采样会压缩遮挡期间的物理时间。','input_scope':'H3统一画布和有效帧范围；是官方数值实现下的本地成对评测，未声称复现整套官方榜单输入。'},'FlexiAct':{'repo':'https://github.com/shiyi-zh0408/FlexiAct','commit':'de9fe1d536732c4d1a384577b5ae54f8fc1730d7','code':bind(flex/'vendor/motion_fidelity.py'),'function_binding':bind(flex/'METRIC_FUNCTIONS.json'),'vendor':bind(flex/'VENDOR.json'),'protocol':'author get_tracklets grid55; original49@8fps reference; generated0,3,...144; no foreground mask','meaning_zh':'逐步位移归一化后求方向余弦相似度，对每条编辑轨迹取最相近参考轨迹并求均值；原代码还对相似度矩阵的对角项减1。','input_scope':'原始49帧8fps参考与H3输出的对应时刻；原作者函数由adapter原样提取，未修改评分公式。'}},'inventory_audit':summary,'display_import_evidence':[bind(B/'h3-benchmark-all-results-showcase-20261018/audit/flexiact_inventory/import_motion_fidelity.py'),bind(B/'h3-benchmark-all-results-showcase-20261018/audit/ive_metric_import_20261019/import_scores.py'),bind(B/'h3-benchmark-all-results-showcase-20261018/scripts/build_task_showcase.py')],'historical_value_scope':{'verified_current':'当前inventory的所有有值MF行均标明相应官方实现，导入器绑定实际视频哈希、有效帧、轨迹与评分回执。','excluded_from_MF_column':'人工事件区间、速度lag/姿态诊断另列；它们没有写成MF。尚无与实际媒体绑定的正式MF保持null。','limitation':'本次限定读取未重建每个早期页面的删除历史，不能据此逐项宣称某个旧proxy数值已删除；当前实际MF来源可核。'},'samples':out}
p=O/'PROMPT_AND_METRIC_PROVENANCE.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(bind(p));print(summary)
