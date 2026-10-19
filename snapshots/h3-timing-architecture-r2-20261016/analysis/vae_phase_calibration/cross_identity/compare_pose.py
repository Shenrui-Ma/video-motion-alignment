"""Read independent frozen pose only after latent readouts have been saved."""
import csv
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
OLD=HERE.parents[3]/'h3-timing-autoresearch-20261016'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def direction(lag):
    if lag is None:return None
    return 'near_zero' if abs(lag)<=2 else ('delayed' if lag>0 else 'advanced')


def compact(d):
    def thin(k):
        value=d.get(k)
        if value is None:return None
        return {f:value.get(f) for f in ('lag_frames','error','coverage','valid_frame_count')}
    return dict(status=d['status'],flags=d.get('flags'),reliable_lag_frames=d.get('reliable_lag_frames'),
                same_frame=thin('same_frame'),best=thin('best'),unqualified_best=thin('unqualified_best'))


def main():
    # This report must never be imported by the latent scoring stage.
    result=json.loads((HERE/'RESULTS.json').read_text())
    protocol=json.loads((HERE/'PROTOCOL.json').read_text())
    poses={};inputs={};rows=[]
    for source,entry in result['sources'].items():
        for run,values in entry['runs'].items():
            mode,checkpoint=run.split('/')
            key=(source,run)
            if checkpoint=='sampler_final':
                all_windows={}
                for threshold in ('0.3','0.5'):
                    path=OLD/'analysis/pose/pilot'/f's{source}_full_seed1_{mode}_x0_00001_.threshold{threshold}.timing.json'
                    p=json.loads(path.read_text());inputs[str(path)]=sha(path)
                    for d in p['diagnostics']:
                        window=':'.join(map(str,d['window']))
                        all_windows.setdefault(window,{}).setdefault(threshold,{})[d['feature']]=compact(d)
                poses[key]=dict(stage='final_mp4_frozen_pose',diagnostics=all_windows,observability=None)
            else:
                path=OLD/'analysis/pose/x0'/f's{source}_full_seed1_{mode}_x0'/(checkpoint+'.observability.json')
                p=json.loads(path.read_text());inputs[str(path)]=sha(path)
                poses[key]=dict(stage='same_checkpoint_offline_x0_decode',
                                diagnostics={w:{th:{f:compact(d) for f,d in features.items()} for th,features in levels.items()} for w,levels in p['diagnostics'].items()},
                                observability=p['observability'])
            for region,methods in values['regions'].items():
                for method,details in methods.items():
                    for row in details['rows']:
                        window=':'.join(map(str,row['window_inclusive']))
                        pose=poses[key]['diagnostics'][window]
                        lags=[pose[th]['arm_direction']['reliable_lag_frames'] for th in ('0.3','0.5')]
                        lag=row['best']['lag_frames'] if row['best'] else None
                        agreement=all(v is not None for v in lags) and abs(lags[0]-lags[1])<=2
                        observation=poses[key]['observability'][window] if poses[key]['observability'] else None
                        strict=agreement if checkpoint=='sampler_final' else bool(observation and observation['status']!='unknown_or_confounded')
                        comparisons=[]
                        for th,pl in zip(('0.3','0.5'),lags):
                            comparisons.append(dict(threshold=th,pose_lag=pl,
                                absolute_error=None if pl is None or lag is None else abs(pl-lag),
                                within2=None if pl is None else bool(row['accepted'] and abs(pl-lag)<=2),
                                coarse_direction_agrees=None if pl is None else bool(row['accepted'] and direction(pl)==direction(lag)),
                                false_nonzero_on_pose_near_zero=None if pl is None else bool(row['accepted'] and abs(pl)<=2 and abs(lag)>2)))
                        rows.append(dict(source=source,run=run,region=region,method=method,window=row['window_inclusive'],
                            latent_lag=lag,latent_accepted=row['accepted'],rejection_reasons=row['rejection_reasons'],
                            score=row['best']['signed_cosine_error'] if row['best'] else None,
                            margin=row['margin'],clamped_frames=row['best']['clamped_frames'] if row['best'] else None,
                            at_search_boundary=abs(lag)==24 if lag is not None else None,
                            pose_stage=poses[key]['stage'],pose=pose,same_checkpoint_observability=observation,
                            pose_direction_two_threshold_agreement=agreement,strict_pose_available=strict,
                            strict_within2=(row['accepted'] and all(c['within2'] for c in comparisons)) if strict else None,
                            comparisons=comparisons))
    summary={}
    for region in protocol['regions']:
        summary[region]={}
        for method in protocol['methods']:
            group=[r for r in rows if r['region']==region and r['method']==method]
            splits={}
            for stage in ('final','intermediate'):
                subset=[r for r in group if (r['run'].endswith('/sampler_final'))==(stage=='final')]
                available=[r for r in subset if r['strict_pose_available']]
                known=[c for r in subset for c in r['comparisons'] if c['pose_lag'] is not None]
                low=[c for c in known if abs(c['pose_lag'])<=2]
                splits[stage]=dict(total_windows=len(subset),latent_accepted=sum(r['latent_accepted'] for r in subset),
                    strict_pose_available=len(available),strict_within2=sum(r['strict_within2'] for r in available),
                    strict_pose_unavailable=len(subset)-len(available),
                    known_threshold_cells=len(known),known_threshold_within2=sum(c['within2'] for c in known),
                    known_low_lag_threshold_cells=len(low),false_nonzero_on_known_low_lag=sum(c['false_nonzero_on_pose_near_zero'] for c in low))
            summary[region][method]=splits
    output=dict(schema='h3-phase-observer-independent-pose-comparison-v1',
        latent_results_sha256=sha(HERE/'RESULTS.json'),protocol_sha256=sha(HERE/'PROTOCOL.json'),
        pose_inputs=inputs,rows=rows,summary=summary,
        scope='Old selected samples, exploratory. Threshold/window/ROI/methods unchanged. No new correctness label for unknown pose.',
        caveat='Final MP4 pose and offline x0 decoder pose can differ near confidence thresholds; final row uses original pilot MP4 table, intermediate uses matching x0 checkpoint.')
    with (HERE/'POSE_COMPARISON.json').open('x') as stream:
        json.dump(output,stream,indent=2,ensure_ascii=False,allow_nan=False);stream.write('\n')
    with (HERE/'ALL_WINDOWS.csv').open('x',newline='') as stream:
        fields=['source','run','region','method','window','latent_lag','latent_accepted','rejection_reasons','margin','score','clamped_frames','at_search_boundary','pose03','pose05','pose03_status','pose05_status','strict_pose_available','strict_within2']
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in rows:
            item={k:row[k] for k in fields if k in row}
            item.update(pose03=row['comparisons'][0]['pose_lag'],pose05=row['comparisons'][1]['pose_lag'],
                        pose03_status=row['pose']['0.3']['arm_direction']['status'],pose05_status=row['pose']['0.5']['arm_direction']['status'])
            writer.writerow(item)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
