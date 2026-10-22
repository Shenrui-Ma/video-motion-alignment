"""Prepare source media only, retaining the verified R120 pixel transform."""
from pathlib import Path
import fcntl, hashlib, importlib.util, json, subprocess, time

ROOT=Path(__file__).resolve().parent
PLAN=ROOT/'R122_SIX_SOURCE_INPUT_PLAN.json'
PLAN_SHA='6703130339dacc39586e6bf3b6881bcf0591853de6e712555a12dc0bd6d25e2d'
R120=ROOT.parent/'h3-timing-ive-official-prompt-r120-20261019/scripts/prepare_inputs.py'
H=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('verified_r120_input_transform',R120)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
OUT=ROOT/'prepared_media';OUT.mkdir(exist_ok=True)
assert H(PLAN)==PLAN_SHA
selection=json.loads(PLAN.read_text())
results=[]
with module.LOCK.open('r+') as lock:
    startwait=time.monotonic()
    while True:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
        except BlockingIOError:
            if time.monotonic()-startwait>300:raise TimeoutError('Shared CPU media lock occupied')
            time.sleep(1)
    for row in selection['pairs']:
        started=time.monotonic();sid=row['source_id'];source=Path(row['source']['file'])
        assert H(source)==row['source']['sha256']
        target=OUT/f'{sid}_video.mp4';provenance=OUT/f'{sid}_provenance.json'
        if target.exists() or provenance.exists():
            assert target.exists() and provenance.exists(), 'Incomplete prior preparation requires inspection'
            prior=json.loads(provenance.read_text());assert prior['selection_sha256']==PLAN_SHA and prior['video_sha256']==H(target)
            results.append({'source_id':sid,'file':str(target),'sha256':H(target),'provenance':str(provenance),'provenance_sha256':H(provenance),'reused':True})
            continue
        raw,decode_command=module.decode(source,transform=True)
        hashes=module.frame_hashes(raw);assert len(hashes)==row['source']['frame_count']
        mapping=row['input_protocol']['input_to_original_frame'];frames=row['input_protocol']['h3_frame_count'];effective=row['input_protocol']['effective_frame_count']
        assert len(mapping)==frames and 0<effective<=frames
        selected=b''.join(raw[i*module.FRAME_BYTES:(i+1)*module.FRAME_BYTES] for i in mapping)
        del raw
        command=[module.FFMPEG,'-v','error','-nostdin','-n','-f','rawvideo','-pix_fmt','yuv420p','-s:v','1312x736','-r','24','-i','pipe:0','-an','-c:v','libx264','-crf','0','-preset','fast','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(target)]
        subprocess.run(command,input=selected,check=True,capture_output=True,timeout=90)
        del selected
        decoded,_=module.decode(target);actual=module.frame_hashes(decoded);del decoded
        assert actual==[hashes[i] for i in mapping]
        probe=json.loads(subprocess.check_output([module.FFPROBE,'-v','error','-select_streams','v:0','-show_frames','-show_streams','-of','json',str(target)]))
        assert len(probe['frames'])==frames
        assert all(abs(float(f['best_effort_timestamp_time'])-i/24)<=1e-6 for i,f in enumerate(probe['frames']))
        record={'schema':'r122-source-only-media-provenance-v1','source_id':sid,'selection_file':str(PLAN),'selection_sha256':PLAN_SHA,'source_original_file':str(source),'source_sha256':H(source),'video_file':str(target),'video_sha256':H(target),'geometry':[1312,736],'content_rectangle_xywh':[16,8,1280,720],'frames':frames,'effective_frame_count':effective,'fps':24,'evaluate_indices':list(range(effective)),'padding_indices':list(range(effective,frames)),'clip':row['clip'],'input_to_original_frame':mapping,'original_pts_rational':row['source']['actual_pts_rational'],'original_transformed_frame_md5':hashes,'input_frame_md5':actual,'decoded_pixel_mapping_exact':True,'decode_command':decode_command,'encode_command':command,'inherited_transform_file':str(R120),'inherited_transform_sha256':H(R120),'official_edit_prompt':row['edit_prompt'],'actual_H3_prompt_status':'Not constructed; pending official Context-IR validation','reference_images':[],'seconds':time.monotonic()-started}
        provenance.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
        results.append({'source_id':sid,'file':str(target),'sha256':H(target),'provenance':str(provenance),'provenance_sha256':H(provenance),'valid_frames':effective,'total_frames':frames,'bytes':target.stat().st_size})
        print(json.dumps(results[-1]),flush=True)
receipt={'schema':'r122-six-source-cpu-media-v1','passed':len(results)==6,'prepared':results,'source_plan_sha256':PLAN_SHA,'new_original_copies':0,'GPU_started':False}
(ROOT/'CPU_MEDIA_READY.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print('READY',H(ROOT/'CPU_MEDIA_READY.json'),flush=True)
