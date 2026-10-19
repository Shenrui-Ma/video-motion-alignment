"""CPU-only fixed source/R14/R22 frames55/86/105 and raw-speed clips, no retiming."""
from pathlib import Path
import hashlib,json,os,subprocess,time
RUN='r22_s05_seed1313_full6to11'
ROOT=Path('/data5/researcher/h3_runs/timing_normal_fixed_r22_20261016')
R14=Path('/data5/researcher/h3_runs/timing_native_screen_r14_host9_20261016')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def output_path(root,run):
    h=read(root/'logs'/f'{run}_history.json');g=h['prompt'][2]
    if h['status']['status_str']!='success' or not h['status']['completed']:raise ValueError('No actual successful output')
    items=[item for k,n in g.items() if n['class_type']=='SaveVideo' for item in h['outputs'].get(k,{}).get('images',[]) if item.get('type')=='output' and item['filename'].endswith('.mp4')]
    if len(items)!=1:raise ValueError('Unique actual MP4 required')
    p=root/'output'/items[0].get('subfolder','')/items[0]['filename']
    if not p.resolve().is_relative_to((root/'output').resolve()):raise ValueError('Unsafe MP4')
    return p

def main():
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import cv2
    cv2.setNumThreads(1)
    root=ROOT/'analysis/pose';out=root/'media';out.mkdir(exist_ok=True)
    b=read(root/'bundles'/f'{RUN}.json');gate=read(root/'replication'/f'{RUN}_integrity.json');assert gate['passed']
    edited=root/'raw'/b['relative_video'];assert sha(edited)==b['video_sha256']
    native=output_path(R14,'r14_s05_seed1313_native_host9')
    assert sha(native)=='44ba5631a7e04895c1ed87d4a593d3d0f7c314e7abef3106e7f21b5221ffd8f6'
    oldpose=R14/'analysis/pose/pilot'/(native.stem+'.pose.json');assert read(oldpose)['video']['sha256']==sha(native)
    source=ROOT/'inputs/05_real_megumi_v.mp4'
    assert sha(source)=='c80a126374966191cf87eebb8b8952d84fc88a7d6a56ca4c8be01a099ca2a857'
    videos=[source,native,edited];labels=['Reference','Native seed 1313','Full 6..11 seed 1313'];started=time.time()
    frames={};geometry={}
    for label,p in zip(labels,videos):
        cap=cv2.VideoCapture(str(p));images=[]
        while True:
            ok,frame=cap.read()
            if not ok:break
            images.append(frame)
        cap.release()
        if len(images)!=141:raise ValueError('Every display stream must have141 actual frames')
        frames[label]=images
        raw=subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=best_effort_timestamp_time,width,height','-of','json',str(p)],text=True)
        meta=json.loads(raw)['frames'];times=[float(x['best_effort_timestamp_time']) for x in meta]
        if len(times)!=141 or any(abs(t-times[0]-i/24)>1e-5 for i,t in enumerate(times)):raise ValueError('Raw physical frame time grid differs')
        geometry[label]={'path':str(p),'sha256':sha(p),'frames':141,'timestamps':times,'width':images[0].shape[1],'height':images[0].shape[0]}
        if p!=source and (images[0].shape[:2]!=(736,1312)):raise ValueError('Generated display geometry changed')
    import numpy as np
    def panel(image,label):
        h,w=image.shape[:2];scale=min(1312/w,736/h);a=cv2.resize(image,(round(w*scale),round(h*scale)))
        canvas=np.zeros((776,1312,3),dtype=np.uint8);y=(736-a.shape[0])//2;x=(1312-a.shape[1])//2;canvas[y:y+a.shape[0],x:x+a.shape[1]]=a
        cv2.putText(canvas,label,(20,765),cv2.FONT_HERSHEY_SIMPLEX,.7,(255,255,255),1,cv2.LINE_AA);return canvas
    for n in (55,86,105):
        canvas=np.concatenate([panel(frames[label][n],label) for label in labels],axis=1)
        if not cv2.imwrite(str(out/f'frame{n:03d}.png'),canvas):raise IOError('frame write failed')
    # Same frames and raw speed in all panels. Codec output is display-only.
    for name,start,end in [('full',0,141),('short_042_082',42,83)]:
        target=out/(name+'.mp4');cmd=['ffmpeg','-hide_banner','-loglevel','error','-y']
        for p in videos:cmd+=['-i',str(p)]
        filters=[]
        for i,label in enumerate(labels):
            filters.append(f'[{i}:v]trim=start_frame={start}:end_frame={end},setpts=PTS-STARTPTS,scale=1312:736:force_original_aspect_ratio=decrease,pad=1312:776:(ow-iw)/2:(736-ih)/2:black,drawtext=text={label}:x=20:y=752:fontsize=22:fontcolor=white[v{i}]')
        filters.append('[v0][v1][v2]hstack=inputs=3[v]')
        cmd+=['-filter_complex',';'.join(filters),'-map','[v]','-an','-c:v','libx264','-crf','18','-preset','fast','-threads','4','-filter_complex_threads','1','-pix_fmt','yuv420p',str(target)]
        done=subprocess.run(cmd,capture_output=True,text=True)
        (out/(name+'.ffmpeg.log')).write_text(done.stdout+'\n'+done.stderr)
        if done.returncode:raise RuntimeError('Comparison media failed; retain logs')
    result={'status':'complete','display_only':True,'source_and_raw':geometry,'frames':[55,86,105],'short_frames_inclusive':[42,82],'no_retiming':True,'no_interpolation':True,'R21':'not included until actual complete','CPU_seconds':time.time()-started,'files':{p.name:sha(p) for p in out.iterdir() if p.suffix in ('.png','.mp4')}}
    (out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
