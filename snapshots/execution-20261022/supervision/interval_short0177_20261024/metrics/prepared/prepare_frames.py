import argparse,json,hashlib,subprocess,shutil
from pathlib import Path
from metric_worker import atomic

def main(a):
    manifest=json.loads(Path(a.manifest).read_text())
    for job in manifest['jobs']:
        video=Path(job['video'])
        if not video.exists():continue
        target=Path(job['target_frames_parent'])/Path(job['metadata']['src_video_name']).stem
        receipt=target/'PREPARED.json'
        if receipt.exists() and json.loads(receipt.read_text()).get('sha256')==job['sha256'] and len(list(target.glob('*.png')))==job['valid_frames']:continue
        digest=hashlib.sha256(video.read_bytes()).hexdigest()
        if digest!=job['sha256']:raise ValueError('Video hash mismatch: '+str(video))
        temporary=target.with_name(target.name+'.partial')
        if temporary.exists():shutil.rmtree(temporary)
        temporary.mkdir(parents=True)
        x,y,w,h=job['crop_xywh'];vf=f'trim=end_frame={job["valid_frames"]},crop={w}:{h}:{x}:{y}'
        subprocess.run([a.ffmpeg,'-v','error','-threads','2','-i',str(video),'-vf',vf,'-vsync','0',str(temporary/'%06d.png')],check=True,timeout=600)
        if len(list(temporary.glob('*.png')))!=job['valid_frames']:raise ValueError('Unexpected frame count')
        atomic(temporary/'PREPARED.json',{'sha256':digest,'crop_xywh':job['crop_xywh'],'frames':job['valid_frames'],'fps':job['fps']})
        if target.exists():shutil.rmtree(target)
        temporary.rename(target);atomic(job['metadata_file'],[job['metadata']])
        print('prepared',job['id'],flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--ffmpeg',default='ffmpeg');main(p.parse_args())
