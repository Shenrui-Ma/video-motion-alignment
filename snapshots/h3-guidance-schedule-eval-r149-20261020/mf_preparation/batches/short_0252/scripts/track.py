"""Per-video provenance and lifecycle adapter; pinned tracker numerical modules unchanged."""
import argparse,time,sys,os
from common import *
def flex_manifest(c,m,role):
 runtime=ROOT/'runtime/flex';sources=[]
 for key in read(ROOT/'configs/PLAN.json')['groups']:
  b=case(key);g=read(b/'INPUTS.json')
  if g['benchmark']=='FlexiAct':sources.append(dict(id=g['canonical_id'],role='reference',file=str(b/'source_score.mp4'),sha256=g['source_score_sha256'],frames=49,pts_seconds=[i/8 for i in range(49)],original_frame_indices=list(range(49)),original_fps=8))
 path=runtime/'SOURCE_INPUTS.json';value=dict(schema='pending-flex-source-inputs-v1',inputs=sources)
 if path.exists():assert read(path)==value
 else:save(path,value)
 if role=='source':return path
 t=next(x for x in m['targets']if x['role']==role);b=c/role;mapping=read(b/'score.mapping.json');mapping['source']=str(b/'full.mp4');mapping['destination']=str(b/'score.mp4');save(b/'DEPLOYED_MAPPING.json',mapping)
 meta=dict(official_pair_id=m['canonical_id'],edited49=str(b/'score.mp4'),edited49_sha256=t['score_sha256'],full158_output=str(b/'full.mp4'),full158_output_sha256=t['full_sha256'],full_output_indices=list(range(0,147,3)),physical_seconds=[i/8 for i in range(49)],padding_evaluated=False,original_source_sha256=m['source_score_sha256']);save(b/'DEPLOYED_METRIC_INPUTS.json',meta)
 item=dict(id=m['canonical_id'],role='generated',file=str(b/'score.mp4'),sha256=t['score_sha256'],frames=49,pts_seconds=[i/8 for i in range(49)],generation_frame_indices=list(range(0,147,3)),generation_binding=dict(metric_inputs=bound(b/'DEPLOYED_METRIC_INPUTS.json'),release_mapping=bound(b/'DEPLOYED_MAPPING.json')))
 path=b/'DEPLOYED_TRACK_INPUTS.json';save(path,dict(inputs=[item]));return path

def track(c,m,role,gpu,out,check_only=False):
 if m['benchmark']=='IVEBench':
  sys.path.insert(0,str(ROOT/'runtime/ive/metric_runtime'));import run_tracks as run
  row=dict(pair_id=m['canonical_id'],selection_sha256=m['selection_sha256'],source_prepared_video=bound(c/'source_full.mp4'),source_score_video=bound(c/'source_score.mp4'),score_frame_indices=list(range(m['valid_frames'])),edited={x['role']:dict(score_video=bound(c/x['score_file']),full_video=bound(c/x['full_file']))for x in m['targets']})
  run.SELECTION_SHA=m['selection_sha256'];run.LITERATURE=ROOT/'runtime/ive'
  run.select_pair=lambda *a:(row,dict(input_protocol=dict(effective_frame_count=m['valid_frames'])))
  run.validate_source_row=lambda *a:validate_case(c,role)
  run.validate_edited_entry=lambda *a:validate_case(c,role)
  run.check_gpu=lambda g:resource_check(g,os.getpid())
  run.main(argparse.Namespace(input_manifest=str(c/'INPUTS.json'),selection=str(c/'INPUTS.json'),pair=m['canonical_id'],method=role,gpu_uuid=gpu,check_only=check_only,output=str(out),ffmpeg='ffmpeg',ffprobe='ffprobe'))
 else:
  sys.path.insert(0,str(ROOT/'runtime/flex'));import run_tracks as run
  manifest=flex_manifest(c,m,role);item=next(x for x in read(manifest)['inputs']if x['id']==m['canonical_id']);run.check_timebase(Path(item['file']))
  if role!='source':run.validate_generated_binding(item,Path(item['file']))
  if check_only:return
  run.check_gpu=lambda g:resource_check(g,os.getpid())
  sys.argv=['run_tracks','--input-manifest',str(manifest),'--case',m['canonical_id'],'--gpu-uuid',gpu,'--output',str(out)];run.main()

def main():
 p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--role',required=True);p.add_argument('--gpu');p.add_argument('--attempt');p.add_argument('--check-only',action='store_true');a=p.parse_args();verify_seal();c=case(a.case);m=validate_case(c,a.role)
 if a.check_only:
  if m['benchmark']=='FlexiAct':track(c,m,a.role,None,None,True)
  assert 'torch'not in sys.modules;print('CPU_BINDING_OK',a.case,a.role);return
 assert a.attempt and a.attempt.replace('_','').isalnum();assert a.gpu and os.environ.get('CUDA_VISIBLE_DEVICES')==a.gpu
 control=ROOT/'audit'/a.attempt/'controls'/a.case/a.role;control.mkdir(parents=True,exist_ok=False);out=ROOT/'audit'/a.attempt/'tracks'/a.case/a.role
 ready=dict(identity=identity(os.getpid()),input_sha256=sha(c/'INPUTS.json'),seal_sha256=sha(ROOT/'SEAL.json'),case=a.case,role=a.role,gpu=a.gpu,CUDA_started=False);save(control/'ready.json',ready);deadline=time.monotonic()+180
 while not(control/'go.json').exists():assert time.monotonic()<deadline;time.sleep(.2)
 assert read(control/'go.json')==ready and identity(os.getpid())==ready['identity'];verify_seal();track(c,m,a.role,a.gpu,out)
 r=read(out/'REPORT.json');assert r['passed'];save(out/'INPUT_BINDING.json',dict(case_input=bound(c/'INPUTS.json'),seal=bound(ROOT/'SEAL.json'),control=bound(control/'go.json'),report=bound(out/'REPORT.json')))
if __name__=='__main__':main()
