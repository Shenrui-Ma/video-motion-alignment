"""Bind an existing official score to a released identical score-domain input."""
import argparse, hashlib, json
from pathlib import Path
HERE=Path(__file__).resolve().parent
RUNTIME=Path('/data3/researcher/h3_runs/ivebench_official_metric_20261017')
FREEZE='d46b5c807c56aeb39e219e71271c7e5f050873ee74c5fe342988a3c1cb63dd45'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
def require(ok,message):
 if not ok:raise ValueError(message)
def bound(row):
 require(sha(row['file'])==row['sha256'],'bound content changed');return read(row['file'])
def compatible(auto,native,proof):
 require(auto['pair_id']==native['pair_id'],'pair differs')
 for key in ('source_original','source_prepared_video','source_score_video','source_preparation_record'):
  require(auto[key]['sha256']==native[key]['sha256'],'source binding differs')
 for key in ('score_frame_indices','input_to_original_frame'):require(auto[key]==native[key],'physical frame mapping differs')
 require(proof['runtime_freeze_sha256']==FREEZE and proof['same_physical_timebase'] and proof['comparison']['exact'] and not proof['cuda_initialized'],'official reader proof differs')
 require(proof['left']==native['edited']['native']['score_video'] and proof['right']==auto['edited']['auto']['score_video'],'proof input differs')
def main():
 p=argparse.ArgumentParser();p.add_argument('--pair',required=True);a=p.parse_args()
 summary=read(HERE/'media_identity'/a.pair/'SUMMARY.json');auto=bound(summary['auto_metric_inputs']);native=bound(summary['native_metric_inputs']);ready=bound(summary['case_ready'])
 require(ready['status']=='case_ready' and ready['summary']['passed'] and ready['metric_inputs_sha256']==summary['auto_metric_inputs']['sha256'],'release differs')
 proof=bound(summary['proofs']['score_video']);compatible(auto,native,proof)
 freeze=RUNTIME/'RUNTIME_FREEZE_HOST41.json';require(sha(freeze)==FREEZE,'runtime freeze differs')
 data=read(freeze)
 for item in data['files']:require(sha(RUNTIME/item['file'])==item['sha256'],'runtime member changed')
 checkpoint=data['checkpoint'];require(sha(RUNTIME/checkpoint['file'])==checkpoint['sha256'],'checkpoint changed')
 cached_path=RUNTIME/'scores/native'/(a.pair+'.json');score=read(cached_path)
 source=bound(score['source_report']);target=bound(score['target_report'])
 require(score['pair_id']==a.pair and score['method']=='native' and target['input_manifest']==summary['native_metric_inputs'],'cached input differs')
 require(target['score_video']==native['edited']['native']['score_video'] and target['source_score_sha256']==auto['source_score_video']['sha256'],'cached video differs')
 require(target['source_prepared_sha256']==auto['source_prepared_video']['sha256'] and target['score_frame_indices']==auto['score_frame_indices'],'cached source/time differs')
 require(source['score_video']['sha256']==auto['source_score_video']['sha256'],'source tracker differs')
 for role,report in [('source',source),('target',target)]:
  require(report['checkpoint_sha256']==checkpoint['sha256']==score['checkpoint_sha256'] and report['vendor']==score['official_vendor'],'tracker settings differ')
  path=Path(score[role+'_report']['file']).parent/'tracks.npz';require(sha(path)==score[role+'_tracks_sha256']==report['tracks_sha256'],'cached tracks changed')
  require(report['tracker']=={'grid_size':10,'grid_query_frame':0,'backward_tracking':False,'offline':True,'window_len':60},'tracker configuration differs')
 record={'schema':'official-mf-reused-identical-input-v1','pair_id':a.pair,'method':'auto','motion_fidelity':score['motion_fidelity'],'status':'reused_identical_input','new_tracker_invocations':0,'partial_batch':True,'planned_denominator':5,'runtime_freeze_sha256':FREEZE,'official_vendor':score['official_vendor'],'checkpoint_sha256':checkpoint['sha256'],'auto_metric_inputs':summary['auto_metric_inputs'],'native_metric_inputs':summary['native_metric_inputs'],'release_evidence':summary['case_ready'],'score_input_identity_proof':summary['proofs']['score_video'],'full_video_identity_proof':summary['proofs']['full_video'],'cached_native_score':{'file':str(cached_path),'sha256':sha(cached_path),'json_pointer':'/motion_fidelity'},'source_report':score['source_report'],'target_report':score['target_report'],'source_tracks_sha256':score['source_tracks_sha256'],'target_tracks_sha256':score['target_tracks_sha256'],'interpretation':'This completed Auto result has identical official evaluation input to Native; the score is reused with no new tracker computation.'}
 out=HERE/'media_identity'/a.pair/'REUSED_MF_SCORE.json'
 with out.open('x') as f:json.dump(record,f,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps({'file':str(out),'sha256':sha(out),'motion_fidelity':record['motion_fidelity'],'status':record['status']}))
if __name__=='__main__':main()
