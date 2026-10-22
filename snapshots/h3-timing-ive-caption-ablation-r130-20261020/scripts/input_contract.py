"""CPU geometry and source bindings for three source-preserving event tasks."""
import hashlib
import json
from fractions import Fraction
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCES=('long_0163',)
LENGTHS=((158, 144),)

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def read(p):return json.loads(Path(p).read_text())

def nearest_map(pts,count):
    pts=[Fraction(x) for x in pts]
    return [min(range(len(pts)),key=lambda k:(abs(pts[k]-Fraction(i,24)),k)) for i in range(count)]

def clip_nearest_map(pts,start,end,count):
    pts=[Fraction(x) for x in pts]
    if not 0<=start<=end<len(pts) or count<1:
        raise ValueError('Invalid clip indices/count')
    if any(a>=b for a,b in zip(pts,pts[1:])):
        raise ValueError('Source PTS must increase strictly')
    return [min(range(start,end+1),key=lambda k:(abs(pts[k]-(pts[start]+Fraction(i,24))),k)) for i in range(count)]

def clip_valid_count(start,end_exclusive):
    duration=(Fraction(end_exclusive)-Fraction(start))*24
    if duration<=0:raise ValueError('Nonpositive clip duration')
    return -(-duration.numerator//duration.denominator)

def latent_shape(t):
    return {'video':[1,24,((t-5)//17)*5+2,46,82],'audio':[1,32,2,round(t/24*40)]}

def route_bins(t,valid):
    count=latent_shape(t)['video'][2];spans=[(1,4,4,4,4)[i%5] for i in range(count)]
    cursor=0;stop=0
    for i,n in enumerate(spans):
        if cursor<valid:stop=i+1
        cursor+=n
    return {'latent_interval_half_open':[0,stop],'position_bin_coverage_inclusive':[0,sum(spans[:stop])-1],
            'total_latent_bins':count,'pure_pad_bins':list(range(stop,count))}
