"""Pinned public CSV inventory; selection reads input assets only."""
import csv,hashlib,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DATA=Path('/Users/researcher/DevProjects/h3-flexiact-expanded-selection-20261018')
TREE=json.loads((DATA/'metadata/HF_TREE.json').read_text())
REV=TREE['revision'];FILES={x['path']:x for x in TREE['files'] if x['type']=='file'}
SOURCES=['chest','crouch','fitness','one_leg','rotate','human2animal_1','human2animal_2','human2animal_3']

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bound(rel,path):
 data=path.read_bytes();item=FILES[rel]
 assert len(data)==item['size'],rel
 if 'lfs' in item:assert hashlib.sha256(data).hexdigest()==item['lfs']['oid'],rel
 else:assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==item['oid'],rel
 return {'path':str(path),'sha256':sha(path),'bytes':len(data),'dataset_path':rel,'dataset_revision':REV,'git_blob_oid':item['oid'],'lfs_sha256':item.get('lfs',{}).get('oid'),'pinned_url':'https://huggingface.co/datasets/shiyi0408/FlexiAct/resolve/'+REV+'/'+rel}

contracts=[];tested={}
for name in ['native-r49-20261017','forced-r65-20261018','expanded-r66-20261018']:
 p=Path('/Users/researcher/DevProjects/h3-timing-flexiact-'+name+'/configs/scientific_contract.json');value=json.loads(p.read_text());contracts.append({'file':str(p),'sha256':sha(p)})
 for row in value['cases']:
  key=(row.get('motion_source_id',row['source_id']),row['identity'])
  tested.setdefault(key,[]).append({'contract':str(p),'run_id':row['run_id'],'arm':row.get('arm','native')})
# Review only the original supplied target images. Identity names below are filenames.
full={'game_man_1.jpg','game_man_4.jpg','game_man_5.jpeg','movie_man_5.jpg','movie_man_9.webp','movie_man_11.jpg'}
partial_arms={'movie_man_4.jpg','movie_man_7.jpg','movie_man_10.webp'}
review={}
for p in sorted((DATA/'official_assets/benchmark/target_images/human').iterdir()):
 role='full_body' if p.name in full else 'visible_arms_upper_legs' if p.name in partial_arms else 'upper_body_or_face_cropped_limbs'
 review[p.name]={'visibility':role,'full_body':p.name in full,'review_asset':bound('benchmark/target_images/human/'+p.name,p),'review_basis':'target_inventory.jpg: original image, no H3 output','note':'Legs/feet outside portrait; full-body motion transfer requires extrapolation.' if role=='visible_arms_upper_legs' else 'Original target image includes head, torso and both feet.' if role=='full_body' else 'Some body/limb regions unavailable in portrait.'}

rows=[];csvs=[];source_assets={};counts={}
for source in SOURCES:
 rel='benchmark/captions/human/'+source+'/val_image.csv';p=DATA/'metadata'/('flexiact_hf__'+rel.replace('/','__'));csvs.append(bound(rel,p))
 source_rel='benchmark/reference_videos/human/'+source+'.mp4';source_assets[source]=bound(source_rel,DATA/'official_assets'/source_rel)
 source_rows=list(csv.DictReader(p.open()));counts[source]=len(source_rows)
 for n,row in enumerate(source_rows):
  key=(source,row['path']);is_human='/human/' in row['path'];target=Path(row['path']).name
  rows.append({'source':source,'target':row['path'],'csv_row_zero_based':n,'official_caption':row['caption'],'target_kind':'human' if is_human else 'animal','previously_tested':key in tested,'prior_registered_runs':tested.get(key,[]),'visibility':review[target]['visibility'] if is_human else 'animal_not_reviewed_for_human_pose','metadata_flag':'official caption describes resistance machine, while source is an outdoor squat sequence' if source=='crouch' else None})
