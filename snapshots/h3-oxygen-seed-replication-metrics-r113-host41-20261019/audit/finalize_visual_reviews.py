from pathlib import Path
import json,hashlib,itertools,time
R=Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text())
def bind(p):return {'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def enrich(e):
 s,n,g=e['source_frames'],e['native_frames'],e['fixed_frames']; e['native_signed_lag_frames']=[n[0]-s[1],n[1]-s[0]];e['fixed_signed_lag_frames']=[g[0]-s[1],g[1]-s[0]]
 v=[abs(c-a)-abs(b-a) for a,b,c in itertools.product(range(s[0],s[1]+1),range(n[0],n[1]+1),range(g[0],g[1]+1))];e['paired_absolute_error_change_bounds_frames']=[min(v),max(v)]
prev=load(R/'audit/actual_seed2026101702_preview/REVIEW.json');ppt=load(R/'audit/actual_seed2026101702_preview/media/PREVIEW_PRESENTATION.json');present=load(R/'showcase/2026101702/PRESENTATION.json')
assert ppt['video']['sha256']==present['video']['sha256']
assert [(x['frames'],x['sha256']) for x in ppt['pages']]==[(x['frames'],x['sha256']) for x in present['pages']]
oldreview=bind(R/'audit/actual_seed2026101702_preview/REVIEW.json');template=load(R/'audit/full98_review/2026101702/REVIEW_TEMPLATE.json')
prev.update(formal_batch_complete=True,all_valid_frames_inspected=True,reviewer='continue_metrics',evidence=template['evidence'],preview_review_preserved=oldreview,preview_and_formal_render_byte_equal=True)
prev['frame_ledger']=template['evidence']['frame_ledger'];prev['pair_gate']=template['evidence']['pair_gate'];prev['intake']=template['evidence']['collection'];prev['official_MF']='RUNNING_SEPARATE_OFFICIAL_SCORE'
save(R/'audit/full98_review/2026101702/REVIEW.json',prev)
r=load(R/'audit/full98_review/2026101703/REVIEW_TEMPLATE.json');r.update(all_valid_frames_inspected=True,examined_frames=list(range(98)),reviewer='continue_metrics + continue_r111_r103',review_coverage=[{'reviewer':'continue_metrics','frames':list(range(50)),'supplementary_frames':list(range(55,75))},{'reviewer':'continue_r111_r103','frames':list(range(50,98)),'receipt':bind(R/'audit/seed1703_late_independent_review.json')}],formal_batch_complete=True)
for role in ['native','fixed']:
 r['task_acceptance'][role]={'status':'PASS_CORE_EDIT','elderly_woman_identity':True,'cabin_child_mask_retained':True,'action_sequence_retained':True,'framing_and_motion_amplitude':'主构图与抓取/举带阶段保留；手部与面罩细节有生成差异。','notes':'年长女性、浅粉开衫和浅色内搭稳定，邻座儿童、座椅和机舱保留。'}
 r['whole_clip_quality'][role]={'status':'PASS_CORE_EDIT','notes':'未见整场景改写或主体身份跳变；细小手形/杯形差异保留记录。'}
events=[
 {'name':'双手明显离开膝部并向面罩靠拢','source_frames':[42,45],'native_frames':[57,60],'fixed_frames':[42,45],'status':'COMPARABLE_VISIBLE','note':'普通版55–56帧手仍近膝，57–60帧双手向杯靠拢；引导版42–45帧已做对应动作。'},
 {'name':'双手明确握住黄色面罩部分','source_frames':[48,51],'native_frames':[62,64],'fixed_frames':[48,51],'status':'COMPARABLE_VISIBLE','note':'引导版47帧接触杯边，48–51帧双手握杯；普通版62–64帧握杯。模糊接触以区间保留。'},
 {'name':'解剖右手举带到上胸/脸侧区域','source_frames':[69,75],'native_frames':[84,89],'fixed_frames':[69,75],'status':'COMPARABLE_VISIBLE','note':'引导版与参考69–75帧右手由杯向上胸/脸侧移动；普通版到84–89帧才出现相同过渡。'}]
for e in events:enrich(e)
r['events']=events;r['terminal_pose_presence']={'source':{'status':'PRESENT','frames':[90,97]},'native':{'status':'PRESENT','frames':[90,97]},'fixed':{'status':'PRESENT','frames':[90,97]},'notes':'末段都进入高抬手阶段；这只能说明举带/整理面罩，未判定已戴稳。'}
r['alignment']={'native':False,'fixed':True,'scope':'三项预登记可见事件及全片动作顺序','reason':'普通版三阶段延后；引导版三阶段区间均与源片重叠，末段姿态也存在。'}
r['conclusion']='EVENT_TIMING_BENEFIT';r['summary']='第二个新种子中，引导版抓取面罩和举带时刻接近参考，普通版三个阶段均明显延后；角色、机舱和动作顺序保留。';r['suggested_still_frame']=50;r['suggested_secondary_frame']=74;r['official_MF']='RUNNING_SEPARATE_OFFICIAL_SCORE';r['arithmetic_note']='24fps物理帧视觉区间；绝对误差变化共享同一source事件时刻穷举，非置信区间。';r['mask_worn_securely_claim']=False
save(R/'audit/full98_review/2026101703/REVIEW.json',r)
report={'passed':True,'reviews':{str(s):bind(R/f'audit/full98_review/{s}/REVIEW.json') for s in [2026101702,2026101703]},'presentations':{str(s):bind(R/f'showcase/{s}/PRESENTATION.json') for s in [2026101702,2026101703]},'source_count':1,'seed_count':2,'all_four_actual':True,'formal_batch':bind(R/'incoming/actual/AGGREGATE_GATE.json'),'release':bind(R/'incoming/actual/ROOT_EXIT_RECEIPT.json'),'MF_status':'running','unix':time.time()}
save(R/'audit/FULL98_REVIEW_VERIFIED.json',report)
print(json.dumps(report,ensure_ascii=False));print('seed1703 bounds',[e['paired_absolute_error_change_bounds_frames'] for e in events])
