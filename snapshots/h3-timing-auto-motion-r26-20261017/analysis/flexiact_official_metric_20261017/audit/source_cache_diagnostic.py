from pathlib import Path
import json,hashlib,time,torch
from score_pair import read_tracks
from metric_adapter import score_tracks
r=Path.cwd();torch.set_num_threads(1);rows=[]
for action in ['chest','crouch','fitness','one_leg','rotate']:
 folder=r/'audit/five_source_tracks/outputs/reference'/action
 tracks,report=read_tracks(folder,torch)
 started=time.monotonic();record,matrix=score_tracks(tracks,tracks)
 velocity=tracks[:,1:]-tracks[:,:-1]
 rows.append(dict(action=action,self_MF=record,zero_velocity_vectors=int((velocity.square().sum(-1)==0).sum()),total_velocity_vectors=3025*48,seconds=time.monotonic()-started,report_sha256=hashlib.sha256((folder/'REPORT.json').read_bytes()).hexdigest()))
out={'scope':'source-cache self-comparison sanity diagnostic; not H3 method performance','rows':rows,'cuda_initialized':torch.cuda.is_initialized()}
p=r/'audit/SOURCE_CACHE_DIAGNOSTIC.json';assert not p.exists();p.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');print(json.dumps(out,allow_nan=False))
