"""Torch-free audit CLI: python audit.py runtime.json (never mutates input)."""
import copy
import json
import math
from pathlib import Path
import sys
try:
    from .base_audit import check_field,require,close
except ImportError:
    from base_audit import check_field,require,close


def check_role5(doc):
    require(doc.get('schema')=='h3-temporal-gain-field-role5-v1','wrong role5 schema')
    expected_schedule={'steps':[0,9,19],'layers':[8,25,42]}
    require(all(doc.get('shadow_schedule',{}).get(k)==v for k,v in expected_schedule.items()),'shadow schedule')
    shadow_anchors={};shadow_calls=0;seams_checked=0
    for f in doc['feature_forward_summaries']:
        for row in f['layers']:
            bins=row['latent_bin_indices'];lo=bins[0];hi=bins[-1]+1;n=len(bins)
            require(bins==list(range(lo,hi)),'bin coordinates')
            role5=[lo+5<=t<hi-5 for t in bins]
            require(row['role5_mask']==role5,'role5 interior mask')
            require(row['neighbor_previous']==[max(lo,t-(5 if m else 1)) for t,m in zip(bins,role5)],'previous indices')
            require(row['neighbor_following']==[min(hi-1,t+(5 if m else 1)) for t,m in zip(bins,role5)],'following indices')
            expected=f['forward'] in (0,9,19) and row['block'] in (8,25,42) and n>=11
            require(('shadow' in row)==expected,'missing/unexpected shadow')
            require(row['shadow_attention_calls']==(2 if expected else 0),'shadow call count')
            require(row['attention_calls']==(7 if expected else 5),'total attention call count')
            if f['forward']==0:require(all(close(x,.25,1e-7) for x in row['alpha']),'first-step prior')
            seams=sorted({x for x in (lo+4,lo+5,hi-6,hi-5) if lo<=x<hi}) if n>=11 else []
            require(row['seam_bin_indices']==seams,'seam indices')
            require([x['bin'] for x in row['seam_statistics']]==seams,'seam records')
            for rec in row['seam_statistics']:
                j=rec['bin']-lo;require(rec['role5']==role5[j],'seam operator')
                require(close(rec['alpha'],row['alpha'][j],1e-9),'seam alpha')
                for key in ('temporal_energy','complement_energy','valid_probe_count','anchor_temporal',
                            'anchor_complement','normalized_temporal','fallback_to_prior'):
                    require(rec[key]==row['control'][key][j],'seam statistic '+key)
                seams_checked+=1
            if not expected:continue
            shadow_calls+=1;s=row['shadow']
            require(s['same_query_correction_mass_probes'] is True,'shadow shared-input contract')
            require(s['common_interior_half_open']==[lo+5,hi-5],'shadow comparison range')
            for key in ('temporal_energy','complement_energy','valid_probe_count','anchor_temporal',
                        'anchor_complement','anchor_step','usable_anchor','normalized_temporal','normalized_complement'):
                require(len(s[key])==n,'shadow vector '+key)
            for j,inside in enumerate(role5):
                A,B,count=(s[k][j] for k in ('temporal_energy','complement_energy','valid_probe_count'))
                require(all(math.isfinite(x) and x>=0 for x in (A,B,count)),'shadow finite statistics')
                if not inside:
                    require(A==B==count==0 and not s['usable_anchor'][j] and s['anchor_step'][j]==-1,'shadow outside common window')
                    continue
                key=(row['block'],bins[j]);pair=(s['anchor_temporal'][j],s['anchor_complement'][j],s['anchor_step'][j])
                if f['forward']==0:
                    if pair[2]==0:
                        require(pair[:2]==(A,B) and A>0 and B>0,'shadow wrong initial anchor')
                        shadow_anchors[key]=pair
                elif key in shadow_anchors:require(pair==shadow_anchors[key],'shadow anchor changed')
                else:require(pair[2]==-1 and not s['usable_anchor'][j],'shadow future anchor')
                if s['usable_anchor'][j]:
                    a,b=A/pair[0],B/pair[1];require(a+b>0,'shadow empty normalized energy')
                    require(close(s['normalized_temporal'][j],a/(a+b),1e-9),'shadow normalization')
                    require(close(s['normalized_temporal'][j]+s['normalized_complement'][j],1.,1e-9),'shadow share sum')
    # Explicit adapter into the unchanged existing field numerical contract.
    # Only the validated schema/call-count extension is normalized in a copy.
    base=copy.deepcopy(doc);base['schema']='h3-temporal-gain-field-v1'
    for f in base['feature_forward_summaries']:
        for row in f['layers']:row['attention_calls']=5
    result=check_field(base)
    result.update(schema=doc['schema'],shadow_calls=shadow_calls,additional_probe_attention_calls=2*shadow_calls,
                  seam_records_checked=seams_checked,shadow_anchors=len(shadow_anchors),input_modified=False)
    return result


if __name__=='__main__':
    print(json.dumps(check_role5(json.loads(Path(sys.argv[1]).read_text())),indent=2))
