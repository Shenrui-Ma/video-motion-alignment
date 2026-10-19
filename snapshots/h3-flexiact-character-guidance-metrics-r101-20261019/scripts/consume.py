"""One bounded CPU intake/render invocation. No polling loop or GPU tools."""
import argparse,json
from collect import collect
from render import render,choose_font
from common import config
from metric_inputs import prepare
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--ffmpeg',default='/opt/homebrew/bin/ffmpeg');p.add_argument('--ffprobe',default='/opt/homebrew/bin/ffprobe');p.add_argument('--font');p.add_argument('--output');a=p.parse_args()
 receipt=collect(a.attempt)
 if receipt.get('status')=='PENDING_ACTUAL_GATE_OR_ROOT_EXIT':print(json.dumps(receipt));raise SystemExit(3)
 presentation=render(a.ffmpeg,a.ffprobe,choose_font(a.font),a.output or config()['default_output'])
 print(json.dumps({'presentation':presentation,'metric_inputs':prepare()},ensure_ascii=False,indent=2))
