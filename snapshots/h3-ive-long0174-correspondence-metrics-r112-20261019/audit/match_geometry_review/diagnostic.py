"""CPU correspondence diagnostic against cached source CoTracker observations."""
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
CONSUMER=ROOT.parents[1]
BASE=CONSUMER.parent/'h3-ive-followup-quantitative-r97-r99-r100-20261019/audit/recovery_20261019/r107_long_0174'
CACHE=BASE/'actual_host41/cases/r107_long_0174/tracks/source'
GEOMETRY={'content_wh':[1280,720],'input_wh':[1312,736],'pad_xy':[16,8],'grid_hw':[23,41],'patch_size':32}
THRESHOLDS=(16,32,64)
STATUS={'MATCHED':0,'UNMATCHED':1,'UNKNOWN_VISIBILITY':2,'UNKNOWN_NONFINITE':3,'UNKNOWN_OUTSIDE_CONTENT':4}
DTYPE=np.dtype([('block','i2'),('direction','i1'),('pair','i2'),('source_frame','i2'),('target_frame','i2'),
    ('track','i2'),('status','i1'),('source_cell','i4'),('target_cell','i4'),('region','i1'),
    ('source_x','f8'),('source_y','f8'),('target_x','f8'),('target_y','f8'),
    ('predicted_x','f8'),('predicted_y','f8'),('error_px','f8'),('identity_error_px','f8')])

def require(ok,msg):
    if not ok:raise ValueError(msg)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bound(p):return {'file':str(Path(p).resolve()),'sha256':sha(p)}
