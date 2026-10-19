"""Common-support paired descriptive screen; never changes frozen lag endpoints."""
import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case',choices=['05','07'],required=True)
    p.add_argument('--tag',required=True)
    args=p.parse_args()
    root=Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')
    transfer=Path(str(root)+'_transfer0')
    if hashlib.sha256((root/'scripts/timing_metrics.py').read_bytes()).hexdigest()!='eebb6893896aca76276ae2e749b8cd44d6efa24ace1cc0fcbbcc9e17cd1b3d8e':
        raise ValueError('Frozen metrics changed')
    cfg=json.loads((root/'analysis/pose/TRANSFER_CPU_PLAN.json').read_text())['cases'][args.case]
    home=transfer/'analysis/pose/pilot'
    runs={}
    provenance={}
    for label,run in zip(['native','mass'],cfg['runs']):
        history=json.loads((home/f'{run}.history_provenance.json').read_text())
        if history['history_status']['status_str']!='success' or not history['history_status']['completed']:
            raise ValueError('Success history required; failure remains in formal inventory')
        pose=home/(Path(history['history_output']['filename']).stem+'.pose.json')
        if not pose.is_file():
            raise ValueError(f'Pose absent: {run}')
        runs[label]=pose
        provenance[label]={'history':history,'pose_sha256':hashlib.sha256(pose.read_bytes()).hexdigest()}
    # Segment splits are a posthoc whole-clip safety screen, not new lag endpoints.
    # For source05 they exactly retain the primary discovery screen's split.
    windows=[[0,140], *[list(map(int,s.split(':'))) for s in cfg['windows']]]
    if args.case=='05':
        windows += [[0,46],[47,67],[68,140],[112,140]]
    else:
        # Original source07 event54:69 maps to positional bins16:22, pixels52:72.
        windows += [[0,51],[52,72],[73,140],[112,140]]
    dest=transfer/'analysis/pose/pairs'/args.tag
    dest.mkdir(parents=True,exist_ok=False)
    summary={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'case':args.case,
             'status':'descriptive common-support screen; frozen lag endpoints separate',
             'windows':windows,'provenance':provenance,'thresholds':{}}
    spec=importlib.util.spec_from_file_location('full_support',root/'analysis/pose/full_support/run_full_support.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    for threshold in [.3,.5]:
        output=dest/f'common_support.threshold{threshold}.json'
        command=[sys.executable,str(root/'analysis/pose/compare_runs.py'),'--source',cfg['source'],
                 '--confidence',str(threshold),'--output',str(output)]
        for label,path in runs.items():command+=['--run',f'{label}={path}']
        for a,b in windows:command+=['--window',f'{a}:{b}']
        result=subprocess.run(command,capture_output=True,text=True)
        (dest/f'threshold{threshold}.log').write_text(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('Comparison failed; log retained')
        report=json.loads(output.read_text())
        module.svg_chart(report,output.with_suffix('.svg'))
        if args.case == '07':
            # The shared chart defaults to source05's 47:67 bin. Only correct
            # the decorative shading here; metric windows remain unchanged.
            svg = output.with_suffix('.svg')
            tree = ET.parse(svg)
            segments = {'#eeeeee': (0, 52), '#f5df9a': (52, 73),
                        '#f5f5f5': (73, 141)}
            for element in tree.getroot().iter():
                if element.tag.endswith('rect') and element.get('fill') in segments:
                    start, end = segments[element.get('fill')]
                    element.set('x', f'{70+start/140*1000:.2f}')
                    element.set('width', f'{min(end-start,140-start)/140*1000:.2f}')
            tree.write(svg, encoding='unicode')
        summary['thresholds'][str(threshold)]=[{k:v for k,v in row.items() if k!='runs'}|
               {'errors':{label:r['same_frame_error_on_common_support'] for label,r in row['runs'].items()}}
               for row in report['results'] if row['feature']=='arm_direction']
    (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'saved':str(dest),'thresholds':summary['thresholds']}))


if __name__=='__main__':main()
