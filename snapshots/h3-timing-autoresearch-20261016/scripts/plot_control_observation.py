#!/usr/bin/env python3
"""Plot frozen discrete control settings and native x0 observability.

Uses existing Pillow and emits matching vector SVG; no packages installed, no GPU.
Unknown observations occupy a separately labelled non-numeric status strip.
"""
import argparse
import hashlib
import html
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

METRIC_SHA='eebb6893896aca76276ae2e749b8cd44d6efa24ace1cc0fcbbcc9e17cd1b3d8e'
WINDOW=[50,65]
CUTOFFS=('0.3','0.5')
COLORS=('#1675b8','#ca6a00')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition,message):
    if not condition:raise ValueError(message)


def collect(root):
    files=[]
    def read(path):
        p=root/path;value=json.loads(p.read_text())
        files.append({'path':str(path),'sha256':sha(p)})
        return value
    def final(run):
        rows=[]
        for cutoff in CUTOFFS:
            path=Path(f'analysis/pose/pilot/{run}_00001_.threshold{cutoff}.timing.json')
            data=read(path)
            require(data['measurement_script_sha256']==METRIC_SHA,'metric drift')
            require(data['confidence_threshold']==float(cutoff),'wrong confidence file')
            row=next(x for x in data['diagnostics'] if x['window']==WINDOW and x['feature']=='arm_direction')
            rows.append({'pose_score_cutoff':float(cutoff),'lag_video_frames':row['reliable_lag_frames'],
                         'flags':row.get('flags',[]),'same_frame_error':row['same_frame']['error'],
                         'best_error':row.get('best',{}).get('error'),'report_path':str(path)})
        return rows
    native=final('s05_full_seed1_native_x0')
    require(all(x['lag_video_frames'] is not None for x in native),'native final lag unknown')
    require(native[0]['lag_video_frames']==native[1]['lag_video_frames'],'native thresholds diverge: cannot draw one baseline')
    arms=[]
    for run in ('s05_full_seed1_mass_x0','s05_full_seed1_mass_late6_x0','s05_full_seed1_mass_late11_x0'):
        graph=read(Path('configs')/(run+'.json'));params=graph['50']['inputs']
        require((params['mode'],params['alpha'],params['radius'],params['time_offset'])==('mass_preserve',1.,0,0),'unexpected actuator')
        require([params['start_frame'],params['end_frame']]==WINDOW,'wrong video window')
        require([params['block_start'],params['block_end'],params['step_end']]==[0,50,20],'wrong extent')
        require(graph['6']['inputs']['noise_seed']==2026101311,'wrong discovery seed')
        rows=final(run)
        require(all(x['lag_video_frames'] is not None for x in rows),'a final lag is unknown; do not coerce to zero')
        arms.append({'run_id':run,'first_guided_call_one_based':params['step_start']+1,
                     'step_interval_zero_based_half_open':[params['step_start'],20],'results':rows})
    manifest=read(Path('audit/x0/s05_full_seed1_native_x0/manifest.json'))
    require(manifest['status']=='complete' and manifest['callback_count']==20,'incomplete native capture')
    observations=[]
    for checkpoint in ('x0_step005','x0_step010','x0_step015','x0_step019','sampler_final'):
        p=Path('analysis/pose/x0/s05_full_seed1_native_x0')/(checkpoint+'.observability.json');d=read(p)
        require(d['observer_sha256']==METRIC_SHA,'observer drift')
        require(d['edited_video']['container_frame_count']==141 and d['edited_video']['fps']==24,'geometry/fps drift')
        require(d['checkpoint']==checkpoint,'checkpoint identity mismatch')
        gate=d['observability']['50:65'];final_sample=checkpoint=='sampler_final'
        capture=manifest['final_sampler_result'] if final_sample else next(x for x in manifest['captures'] if x['file']==checkpoint+'.pt')
        step=capture['step_zero_based']
        require(capture['model_call_one_based']==step+1,'captured model-call label mismatch')
        observations.append({'checkpoint':checkpoint,'step_zero_based':step,
            'after_call_one_based':step+1,'sampler_final':final_sample,
            'gate_status':gate['status'],'direction_lags_video_frames':gate['direction_lags_by_threshold'],
            'wrist_lags_video_frames':gate['position_lags_by_threshold'],
            'reasons':gate['reasons'],'automatic_intervention_authorized':gate['automatic_intervention_authorized'],
            'sigma_video_at_model_call':None if final_sample else manifest['sigmas_video'][step],
            'report_path':str(p)})
    return {'schema':'h3-control-observation-figure-v1','source_case':'05 / Sam Altman',
        'seed':2026101311,'video_geometry':[1312,736],'fps':24,'source_video_frame_window_inclusive':WINDOW,
        'metric_sha256':METRIC_SHA,'pose_score_cutoffs':[.3,.5],'native_final':native,
        'fixed_mass_control':arms,'native_observations':observations,'source_files':files,
        'semantics':{'lag_unit':'physical video frames at 24 fps; positive = edited action later',
            'x_axis_unit':'denoiser/model call, one-based; not a video frame',
            'points':'discrete settings only; no fitted/interpolated trend or error bars',
            'horizontal_dodge':'paired markers offset by 7 screen pixels for visibility; not separate call times',
            'unknown':'null lag in a separate non-numeric status strip; never zero',
            'scope':'exploratory one discovery case/window/seed; no precise observability onset or complete control-observation gap',
            'score_cutoffs':'two raw pose-score thresholds, not confidence intervals',
            'final_sample':'after final Euler update; not an extra denoiser call'},
        'rendering':{'library':'existing Pillow + equivalent SVG primitives','gpu_used':False,
                     'new_dependencies':False,'width':1800,'height':1000}}


