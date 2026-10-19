import hashlib, json, os, subprocess, tempfile
from pathlib import Path

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
    return h.hexdigest()

def write(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,p)

def require(c,m):
    if not c: raise ValueError(m)

def tensor_signature(t):
    import torch
    require(t.device.type=='cpu' and t.is_contiguous(),'tensor CPU/contiguous')
    h=hashlib.sha256(); flat=t.reshape(-1)
    for c in flat.split(4*1024*1024):
        require(bool(torch.isfinite(c).all()),'tensor finite')
        h.update(c.view(torch.uint8).numpy().data)
    return {'shape':list(t.shape),'dtype':str(t.dtype),'sha256':h.hexdigest()}

def load_bound_tensor(p,expected):
    import torch
    t=torch.load(p,map_location='cpu',weights_only=True,mmap=True)
    require(isinstance(t,torch.Tensor),'plain Tensor expected')
    require(tensor_signature(t)=={k:expected[k] for k in ('shape','dtype','sha256')},'actual tensor signature')
    return t

def write_frames(frames,indices,fps,path,ffmpeg='ffmpeg'):
    import torch
    path=Path(path);require(not path.exists(),'new output required')
    indices=list(indices); h,w=frames.shape[1:3]
    cmd=[ffmpeg,'-v','error','-nostdin','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}','-r',str(fps),'-i','pipe:0','-an','-c:v','libx264rgb','-crf','0','-preset','fast','-threads','2','-pix_fmt','rgb24','-movflags','+faststart',str(path)]
    p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE);hashes=[]
    try:
        for i in indices:
            b=(frames[i]*255).clamp(0,255).byte().contiguous().numpy().tobytes()
            hashes.append(hashlib.sha256(b).hexdigest());p.stdin.write(b)
        p.stdin.close();err=p.stderr.read().decode();require(p.wait()==0,'encode failed '+err[-2000:])
    finally:
        if p.poll() is None:p.kill();p.wait()
        if p.stdin and not p.stdin.closed:p.stdin.close()
        p.stderr.close()
    # Full lossless decoded pixel check; no timestamps/frames silently dropped.
    q=subprocess.Popen([ffmpeg,'-v','error','-threads','2','-i',str(path),'-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    observed=[];n=h*w*3
    try:
        while True:
            b=q.stdout.read(n)
            if not b:break
            require(len(b)==n,'partial RGB frame');observed.append(hashlib.sha256(b).hexdigest())
        err=q.stderr.read().decode();require(q.wait()==0,'decode failed '+err[-2000:])
    finally:
        if q.poll() is None:q.kill();q.wait()
        q.stdout.close();q.stderr.close()
    require(observed==hashes,'lossless decoded RGB mismatch')
    return {'file':path.name,'sha256':sha(path),'frames':len(indices),'fps':fps,'width':w,'height':h,'selected_full158_indices':indices,'rgb24_frame_sha256':hashes,'lossless_pixel_verified':True}
