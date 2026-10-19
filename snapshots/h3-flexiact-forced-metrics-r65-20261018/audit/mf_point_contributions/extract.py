"""Read already computed official MF tensors. Never import or call a tracker."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
os.environ['CUDA_VISIBLE_DEVICES']=''
import torch
torch.set_num_threads(2)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())

def run(root,out):
    sys.path.insert(0,str(root/'scripts'))
    from common import verify_runtime, cpu_lock
    sys.path.insert(0,str(root/'runtime/official_metric'))
    from metric_adapter import scoring_functions
    with cpu_lock():
        verify_runtime()
        scorer=scoring_functions()['get_score']
        methods={};scores={};coords={};rows={};bindings={}
        for method in ('native','forced'):
            score_dir=root/'scores'/method/'fitness'; track_dir=root/'tracks'/method/'fitness'
            score=read(score_dir/'SCORE.json'); report=read(track_dir/'REPORT.json')
            assert sha(score_dir/'similarity.pt')==score['similarity_sha256']
            assert sha(track_dir/'tracks.pt')==report['tracks_sha256']
            assert sha(track_dir/'REPORT.json')==score['edit_report_sha256']
            assert score['pair_id']=='human/fitness/000' and report['passed'] is True
            matrix=torch.load(score_dir/'similarity.pt',map_location='cpu',weights_only=True)['similarity_matrix']
            tracks=torch.load(track_dir/'tracks.pt',map_location='cpu',weights_only=True)['tracks']
            assert matrix.shape==(3025,3025) and tracks.shape==(3025,49,2)
            assert matrix.dtype==tracks.dtype==torch.float32 and torch.isfinite(matrix).all() and torch.isfinite(tracks).all()
            point,match=(matrix-torch.eye(3025)).max(dim=1)
            mean=point.mean().item(); official=scorer(matrix)['average_score']
            assert mean==official==score['score']
            scores[method]=point;coords[method]=tracks[:,0,:].clone()
            methods[method]={'mean':mean,'minimum_point_score':point.min().item(),'maximum_point_score':point.max().item(),'saved_score_exactly_reproduced':True}
            rows[method]={'xy':coords[method].tolist(),'point_score':point.tolist(),'matched_reference_point_index':match.tolist()}
            bindings[method]={str(p.relative_to(root)):sha(p) for p in (score_dir/'SCORE.json',score_dir/'similarity.pt',track_dir/'REPORT.json',track_dir/'tracks.pt')}
        delta=scores['forced']-scores['native']; distance=(coords['forced']-coords['native']).norm(dim=-1)
        result={'schema':'r65-fitness-official-mf-point-contributions-v1','methods':methods,'inputs':bindings,'rows':rows,'delta':delta.tolist(),
                'delta_mean_float32':delta.mean().item(),'difference_of_reported_means':methods['forced']['mean']-methods['native']['mean'],
                'initial_grid_coordinates_exactly_equal':torch.equal(coords['native'],coords['forced']),
                'initial_coordinate_max_distance_pixels':distance.max().item(),
                'delta_summary':{'positive_points':int((delta>0).sum()),'negative_points':int((delta<0).sum()),'zero_points':int((delta==0).sum()),'min':delta.min().item(),'max':delta.max().item(),'quantiles':torch.quantile(delta,torch.tensor([0.,.1,.25,.5,.75,.9,1.])).tolist()},
                'cuda_initialized':torch.cuda.is_initialized(),'tracker_calls':0,'foreground_mask':'unavailable; no semantic region fractions computed',
                'extractor_sha256':sha(Path(__file__))}
        assert result['cuda_initialized'] is False
        with out.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
        print(json.dumps({k:v for k,v in result.items() if k not in ('rows','delta')},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.root,a.output)
