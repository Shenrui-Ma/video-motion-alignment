"""Build an offline draft from frozen development evidence and explicit benchmark data."""
import argparse,base64,hashlib,json,math,re,subprocess
from fractions import Fraction
from pathlib import Path
from html import escape
HERE=Path(__file__).resolve().parent
PAPER=HERE.parent
BASE=PAPER.parent
EXPECTED={'flexiact':['chest','crouch','fitness','one_leg','rotate'],'ivebench':['short_0210','short_0230','short_0263','short_0352','short_0370']}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def require(ok,msg):
 if not ok:raise ValueError(msg)
def evidence_value(record):
 require(record and sha(record['path'])==record['sha256'],'metric evidence missing or changed')
 value=read(record['path']);pointer=record.get('json_pointer')
 require(isinstance(pointer,str) and (pointer=='' or pointer.startswith('/')),'metric JSON pointer missing')
 for part in pointer.split('/')[1:]:
  part=part.replace('~1','/').replace('~0','~');value=value[int(part)] if isinstance(value,list) else value[part]
 return value
def asset(record):
 p=Path(record['path']);require(p.is_file() and sha(p)==record['sha256'],'asset bytes changed:'+str(p))
 if 'bytes' in record:require(p.stat().st_size==record['bytes'],'asset size changed')
 return 'data:'+record['mime']+';base64,'+base64.b64encode(p.read_bytes()).decode()
def frame_times(path):
 frames=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','frame=best_effort_timestamp_time','-of','json',str(path)],text=True))['frames']
 times=[Fraction(f['best_effort_timestamp_time']) for f in frames]
 return [t-times[0] for t in times]
def validate(data):
 require(data['schema']=='h3-benchmark-report-v2','wrong input schema')
 require([b['id'] for b in data['benchmarks']]==list(EXPECTED),'benchmark list changed')
 for b in data['benchmarks']:
  require(b['planned_denominator']==5 and [c['id'] for c in b['cases']]==EXPECTED[b['id']],'fixed five-case denominator/order changed')
  require(b['policy_id'] in ('delay_only_R50','signed_R53','ROOT_DECISION_PENDING'),'unrecognized policy')
  if b['id']=='flexiact':require(b['policy_id']=='delay_only_R50' and b['policy_status']=='frozen','FlexiAct R50 policy changed')
  if b['policy_status']=='pending':require(b['policy_id']=='ROOT_DECISION_PENDING','pending policy identifier differs')
  else:
   require(b['policy_status']=='frozen' and b['policy_id']!='ROOT_DECISION_PENDING','policy not frozen')
   if b['id']=='ivebench':
    record=b.get('policy_evidence');require(record and sha(record['path'])==record['sha256'],'IVEBench independent policy evidence missing')
    policy=read(record['path']);require(policy['status']=='FROZEN_BY_ROOT' and policy['choice']==b['policy_id'],'IVEBench frozen policy differs')
  for c in b['cases']:
   context=c.get('timing_evaluation')
   if any(c[a]['timing_lag_ms']['status'] in ('complete','unknown') for a in ('ordinary','automatic')):
    require(isinstance(context,dict),'timing evaluation interval and body part missing')
    require(isinstance(context.get('body_part'),str) and context['body_part'],'timing body part missing')
    window=context.get('frame_interval_inclusive')
    require(isinstance(window,list) and len(window)==2 and all(type(x)is int for x in window) and 0<=window[0]<=window[1],'timing interval invalid')
    require(type(context.get('fps')) in (int,float) and context['fps']>0,'timing fps missing')
   for arm in ('ordinary','automatic'):
    a=c[arm]
    if a.get('visual_observation'):
     record=a.get('visual_evidence')
     require(record and sha(record['path'])==record['sha256'],'visual observation evidence missing or changed')
    if a.get('inference_observation'):
     record=a.get('inference_evidence')
     require(record and sha(record['path'])==record['sha256'],'inference observation evidence missing or changed')
    for key in ('official_motion_fidelity','timing_lag_ms','edit_success'):
     m=a[key];require(m['status'] in ('pending','complete','unknown','failed'),'metric status differs')
     if m['status']!='complete':require(m['value'] is None,'unfinished metric cannot have a number')
     else:
      require(evidence_value(m.get('evidence'))==m['value'],'metric number differs from evidence JSON pointer')
      if key=='edit_success':require(type(m['value']) is bool,'edit_success must be bool')
      else:require(type(m['value']) in (int,float) and math.isfinite(m['value']),'metric must be finite')
      if key=='official_motion_fidelity':require(m.get('evaluator') and all(m['evaluator'].get(k) for k in ('name','revision','protocol_id')),'official metric evaluator/protocol missing')
    if arm=='automatic' and b['policy_status']=='pending':require(a['video'] is None and all(a[k]['status']=='pending' for k in ('official_motion_fidelity','timing_lag_ms','edit_success')),'automatic output cannot precede frozen policy')
 return data

