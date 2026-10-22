"""Validate frozen source-only selection and bind the preauthorized Native screen."""
import json,shutil
from pathlib import Path
from bind_cases import ROOT,LANES,write,bind_manifest
from r26_contract import read,sha

def main():
 manifest_path=ROOT/'configs/source_selection_manifest.json';manifest=read(manifest_path)
 if manifest['protocol_sha256']!=sha(ROOT/'configs/source_selection_protocol.json') or manifest['freeze_sha256']!=sha(ROOT/'configs/source_selection_freeze.json'):raise ValueError('selection protocol/freeze changed')
 if set(manifest['sources'])!={'40372','51317','51304'}:raise ValueError('screen source set changed')
 science=read(ROOT/'configs/runtime_templates/scientific_contract.json');portrait=Path(science['portrait_source_file'])
 if sha(portrait)!=science['portrait_sha256']:raise ValueError('Sam portrait differs from R24')
 cases=[]
 for lane,ids in LANES.items():
  for sid in ids:
   row=manifest['sources'][sid];video=ROOT/row['prepared_path'];proof=ROOT/row['provenance_path'];p=read(proof)
   if sha(video)!=row['prepared_sha256'] or sha(proof)!=row['provenance_sha256'] or p['prepared_sha256']!=row['prepared_sha256']:raise ValueError('selected file/provenance mismatch')
   if any(row['geometry'][k]!=v or p['geometry'][k]!=v for k,v in dict(width=1312,height=736,frames=141,fps=24).items()):raise ValueError('source geometry mismatch')
   mapping=row['frame_map'];start=row['source_frame_start'];end=row['source_frame_end']
   if p['source_only'] is not True or p['frame_map']!=mapping or end-start!=140 or len(mapping)!=141 or row['intervention_event_window'] is not None:raise ValueError('source-only/full selected span mismatch')
   if [x['prepared_frame'] for x in mapping]!=list(range(141)) or [x['full_prepared_frame'] for x in mapping]!=list(range(start,end+1)) or any(abs(x['prepared_time_s']-i/24)>1e-9 for i,x in enumerate(mapping)):raise ValueError('selected frame/time map mismatch')
   if any(p['frame_identity'][fmt]['all141_equal'] is not True for fmt in ('rgb24','yuv420p')):raise ValueError('selected frame identity gate missing')
   if sha(ROOT/row['source_pose_path'])!=row['source_pose_sha256']:raise ValueError('selected source pose binding changed')
   cases.append({'lane':lane,'case_id':'source_'+sid,'source_id':sid,'video_file':str(video),'video_sha256':row['prepared_sha256'],'portrait_file':str(portrait),'portrait_sha256':science['portrait_sha256'],'source_provenance_file':str(proof),'provenance_sha256':row['provenance_sha256'],'prompt':science['prompt'],'new_to_study_attestation':True,'source_selection_manifest_sha256':sha(manifest_path),'selection_status':row['selection_status'],'source_pose_sha256':row['source_pose_sha256'],'source_frame_start':start,'source_frame_end':end,'no_intervention_window':True})
 out=ROOT/'configs/native_material_manifest.json'
 if out.exists():raise FileExistsError('preserve previous material binding')
 write(out,{'approved_for_binding':True,'approval_basis':'root explicitly authorized these three source-only selected Native screen cases; launch still needs root live admission','source_selection_manifest_sha256':sha(manifest_path),'cases':cases})
 results=bind_manifest(out)
 for lane in LANES:
  target=ROOT/'lanes'/lane/'configs'
  for src,name in [(out,'native_material_manifest.json'),(manifest_path,'native_source_selection_manifest.json'),(ROOT/'configs/source_selection_protocol.json','native_source_selection_protocol.json'),(ROOT/'configs/source_selection_freeze.json','native_source_selection_freeze.json')]:shutil.copy2(src,target/name)
 write(ROOT/'audit/runtime_material_binding.json',{'selection_manifest_sha256':sha(manifest_path),'results':results});print(json.dumps(results,indent=2))
if __name__=='__main__':main()
