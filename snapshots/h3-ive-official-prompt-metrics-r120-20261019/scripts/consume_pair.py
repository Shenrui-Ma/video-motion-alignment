"""One explicit invocation: bind, check, collect, render, return. No polling."""
import argparse
from common import *
from bind_execution import bind
from full_frame_review import prepare as prepare_review
from metric_inputs import prepare as prepare_metrics
from collect_pair import status,collect
from render_pair import render,choose_font

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',choices=SOURCES,required=True);p.add_argument('--attempt',required=True);p.add_argument('--ffmpeg',default='/opt/homebrew/bin/ffmpeg');p.add_argument('--ffprobe',default='/opt/homebrew/bin/ffprobe');p.add_argument('--font');p.add_argument('--output',type=Path);a=p.parse_args()
 bind(a.attempt);s=status(a.source)
 if s['status']!='PASSED_GATE':print(json.dumps(s));return 3
 collected=collect(a.source);out=a.output or Path('/Users/researcher/Downloads')/f'H3_R120_{a.source}_固定时序引导对照_20261019.html';result=render(a.source,a.ffmpeg,a.ffprobe,choose_font(a.font),out)
 review=prepare_review(a.source,True,a.ffmpeg,a.ffprobe,a.font)
 metrics=prepare_metrics(a.source,paired=True)
 print(json.dumps({'review_frames':review,'metric_inputs':metrics,'status':'PAIRED_MEDIA_READY','source_id':a.source,'collection':collected,**result},ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
