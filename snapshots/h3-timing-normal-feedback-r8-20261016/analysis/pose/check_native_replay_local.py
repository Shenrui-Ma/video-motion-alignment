"""Read-only actual-input and decoded-RGB comparison; no model execution."""
from pathlib import Path
import hashlib
import json
import subprocess

HERE=Path(__file__).resolve().parent
OLD=Path('/Users/researcher/DevProjects/h3-timing-normal-replay-r7-20261016/analysis/pose')


def read(p):return json.loads(p.read_text())


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    out=HERE/'replication';out.mkdir(exist_ok=True)
    a=OLD/'pilot/r7_s05_normal_native_x0_provenance'
    b=HERE/'pilot/r8_s05_normal_feedback_provenance'
    manifest=read(b/'intake_manifest.json')
    conditions=[read(p/'conditioning.json') for p in (a,b)]
    noise=[read(p/'noise.json') for p in (a,b)]
    checks={key:conditions[0][key]==conditions[1][key] for key in
            ('prompt','input_video','native_vae_calls','qwen_presentation',
             'tokenization_before_vision_expansion','conditioning_embedding','token_tags','target_latent_shapes','packed_layout')}
    checks['pair_snapshot_actual']=conditions[0]['pair_snapshot']['actual']==conditions[1]['pair_snapshot']['actual']
    checks['actual_noise_streams']=noise[0]['actual_noise_streams']==noise[1]['actual_noise_streams']
    checks['noise_signature']=noise[0]['signature']==noise[1]['signature']
    videos=[OLD/'raw/r7_s05_normal_native_x0_00001_.mp4', HERE/'raw'/manifest['relative_video']]
    assert digest(videos[1])==manifest['video_sha256']
    frames=[];geometry=[]
    for label,video in zip(('r7_normal_native','r8_normal_feedback'),videos):
        target=out/(label+'.rgb.framehash')
        subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','1','-i',str(video),
                        '-map','0:v:0','-an','-pix_fmt','rgb24','-c:v','rawvideo','-threads','1',
                        '-f','framehash','-hash','sha256','-y',str(target)],check=True)
        rows=[line.split(',') for line in target.read_text().splitlines() if line and not line.startswith('#')]
        frames.append([tuple(piece.strip() for piece in row[1:]) for row in rows])
        probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0',
            '-show_entries','stream=width,height,r_frame_rate,avg_frame_rate,time_base,duration,nb_frames',
            '-of','json',str(video)],text=True))
        geometry.append(probe['streams'][0])
    checks['geometry_timebase']=geometry[0]==geometry[1]
    routers=[read(p/'router_audit.json') for p in (a,b)]
    checks['baseline_native_20x50']=routers[0]['mode']=='native' and routers[0]['completed_calls']==1000 and routers[0]['routed_calls']==0 and routers[0]['calls_by_forward']==[50]*20
    checks['feedback_all_off_20x50']=routers[1]['completed_calls']==1000 and routers[1]['routed_calls']==0 and routers[1]['routed_by_forward']==[0]*20 and routers[1]['calls_by_forward']==[50]*20
    checks['both_141_frames']=len(frames[0])==len(frames[1])==141
    checks['all_decoded_rgb_and_frame_timing_equal']=frames[0]==frames[1]
    result={'baseline_run':'r7_s05_normal_native_x0','new_run':'r8_s05_normal_feedback',
            'checks':checks,'passed':all(checks.values()),'geometry':geometry,
            'rgb_frame_counts':[len(x) for x in frames],
            'matching_rgb_frame_count':sum(x[-1]==y[-1] for x,y in zip(*frames)),
            'videos':[{'path':str(p),'sha256':digest(p)} for p in videos],
            'input_provenance_sha256':{str(p/name):digest(p/name) for p in (a,b) for name in ('conditioning.json','noise.json','history.json','config.json')},
            'scope':'Actual prepared inputs/noise, video geometry/timebase and all decoded RGB frames. Actual common x0 tensors and first-prefix equality are checked separately. This is a deliberately selected normal case, not an independent unseen example. Exact unchanged output does not establish correction efficacy.'}
    (out/'native_replay_local_gate.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':result['passed'],'checks':checks,'matching_rgb_frames':result['matching_rgb_frame_count']}))


if __name__=='__main__':main()