def lag_pair(fixed,key,window,flat=False):
 return [next(row['reliable_lag_frames'] for row in (fixed[key][conf] if flat else fixed[key][conf]['diagnostics']) if row['window']==window and row['feature']=='arm_direction') for conf in ('0.3','0.5')]
def ms(values):return ' / '.join('UNKNOWN' if v is None else ('0' if v==0 else f'{v*1000/24:+.0f}') for v in values)
def table(headers,rows):return '<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+escape(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def metric(m,kind='score'):
 if m['status']=='pending':return '待评分'
 if m['status']=='unknown':return 'UNKNOWN'
 if m['status']=='failed':return '评价失败'
 if kind=='edit':return '完成' if m['value'] else '未完成'
 return f"{m['value']:+.0f}" if kind=='lag' else f"{m['value']:.4f}"

class Builder:
 def __init__(self,evidence):
  self.e=evidence;self.assets={};self.provenance=[];self.derivatives=[]
  self.bound={r['path']:r for r in evidence['sources']+evidence['assets']}
 def verified(self,path):
  path=str(path);r=self.bound[path];require(sha(path)==r['sha256'],'frozen development evidence changed:'+path);self.provenance.append(r);return read(path)
 def media_key(self,record):
  key='a'+record['sha256'];self.assets.setdefault(key,asset(record));return key
 def composite(self,records):
  """Bake three identity frame mappings into a single presentation video."""
  mappings=[];inputs=[];probes=[];timelines=[]
  for r in records:
   p=Path(r['path']);require(sha(p)==r['sha256'],'composite input bytes changed')
   panels=r.get('panel_count',1);index=r.get('panel_index',0)
   w=r['width'];h=r['height'];visible=r.get('visible_height',h)
   require(type(panels)is int and 0<=index<panels and w%panels==0 and 0<visible<=h,'invalid media panel mapping')
   probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate,r_frame_rate,nb_frames','-of','json',str(p)],text=True))['streams'][0]
   require((probe['width'],probe['height'])==(w,h),'actual input dimensions differ')
   require(int(probe['nb_frames'])>0 and Fraction(probe['avg_frame_rate'])>0,'input frame metadata missing')
   times=frame_times(p);timelines.append(times)
   inputs.append(str(p));probes.append(probe)
   mappings.append({'source_path':str(p),'source_sha256':r['sha256'],'crop_xywh':[index*(w//panels),0,w//panels,visible],'frame_mapping':'output_frame_i_equals_source_frame_i','source_frames':int(probe['nb_frames']),'source_fps':probe['r_frame_rate'],'reported_avg_frame_rate':probe['avg_frame_rate'],'normalized_frame_times':[str(t) for t in times]})
  require(len({(x['source_frames'],Fraction(x['source_fps'])) for x in mappings})==1,'comparison frame counts or fps differ')
  require(all(t==timelines[0] for t in timelines),'comparison frame timestamps differ')
  require(len({x['crop_xywh'][3] for x in mappings})==1,'comparison visible heights differ')
  key=hashlib.sha256(json.dumps(mappings,sort_keys=True).encode()).hexdigest()[:20]
  directory=HERE/'derived_assets';directory.mkdir(exist_ok=True)
  path=directory/(key+'.mp4');map_path=directory/(key+'.mapping.json')
  if path.exists() or map_path.exists():
   require(path.exists() and map_path.exists(),'incomplete composite cache')
   mapping=read(map_path);require(mapping['inputs']==mappings and mapping['output_sha256']==sha(path),'derived composite cache changed')
  else:
   command=['ffmpeg','-v','error','-nostdin'];filters=[]
   for source in inputs:command+=['-i',source]
   for i,m in enumerate(mappings):
    x,y,w,h=m['crop_xywh'];filters.append(f'[{i}:v]crop={w}:{h}:{x}:{y},setpts=PTS-STARTPTS[v{i}]')
   filters.append('[v0][v1][v2]hstack=inputs=3[out]')
   command+=['-filter_complex',';'.join(filters),'-map','[out]','-an','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-fps_mode','passthrough','-movflags','+faststart',str(path)]
   subprocess.run(command,check=True)
   check=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate,nb_frames','-of','json',str(path)],text=True))['streams'][0]
   output_times=frame_times(path)
   require(len(output_times)==len(timelines[0]) and all(abs(a-b)<=Fraction(1,1000000) for a,b in zip(output_times,timelines[0])),'derived video timestamps changed')
   require(int(check['nb_frames'])==mappings[0]['source_frames'],'derived video frame count changed')
   require(check['width']==sum(m['crop_xywh'][2] for m in mappings) and check['height']==mappings[0]['crop_xywh'][3],'derived video geometry differs')
   mapping={'schema':'single-clock-triptych-v1','inputs':mappings,'output':str(path),'output_sha256':sha(path),'output_probe':check,'normalized_output_frame_times':[str(t) for t in output_times],'maximum_timestamp_error_s':float(max(abs(a-b) for a,b in zip(output_times,timelines[0]))),'command':command,'audio':'omitted for visual comparison','temporal_resampling':False}
   map_path.write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n')
  self.derivatives.append({'mapping_path':str(map_path),'mapping_sha256':sha(map_path),'output_path':str(path),'output_sha256':sha(path)})
  return {'path':str(path),'sha256':sha(path),'mime':'video/mp4','fps':float(Fraction(mappings[0]['source_fps']))}
 def triptych(self,title,records,labels=None):
  labels=labels or ['Source · 参考视频','普通编辑','完整自动法']
  captions='<div class="triptych">'+''.join('<div class="caption">'+escape(label)+'</div>' for label in labels)+'</div>'
  if all(r is not None for r in records):
   composite=self.composite(records);key=self.media_key(composite)
   content=f'<video class="combined-video" muted playsinline preload="metadata" data-asset="{key}" aria-label="{escape(title)}"></video>'+captions
  else:
   content='<div class="triptych">'+''.join('<div class="missing">'+('素材已归档；等待成组' if r else '等待接入对比素材')+'</div>' for r in records)+'</div>'+captions
  fps=composite['fps'] if all(r is not None for r in records) else next((r.get('fps',24) for r in records if r is not None),24)
  require(type(fps) in (int,float) and fps>0,'media fps must be positive')
  return '<figure class="comparison" data-fps="'+str(fps)+'"><h3>'+escape(title)+'</h3>'+content+'<div class="playbar"><button data-action="play">播放</button><button data-action="pause">暂停</button><button data-action="back">前一帧</button><button data-action="next">后一帧</button><input type="range" min="0" max="1" step="0.001" value="0" aria-label="播放位置"><select aria-label="播放速度"><option value="1">1×</option><option value="0.5">0.5×</option></select><button data-action="fullscreen">放大整组</button></div></figure>'
 def existing_triptych(self,title,path,panels,indices,height=400,labels=None):
  original=self.bound[str(path)];records=[dict(original,panel_count=panels,panel_index=i,width=656*panels,height=height,visible_height=368) for i in indices]
  return self.triptych(title,records,labels)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--data',type=Path,default=HERE/'benchmarks.template.json');parser.add_argument('--output',type=Path,default=HERE/'DRAFT_NOT_DELIVERED.html');args=parser.parse_args()
 require(args.output.resolve().is_relative_to(HERE),'draft builder output must stay inside benchmark_revision_v2')
 data=validate(read(args.data));evidence=read(PAPER/'evidence.json');b=Builder(evidence)
 r33=BASE/'h3-timing-window-location-r33-20261017/analysis/postrun/captured/batch/final/r33_s05_index4_bins23to27'
 r34=BASE/'h3-timing-fixed-early-global-r34-20261017/analysis/postrun_v3/captured/r34_source40372_seed2026101701_global_full_index4/analysis'
 r39=BASE/'h3-timing-matched-global-r39-20261017/analysis/postrun/independent_review/COMPACT_RESULTS.json'
 f33=b.verified(r33/'FIXED_WINDOWS.json')['results'];f34=b.verified(r34/'compare/FIXED_WINDOWS.json')['results'];matched=b.verified(r39)
 development=[]
 for case,label,feature in [('case05','动作片段05','两侧手臂'),('case40372','棚内舞蹈40372','两侧手臂'),('case07','床边舞蹈07','两侧手臂')]:
  row=evidence['scientific_claims'][case];development.append([label,feature,'–'.join(map(str,row['window'])),ms(row['ordinary_lag']),ms(row['auto_lag'])])
 case=evidence['scientific_claims']['case51310'];development.append(['球场51310','左臂','64–95',ms(case['left_arm_lag']['Native']),ms(case['left_arm_lag']['Auto'])])
 ablation=[['动作片段05','完整自动法','自动选择视频区间；去噪索引4',ms(lag_pair(f33,'Auto',[50,65]))],['动作片段05','替换视频区间','保持同一次引导；改为约77–93帧',ms(lag_pair(f33,'Displaced',[50,65]))],['棚内舞蹈40372','完整自动法','自动区间；去噪索引2、4、5、6',ms(lag_pair(f34,'Auto',[40,55]))],['棚内舞蹈40372','移除局部区间选择','同一组四个去噪索引；改为全片',ms(lag_pair(matched['fixed'],'MatchedGlobal',[40,55],True))],['棚内舞蹈40372','固定单次全片引导','固定去噪索引4；全片',ms(lag_pair(f34,'EarlyGlobalPulse',[40,55]))]]
 videos=b.existing_triptych('动作片段05',r33/'media/full_comparison.mp4',5,[0,1,3])+b.existing_triptych('棚内舞蹈40372',r34/'media/all_methods/fixed_clip_comparison.mp4',5,[0,1,3])
 bed=BASE/'h3-timing-architecture-r2-20261016/presentation/automatic_20261017/assets_r35/full_comparison.mp4'
 videos+=b.existing_triptych('床边舞蹈07',bed,4,[0,1,3])
 court=BASE/'h3-timing-manual-source51310-r41-20261017/analysis/postrun/captured/r41_source51310_seed2026101701_manual56to127_6to14/analysis/media/source_native_auto_manual/comparison_141frames.mp4'
 videos+=b.existing_triptych('球场51310 · 左臂仍有残余延后',court,4,[0,1,2],416)
 # One visual row per ablation comparison, separated from complete-method results.
 ablation_media=b.existing_triptych('消融：将视频区间移动到较晚位置',r33/'media/full_comparison.mp4',5,[0,3,4],labels=['Source · 参考视频','完整自动法','较晚区间引导'])
 sections=[]
 for bench in data['benchmarks']:
  rows=[];figures=[];observations=[];complete=0
  for c in bench['cases']:
   n,a=c['ordinary'],c['automatic'];pair=all(v['official_motion_fidelity']['status']=='complete' for v in (n,a));complete+=pair
   delta=f"{a['official_motion_fidelity']['value']-n['official_motion_fidelity']['value']:+.4f}" if pair else '待成对评分'
   context=c.get('timing_evaluation');where=(context['body_part']+' · '+'–'.join(map(str,context['frame_interval_inclusive']))+'帧') if context else '待定评价段'
   rows.append([c['name'],metric(n['official_motion_fidelity']),metric(a['official_motion_fidelity']),delta,where,metric(n['timing_lag_ms'],'lag'),metric(a['timing_lag_ms'],'lag'),metric(n['edit_success'],'edit')+' / '+metric(a['edit_success'],'edit')])
   for arm,label in ((n,'普通编辑'),(a,'完整自动法')):
    if arm.get('visual_observation'):
     observations.append('<p><strong>'+escape(c['name']+' · '+label)+'：</strong>'+escape(arm['visual_observation'])+' <span class="note">'+escape(arm.get('visual_scope',''))+'</span></p>')
    if arm.get('inference_observation'):
     observations.append('<p><strong>'+escape(c['name']+' · '+label)+'：</strong>'+escape(arm['inference_observation'])+'</p>')
   figures.append(b.triptych(bench['name']+' · '+c['name'],[c['source_video'],n['video'],a['video']]))
  sections.append('<section class="benchmark"><h3>'+escape(bench['name']+' · '+bench['role'])+'</h3><p class="policy">'+escape(bench['policy_label'])+'</p><p>'+escape(bench['protocol'])+'</p><p>'+escape(bench['metric_definition'])+f' 成对评分已接入 {complete}/5 条。</p>'+table(['样例','普通编辑 MF ↑','完整自动法 MF ↑','差值 Auto−普通','Δt测量：部位 / 帧段','普通编辑 Δt (ms)','自动法 Δt (ms)','编辑完成：普通 / 自动'],rows)+''.join(observations)+'<details><summary>展开全部5条公开样例</summary>'+''.join(figures)+'</details></section>')
 diagnostic_html=''
 if data.get('metric_diagnostic'):
  diagnostic=evidence_value(data['metric_diagnostic']['evidence'])
  require(diagnostic['status']=='COMPLETE' and diagnostic['fixed_source_count']==5 and diagnostic['actual_score_count']==30 and diagnostic['generated_video_results'] is False,'synthetic diagnostic scope differs')
  diagnostic_rows=[]
  for variant,label in [('self_common','原轨迹'),('delay_2','延后2帧'),('delay_4','延后4帧'),('delay_8','延后8帧'),('visibility_gap_8','中央8帧跟踪不可见')]:
   rows=[r for r in diagnostic['per_case'] if r['variant']==variant]
   require(len(rows)==5 and len({r['pair_id'] for r in rows})==5 and len({r['known_delay_ms'] for r in rows})==1,'synthetic diagnostic denominator or delay differs')
   diagnostic_rows.append([label,f"{rows[0]['known_delay_ms']:.2f}",f"{sum(r['MF'] for r in rows)/5:.4f}"])
  diagnostic_html='<details class="text"><summary>指标校验：MF与物理时差的关系</summary><p>对五条源视频的既有轨迹施加固定时移，并用官方IVEBench MF评分。各组保留相同物理评价区间；可见性缺口组仅删去观测标记，真实动作时序相同。</p>'+table(['合成轨迹变换','已知延后 (ms)','五条平均 MF'],diagnostic_rows)+'<p>MF随时移增加而下降；333 ms的整体延后仍可得到约0.91。跟踪可见性也会影响分数，因此同时检查动作事件及其物理时间。</p></details>'
 observer_html=''
 if data.get('observer_diagnostic'):
  versions={key:evidence_value(record) for key,record in data['observer_diagnostic'].items()}
  observer_rows=[]
  for case in EXPECTED['ivebench']:
   cells=[]
   for key in ('r55_original','r56_arm_only'):
    diagnostic=versions[key]
    require(diagnostic['version']==key and diagnostic['status']=='complete' and diagnostic['synthetic_CPU_diagnostic'] is True and diagnostic['GPU_calls']==diagnostic['new_pose_calls']==0,'observer diagnostic scope differs')
    records=[r for r in diagnostic['records'] if r['source_id']==case]
    require(sorted(r['known_lag_frames'] for r in records)==[-8,-4,0,4,8],'observer diagnostic cases differ')
    shifted=[r for r in records if r['known_lag_frames']]
    require(all(all(pair['lags']==[r['known_lag_frames']]*2 for pair in r['reliable_lag_pairs']) for r in records),'observer diagnostic estimated lag differs')
    detected=sum(r['second_identical_observation_possible_ON'] for r in shifted)
    zero=next(r for r in records if r['known_lag_frames']==0)
    require(not zero['second_identical_observation_possible_ON'],'zero-lag diagnostic unexpectedly triggers')
    cells.append(f'{detected}/4 可检测' if detected else 'UNKNOWN')
   observer_rows.append([case.removeprefix('short_'),*cells])
  observer_html='<details class="text"><summary>观察器可用性：已知时移诊断</summary><p>对五条源姿态分别施加−8、−4、+4、+8帧时移，检查原检测规则能否识别。表中每条的四种时移属于同一源视频的合成诊断。</p>'+table(['样例','本轮观察器','单独移除躯干前置检查'],observer_rows)+'<p>原实现覆盖2/5条源视频；保留上肢方向计算并移除其不需要的躯干前置检查后，覆盖4/5条。所有可报告时差均与已知位移一致，零时移均未触发。该检查定位了观测范围限制；右列尚未接入本轮生成。</p></details>'
 attention=(PAPER/'audit/benchmark_revision/attention.svg').read_text()
 text=(HERE/'template.html').read_text()
 substitutions={'ATTENTION':attention,'DEVELOPMENT_TABLE':table(['开发样例','测量部位','评价帧段','普通编辑 Δt (ms)','完整自动法 Δt (ms)'],development),'DEVELOPMENT_VIDEOS':videos,'ABLATION_TABLE':table(['样例','方法','具体改动','相同评价段 Δt (ms)'],ablation),'ABLATION_MEDIA':ablation_media,'BENCHMARKS':''.join(sections),'ASSETS':json.dumps(b.assets).replace('<','\\u003c'),'BENCHMARK_DATA':json.dumps(data,ensure_ascii=False).replace('<','\\u003c')}
 substitutions['METRIC_DIAGNOSTIC']=diagnostic_html
 substitutions['OBSERVER_DIAGNOSTIC']=observer_html
 for key,value in substitutions.items():text=text.replace('{{'+key+'}}',value)
 require(not re.search(r'{{[A-Z_]+}}',text),'unresolved template placeholder')
 args.output.write_text(text)
 manifest={'schema':'h3-benchmark-draft-build-v2','status':'DRAFT_NOT_DELIVERED','html':str(args.output),'html_sha256':sha(args.output),'html_bytes':args.output.stat().st_size,'builder_sha256':sha(Path(__file__)),'template_sha256':sha(HERE/'template.html'),'evidence_sha256':sha(PAPER/'evidence.json'),'benchmark_data_sha256':sha(args.data),'attention_svg_sha256':sha(PAPER/'audit/benchmark_revision/attention.svg'),'sources':b.provenance,'derived_media':b.derivatives,'embedded_asset_count':len(b.assets),'browser_review':'not performed; existing browser policy block respected','new_inference_calls':0,'new_pose_calls':0,'single_video_per_comparison':True}
 (HERE/'DRAFT_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:manifest[k] for k in ['status','html','html_bytes','embedded_asset_count']},ensure_ascii=False))

if __name__=='__main__':main()
