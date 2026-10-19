"""Compare decoded RGB frames, not MP4 container metadata, with the historical baseline."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OLD=Path('/Users/researcher/DevProjects/h3-short-event-switching-20261013/outputs/06_anime_eye_insert_a_s2_00001_.mp4')
NEW=ROOT/'outputs/06_seed2_baseline_00001_.mp4'


def decoded_hashes(path):
    out=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-i',str(path),'-map','0:v:0',
        '-an','-pix_fmt','rgb24','-fps_mode','passthrough','-f','framemd5','-'],text=True)
    return [line.split(',')[-1].strip() for line in out.splitlines() if line and not line.startswith('#')]


if not NEW.exists():
    print(json.dumps({'status':'pending','missing':str(NEW)}))
else:
    a,b=decoded_hashes(OLD),decoded_hashes(NEW)
    assert len(a)==len(b)==141
    equal=[i for i,(x,y) in enumerate(zip(a,b)) if x==y]
    result={'status':'complete','old':str(OLD),'new':str(NEW),'old_file_sha256':hashlib.sha256(OLD.read_bytes()).hexdigest(),
        'new_file_sha256':hashlib.sha256(NEW.read_bytes()).hexdigest(),'frames':141,'identical_decoded_rgb_frames':equal,
        'identical_count':len(equal),'all_rgb_frames_identical':len(equal)==141,'old_rgb_frame_md5':a,'new_rgb_frame_md5':b,
        'scope':'displayed RGB pixel reproduction only, no claim of model-internal bitwise identity or audio equivalence'}
    (ROOT/'analysis/baseline_pixel_reproduction.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ['status','frames','identical_count','all_rgb_frames_identical']}))
