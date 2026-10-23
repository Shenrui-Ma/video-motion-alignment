"""Read existing paired outputs and official scores; never submit inference."""
from pathlib import Path
import json,subprocess,hashlib,statistics
D=Path(__file__).resolve().parent;E=D.parent
SIDS=['short_0252','short_0358','short_0085','long_0059','short_0343']
metrics=['motion_fidelity','subject_consistency','background_consistency','temporal_flickering','motion_smoothness','vtss','overall_semantic_consistency','phrase_semantic_consistency','semantic_fidelity']
manifest=json.loads((E/'metrics/manifest.json').read_text())['jobs'];catalog={c['task_id']:c for c in json.loads((E/'innovation/pilot_ten/manifest_preparation/catalog.json').read_text())['cases']};results={r['metadata']['task_id']:r for r in json.loads((D/'five_results.json').read_text())}
jobs=[next(j for j in manifest if j['task_id']==sid and j['method']==m) for sid in SIDS for m in ['source','native','six_section_native']]
code='from pathlib import Path\nimport json\np=Path("/data/research-user/h3_metrics_20261022/evaluation/results")\nids='+repr([j['id'] for j in jobs])+'\nms='+repr(metrics)+'\nprint(json.dumps({i:{m:json.loads((p/i/(m+".json")).read_text()) if (p/i/(m+".json")).exists() else {"status":"pending"} for m in ms} for i in ids}))'
r=subprocess.run(['ssh','-o','ConnectTimeout=12','H3_HOST_CONFIGURE_LOCALLY','python3 -'],input=code,text=True,capture_output=True,check=True,timeout=90);scores=json.loads(r.stdout)
(D/'paired_raw_metrics.json').write_text(json.dumps(scores,ensure_ascii=False,indent=2))
paired=[]
for sid in SIDS:
 c=catalog[sid];r=results[sid];md=r['metadata'];js={j['method']:j for j in jobs if j['task_id']==sid}
 assert all(j['seed']==c['seed'] and j['fps']==md['fps'] and j['valid_frames']==md['valid_frames'] and j['crop_xywh']==md['evaluation_crop_xywh'] for j in js.values())
 assert md['geometry']['frames']==c['geometry'].get('sampled_frames',c['geometry'].get('frames'))
 assert hashlib.sha256(c['prompt'].encode()).hexdigest()==c['prompt_sha256']
 # H3 model, sampler, sigma schedule are identical; historical node wrappers differ.
 ng=json.loads(Path(c['graphs']['native']['copy']).read_text());sg=json.loads((D/'host9a/graphs'/('promptfmt_'+sid+'_six_section_native.json')).read_text())
 for n,k in [('1','unet_name'),('2','clip_name'),('3','vae_name'),('4','vae_name'),('8','sampler_name'),('9','sigmas')]:
  assert ng[n]['inputs'][k]==sg[n]['inputs'][k],(sid,n,k)
 out={'task_id':sid,'jobs':js,'seed':c['seed'],'geometry':md['geometry'],'prior_prompt':c['prompt'],'prior_prompt_protocol':c['prompt_protocol'],'six_section_prompt':md['prompt'],'official_edit_prompt':c['official_edit_prompt'],'source_sha256':js['source']['sha256'],'scores':{},'awq':{}}
 for m,j in js.items():
  out['scores'][m]={k:scores[j['id']][k].get('score') if scores[j['id']][k].get('status')=='done' else None for k in metrics}
 for m in ['native','six_section_native']:
  jid=js[m]['id'];out['awq'][m]={}
  for metric in ['instruction_satisfaction','content_fidelity']:
   files=list((E/'metrics/qwen_runtime').glob('host41/snapshot/qwen_runtime/evaluation_awq/results/'+jid+'/'+metric+'.json'))+list((E/'metrics/qwen_runtime').glob('host60_extra/snapshot/extra26_20261022/evaluation_awq/results/'+jid+'/'+metric+'.json'))
   if files:
    d=json.loads(files[-1].read_text());out['awq'][m][metric]={'score':d.get('score') if d.get('status')=='done' else None,'status':d.get('status'),'configuration_id':d.get('evaluator',{}).get('configuration_id'),'file':str(files[-1])}
   else:out['awq'][m][metric]={'status':'pending','score':None}
 out['mf_delta_six_minus_prior']=out['scores']['six_section_native']['motion_fidelity']-out['scores']['native']['motion_fidelity'];paired.append(out)
summary={'count':5,'metrics':{},'note':'前四组为历史详细或保留约束提示词；医生组为官方一句话。六段新版仅summary使用官方指令，其余未指定。'}
for metric in metrics+['instruction_satisfaction','content_fidelity']:
 def get(p,m):return p['scores'][m][metric] if metric in metrics else p['awq'][m][metric]['score']
 valid=[p for p in paired if get(p,'native') is not None and get(p,'six_section_native') is not None]
 if valid:
  a=statistics.mean(get(p,'native') for p in valid);b=statistics.mean(get(p,'six_section_native') for p in valid)
  summary['metrics'][metric]={'prior_mean':a,'six_section_mean':b,'difference':b-a,'paired_n':len(valid),'improved_count':sum(get(p,'six_section_native')>get(p,'native') for p in valid)}
  if metric=='motion_fidelity':
   source=statistics.mean(p['scores']['source'][metric] for p in valid);summary['metrics'][metric].update(source_mean=source,prior_minus_reference=a-source,six_section_minus_reference=b-source)
(D/'paired_metrics.json').write_text(json.dumps(paired,ensure_ascii=False,indent=2));(D/'paired_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
