"""Official FlexiAct MF media specification. No tracker or score execution."""
from common import *
def prepare():
 c=validate_static();g=verify_intake()
 media={k:bound(c['media'][k]['file']) for k in ('source','native')};media['forced']=bound(ROOT/'incoming/forced.mp4')
 require(media['native']['sha256']==g['runs']['native']['video']['sha256'] and media['forced']['sha256']==g['runs']['forced']['video']['sha256'],'metric media mismatch')
 value={'schema':'r101-official-mf-media-inputs-v1','status':'inputs_ready_score_pending','scores':None,'protocol':'FlexiAct official MF, original 49 source timestamps; use frozen official evaluator','media':media,'source_id':c['source_id'],'original_pair_id':c['original_pair_id'],'group':c['group'],'physical_frame_indices':list(range(0,147,3)),'physical_pts_seconds':[i/8 for i in range(49)],'generated_fps':24,'original_motion_fps':8,'valid_frames':147,'total_frames':158,'crop_xywh':[0,0,1152,768],'gate':bound(ROOT/'incoming/PAIR_RUNTIME_GATE.json'),'collection':bound(ROOT/'incoming/COLLECTION.json'),'scope':'Official assets cross-pair extension; this single case is not the original paper 250-pair mean.'}
 path=ROOT/'prepared/MF_INPUTS.json'
 if path.exists():require(read(path)==value,'existing metric inputs changed')
 else:save(path,value)
 return bound(path)
