"""Keep original FlexiAct reference bytes separate from H3 conditioning media."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import bound, read, require, save, sha, validate_static
from render_native import media_info

config=validate_static()
rows={}
for case in config['sources']:
    provenance=read(ROOT/case['provenance']['file'])
    original=provenance.get('original_source')
    if original is None:
        source=provenance['official_source']
        original={'path':source['local_path'],'sha256':source['sha256'],
            'dataset_path':source['official_path'],
            'dataset_revision':source['pinned_url'].split('/resolve/')[1].split('/')[0]}
    path=Path(original['path'])
    require(path.is_file() and sha(path)==original['sha256'],'Original benchmark media differs')
    properties=media_info(path,'/opt/homebrew/bin/ffprobe')
    require((properties['width'],properties['height'],properties['count'],properties['avg_frame_rate'])==(720,480,49,'8/1'),'Original benchmark geometry differs')
    require(all(abs(t-i/8)<1e-6 for i,t in enumerate(properties['pts_s'])),'Original benchmark PTS differ')
    rows[case['source_id']]={
        'official_reference':{**bound(path),'properties':properties,'evaluate_indices':list(range(49))},
        'dataset_revision':original['dataset_revision'],'dataset_path':original['dataset_path'],
        'h3_conditioning_source':bound(ROOT/case['source']['file']),
        'generated_evaluation_indices':list(range(0,147,3)),
        'provenance':bound(ROOT/case['provenance']['file']),
    }
value={'schema':'r104-official-reference-bindings-v1','evaluation_fps':8,'cases':rows,
    'policy':'Official MF reads original benchmark reference indices0..48, and generated indices0,3,...144. Scaled 24fps H3 conditioning source is retained for inference/display provenance only. Bind this document together with the actual Native or paired MF_INPUTS manifest.',
    'score':None,'inference_output_required_for_scoring':True}
dest=ROOT/'prepared/OFFICIAL_REFERENCE_BINDINGS.json'
if dest.exists():require(read(dest)==value,'Existing original reference binding differs')
else:save(dest,value)
print(json.dumps(bound(dest)))
