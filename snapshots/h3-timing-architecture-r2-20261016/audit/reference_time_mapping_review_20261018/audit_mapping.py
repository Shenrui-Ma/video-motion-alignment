"""Read-only coordinate audit: reconstruct small position arrays; never load model/latent weights."""
from pathlib import Path
from fractions import Fraction
import ast,math,json,hashlib,shutil
import torch
ROOT=Path(__file__).resolve().parent
DEV=Path('/Users/researcher/DevProjects')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
sourcefiles={
 'model.py':DEV/'h3-flexiact-official-six-metrics-r74-20261018/audit/prompt_protocol_review/actual_code/host9/comfy/ldm/minimax/model.py',
 'nodes_minimax_h3.py':DEV/'h3-flexiact-official-six-metrics-r74-20261018/audit/prompt_protocol_review/actual_code/host9/comfy_extras/nodes_minimax_h3.py',
 'vae.py':DEV/'h3-vae-temporal-operator-r70-20261018/audit/source_code/h3_vae.py'}
expected_keys={'model.py':'comfy/ldm/minimax/model.py','nodes_minimax_h3.py':'comfy_extras/nodes_minimax_h3.py','vae.py':'comfy/ldm/minimax/vae.py'}
(ROOT/'source').mkdir(exist_ok=True)
for name,p in sourcefiles.items():shutil.copyfile(p,ROOT/'source'/name)
model=sourcefiles['model.py'];tree=ast.parse(model.read_text());names={'_axis_from_sqrt_area','_frame_grid','_video_t_spans','_video_t_grid','_ref_t_span','_audio_grid','_video_grid','PackedLayout'}
module=ast.Module(body=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names],type_ignores=[])
ns={'torch':torch,'math':math,'FRAME_PER_TOKEN':(1,4,4,4,4),'FRAME_RESCALE':5./3.};exec(compile(module,str(model),'exec'),ns)
cases=[('r85','one_leg__movie_man_9','h3-timing-flexiact-expanded-r85-20261018','h3-flexiact-expanded-metrics-r85-20261018',147),('r89','short_0131','h3-timing-ive-subject-capacity-r89-20261018','h3-ive-subject-capacity-metrics-r89-20261018',43),('r89','short_0343','h3-timing-ive-subject-capacity-r89-20261018','h3-ive-subject-capacity-metrics-r89-20261018',61),('r73','short_0252','h3-timing-ivebench-expanded-r73-20261018','h3-ivebench-expanded-metrics-r73-20261018',98)]
rows=[];bindings={}
for prefix,source,producer,consumer,valid in cases:
 p=DEV/producer;d=DEV/consumer/'incoming'/source;hashes=read(p/'configs/parent_core_hashes.json')
 for name,code in sourcefiles.items():assert sha(code)==hashes[expected_keys[name]]
 gate=read(d/'PAIR_RUNTIME_GATE.json');assert gate['passed'] and all(gate['checks'].values());row={'case':prefix+'_'+source,'producer':str(p),'consumer':str(d),'pair_gate_sha256':sha(d/'PAIR_RUNTIME_GATE.json'),'valid_frames':valid,'arms':{}}
 for arm in ['native','forced']:
  run=f'{prefix}_{source}_seed2026101701_{arm}';condfile=ROOT/'actual'/(run+'_conditioning.json');cond=read(condfile);routerfile=d/(arm+'_router.json');router=read(routerfile);assert sha(routerfile)==gate['runs'][arm]['router_file_sha256'];plan=router['validated_layout'];metadata=router['metadata'];signature=plan['signature'];layout=ns['PackedLayout'](*signature,refs=metadata['refs']);pos=layout.position_ids
  digest=hashlib.sha256(pos.contiguous().view(torch.uint8).numpy().data).hexdigest();assert digest==cond['packed_layout']['position_ids']['sha256'];assert [list(x) for x in layout.segments]==plan['segments']==cond['packed_layout']['segments'];assert layout.seq_len==plan['seq_len'];assert router['radius']==0 and router['time_offset']==0
  rindex=plan['reference_index'];refs=metadata['refs'];ref=refs[rindex];call=cond['native_vae_calls'][rindex];assert ref['kind']=='video';assert call['latent']['shape']==cond['target_latent_shapes'][0]==[1,24,*signature[1:4]];assert cond['input_video']['shape'][0]==call['prepared_frames']['shape'][0]
  total=call['prepared_frames']['shape'][0];t=signature[1];fr=plan['frame_rows'];ra,rb=plan['reference_video_segment'];qa,qb=plan['target_video_segment'];assert rb-ra==qb-qa==t*fr;assert sum([1,4,4,4,4][i%5] for i in range(t))==total
  rcoords=pos[ra:rb:fr,0];qcoords=pos[qa:qb:fr,0];r0=rcoords[0].item();q0=qcoords[0].item();relative_error=(rcoords-r0-(qcoords-q0)).abs().max().item();assert relative_error<1e-10
  assert torch.equal(pos[ra:rb,1:],pos[qa:qb,1:]);assert all(max(ra,a)>=min(rb,b) for a,b in plan['reference_image_segments'])
  bins=[];start=0
  for k in range(t):
   size=[1,4,4,4,4][k%5];end=start+size;assert abs((rcoords[k].item()-r0)/40-start/24)<1e-10
   bins.append({'k':k,'nominal_pixel_range_half_open':[start,end],'nominal_seconds_half_open':[str(Fraction(start,24)),str(Fraction(end,24))],'key_rows':[ra+k*fr,ra+(k+1)*fr],'query_rows':[qa+k*fr,qa+(k+1)*fr],'relative_start_rope':rcoords[k].item()-r0,'guided':arm=='forced' and plan['latent_interval_half_open'][0]<=k<plan['latent_interval_half_open'][1],'valid_pixels':list(range(start,min(end,valid))) if start<valid else [],'padding_pixels':list(range(max(start,valid),end))})
   start=end
  sampling=next(x['sampling'] for x in cond['qwen_presentation'] if x['type']=='video');assert sampling['source_fps']==24 and sampling['semantic_fps']==2 and sampling['phase_frames']==0 and sampling['sample_indices']==list(range(0,total,12));assert sampling['sample_timestamps_seconds']==[i/24 for i in sampling['sample_indices']]
  assert cond['pair_snapshot']['verified']
  armresult={'run_id':run,'input_frames':total,'latent_t':t,'latent_h_w':signature[2:4],'frame_rows':fr,'reference_index':rindex,'reference_video_segment':[ra,rb],'reference_image_segments':plan['reference_image_segments'],'target_video_segment':[qa,qb],'ref_origin':r0,'target_origin':q0,'absolute_time_coordinate_offset':q0-r0,'relative_time_max_error':relative_error,'all_position_bytes_reconstructed_exact':True,'position_ids_sha256':digest,'coordinate_shape':list(pos.shape),'routing_interval_half_open':plan['latent_interval_half_open'],'coverage':plan['position_bin_coverage_inclusive'],'same_spatial_coords_exact':True,'same_bin_is_same_relative_time':True,'native_prepared_frames_match_input_count':True,'Qwen_semantic_frames':len(sampling['sample_indices']),'semantic_fps':2,'bins':bins}
  row['arms'][arm]=armresult
  for x in [condfile,routerfile,d/'PAIR_RUNTIME_GATE.json',p/'configs/parent_core_hashes.json',p/'extensions/H3TemporalRouter/layout.py',p/'extensions/H3TemporalRouter/core.py']:bindings[str(x)]={'sha256':sha(x),'bytes':x.stat().st_size}
 assert row['arms']['native']['position_ids_sha256']==row['arms']['forced']['position_ids_sha256'];rows.append(row)
