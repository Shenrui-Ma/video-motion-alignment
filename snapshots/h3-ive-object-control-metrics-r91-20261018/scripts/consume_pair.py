"""Explicit one-shot CPU consumer: bind, collect, render and embed. No polling loop."""
import argparse
from common import *
import bind_execution,collect_pair,render_pair,make_showcase

def run(pair,attempt,output,ffmpeg='ffmpeg',ffprobe='ffprobe',font=None):
 validate_static();binding=ROOT/'audit/EXECUTION_BINDING.json'
 if not binding.exists():bind_execution.bind(attempt)
 require(read(binding)['attempt']==attempt,'existing intake belongs to a different attempt')
 state=collect_pair.status(pair);save(ROOT/'audit/status'/f'{pair}.json',{k:v for k,v in state.items() if k not in ('gate','binding')},replace=True)
 if state['status']!='PASSED_GATE':return {'pair':pair,'status':state['status'],'GPU_started':False}
 if not (ROOT/'incoming'/pair/'COLLECTION.json').exists():collect_pair.collect(pair)
 else:verify_intake(pair)
 if not (ROOT/'showcase'/pair/'PRESENTATION.json').exists():render_pair.render(pair,ffmpeg,ffprobe,render_pair.choose_font(font))
 return {'pair':pair,'status':'MEDIA_READY','showcase':make_showcase.build(output),'GPU_started':False}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--pair',choices=PAIRS,required=True);p.add_argument('--attempt',required=True);p.add_argument('--output',required=True);p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--ffprobe',default='ffprobe');p.add_argument('--font');a=p.parse_args()
 print(json.dumps(run(a.pair,a.attempt,a.output,a.ffmpeg,a.ffprobe,a.font)))
