"""Descriptive aggregation only, no new threshold or policy choice."""
import argparse,collections,hashlib,json
from pathlib import Path
METHODS=('uniform_coarse','uniform_tight','confidence_completion_coarse','confidence_completion_tight')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def count(values):return dict(sorted(collections.Counter(values).items()))
def certified(status):return status.startswith('CERTIFIED_')

def summarize_case(result):
    rows=result['rows']
    if len(rows)!=186:raise ValueError('missing window/part rows')
    out={'case_id':result['case_id'],'run_id':result['run_id'],'endpoint':result['endpoint'],
         'denominator':186,'original_joint':count(r['original_joint_status'] for r in rows),
         'original_confidence_diagnostics':{},'methods':{}}
    for conf in ('0.3','0.5'):
        records=[r['confidence'][conf] for r in rows]
        out['original_confidence_diagnostics'][conf]={
          'diagnostic_status':count(v.get('original_diagnostic',{}).get('status',v.get('status','missing')) for v in records),
          'reliable_lag_present':sum(v.get('original_diagnostic',{}).get('reliable_lag_frames') is not None for v in records),
          'candidate_flags':count(flag for v in records for flag in v.get('proposal',{}).get('candidate_flags',[]))}
    for name in METHODS:
        status=count(r['joint'][name]['status'] for r in rows)
        transitions=count(r['original_joint_status']+' -> '+r['joint'][name]['status'] for r in rows)
        newly=[];removed=[];all_cert=[];null_reasons=[];joint_reasons=[];pairs=[]
        for r in rows:
            new=r['joint'][name];isnew=certified(new['status']);old=r['original_joint_status']
            joint_reasons.extend(new['reasons'])
            cs=[]
            for conf in ('0.3','0.5'):
                item=r['confidence'][conf].get('bounds',{}).get(name,{})
                for comp in item.get('comparisons',[]):
                    b=comp['bound'];null_reasons.extend(b.get('reasons',[]));pairs.append(b)
                    if 'common_coverage' in b:cs.append(b['common_coverage'])
            item={'window':r['window'],'feature':r['feature'],'old_status':old,
                  'new_status':new['status'],'candidate_lags':new['candidate_lags'],
                  'minimum_pairwise_coverage':min(cs) if cs else None}
            if isnew:all_cert.append(item)
            if isnew and old not in ('delayed_evidence','advanced_evidence'):newly.append(item)
            if not isnew and old in ('delayed_evidence','advanced_evidence'):removed.append(item)
        coverages=[b['common_coverage'] for b in pairs if 'common_coverage' in b]
        out['methods'][name]={'status_counts':status,'transitions':transitions,'certified_rows':all_cert,
             'newly_certified_rows':newly,'removed_original_evidence_rows':removed,
             'newly_certified_count':len(newly),'removed_count':len(removed),
             'certified_below_original_coverage_count':sum(x['minimum_pairwise_coverage'] is not None and x['minimum_pairwise_coverage']<.8 for x in all_cert),
             'newly_certified_below_original_coverage_count':sum(x['minimum_pairwise_coverage'] is not None and x['minimum_pairwise_coverage']<.8 for x in newly),
             'null_comparison_count':len(pairs),'possible_null_comparisons':186*2*5,
             'computed_common_support_count':len(coverages),
             'common_coverage_min_max':[min(coverages),max(coverages)] if coverages else None,
             'unknown_joint_reason_counts_overlapping':count(joint_reasons),
             'unknown_null_reason_counts_overlapping':count(null_reasons),
             'original_aligned_not_certified_count':sum(r['original_joint_status']=='aligned' and not certified(r['joint'][name]['status']) for r in rows)}
    return out

def run(directory):
    complete=json.loads((directory/'COMPLETE.json').read_text())
    if complete.get('complete') is not True:raise ValueError('batch incomplete')
    reports=[]
    for record in complete['results']:
        p=directory/Path(record['file']).name
        if sha(p)!=record['sha256']:raise ValueError('result SHA mismatch')
        reports.append(summarize_case(json.loads(p.read_text())))
    methods={}
    for name in METHODS:
        totals=collections.Counter();transitions=collections.Counter();reasons=collections.Counter()
        for r in reports:
            totals.update(r['methods'][name]['status_counts']);transitions.update(r['methods'][name]['transitions']);reasons.update(r['methods'][name]['unknown_joint_reason_counts_overlapping'])
        methods[name]={'status_counts':dict(totals),'transitions':dict(transitions),'unknown_reasons_overlapping':dict(reasons),
          'newly_certified':sum(r['methods'][name]['newly_certified_count'] for r in reports),
          'removed_original_evidence':sum(r['methods'][name]['removed_count'] for r in reports),
          'new_below_coverage':sum(r['methods'][name]['newly_certified_below_original_coverage_count'] for r in reports)}
    return {'complete_sha256':sha(directory/'COMPLETE.json'),'binding_sha256':complete['binding_sha256'],
            'protocol_sha256':complete['protocol_sha256'],'freeze_sha256':complete['freeze_sha256'],
            'cases':reports,'overall':{'independent_source_trajectories':len(reports),'window_part_denominator':186*len(reports),
              'confidence_rows':372*len(reports),'methods':methods},
            'limitations':['Overlapping windows/parts/confidences are not independent samples.',
              'UNKNOWN certificate status includes within-tolerance/no-action rows; see original_aligned_not_certified_count and reasons.',
              'Certificates are conditional on measured visible pose, compare only null[-2,2], and do not certify physical lag uniqueness.',
              'Uniform and confidence-completion are different estimands, not interchangeable versions of the old metric.',
              'No causal inference about continuing guidance or R27 index5 is supported.']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report=run(a.results)
    with a.output.open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps(report['overall'],ensure_ascii=False),flush=True)
