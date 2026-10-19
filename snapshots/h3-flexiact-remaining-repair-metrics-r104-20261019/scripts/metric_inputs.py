"""CPU manifest for later official MF tracking; this module produces no score."""
from common import *
from paired import verify_pair_intake

def bind_media(p,g,directory,paired):
 rows={'source':{'file':str((ROOT/p['source']['file']).resolve()),'sha256':p['source']['sha256']}}
 for mode in (('native','forced') if paired else ('native',)):
  file=Path(directory)/(mode+'.mp4');require(sha(file)==g['runs'][mode]['video']['sha256'],'metric output SHA differs');rows[mode]={'file':str(file.resolve()),'sha256':sha(file),'producer_file':g['runs'][mode]['video']['file']}
 require(sha(ROOT/p['portrait']['file'])==p['portrait']['sha256'],'metric portrait SHA differs')
 require(sha(rows['source']['file'])==rows['source']['sha256'],'metric reference SHA differs')
 return {'schema':'r104-official-mf-ready-inputs-v1','source_id':p['source_id'],'status':'inputs_ready_score_pending','protocol':'FlexiAct official MF; exact evaluator/checkpoint/runtime must be bound by the later scoring task','fps':24,'valid_frames':p['valid_frames'],'total_frames':p['geometry']['frames'],'evaluate_indices':p['evaluation_indices'],'evaluation_fps':8,'crop_xywh':p['crop_xywh'],'raw_videos':rows,'task':p['original_task'],'reference_image_used':True,'reference_image':bound(ROOT/p['portrait']['file']),'scope':'49 original source instants at 8fps, indices 0,3,...144 in 24fps media. Official pairing or crosspair is retained in the per-case task group. Score all fixed instants without time alignment. Motion score and basic editing acceptance are reported separately.','GPU_started':False,'score':None}

def prepare(source,paired=False):
 validate_static();p=info(source);g=verify_pair_intake(source) if paired else verify_intake(source);directory=ROOT/('incoming_pairs' if paired else 'incoming')/source
 data=bind_media(p,g,directory,paired);data.update(producer_seal_sha256=config()['producer_seal_sha256'],gate=bound(directory/('PAIR_RUNTIME_GATE.json' if paired else 'NATIVE_RUNTIME_GATE.json')),collection=bound(directory/'COLLECTION.json'),provenance=bound(ROOT/p['provenance']['file']))
 dest=ROOT/'prepared'/source/('paired' if paired else 'native')/'MF_INPUTS.json'
 if dest.exists():require(read(dest)==data,'existing MF input manifest changed')
 else:save(dest,data)
 return bound(dest)