class Canvas:
    def __init__(self):
        self.image=Image.new('RGB',(1800,1000),'white');self.draw=ImageDraw.Draw(self.image)
        self.svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="1000" viewBox="0 0 1800 1000">',
                  '<rect width="1800" height="1000" fill="white"/>']
        self.fonts={}
    def font(self,size,bold=False):
        key=(size,bold)
        if key not in self.fonts:
            name='Arial Bold.ttf' if bold else 'Arial.ttf'
            p=Path('/System/Library/Fonts/Supplemental')/name
            if not p.exists():
                p=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
            self.fonts[key]=ImageFont.truetype(str(p),size)
        return self.fonts[key]
    def text(self,x,y,value,size=22,color='#243347',anchor='left',bold=False):
        value=str(value);f=self.font(size,bold);box=self.draw.textbbox((0,0),value,font=f)
        width=box[2]-box[0];offset=width/2 if anchor=='middle' else width if anchor=='right' else 0
        self.draw.text((x-offset,y),value,font=f,fill=color)
        svganchor={'left':'start','middle':'middle','right':'end'}[anchor]
        self.svg.append(f'<text x="{x}" y="{y+size*.84}" text-anchor="{svganchor}" font-family="Arial,DejaVu Sans,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{html.escape(value)}</text>')
    def line(self,x1,y1,x2,y2,color='#d9e0e8',width=1,dashed=False):
        if dashed:
            length=math.hypot(x2-x1,y2-y1)
            for t in range(0,int(length),16):
                a=t/length;b=min(t+9,length)/length
                self.draw.line((x1+(x2-x1)*a,y1+(y2-y1)*a,x1+(x2-x1)*b,y1+(y2-y1)*b),fill=color,width=width)
        else:self.draw.line((x1,y1,x2,y2),fill=color,width=width)
        self.svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"'+(' stroke-dasharray="9,7"' if dashed else '')+'/>')
    def rect(self,x,y,w,h,fill):
        self.draw.rectangle((x,y,x+w,y+h),fill=fill)
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"/>')
    def marker(self,x,y,index,hollow=False):
        color=COLORS[index];r=7;fill='white' if hollow else color
        if index==0:
            self.draw.ellipse((x-r,y-r,x+r,y+r),fill=fill,outline=color,width=3)
            self.svg.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{color}" stroke-width="3"/>')
        else:
            points=[(x,y-r-1),(x+r+1,y),(x,y+r+1),(x-r-1,y)]
            self.draw.polygon(points,fill=fill,outline=color);self.draw.line(points+[points[0]],fill=color,width=3)
            self.svg.append(f'<polygon points="'+ ' '.join(f'{a},{b}' for a,b in points)+f'" fill="{fill}" stroke="{color}" stroke-width="3"/>')
    def save(self,png,svg):
        self.image.save(png,dpi=(180,180));Path(svg).write_text('\n'.join(self.svg+['</svg>'])+'\n')


