"""Copy the existing three stride-three exploratory event brackets, preserving MF."""
from import_scores import *
import copy
p=ROOT/'inventory/ivebench.json';d=read(p);before=copy.deepcopy(d);row=next(x for x in d['items'] if x['id']=='r73_short_0252');r=DEV/'h3-ivebench-expanded-metrics-r73-20261018';a=r/'audit/physical_time_short0252';manifest=read(a/'EVIDENCE_MANIFEST.json');sealed={v['path']:v['sha256'] for v in manifest['files']}
for rel in ['VISUAL_EVENT_INTERVALS_EXPLORATORY.json','PROTOCOL.json','dense_frames/MANIFEST.json']:
 req(sha(a/rel)==sealed[rel],'existing evidence seal differs '+rel)
v=read(a/'VISUAL_EVENT_INTERVALS_EXPLORATORY.json');proto=read(a/'PROTOCOL.json');dense=read(a/'dense_frames/MANIFEST.json');req(dense['protocol_sha256']==sha(a/'PROTOCOL.json') and dense['exploratory'] is True,'visual protocol differs')
req(v['fps']==row['fps']==24 and v['full_valid_frames']==[0,97] and proto['valid_frames']==row['valid_frames']==98,'time support mismatch')
for role,field in [('source','reference_video_path'),('native','ordinary_video_path'),('forced','guided_video_path')]:
 expected=proto['media'][role];req(sha(r/expected['file'])==expected['sha256']==sha(row[field])==row['media_sha256'][field],'media binding differs '+role)
for im in dense['files']:req(sha(im['file'])==im['sha256'],'visual sheet changed')
gate=next(Path(x) for x in row['evidence_paths'] if x.endswith('PAIR_RUNTIME_GATE.json'));g=read(gate);req(g['passed'] is True and all(x is True for x in g['checks'].values()),'actual gate failed')
for role in ['native','forced']:req(g['runs'][role]['video']['sha256']==proto['media'][role]['sha256'],'gate output mismatch')
req(len(v['events'])==4 and not any(k.endswith('boundary_frames') for k in v['events'][3]),'fourth event is not final-pose-only')
events=[]
for e in v['events'][:3]:
 x={'name':e['name'],'source_frames':e['source_boundary_frames'],'native_frames':e['native_boundary_frames'],'guided_frames':e['forced_boundary_frames']}
 for k in ['source_frames','native_frames','guided_frames']:
  lo,hi=x[k];req(0<=lo<=hi<=97 and lo in proto['dense_frames'] and hi in proto['dense_frames'],'event bracket differs from sampled times')
 events.append(x)
row['quantitative_metrics']['event_timing']={'measurement':'每3帧视觉复核（探索性）','fps':24,'events':events,'source_file':str(a/'VISUAL_EVENT_INTERVALS_EXPLORATORY.json'),'source_sha256':sha(a/'VISUAL_EVENT_INTERVALS_EXPLORATORY.json'),'scope':'仅右侧前景成人的3个事件。边界包含运动模糊与遮挡造成的不确定性；这些探索性范围不代表精确时差或统计置信区间。第四个最终姿态没有到达时间，未计入。'}
for old,new in zip(before['items'],d['items']):
 if old['id']!='r73_short_0252':req(old==new,'other item changed')
 else:
  test=copy.deepcopy(new);test['quantitative_metrics'].pop('event_timing');req(test==old,'MF/visual field changed')
out=AUDIT/'events_0252';out.mkdir();(out/'PREVIOUS_IVEBENCH.json').write_bytes(p.read_bytes());tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
receipt={'changed_item':'r73_short_0252','events_imported':3,'final_pose_excluded':True,'source_sha256':sha(a/'VISUAL_EVENT_INTERVALS_EXPLORATORY.json'),'protocol_sha256':sha(a/'PROTOCOL.json'),'gate_sha256':sha(gate),'inventory_sha256':sha(p),'original_MF_and_visual_fields_unchanged':True};(out/'RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt))
