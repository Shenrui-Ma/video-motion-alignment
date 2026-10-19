"""Exactly one CPU intake attempt; root runs the actual verifier separately."""
import argparse,json
from pathlib import Path
from bind_execution import bind
from collect import status,collect
from render import render,choose_font

def main():
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--ffmpeg',default='/opt/homebrew/bin/ffmpeg');p.add_argument('--ffprobe',default='/opt/homebrew/bin/ffprobe');p.add_argument('--font');p.add_argument('--output',type=Path,default=Path('/Users/researcher/Downloads/H3_R97_眼镜编辑_引导区间对照_20261019.html'));a=p.parse_args()
 binding=bind(a.attempt);s=status()
 if s['status']!='PASSED_GATE':print(json.dumps(s));return 3
 result={'binding':binding,'collection':collect(),'presentation':render(a.ffmpeg,a.ffprobe,choose_font(a.font),a.output)};print(json.dumps(result,ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