def render(data,png,svg):
    c=Canvas();ink='#172b43';muted='#58677b'
    c.text(70,38,'Timing control and checkpoint observability',size=38,bold=True,color=ink)
    c.text(70,91,'One discovery case: source 05 / Sam Altman / seed 2026101311 / 1312 x 736 / 24 fps',size=23,color=muted)
    for i,cutoff in enumerate(CUTOFFS):
        x=1060+i*250;c.marker(x,139,i);c.text(x+18,126,f'Pose score cutoff {cutoff}',size=20)
    c.text(70,128,'Source-video window: frames 50-65 (zero-based, inclusive)',size=21)
    c.text(70,180,'a  Fixed same-frame mass routing',size=27,bold=True,color=ink)
    c.text(990,180,'b  Native x0 readout',size=27,bold=True,color=ink)
    xleft=(130,830);xright=(1040,1730);top,bottom=260,620
    def y(v):return bottom-v/15*(bottom-top)
    for span,label in [(xleft,'Final lag (video frames)'),(xright,'Observed lag (video frames)')]:
        c.text(span[0],226,label,size=20,color=muted)
        for tick in (0,3,6,9,12,15):
            yy=y(tick);c.line(span[0],yy,span[1],yy,color='#e5eaf0')
            c.text(span[0]-18,yy-12,tick,size=20,anchor='right',color=muted)
        c.line(span[0],top,span[0],bottom,color='#8190a1');c.line(span[0],bottom,span[1],bottom,color='#8190a1')
    native=data['native_final'][0]['lag_video_frames']
    c.line(*[xleft[0],y(native),xleft[1],y(native)],color='#79889a',width=2,dashed=True)
    c.text(xleft[0]+12,y(native)-31,f'Native baseline: +{native}',size=20,color=muted)
    for arm in data['fixed_mass_control']:
        call=arm['first_guided_call_one_based'];x=xleft[0]+65+(call-1)/11*(xleft[1]-xleft[0]-130)
        vals=[r['lag_video_frames'] for r in arm['results']]
        for i,v in enumerate(vals):c.marker(x+(-7 if i==0 else 7),y(v),i)
        c.text(x,y(max(vals))-(64 if max(vals)>10 else 39),' / '.join(str(v) for v in vals),size=23,anchor='middle',bold=True)
        c.text(x,636,str(call),size=23,anchor='middle')
    c.text(sum(xleft)/2,676,'First guided denoiser call (1-based)',size=22,anchor='middle')
    c.text(sum(xleft)/2,713,'Guidance remains ON through call 20.',size=20,anchor='middle',color=muted)
    c.text(sum(xleft)/2,746,'Only the three tested settings are shown.',size=20,anchor='middle',color=muted)
    # This strip has no lag coordinate. In particular, unknown is not drawn at 0.
    c.rect(xright[0],650,xright[1]-xright[0],49,'#f2f4f7')
    c.text(xright[0]+115,661,'Unknown / non-numeric status',size=18,color=muted)
    xs=[xright[0]+42+i*(xright[1]-xright[0]-78)/4 for i in range(5)]
    c.line((xs[3]+xs[4])/2,top,(xs[3]+xs[4])/2,620,color='#adb6c2',dashed=True)
    for x,obs in zip(xs,data['native_observations']):
        vals=obs['direction_lags_video_frames'];unknown=obs['gate_status']=='unknown_or_confounded'
        for i,v in enumerate(vals):
            if unknown or v is None:c.marker(x+(-7 if i==0 else 7),674,i,hollow=True)
            else:c.marker(x+(-7 if i==0 else 7),y(v),i)
        if not unknown:
            c.text(x,y(max(vals))-37,' / '.join(str(v) for v in vals),size=20,anchor='middle',bold=True)
        label='Final' if obs['sampler_final'] else str(obs['after_call_one_based'])
        c.text(x,712,label,size=22,anchor='middle')
        c.text(x,741,'sample' if obs['sampler_final'] else f"(step {obs['step_zero_based']})",size=17,anchor='middle',color=muted)
    c.text(sum(xright)/2,781,'Snapshot after denoiser call (1-based)',size=22,anchor='middle')
    c.line(70,829,1730,829,color='#d7dfe8')
    c.text(70,851,'Lag is measured in video frames; the x-axes index denoising calls. Positive lag means later motion.',size=22)
    c.text(70,890,'Unknown at call 6; the first passing sampled checkpoint is call 11. Intermediate calls were not observed.',size=21,color=muted)
    c.text(70,926,'Exploratory single-case evidence: no precise onset, continuous trend, or complete control-observation gap is established.',size=20,color=muted)
    c.text(70,960,'Two markers show pose-score cutoffs, not error bars. Final sample follows the last Euler update; it is not call 21.',size=18,color=muted)
    c.save(png,svg)


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);args=p.parse_args()
    root=args.root.resolve();data=collect(root);out=root/'review/control_observation'
    render(data,out.with_suffix('.png'),out.with_suffix('.svg'))
    data['rendering']['script_sha256']=sha(__file__)
    data['artifacts']={suffix:{'path':str(out.with_suffix(suffix).relative_to(root)),'sha256':sha(out.with_suffix(suffix))} for suffix in ('.png','.svg')}
    out.with_suffix('.json').write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'outputs':[str(out.with_suffix(s)) for s in ('.png','.svg','.json')],
        'control':[[r['lag_video_frames'] for r in a['results']] for a in data['fixed_mass_control']],
        'readout':[o['gate_status'] for o in data['native_observations']]},indent=2))

if __name__=='__main__':main()