assert len(rows)==46 and len({(r['source'],r['target']) for r in rows})==46
human=[r for r in rows if r['target_kind']=='human'];animals=[r for r in rows if r['target_kind']=='animal'];official_keys={(r['source'],r['target']) for r in rows}
new_human=[r for r in human if not r['previously_tested']]
strict=[r for r in new_human if r['visibility']=='full_body']
# All seven untouched official full-body human pairings; one compatible upper-body action pairing.
# Preserve source order then official CSV row order. No selection uses generated results.
chosen_keys={(r['source'],r['target']) for r in strict}
chosen_keys.add(('chest','benchmark/target_images/human/movie_man_7.jpg'))
selected=[]
for row in rows:
 if (row['source'],row['target']) not in chosen_keys:continue
  # no change to official task membership or historical P0 editing instruction
 item=dict(row);item['candidate_id']=str(len(selected)+1).zfill(2)+'_'+row['source']+'__'+Path(row['target']).stem
 item['source_asset']=source_assets[row['source']];item['target_asset']=review[Path(row['target']).name]['review_asset']
 item['selection_reason']='all remaining official full-body human-target combinations' if row['visibility']=='full_body' else 'source chest contains upper-body cable pulls; this target exposes both arms and torso, while feet are outside portrait'
 item['prompt_version']='R49_original_P0_unchanged';selected.append(item)
assert len(selected)==8 and len(strict)==7
assert not any(x['previously_tested'] for x in selected)
assert len({x['source'] for x in selected})==5
summary={'schema':'flex-public-csv-untested-pairs-inventory-v1','created_unix':time.time(),'dataset_revision':REV,'source_count':8,'raw_official_rows':46,'unique_official_pairs':46,'human_target_pairs':39,'animal_target_pairs':7,'prior_unique_registered_source_target_pairs':len(tested),'prior_official_pairs':len(official_keys.intersection(tested)),'prior_crosspairs':len(set(tested)-official_keys),'untested_official_human_pairs':len(new_human),'untested_official_animal_pairs':sum(not r['previously_tested'] for r in animals),'remaining_strict_fullbody_human_pairs':len(strict),'selected_count':len(selected),'selected_full_body_target_count':len(strict),'selected_partial_target_count':1,'distinct_selected_motion_sources':len({x['source'] for x in selected}),'distinct_selected_target_images':len({x['target'] for x in selected}),'rows_per_source':counts,'generation_started':False,'gpu_work_started':False,'existing_P0_changed':False,'selection_uses_new_H3_output':False,'dedup_key':['underlying_motion_source','official_target_image_path'],'crop_variants_count_as_new_motion':False,'protocol':'Include every untested official human-target pair with head-to-feet image visibility (seven). Add chest/movie_man_7 as an upper-body-compatible pair to reach eight; preserve source order and CSV row order. All other rows remain in inventory. Past failures remain in their original denominator. Human2animal official targets are animal identities; prior six human substitutions are crosspairs and are reported separately.','source_preview':'source_inventory.jpg uses frames0,24,48 as visibility illustrations, not timing ground truth','primary_csv_bindings':csvs,'tested_contract_bindings':contracts,'source_assets':source_assets,'target_visual_review':review,'all_official_rows':rows,'selected_candidates':selected,'existing_crosspairs':[{'source':k[0],'target':k[1],'runs':tested[k]} for k in sorted(set(tested)-official_keys)]}
assert summary['prior_official_pairs']==7 and summary['prior_crosspairs']==6 and summary['untested_official_human_pairs']==32
(ROOT/'INVENTORY_AND_FIXED_8.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
(ROOT/'FIXED_8_CANDIDATES.json').write_text(json.dumps({'schema':'flex-official-fixed8-input-candidates-v1','dataset_revision':REV,'frozen_before_new_generation':True,'P0_unchanged':True,'pairs':selected},indent=2,ensure_ascii=False)+'\n')
with (ROOT/'ALL_OFFICIAL_ROWS.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['source','target','csv_row_zero_based','target_kind','previously_tested','visibility','selected','official_caption','metadata_flag']);w.writeheader()
 for row in rows:w.writerow({**{k:row[k] for k in w.fieldnames if k!='selected'},'selected':(row['source'],row['target']) in chosen_keys})
(ROOT/'INVENTORY_FREEZE.json').write_text(json.dumps({'schema':'flex-official-candidates-freeze-v1','files':{p.name:sha(p) for p in ROOT.iterdir() if p.is_file() and p.name not in ['INVENTORY_FREEZE.json','REPORT.txt']}},indent=2)+'\n')
print(json.dumps({k:summary[k] for k in ['raw_official_rows','unique_official_pairs','prior_official_pairs','prior_crosspairs','untested_official_human_pairs','remaining_strict_fullbody_human_pairs','selected_count','distinct_selected_target_images']}))
print('\n'.join(x['candidate_id'] for x in selected))
