from pathlib import Path
import subprocess,importlib.util
D=Path(__file__).resolve().parent;E=D.parents[4]
spec=importlib.util.spec_from_file_location('v',E/'innovation/adaptive_strength_20261023/batch/prepare_visual.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
f=D/'native_event_frames';f.mkdir(exist_ok=True)
for lo,hi in [(10,25),(31,43),(73,86)]:
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(D/'temporal_gain_field.mp4'),'-vf',f'select=between(n\\,{lo}\\,{hi}),crop=1280:720:16:8','-fps_mode','vfr','-start_number',str(lo),'-q:v','2',str(f/'%03d.jpg')],check=True)
v.sheet(f,range(10,26),D/'lowering.jpg','field',crop=(0,100,750,650),cols=4,width=400)
v.sheet(f,range(31,44),D/'contact.jpg','field',crop=(90,125,660,520),cols=4,width=400)
v.sheet(f,range(73,87),D/'release.jpg','field',crop=(90,125,660,520),cols=4,width=400)
