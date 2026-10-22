"""Combine completed method manifests only when every source binding matches."""
import argparse,copy,json
from pathlib import Path
from ive_mf_adapter import SELECTION_SHA,bound_file,read_json,sha

SOURCE_BINDINGS=('source_original','source_prepared_video','source_score_video','source_preparation_record')
TIME_FIELDS=('score_frame_indices','input_to_original_frame')

def merge(paths,selection_path):
    if sha(selection_path)!=SELECTION_SHA:raise ValueError('selection changed')
    expected={p['pair_id'] for p in read_json(selection_path)['pairs']}
    merged=None
    for path in paths:
        d=read_json(path)
        if d.get('schema')!='h3-ivebench-official-mf-inputs-v1' or d.get('selection_sha256')!=SELECTION_SHA:
            raise ValueError('manifest schema/selection mismatch')
        methods=d['methods'];rows=d['pairs']
        if not methods or len(set(methods))!=len(methods):raise ValueError('method names must be unique')
        if len(rows)!=5 or {r['pair_id'] for r in rows}!=expected:raise ValueError('all five frozen pairs required')
        for row in rows:
            if set(row['edited'])!=set(methods):raise ValueError('method outputs missing/extra')
            for key in SOURCE_BINDINGS:bound_file(row[key])
        if merged is None:
            merged=copy.deepcopy(d)
        else:
            if set(merged['methods'])&set(methods):raise ValueError('duplicate method name across manifests')
            by_id={r['pair_id']:r for r in merged['pairs']}
            for row in rows:
                old=by_id[row['pair_id']]
                for key in SOURCE_BINDINGS:
                    if old[key]['sha256']!=row[key]['sha256']:
                        raise ValueError('methods used different source binding: '+row['pair_id']+' '+key)
                for key in TIME_FIELDS:
                    if old[key]!=row[key]:raise ValueError('methods used different time samples: '+key)
                old['edited'].update(copy.deepcopy(row['edited']))
            merged['methods'].extend(methods)
    if merged is None:raise ValueError('at least one completed manifest required')
    merged['merged_from']=[{'file':str(Path(p).resolve()),'sha256':sha(p)} for p in paths]
    merged['status']='completed manifests merged; run official adapter --check-only before resource admission'
    return merged

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',nargs='+',required=True);p.add_argument('--selection',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    dest=Path(a.output)
    if dest.exists():raise FileExistsError('keep prior merged manifests immutable; use a new output path')
    dest.write_text(json.dumps(merge(a.inputs,a.selection),ensure_ascii=False,indent=2)+'\n')
