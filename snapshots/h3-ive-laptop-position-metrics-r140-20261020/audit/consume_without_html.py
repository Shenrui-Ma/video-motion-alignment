"""Use the frozen collection/media checks while suppressing standalone HTML export."""
from pathlib import Path
import argparse, importlib, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['native','pair'],required=True);a,rest=p.parse_known_args()
renderer=importlib.import_module('render_native' if a.mode=='native' else 'render_pair')
assert callable(renderer.publish)
renderer.publish=lambda *args,**kwargs: {'skipped':True,'reason':'standalone HTML export paused; media and manifest retained'}
consumer=importlib.import_module('consume_native' if a.mode=='native' else 'consume_pair')
sys.argv=[sys.argv[0]]+rest
if __name__=='__main__':raise SystemExit(consumer.main())
