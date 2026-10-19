from pathlib import Path
import sys,json,hashlib,time
B=Path('/Users/researcher/DevProjects/h3-ivebench-expanded-metrics-r73-20261018')
sys.path.insert(0,str(B/'scripts'))
import common,bindings
out=[]
missing=json.loads((Path(__file__).parent/'MISSING_MF.json').read_text())
for key in ('short_0035','short_0135'):
 row=common.read(B/'prepared'/key/'SOURCE_INPUTS.json'); expected=common.entry(key)
 bindings.validate_source_row(row,expected,'/opt/homebrew/bin/ffprobe','/opt/homebrew/bin/ffmpeg')
 rp=B/'tracks/source'/key/'attempt1/REPORT.json';r=common.read(rp);t=rp.parent/'tracks.npz'
 assert r['passed'] and r['method']=='source' and r['pair_id']==key
 assert common.sha(t)==r['tracks_sha256']
 assert r['source_prepared_sha256']==row['source_prepared_video']['sha256']
 assert r['source_score_sha256']==row['source_score_video']['sha256']
 assert r['score_frame_indices']==row['score_frame_indices']
 assert r['decoded_frame_md5']==bindings.official.frame_hashes(Path(row['source_score_video']['file']),'/opt/homebrew/bin/ffmpeg')
 assert r['official_commit']=='2dcf8900ee65197f43854c76f61c66a32bb8dbfc'
 assert r['checkpoint_sha256']=='da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df'
 assert r['tracker']==dict(grid_size=10,grid_query_frame=0,backward_tracking=False,offline=True,window_len=60)
 visible=next(x for x in missing['current_missing'] if x['id']=='r73_'+key)
 assert common.sha(visible['existing_videos']['reference_video_path'])==row['source_prepared_video']['sha256']
 out.append(dict(id='r73_'+key,passed=True,cache_scope='source_only',report=common.bound(rp),tracks=common.bound(t),source_inputs=common.bound(B/'prepared'/key/'SOURCE_INPUTS.json'),effective_frames=len(row['score_frame_indices']),official_commit=r['official_commit'],checkpoint_sha256=r['checkpoint_sha256'],tracker=r['tracker'],decoded_pixels_and_current_source_equal=True,requires_new_tracks=['native','forced']))
p=Path(__file__).parent/'VERIFIED_SOURCE_CACHES.json';p.write_text(json.dumps(dict(created_unix=time.time(),entries=out,new_GPU=False),ensure_ascii=False,indent=2)+'\n');print(str(p),common.sha(p))
