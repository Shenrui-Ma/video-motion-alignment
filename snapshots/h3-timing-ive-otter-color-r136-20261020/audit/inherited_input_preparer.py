"""Prepare three source-selected official inputs with the inherited R64 pixel transform."""
from pathlib import Path
import argparse
import fcntl
import hashlib
import json
import shutil
import os
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
SELECTION = ROOT/'design/INPUT_PLAN.json'
SELECTION_SHA = 'ad813e4685b68e9ed67ca4e1a28166f740534e94a23a8e1a9193700424233211'
FFMPEG = '/opt/homebrew/bin/ffmpeg'
FFPROBE = '/opt/homebrew/bin/ffprobe'
LOCK = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
WIDTH, HEIGHT, FPS = 1312, 736, 24
FRAME_BYTES = WIDTH * HEIGHT * 3 // 2

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def frame_hashes(raw):
    if len(raw) % FRAME_BYTES:
        raise ValueError('Incomplete decoded frame')
    return [hashlib.md5(raw[i:i+FRAME_BYTES]).hexdigest() for i in range(0,len(raw),FRAME_BYTES)]

def decode(path, transform=False):
    command = [FFMPEG,'-v','error','-threads','2','-i',str(path),'-an']
    if transform:
        command += ['-vf','scale=1280:720:flags=lanczos,pad=1312:736:16:8:black,setsar=1']
    command += ['-fps_mode','passthrough','-pix_fmt','yuv420p','-threads','2','-f','rawvideo','-']
    return subprocess.run(command,check=True,capture_output=True,timeout=90).stdout, command

def prepare(pair_id):
    if sha(SELECTION) != SELECTION_SHA:
        raise ValueError('Frozen source selection changed')
    selection = json.loads(SELECTION.read_text())
    row = next(r for r in selection['pairs'] if r['pair_id']==pair_id)
    source = Path(row['source']['file'])
    if sha(source) != row['source']['sha256']:
        raise ValueError('Original source changed')
    FRAMES = row['input_protocol']['h3_frame_count']
    mapping = row['input_protocol']['input_to_original_frame']
    effective = row['input_protocol']['effective_frame_count']
    if len(mapping)!=FRAMES or not 1<=effective<=FRAMES:
        raise ValueError('Unexpected frozen temporal geometry')
    for name in ['inputs','design','audit']:
        (ROOT/name).mkdir(parents=True,exist_ok=True)
    dest = ROOT/'inputs'/f'{pair_id}_video.mp4'
    if dest.exists():
        raise FileExistsError('Prepared source already exists; inspect its record')
    start=time.monotonic()
    raw, decode_command = decode(source,transform=True)
    hashes = frame_hashes(raw)
    if len(hashes)!=row['source']['frame_count']:
        raise ValueError('Decoded original count differs')
    selected=b''.join(raw[i*FRAME_BYTES:(i+1)*FRAME_BYTES] for i in mapping)
    command=[FFMPEG,'-v','error','-f','rawvideo','-pix_fmt','yuv420p','-s:v',f'{WIDTH}x{HEIGHT}',
             '-r',str(FPS),'-i','pipe:0','-an','-c:v','libx264','-crf','0','-preset','fast',
             '-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)]
    subprocess.run(command,input=selected,check=True,capture_output=True,timeout=90)
    decoded,_=decode(dest)
    actual_hashes=frame_hashes(decoded)
    if actual_hashes != [hashes[i] for i in mapping]:
        raise ValueError('Lossless encoded source differs from explicit mapped frames')
    probe=json.loads(subprocess.check_output([FFPROBE,'-v','error','-select_streams','v:0',
        '-show_frames','-show_streams','-of','json',str(dest)],text=True))
    if len(probe['frames'])!=FRAMES or any(abs(float(f['best_effort_timestamp_time'])-i/FPS)>1e-6 for i,f in enumerate(probe['frames'])):
        raise ValueError('Prepared timestamps differ from 24fps')
    original=ROOT/'inputs'/f'{pair_id}_original.mp4'
    os.link(source,original)
    prompt=ROOT/'inputs'/f'{pair_id}_prompt.txt'
    prompt.write_text(row['edit_prompt']+'\n')
    provenance=dict(schema='r136-ivebench-source-extension-input-v1',pair_id=pair_id,selection_file=str(SELECTION),
        selection_sha256=SELECTION_SHA,source_sha256=sha(original),video_sha256=sha(dest),
        prompt_sha256=sha(prompt),prompt=row['edit_prompt'],reference_images=[],geometry=[WIDTH,HEIGHT],
        content_rectangle_xywh=[16,8,1280,720],frames=FRAMES,fps=FPS,
        effective_frame_count=effective,evaluate_indices=list(range(effective)),
        original_pts=row['source']['actual_pts_s'],original_pts_rational=row['source']['actual_pts_rational'],clip=row['clip'],input_to_original_frame=mapping,
        prepared_pts=[i/FPS for i in range(FRAMES)],padding_indices=list(range(effective,FRAMES)),
        original_transformed_frame_md5=hashes,input_frame_md5=actual_hashes,
        decoded_pixel_mapping_exact=True,decode_command=decode_command,encode_command=command,
        seconds=time.monotonic()-start)
    record=ROOT/'inputs'/f'{pair_id}_provenance.json'
    record.write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'design'/f'{pair_id}_input_probe.json').write_text(json.dumps(probe,indent=2)+'\n')
    print(json.dumps(dict(pair_id=pair_id,frames=FRAMES,effective=effective,video_sha256=sha(dest),
        exact_frame_map=True,seconds=provenance['seconds'])),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('pair_id',choices=['all', 'short_0235']);args=parser.parse_args()
    with LOCK.open('r+') as lock:
        deadline = time.monotonic()+300
        while True:
            try:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Existing CPU evaluation lock remained busy')
                time.sleep(1)
        for name in (['short_0235'] if args.pair_id=='all' else [args.pair_id]):
            prepare(name)
