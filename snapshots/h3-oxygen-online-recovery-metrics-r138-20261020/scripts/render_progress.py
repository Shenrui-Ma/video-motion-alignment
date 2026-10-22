# CPU renderer copied from pinned R133 helper 9cd9cb658eb99076ce3d43ec5bbef2fdd712941c12ddcdc37abf3673a20da6ee; only generation boundary/title added.
"""CPU-only rendering of frozen observer values; no new motion estimate."""
from pathlib import Path
import argparse,json,hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();d=json.loads(a.input.read_text());rows=d['rows'];n=d['observed_completed_updates'];assert len(rows)==20
fig,(top,bottom)=plt.subplots(2,1,figsize=(11,6.2),sharex=True,gridspec_kw={'height_ratios':[1,1.25]})
for r in rows:
 if r['actual_ON']:
  for start,end in r['ON_frame_windows']:top.add_patch(Rectangle((r['step_1based']-.33,start),.66,end-start+1,color='#32689b',alpha=.85))
top.set_ylim(0,98);top.set_ylabel('ON physical frame window');top.set_title('Actual decisions before each denoising update')
bottom.axhspan(-2,2,color='#50a980',alpha=.18,label='within ±2 frames')
for key,style,color in [('0.3','o-','#245c8d'),('0.5','s--','#cc7426')]:
 y=[float('nan') if r['fixed_window_reliable_lags'][key] is None else r['fixed_window_reliable_lags'][key] for r in rows]
 bottom.plot(range(1,21),y,style,color=color,label='pose confidence ≥'+key,markersize=6 if key=='0.3' else 4,linewidth=1.6,markerfacecolor='none' if key=='0.5' else color)
bottom.axhline(0,color='.4',linewidth=.7);bottom.set_ylabel('Reliable lag (physical frames)');bottom.set_xlabel('Denoising step (1–20)');bottom.set_title(f"First-ON window {d['fixed_window_frames_inclusive']} / {d['fixed_feature']}; UNKNOWN remains a gap")
for ax in (top,bottom):
 ax.set_xlim(.5,20.5);ax.set_xticks(range(1,21));ax.grid(axis='x',alpha=.15)
 ax.axvline(d['recovery_break_after_step_1based']+.5,color='#9b3c47',linestyle=':')
 if d['partial']:ax.axvspan(n+.5,20.5,color='.9',alpha=.8);ax.axvline(n+.5,color='.35',linestyle=':')
bottom.legend(loc='upper right',fontsize=9)
fig.suptitle('R133 partial: interrupted after 9 completed updates; no final-video result' if d['partial'] else 'Actual control trace: R133 indices 0–8 | R138 indices 9–19',fontsize=12)
fig.text(.03,.015,'Measurements use the ordinary prediction before the current update. This trace does not establish final-video timing.',fontsize=9)
fig.tight_layout(rect=[0,.04,1,.95]);fig.savefig(a.output,dpi=150);plt.close(fig)
print(json.dumps({'output':str(a.output),'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest(),'matplotlib':matplotlib.__version__,'partial':d['partial']}))
