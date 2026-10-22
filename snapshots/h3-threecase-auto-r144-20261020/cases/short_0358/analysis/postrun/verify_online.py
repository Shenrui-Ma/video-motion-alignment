"""CPU-only actual branch/pose/prefix/selected-Euler/video verification."""
import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions')]
from r86_contract import RUN,read,sha,require
from execution_gate import atomic

def check(receipt):
 receipt=Path(receipt).resolve();require(receipt.is_relative_to(ROOT/'audit'),'root exit receipt outside task')
 atomic(ROOT/'analysis/postrun/ROOT_EXIT_REFERENCE.json',{'file':str(receipt),'sha256':sha(receipt)})
 from verify_completed import check as verify
 result=verify(ROOT)
 audit=read(ROOT/'audit/counterfactual'/(RUN+'.json'))
 from adult_selector import adult_only
 raw_bound=[];timing=[]
 for m in audit['counterfactual']['measurements']:
  response=read(m['response_file']);filtered_path=Path(response['pose']['file']);raw_path=filtered_path.parent/'native.pose.json'
  expected,rejected=adult_only(read(raw_path),read(ROOT/'configs/protocol.json')['cases'][0]['geometry'],read(ROOT/'configs/protocol.json')['person_selection']['selected_bbox_center_x_fraction'])
  require(expected==read(filtered_path),'actual adult-selected pose differs from R81 source-specified selector')
  selection=read(filtered_path.parent/'adult_selection.json')
  require(selection['raw_pose_sha256']==sha(raw_path) and selection['filtered_pose_sha256']==sha(filtered_path) and selection['rejected_frames']==rejected,'raw/filtered pose binding differs')
  decode=read(response['decode']['file']);pose_complete=read(filtered_path.parent.parent/'pose_complete.json')
  timing.append({'index':m['physical_index'],'observer_total_seconds':response['wall_seconds'],'decoder_stage_seconds':response['decoder_stage_seconds'],'decoder_process_seconds':response['decoder']['wall_seconds'],'decode_including_load_and_encode_seconds':decode['finished_unix']-decode['started_unix'],'decoder_peak_reserved_bytes':decode['max_memory_reserved_bytes'],'pose_metric_seconds':pose_complete['pose_metric_seconds'],'CPU_lock_wait_seconds':pose_complete['lock_wait_seconds']})
  raw_bound.append({'index':m['physical_index'],'raw_sha256':sha(raw_path),'filtered_sha256':sha(filtered_path),'rejected_frames':rejected})
 history=read(ROOT/'logs'/(RUN+'_history.json'));outputs=history['outputs']['14']['images'];require(len(outputs)==1,'single actual video output expected')
 row=outputs[0];require(row['type']=='output','output type differs');video=(ROOT/'output'/row['subfolder']/row['filename']).resolve();require(video.is_relative_to(ROOT/'output') and video.is_file(),'actual output missing/outside task')
 info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,avg_frame_rate,nb_read_frames','-of','json',str(video)],text=True))['streams'][0]
 require([info[k] for k in ('width','height','avg_frame_rate','nb_read_frames')]==[1312,736,'24/1','107'],'actual output geometry/timebase differs')
 result.update(efficiency={'per_step':timing,'NFE':audit['counterfactual']['actual_model_nfe'],'model_seconds_synchronized':sum(x['model_seconds_synchronized'] for x in audit['counterfactual']['branches']),'observer_seconds':sum(x['observer_total_seconds'] for x in timing),'decoder_peak_reserved_bytes':max(x['decoder_peak_reserved_bytes'] for x in timing)},schema='r86-online-runtime-gate-v1',passed=True,raw_filtered_pose_binding=raw_bound,video={'file':str(video),'sha256':sha(video),'properties':info},valid_frames=105,spatial_selection=read(ROOT/'configs/protocol.json')['person_selection'],automatic_scope='online temporal window/start/stop',effectiveness='separate human/physical/MF evaluation required')
 atomic(ROOT/'analysis/postrun/ONLINE_RUNTIME_GATE.json',result)
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root-exit',required=True);a=p.parse_args();print(json.dumps(check(a.root_exit),indent=2))
