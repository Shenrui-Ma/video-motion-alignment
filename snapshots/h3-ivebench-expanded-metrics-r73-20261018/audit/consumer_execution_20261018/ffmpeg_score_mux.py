#!/usr/bin/python3
"""Serialize validated 24fps lossless score frames with explicit PTS; no pixel transform change."""
import json,os,subprocess,sys,time,uuid
from pathlib import Path
args=sys.argv[1:]
if '-c:v' in args and args[args.index('-c:v')+1]=='libx264' and args[-1].endswith('_score.mp4'):
    before=list(args)
    index=args.index('-vf')+1
    args[index]+=',setpts=N/(24*TB)'
    args[-1:-1]=['-bf','0']
    audit=Path(__file__).resolve().parent/'timestamp_recovery'
    audit.mkdir(exist_ok=True)
    with (audit/(uuid.uuid4().hex+'_encoding_command.json')).open('x') as h:
        json.dump({'original_arguments':before,'executed_arguments':args,'reason':'FFmpeg2.8 MP4 edit-list PTS drift; input validated at 24fps by frozen prepare; decoded pixels validated after encode'},h,indent=2)
sys.exit(subprocess.call(['/usr/bin/ffmpeg']+args))
