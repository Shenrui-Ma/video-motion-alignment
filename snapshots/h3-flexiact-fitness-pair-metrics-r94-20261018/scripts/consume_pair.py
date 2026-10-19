"""One explicit CPU invocation. No polling, verifier, queue or GPU action."""
import argparse
from common import *
from bind_execution import bind
from collect_pair import status,collect
from render_pair import render,choose_font
from make_showcase import build

def consume(attempt,output,ffmpeg,ffprobe,font):
 pair=PAIRS[0];bind(attempt);observed=status(pair)
 if observed['status']!='PASSED_GATE':return {'status':observed['status'],'detail':observed},3
 collected=collect(pair)
 if not (ROOT/'showcase'/pair/'PRESENTATION.json').exists():render(pair,ffmpeg,ffprobe,font)
 result=build(output)
 return {'status':'PAIRED_MEDIA_READY','pair':pair,'collection':collected,**result},0

def main():
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--ffmpeg',default='/opt/homebrew/bin/ffmpeg');p.add_argument('--ffprobe',default='/opt/homebrew/bin/ffprobe');p.add_argument('--font');p.add_argument('--output',default='/Users/researcher/Downloads/H3_FlexiAct_R94_fitness固定时序引导_20261018.html');a=p.parse_args()
 result,code=consume(a.attempt,a.output,a.ffmpeg,a.ffprobe,choose_font(a.font));print(json.dumps(result,ensure_ascii=False));return code
if __name__=='__main__':raise SystemExit(main())
