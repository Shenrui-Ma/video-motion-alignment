"""CPU-only synthetic track delays evaluated by unchanged official IVE MF."""
import hashlib,json,os,sys,time
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['PYTHONDONTWRITEBYTECODE']='1'
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'runtime/ive/metric_runtime'))
import ive_mf_adapter as official
import numpy as np
import torch
torch.set_num_threads(2)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bound(p):return {'file':str(p),'sha256':sha(p)}

def main():
    out=Path(__file__).parent/'RESULT.json';assert not out.exists()
    vendor=official.verify_vendor();cls=official.official_class();evaluator=cls.__new__(cls)
    results=[];sources=[]
    for source in ('short_0252','short_0358'):
        folder=ROOT/'cases'/source/'tracks/source';report_path=folder/'REPORT.json';track_path=folder/'tracks.npz'
        report=json.loads(report_path.read_text());original_hash=sha(track_path)
        assert original_hash==report['tracks_sha256'] and report['official_commit']==official.COMMIT
        with np.load(track_path,allow_pickle=False)as data:
            tracks=torch.from_numpy(data['tracks'].copy());visibility=torch.from_numpy(data['visibility'].copy())
        frames=report['effective_frame_count']
        assert tracks.shape==(1,frames,100,2) and visibility.shape==(1,frames,100)
        sources.append({'source_id':source,'report':bound(report_path),'tracks':bound(track_path),'frames':frames,'fps':24})
        for delay in (0,4,8,12,16):
            indices=torch.clamp(torch.arange(frames)-delay,min=0)
            delayed=tracks.index_select(1,indices);delayed_vis=visibility.index_select(1,indices)
            assert torch.equal(delayed[:,0],tracks[:,0]) and torch.equal(delayed_vis[:,0],visibility[:,0])
            if delay==0:assert torch.equal(delayed,tracks) and torch.equal(delayed_vis,visibility)
            else:assert torch.equal(delayed[:,delay:],tracks[:,:-delay]) and torch.equal(delayed_vis[:,delay:],visibility[:,:-delay])
            tick=time.monotonic();score=float(evaluator._compute_similarity_from_tracks(tracks,visibility,delayed,delayed_vis))
            assert np.isfinite(score)
            if delay==0:assert abs(score-1.0)<1e-12
            results.append({'source_id':source,'known_delay_frames':delay,'known_delay_seconds':delay/24,'official_MF':score,'CPU_score_seconds':time.monotonic()-tick})
        assert sha(track_path)==original_hash
    assert not torch.cuda.is_initialized()
    record={'passed':True,'scope':'Synthetic trajectory-level sensitivity check; no generated video or benchmark result',
            'processing':'At physical time t, use source track and visibility at max(0,t-delay). Repeat first position and first visibility for leading samples; trim trailing source samples. Keep original length and 24fps timebase.',
            'sources':sources,'official_vendor':vendor,'official_metric_source':bound(ROOT/'runtime/ive/official_source/metrics/fidelity/motion_fidelity.py'),
            'script':bound(__file__),'torch_version':torch.__version__,'CUDA_initialized':False,'original_tracks_unchanged':True,'results':results}
    out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    rows=['source_id,delay_frames,delay_seconds,official_MF']+[f"{x['source_id']},{x['known_delay_frames']},{x['known_delay_seconds']:.6f},{x['official_MF']:.12f}"for x in results]
    out.with_suffix('.csv').write_text('\n'.join(rows)+'\n')
    print(json.dumps({'result':bound(out),'rows':results},ensure_ascii=False))

if __name__=='__main__':main()
