"""Summarize frozen aggregate outputs; preserve completeness and timing scopes."""
import csv
import json
import statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent
NINE={'SC':'subject_consistency','BC':'background_consistency','TF':'temporal_flickering','MS':'motion_smoothness','VTSS':'vtss','OSC':'overall_semantic_consistency','PSC':'phrase_semantic_consistency','SF':'semantic_fidelity','MF':'motion_fidelity'}
ORDER=['source','native','early','fixed','late','split','global_weak']
LABELS={'source':'参考视频','native':'普通编辑','early':'1–9步引导','fixed':'7–15步引导','late':'12–20步引导','split':'1–4及16–20步引导','global_weak':'全程弱引导'}
SCOPES={'main_all':'主10组（9组IVEBench＋1组FlexiAct）','main_IVEBench':'纯IVEBench 9组','expansion_all':'IVEBench扩展集'}
def fmt(value,d=6):return '待完成' if value is None else f'{value:.{d}f}'
def write_csv(name,rows,columns):
 with (ROOT/name).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(rows)
def main():
 d=json.loads((ROOT/'snapshot.json').read_text());means=d['metrics']['means']
 lines=['H3 主10组区间引导对照：指标与耗时汇总',f"采集时间：{d['collected_at']}",'',
 '主四组补跑24条全部生成完成。主10组共60条编辑视频与10条参考视频。',
 '指标来自现有官方实现aggregate输出。MF差值逐样本计算：MF(参考,编辑)−MF(参考,参考)，再求均值。',
 'QA：当前已评测任务不属于数量修改，记N/A。IS与CF：原精度Qwen72B资源阻塞，暂无数值；AWQ配置单列。',
 '以下只汇总数值结果，本批按要求未做视觉检查。','']
 all_rows=[];time_rows=[];coverage=[]
 for scope,title in SCOPES.items():
  data=means[scope];methods=data['methods'];lines += [title]
  done=sum(v[metric]['n_done'] for v in methods.values() for metric in NINE.values());expected=sum(v[metric]['n_expected'] for v in methods.values() for metric in NINE.values())
  lines += [f'九项数值指标完成 {done}/{expected}；六方法或两方法完整配对组数：'+', '.join(f'{name}={data["complete_paired_subset"][metric]["n_complete_cases"]}' for name,metric in NINE.items())]
  lines += ['方法 | SC | BC | TF | MS | VTSS | OSC | PSC | SF | MF | MF相对参考差 | MF样本数']
  for method in ORDER:
   if method not in methods:continue
   values=methods[method]
   row={'scope':scope,'method':method,'method_label':LABELS[method]}
   for short,key in NINE.items():
    row[short]=values[key]['mean'];row[short+'_n_done']=values[key]['n_done'];row[short+'_n_expected']=values[key]['n_expected']
   row['MF_delta_reference']=values['motion_fidelity_delta_from_reference']['mean'];row['MF_n_paired']=values['motion_fidelity_delta_from_reference']['n_paired'];all_rows.append(row)
   lines.append(' | '.join([LABELS[method]]+[fmt(values[key]['mean']) for key in NINE.values()]+[fmt(row['MF_delta_reference']),f"{row['MF_n_paired']}/{values['motion_fidelity']['n_expected']}"]))
   for metric,counts in values.items():
    if isinstance(counts,dict) and 'n_expected' in counts:
     coverage.append(dict(scope=scope,method=method,metric=metric,**{k:counts[k] for k in ['n_expected','n_done','n_not_applicable','n_failed','n_pending']}))
   timing=values['timing']
   if method!='source':
    time_rows.append(dict(scope=scope,method=method,timing_scope='all_available_mixed_scope',**{k:timing[k] for k in ['mean_sampling_seconds','n_sampling','mean_step_seconds','n_step']}))
    for ts,stats in timing['by_scope'].items():time_rows.append(dict(scope=scope,method=method,timing_scope=ts,**stats))
  paired=data['complete_paired_subset']['motion_fidelity'];rank=sorted(((method,value) for method,value in paired['method_means'].items() if value is not None),key=lambda x:x[1],reverse=True)
  lines += [f"同组配对MF排序（{paired['n_complete_cases']}组）："+' > '.join(f'{LABELS[m]} {v:.6f}' for m,v in rank),'']
 lines += ['采样耗时（秒）','历史6组包含每步x0 CPU拷贝与audit I/O；新4组没有该项。下列分别列出，异常耗时保留。','方法 | 历史6组平均采样 | 历史平均每步 | 新4组平均采样 | 新平均每步 | 混合10组平均采样 | 混合平均每步']
 for method in ORDER[1:]:
  t=means['main_all']['methods'][method]['timing'];h=t['by_scope']['historical_with_x0_capture'];n=t['by_scope']['current_without_x0_capture']
  lines.append(' | '.join([LABELS[method],fmt(h['mean_sampling_seconds'],2),fmt(h['mean_step_seconds'],2),fmt(n['mean_sampling_seconds'],2),fmt(n['mean_step_seconds'],2),fmt(t['mean_sampling_seconds'],2),fmt(t['mean_step_seconds'],2)]))
 new=d['new24_inference'];total=sum(j['timing'].get('sampling_seconds',0) for j in new)
 lines += ['',f'新24条累计采样 {total:.2f} 秒（{total/3600:.2f} 小时）。']
 anomalies=[]
 for job in new:
  steps=job['timing'].get('sampling_step_seconds',[])
  if steps:
   median=statistics.median(steps)
   for index,value in enumerate(steps,1):
    if value>3*median:anomalies.append(dict(job=job['id'],step=index,seconds=value,within_job_median_seconds=median))
 for a in anomalies:lines.append(f"耗时异常记录：{a['job']} 第{a['step']}步 {a['seconds']:.3f}秒，该任务步耗时中位数{a['within_job_median_seconds']:.3f}秒；该值保留在全部均值中。")
 lines += ['已记录的长停顿同期出现主机内存/I/O压力，具体原因未定。','',
 '文件说明：metrics_means.csv为各方法九项均值及分母；metric_coverage.csv为12项完整性；timing_by_scope.csv分开列历史与本轮计时；snapshot.json为紧凑原始汇总快照。',
 '统计scope中的main_all与main_IVEBench分开，扩展集待完成数量仍保留完整计划分母。']
 (ROOT/'summary.txt').write_text('\n'.join(lines)+'\n')
 cols=['scope','method','method_label']+[x for n in NINE for x in (n,n+'_n_done',n+'_n_expected')]+['MF_delta_reference','MF_n_paired']
 write_csv('metrics_means.csv',all_rows,cols)
 write_csv('metric_coverage.csv',coverage,['scope','method','metric','n_expected','n_done','n_not_applicable','n_failed','n_pending'])
 write_csv('timing_by_scope.csv',time_rows,['scope','method','timing_scope','mean_sampling_seconds','n_sampling','mean_step_seconds','n_step'])
 (ROOT/'timing_anomalies.json').write_text(json.dumps(anomalies,indent=2))
 print('\n'.join(lines[:12]))
if __name__=='__main__':main()
