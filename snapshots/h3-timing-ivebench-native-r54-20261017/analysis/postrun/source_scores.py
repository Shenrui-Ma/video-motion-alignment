"""Publish prepared90 source scoring crops before inference; shared CPU locks."""
import argparse
import fcntl
import json
from pathlib import Path
import time
import release_prefix as r
from contract import HERE, read, save, sha, require
P=read(HERE/'PROTOCOL.json')
ROOT=Path(P['root_remote'])
DEST=HERE/'source_scores'

def file_record(path):return {'file':str(path),'sha256':sha(path)}

def verified_row(case):
    folder=DEST/case['source_id'];record=folder/'SOURCE.json'
    row=read(record)
    for key in ('source_original','source_prepared_video','source_preparation_record','source_score_video'):
        require(sha(row[key]['file'])==row[key]['sha256'],'source publisher input/output changed '+key)
    require(row['source_prepared_video']['sha256']==case['video_sha256'] and
            row['source_preparation_record']['sha256']==case['provenance_sha256'],'source publisher case binding differs')
    require(row['pair_id']==case['source_id'] and row['score_frame_indices']==list(range(case['valid_frame_count'])), 'source publisher prefix differs')
    provenance=read(row['source_preparation_record']['file'])
    require(row['input_to_original_frame']==provenance['input_to_original_frame'],'source publisher mapping differs')
    require(sha(folder/'source_score.mapping.json')==row['release_mapping_sha256'],'source release mapping changed')
    return row

def publish(case):
    folder=DEST/case['source_id']
    if folder.exists():return verified_row(case)
    required=[ROOT/'inputs'/case[k] for k in ('video','provenance','original_source')]
    if not all(x.is_file() for x in required):return None
    prepared,provenance,original=required
    if sha(prepared)!=case['video_sha256'] or sha(provenance)!=case['provenance_sha256']:return None
    record=read(provenance)
    if sha(original)!=record['source_sha256']:return None
    folder.mkdir(parents=True)
    smoke=HERE/'audit/short0210_source_crop_cpu.mp4'
    if case['source_id']=='short_0210' and smoke.exists():
        release=r.reuse_source(prepared,original,provenance,smoke,folder/'source_score.mp4')
    else:release=r.source_view(prepared,original,provenance,folder/'source_score.mp4')
    row={'pair_id':case['source_id'],'source_original':file_record(original),
         'source_prepared_video':file_record(prepared),'source_preparation_record':file_record(provenance),
         'source_score_video':file_record(folder/'source_score.mp4'),
         'score_frame_indices':list(range(case['valid_frame_count'])),
         'input_to_original_frame':record['input_to_original_frame'],
         'release_mapping_sha256':sha(folder/'source_score.mapping.json')}
    save(folder/'SOURCE.json',row)
    return verified_row(case)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--one',choices=[c['source_id'] for c in P['cases']]);a=parser.parse_args()
    for rel,digest in read(HERE/'FREEZE.json')['files'].items():require(sha(HERE/rel)==digest,'source publisher code changed')
    with Path(P['consumer']['CPU_lock']).open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:print(json.dumps({'status':'busy','phase_started':False}));return
        started=time.monotonic();selected=[c for c in P['cases'] if not a.one or c['source_id']==a.one]
        rows=[publish(c) for c in selected]
        complete=[c for c in P['cases'] if (DEST/c['source_id']/'SOURCE.json').exists()]
        manifest=None
        if len(complete)==5:
            pairs=[verified_row(c) for c in P['cases']]
            manifest={'schema':'h3-ivebench-official-mf-source-inputs-v1','selection_sha256':P['selection_sha256'],'pairs':pairs,'consumer_freeze_sha256':sha(HERE/'FREEZE.json')}
            save(HERE/'SOURCE_METRIC_MANIFEST.json',manifest)
        print(json.dumps({'status':'complete' if manifest else 'partial','completed':[c['source_id'] for c in complete],'requested_available':[x['pair_id'] for x in rows if x],'seconds':time.monotonic()-started,'manifest':str(HERE/'SOURCE_METRIC_MANIFEST.json') if manifest else None}))
if __name__=='__main__':main()