def save(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')

def spans(count=43):
    result=[];start=0
    for i in range(count):
        size=(1,4,4,4,4)[i%5];result.append((start,start+size-1));start+=size
    return result

def representative_frames(count=43):return [(a+b)//2 for a,b in spans(count)]

def point_cell(point,geometry=GEOMETRY):
    x,y=np.asarray(point,dtype=float)+geometry['pad_xy'];size=geometry['patch_size'];h,w=geometry['grid_hw']
    col,row=int(np.floor(x/size)),int(np.floor(y/size))
    require(0<=col<w and 0<=row<h,'source point outside padded token grid')
    return row*w+col

def center(cell,geometry=GEOMETRY):
    h,w=geometry['grid_hw'];size=geometry['patch_size'];require(0<=int(cell)<h*w,'bad matched token index')
    return np.array([(cell%w+.5)*size,(cell//w+.5)*size],dtype=float)

def transport(point,source_cell,target_cell,geometry=GEOMETRY):
    padded=np.asarray(point,dtype=float)+geometry['pad_xy']
    return center(target_cell,geometry)+padded-center(source_cell,geometry)-geometry['pad_xy']

def region_membership(point,frame,regions,track_id=None):
    if regions is None:return -1
    if regions.get('schema')=='source-only-manual-track-ids-v1':
        require(type(track_id) is int,'physical track ID required for fixed source subset')
        return int(track_id in regions['track_ids'])
    boxes=regions['frames'].get(str(frame))
    if boxes is None:return -1
    return int(any(x0<=point[0]<x1 and y0<=point[1]<y1 for x0,y0,x1,y1 in boxes))

def validate_regions(regions,binding):
    if regions is None:return
    require(regions['source_full_sha256']==binding['source_full']['sha256'] and regions['defined_from_source_only'] is True,
            'regions must bind source-only annotations')
    require(bool(regions.get('annotator')) and bool(regions.get('annotation_note')),'region authorship and source-only scope required')
    if regions['schema']=='source-only-manual-track-ids-v1':
        ids=regions['track_ids']
        require(regions['source_tracks_sha256']==binding['source_tracks']['sha256'] and regions['source_frame']==0,
                'fixed source track or initial frame binding differs')
        require(ids and all(type(i) is int and 0<=i<100 for i in ids) and ids==sorted(set(ids)),
                'unique sorted initial track IDs required')
        if 'groups' in regions:
            grouped_ids=[i for group in regions['groups'].values() for i in group]
            require(sorted(grouped_ids)==ids,'source groups must partition the fixed selected IDs')
        return
    require(regions['schema']=='source-only-manual-regions-v1' and regions['coordinate_space']=='content_1280x720', 'region coordinate system differs')
    for frame,boxes in regions['frames'].items():
        require(frame.isdigit() and 0<=int(frame)<145,'region physical frame outside valid support')
        for box in boxes:
            require(len(box)==4 and all(np.isfinite(x) for x in box),'invalid region box')
            x0,y0,x1,y1=box;require(0<=x0<x1<=1280 and 0<=y0<y1<=720,'region box outside content')


def evaluate_bank(tracks,visibility,forward,backward,frames,block,regions=None,geometry=GEOMETRY):
    """Keep every candidate track/adjacent-time pair, including wrong or missing matches."""
    tracks=np.asarray(tracks,dtype=np.float64);visibility=np.asarray(visibility);h,w=geometry['grid_hw'];cells=h*w
    require(tracks.ndim==3 and tracks.shape[-1]==2 and visibility.shape==tracks.shape[:2],'bad physical tracks')
    require(visibility.dtype==np.bool_,'use cached binary visibility without a new threshold')
    require(len(frames)>=2 and all(type(x)is int for x in frames) and all(0<=a<b<tracks.shape[0] for a,b in zip(frames,frames[1:])),'invalid physical representative frames')
    require(forward.shape==backward.shape==(len(frames)-1,cells),'bank/grid shape differs')
    require(np.issubdtype(forward.dtype,np.integer) and np.issubdtype(backward.dtype,np.integer),'bank indices must be integers')
    require(np.all((forward>=-1)&(forward<cells)) and np.all((backward>=-1)&(backward<cells)),'bank index out of bounds')
    count=(len(frames)-1)*tracks.shape[1]*2;rows=np.zeros(count,dtype=DTYPE)
    for key in ('source_cell','target_cell','region'):rows[key]=-1
    for key in ('predicted_x','predicted_y','error_px','identity_error_px'):rows[key]=np.nan
    n=0;cw,ch=geometry['content_wh']
    for direction,bank in [(1,forward),(-1,backward)]:
        for pair,(left,right) in enumerate(zip(frames,frames[1:])):
            a,b=(left,right) if direction==1 else (right,left)
            for point in range(tracks.shape[1]):
                row=rows[n];n+=1;src=tracks[a,point];dst=tracks[b,point]
                for key,value in [('block',block),('direction',direction),('pair',pair),('source_frame',a),('target_frame',b),('track',point),
                                  ('source_x',src[0]),('source_y',src[1]),('target_x',dst[0]),('target_y',dst[1])]:row[key]=value
                row['region']=region_membership(src,a,regions,point)
                if not(visibility[a,point] and visibility[b,point]):row['status']=STATUS['UNKNOWN_VISIBILITY'];continue
                if not(np.isfinite(src).all() and np.isfinite(dst).all()):row['status']=STATUS['UNKNOWN_NONFINITE'];continue
                if not(0<=src[0]<cw and 0<=src[1]<ch and 0<=dst[0]<cw and 0<=dst[1]<ch):row['status']=STATUS['UNKNOWN_OUTSIDE_CONTENT'];continue
                cell=point_cell(src,geometry);match=int(bank[pair,cell]);row['source_cell']=cell;row['target_cell']=match
                row['identity_error_px']=np.linalg.norm(dst-src)
                if match<0:row['status']=STATUS['UNMATCHED'];continue
                predicted=transport(src,cell,match,geometry);row['predicted_x'],row['predicted_y']=predicted
                row['error_px']=np.linalg.norm(predicted-dst);row['status']=STATUS['MATCHED']
    require(n==count,'candidate accounting mismatch')
    return rows


def summarize(rows):
    matched=rows['status']==STATUS['MATCHED'];unmatched=rows['status']==STATUS['UNMATCHED'];eligible=matched|unmatched
    counts={k:int(np.sum(rows['status']==v)) for k,v in STATUS.items()}
    require(sum(counts.values())==len(rows),'status counts must cover every candidate')
    def ratio(a,b):return float(a/b) if b else None
    n=int(eligible.sum());m=int(matched.sum());thresholds={}
    for threshold in THRESHOLDS:
        correct=int(np.sum(rows['error_px'][matched]<=threshold));identity_common=int(np.sum(rows['identity_error_px'][matched]<=threshold));identity_all=int(np.sum(rows['identity_error_px'][eligible]<=threshold))
        thresholds[str(threshold)]={'matched_correct':correct,'identity_correct_same_matched_points':identity_common,
            'identity_correct_all_eligible':identity_all,'PCK_matched':ratio(correct,m),'PCK_identity_same_matched_points':ratio(identity_common,m),
            'matched_correct_over_all_eligible':ratio(correct,n),'PCK_identity_all_eligible':ratio(identity_all,n)}
    return {'candidate_count':len(rows),'status_counts':counts,'eligible_visible_in_content':n,'matched_count':m,
        'matched_coverage':ratio(m,n),'PCK_threshold_pixels':thresholds,
        'matched_endpoint_error_mean_px':float(np.mean(rows['error_px'][matched])) if m else None,
        'identity_endpoint_error_mean_same_matched_points_px':float(np.mean(rows['identity_error_px'][matched])) if m else None,
        'source_displacement_over_16px_count':int(np.sum(rows['identity_error_px'][eligible]>16))}


def grouped(rows,regions=None):
    result={'full_image':summarize(rows),'directions':{str(d):summarize(rows[rows['direction']==d]) for d in (1,-1)}}
    if regions is not None:
        result['foreground']={'status':'SOURCE_ONLY_MANUAL_ANNOTATION','summary':summarize(rows[rows['region']==1]),
            'unselected':summarize(rows[rows['region']==0]),'unannotated_frame_candidates':int(np.sum(rows['region']==-1)),
            'interpretation':'Fixed source-selected points; unselected points are not background ground truth.'}
        result['source_person_groups']={name:summarize(rows[np.isin(rows['track'],ids)]) for name,ids in regions.get('groups',{}).items()}
    else:result['foreground']={'status':'UNDEFINED_NO_SOURCE_ONLY_REGIONS','summary':None}
    result['per_block']={str(int(block)):summarize(rows[rows['block']==block]) for block in np.unique(rows['block'])}
    return result


def probe(p):
    return json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0',
        '-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(p)],text=True))

def frame_hashes(p,vf=None):
    cmd=['/opt/homebrew/bin/ffmpeg','-v','error','-threads','1','-i',str(p),'-an']
    if vf:cmd+=['-vf',vf]
    cmd+=['-threads','1','-f','framemd5','-']
    text=subprocess.check_output(cmd,text=True)
    return [line.rsplit(',',1)[1].strip() for line in text.splitlines() if line and not line.startswith('#')]

def verify_source():
    manifest=BASE/'cases/r107_long_0174/INPUTS.json';report_file=CACHE/'REPORT.json';tracks_file=CACHE/'tracks.npz'
    m=read(manifest);report=read(report_file);source=BASE/'cases/r107_long_0174'/m['roles']['source']['score_file'];full=BASE/'cases/r107_long_0174'/m['roles']['source']['full_file']
    require(sha(manifest)=='af5f75f62fdfee9d7ceb1f027b167c2860263056f3cc621403f061d31e2c6ed9','original MF manifest differs')
    require(sha(report_file)=='2abe45656b199d5784cacd92271b8d124e80d2b4aaeb91d1e0e53248bda7319a','original source report differs')
    require(sha(tracks_file)==report['tracks_sha256']=='f0eab428f603eddd3b99143346be02a6e9f43e720dd3c0714de8a251c457a1c8','original source tracks differ')
    require(sha(source)==report['source_score_sha256']==m['roles']['source']['score_sha256'] and
            sha(full)==report['source_prepared_sha256']==m['roles']['source']['full_sha256'],'source media bytes differ')
    require(report['passed'] is True and report['method']=='source' and report['effective_frame_count']==145
            and report['score_frame_indices']==list(range(145)) and m['crop_xywh']==[16,8,1280,720] and m['fps']==24,'source physical support differs')
    for p,count,wh in [(source,145,[1280,720]),(full,158,[1312,736])]:
        data=probe(p);require(len(data['streams'])==1,'one video stream required');st=data['streams'][0]
        require([st['width'],st['height']]==wh and st['avg_frame_rate']=='24/1' and len(data['frames'])==count,'source geometry differs')
        require(all(abs(float(x['best_effort_timestamp_time'])-i/24)<1e-6 for i,x in enumerate(data['frames'])),'physical frame timestamps differ')
    require(frame_hashes(source)==report['decoded_frame_md5']==frame_hashes(full,'crop=1280:720:16:8,trim=end_frame=145'),
            'source tracks do not bind the exact content crop pixels')
    with np.load(tracks_file,allow_pickle=False) as z:
        require(set(z.files)=={'tracks','visibility'} and z['tracks'].shape==(1,145,100,2) and z['visibility'].shape==(1,145,100),'source tracker shape differs')
        tracks=z['tracks'][0].copy();visibility=z['visibility'][0].copy()
    require(visibility.dtype==np.bool_,'cached binary visibility required')
    binding={'source_manifest':bound(manifest),'source_report':bound(report_file),'source_tracks':bound(tracks_file),
        'source_score':bound(source),'source_full':bound(full),'tracker':report['tracker'],'geometry':GEOMETRY,
        'physical_frame_indices':list(range(145)),'physical_seconds':[i/24 for i in range(145)],
        'bin_position_spans_inclusive':spans(),'representative_RGB_frames':representative_frames(),
        'interpretation':'CoTracker observations are diagnostic references, not manual ground truth. Position-bin representatives are a display convention, not exact VAE receptive fields.'}
    return tracks,visibility,binding


def run(output,incoming=None,region_file=None):
    output=Path(output);require(not output.exists(),'preserve previous diagnostic outputs')
    tracks,visibility,binding=verify_source();regions=read(region_file) if region_file else None;validate_regions(regions,binding)
    output.mkdir(parents=True);save(output/'SOURCE_BINDING.json',binding)
    frames=representative_frames();identity=np.tile(np.arange(943),(42,1));identity_rows=evaluate_bank(tracks,visibility,identity,identity,frames,-1,regions)
    result={'schema':'r112-source-correspondence-diagnostic-v1','source_binding':bound(output/'SOURCE_BINDING.json'),
        'metric_kind':'CPU CoTracker-reference PCK diagnostic; official MF unchanged','thresholds_px':THRESHOLDS,
        'sampling':'all100 original grid tracks at all42 adjacent representative-frame pairs, forward and backward separately',
        'geometry':GEOMETRY,'status_codes':STATUS,'identity_coordinate':grouped(identity_rows,regions),
        'regions':bound(region_file) if region_file else None,'banks':{},'status':'SOURCE_ONLY_READY_WAIT_ACTUAL_BANKS',
        'diagnostic_code':bound(Path(__file__)),
        'created_unix':time.time()}
    np.savez_compressed(output/'identity_points.npz',rows=identity_rows);result['identity_points']=bound(output/'identity_points.npz')
    if incoming is not None:
        sys.path.insert(0,str(CONSUMER/'scripts'));from common import verify_collection
        incoming=Path(incoming);verify_collection(incoming);pair=read(incoming/'PAIR_RUNTIME_GATE.json')
        result['actual_collection']=bound(incoming/'COLLECTION.json');result['pair_gate']=bound(incoming/'PAIR_RUNTIME_GATE.json')
        all_rows=[]
        for block in range(50):
            folder=incoming/'banks/matched_one_bin'/f'block_{block:02d}'
            with np.load(folder/'indices.npz',allow_pickle=False) as z:
                all_rows.append(evaluate_bank(tracks,visibility,z['forward'],z['backward'],frames,block,regions))
        rows=np.concatenate(all_rows);file=output/'shared_frozen_bank_points.npz';np.savez_compressed(file,rows=rows)
        result['banks']['shared_frozen_bank']={'points':bound(file),'summary':grouped(rows,regions),
            'paired_collection_sha256':pair['paired_bank_collection_sha256'],
            'interpretation':'The two runs store equal correspondence banks. PCK compares these shared matches with identity coordinates on the same accepted points; it does not score generated motion.'}
        result['status']='ACTUAL_BANK_GEOMETRY_DIAGNOSTIC_COMPLETE'
    save(output/'RESULT.json',result)
    require('torch' not in sys.modules,'CPU diagnostic imported torch unexpectedly')
    print(json.dumps({'path':str(output/'RESULT.json'),'sha256':sha(output/'RESULT.json'),'status':result['status'],
                      'identity':result['identity_coordinate']['full_image']},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--incoming');p.add_argument('--regions');a=p.parse_args();run(a.output,a.incoming,a.regions)
