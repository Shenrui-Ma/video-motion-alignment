"""One-shot CPU intake from completed R99/R100 consumer records only."""
import argparse,shutil,sys
from common import *
BASE=Path('/Users/researcher/DevProjects')
SOURCES={'r99':('short_0210','short_0230','short_0352'),'r100':('short_0114','short_0392')}
NAMES={'r99':'h3-ive-p1-guidance-metrics-r99-20261019','r100':'h3-ive-task-repair-metrics-r100-20261019'}

def frozen_inputs(lane,source):
 require(lane in SOURCES and source in SOURCES[lane],'not in fixed followup denominator');consumer=BASE/NAMES[lane];cfg=read(consumer/'configs/contract.json')
 if lane=='r99':
  p=cfg['cases'][source];dest=consumer/'incoming'/source;full=Path(p['reference_video']['file']);source_dir=full.parent
  hist=BASE/('h3-timing-ivebench-prompt-pair-r71-20261018/audit/consumer/incoming/p1_logs_history.json' if source=='short_0210' else 'h3-timing-local-edit-repair-r80-20261018/audit/input_decode_recovery_v2/incoming/'+source+'/history.json')
  return consumer,cfg,p,dest,full,source_dir/(source+'_original.mp4'),source_dir/(source+'_provenance.json'),{'native':hist,'forced':dest/'history.json'},p['valid_frames'],90,'r99-historical-native-paired-runtime-gate-v1'
 p=next(x for x in cfg['sources'] if x['source_id']==source);dest=consumer/'incoming_pairs'/source
 return consumer,cfg,p,dest,consumer/p['source']['file'],Path(p['original_media']['file']),consumer/p['provenance']['file'],{x:dest/(x+'_history.json') for x in ('native','forced')},p['valid_frames'],p['geometry']['frames'],'r100-paired-runtime-gate-v1'

def accept_intake(lane,source,cfg,p,dest,gate):
 receipt=read(dest/'COLLECTION.json')
 for name,digest in receipt['files'].items():
  require(Path(name).name==name,'unsafe collection filename');require(sha(dest/name)==digest,'collected actual media/evidence changed')
 require(gate.get('passed') is True and gate.get('checks') and all(v is True for v in gate['checks'].values()),'actual pair gate has failure')
 require(gate['runtime_profile_sha256']==cfg['producer_runtime_sha256'],'producer runtime differs')
 require(gate['source_id']==source and set(gate['runs'])=={'native','forced'},'actual pair/source differs')
 for role in ('native','forced'):
  row=gate['runs'][role];expected=p['run_id'] if role=='native' else (f'r99_{source}_seed2026101701_forced' if lane=='r99' else p['forced_run_id'])
  require(row['run_id']==expected and row['NFE']==20 and row['Euler_updates']==20 and row['routed_blocks']==(0 if role=='native' else 450),'actual method/run differs')
  require(sha(dest/(role+'.mp4'))==row['video']['sha256'],'actual target video changed')
 prefix=gate['prefix_tensor_comparison'];require(len(prefix)==6 and [x['step_zero_based'] for x in prefix]==list(range(6)) and all(x[k] is True for x in prefix for k in ('video','audio')),'actual six-step prefix gate missing')
 if lane=='r99':require(gate['runs']['native']['video']['sha256']==p['native_video']['sha256'],'wrong historical Native')
 else:
  b=read(BASE/NAMES[lane]/'audit/EXECUTION_BINDING.json');require(receipt['execution_binding_sha256']==sha(BASE/NAMES[lane]/'audit/EXECUTION_BINDING.json') and gate['service_owner']=={'pid':b['owner']['pid'],'identity':b['owner']['identity']},'actual execution binding differs')
 return receipt

def intake(lane,source):
 consumer,cfg,p,dest,full,original,prov,history,valid,total,schema=frozen_inputs(lane,source);gatefile=dest/'PAIR_RUNTIME_GATE.json'
 if not gatefile.exists() or not(dest/'COLLECTION.json').exists():return {'case':lane+'_'+source,'status':'PENDING_ACTUAL_PAIRED_INTAKE','GPU_started':False}
 gate=read(gatefile);require(gate['schema']==schema,'gate schema differs');receipt=accept_intake(lane,source,cfg,p,dest,gate)
 expected_source=p['reference_video']['sha256'] if lane=='r99' else p['source']['sha256'];require(sha(full)==expected_source,'source differs from consumer contract');provenance=read(prov);require(sha(original)==provenance['source_sha256'] and provenance['video_sha256']==expected_source,'source provenance/data differs')
 name=lane+'_'+source;c=ROOT/'cases'/name;require(not c.exists(),'case already collected; preserve immutable inputs');staging=ROOT/'audit'/('staging_'+name);staging.mkdir(exist_ok=False);(staging/'inputs').mkdir()
 copies={'source_full.mp4':full,'source_original.mp4':original,'source_provenance.json':prov,'PAIR_RUNTIME_GATE.json':gatefile,'COLLECTION.json':dest/'COLLECTION.json','CONSUMER_CONTRACT.json':consumer/'configs/contract.json'}
 for role in ('native','forced'):copies[role+'.mp4']=dest/(role+'.mp4');copies[role+'_history.json']=history[role]
 for n,path in copies.items():shutil.copy2(path,staging/'inputs'/n)
 spec={'case_id':name,'source_id':source,'valid_frames':valid,'total_frames':total,'fps':24,'crop_xywh':[16,8,1280,720],'gate':{'file':'inputs/PAIR_RUNTIME_GATE.json','sha256':sha(gatefile),'schema':schema},'source':{'full_file':'inputs/source_full.mp4','full_sha256':sha(full),'original_file':'inputs/source_original.mp4','original_sha256':sha(original),'provenance_file':'inputs/source_provenance.json','provenance_sha256':sha(prov)},'targets':{}}
 if lane=='r100':spec['gate'].update(valid_frame_keys=['runs','native','valid_frames'],crop_keys=['runs','native','evaluation_crop_xywh'])
 for role in ('native','forced'):
  spec['targets'][role]={'full_file':'inputs/'+role+'.mp4','full_sha256':gate['runs'][role]['video']['sha256'],'history_file':'inputs/'+role+'_history.json','history_sha256':sha(history[role]),'run_id':gate['runs'][role]['run_id'],'gate_video_keys':['runs',role,'video'],'gate_run_keys':['runs',role,'run_id'],'method_label':'ordinary' if role=='native' else 'fixed same-bin steps6..14'}
 validate_gate(spec,gate);save(staging/'SPEC.json',spec);save(staging/'INTAKE_RECEIPT.json',{'consumer':str(consumer),'collection':bound(dest/'COLLECTION.json'),'actual_gate':bound(gatefile),'input_sources':{n:bound(path) for n,path in copies.items()},'tracking_forwards':0});staging.rename(c)
 return {'case':name,'status':'ACTUAL_PAIRED_INPUTS_COLLECTED','spec':bound(c/'SPEC.json'),'GPU_started':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--lane',choices=SOURCES,required=True);p.add_argument('--source',required=True);a=p.parse_args();print(json.dumps(intake(a.lane,a.source)))
