import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
MEDIA=Path('/Users/researcher/Downloads/H3_后续实验对照_20261016')
manifest=json.loads((ROOT/'asset_manifest.json').read_text())
checks=[]
for key,item in manifest['cases'].items():
    for kind in ['normal','slow']:
        p=MEDIA/item['media'][kind]['file']
        d=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,avg_frame_rate,nb_read_frames,duration,codec_name','-of','json',str(p)]))['streams'][0]
        assert (d['width'],d['height'])==(1968,744),(key,d)
        assert int(d['nb_read_frames'])==(120 if kind=='normal' else 41),(key,d)
        assert d['avg_frame_rate']==('24/1' if kind=='normal' else '12/1'),(key,d)
        assert d['codec_name']=='h264'
        checks.append({'case':key,'kind':kind,**d})
(ROOT/'media_check.json').write_text(json.dumps({'status':'pass','streams':checks},indent=2))
print('14 embedded-matching video streams passed geometry, decoded frame count, rate and codec checks')