provpath=DEV/'h3-timing-flexiact-expanded-r85-20261018/inputs/source_one_leg_provenance.json';prov=read(provpath);mapping=prov['input_to_original'];assert mapping[:147]==[i//3 for i in range(147)] and mapping[147:]==[48]*11
proof={'repeat_mapping_exact':True,'original_frames':49,'original_fps':8,'prepared_fps':24,'valid_frames':147,'total_frames':158,'original_sample_time_preserved':all(Fraction(i,8)==Fraction(3*i,24) for i in range(49)),'repeat_times_per_original':[0,'1/24','2/24'],'padding_range_half_open':[147,158],'last_original_sample_seconds':6,'source_provenance_sha256':sha(provpath)}
for name,p in sourcefiles.items():bindings[str(p)]={'sha256':sha(p),'bytes':p.stat().st_size}
result={'passed':True,'scope':'Read-only actual JSON+exact source coordinate reconstruction, CPU only; no latent PT/model weights loaded','CUDA_initialized':torch.cuda.is_initialized(),'rows':rows,'one_leg_repeat3_proof':proof,'source_bindings':bindings,'limits':['Position bin is a nominal coordinate interval, not exact VAE receptive field or learned motion semantics.','This verifies temporal wiring/coordinates, not whether same-bin attention preserves motion.','No one_leg reference VAE encode-decode was executed in this audit; possible VAE reconstruction phase bias remains unmeasured for this source.']}
assert not result['CUDA_initialized'];(ROOT/'EVIDENCE.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed':True,'cases':len(rows),'full_position_sha_matches':sum(len(x['arms']) for x in rows),'CUDA_initialized':result['CUDA_initialized'],'sizes':[(x['case'],x['arms']['native']['input_frames'],x['arms']['native']['latent_t'],x['valid_frames']) for x in rows]},indent=2))
