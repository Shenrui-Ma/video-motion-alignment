import av,json,hashlib,sys
from pathlib import Path
p=Path(sys.argv[1])/'inputs/long_0039_video.mp4'
c=av.open(str(p));s=c.streams.video[0];s.thread_type='AUTO'
rows=[]
for i,f in enumerate(c.decode(s)):
 rows.append({'index':i,'pts':f.pts,'time_base':str(f.time_base),'width':f.width,'height':f.height,'format':f.format.name,'colorspace':f.colorspace,'color_range':f.color_range,'yuv_array_sha':hashlib.sha256(f.to_ndarray(format='yuv420p').tobytes()).hexdigest()})
print(json.dumps({'frames':rows,'library_versions':av.library_versions,'av_version':av.__version__}))
