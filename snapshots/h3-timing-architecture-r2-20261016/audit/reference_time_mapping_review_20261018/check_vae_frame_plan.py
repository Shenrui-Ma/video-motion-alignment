from pathlib import Path
import ast,json,math
ROOT=Path(__file__).resolve().parent
source=ROOT/'source/vae.py';tree=ast.parse(source.read_text());methods={'_decode_temporal_pad_frames','_decode_temporal_frame_plan','_decode_temporal_chunks'}
cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and any(isinstance(x,ast.FunctionDef) and x.name=='encode_temporal' for x in n.body))
small=ast.ClassDef(name='Plan',bases=[],keywords=[],body=[x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name in methods],decorator_list=[])
module=ast.fix_missing_locations(ast.Module(body=[small],type_ignores=[]));namespace={'math':math};exec(compile(module,str(source),'exec'),namespace);p=namespace['Plan']();p.clip_length=17;p.vae_ratio_t=4;p.token_drop=3;p.frame_pre_padding=3;p.tokens_chunk_size=5;p.token_overlap=2;p.frame_overlap=5
rows=[]
for rgb in [56,73,107,158]:
 tokens=math.ceil(rgb/17)*5-3;pad,chunks=p._decode_temporal_chunks(tokens);recon=p._decode_temporal_frame_plan(tokens+pad,chunks,pad);assert recon==rgb
 rows.append({'input_rgb_frames':rgb,'encode_chunks':math.ceil(rgb/17),'tokens_before_tail_drop':math.ceil(rgb/17)*5,'tail_tokens_dropped':3,'latent_t':tokens,'decode_temporary_pad_tokens':pad,'decode_chunks':chunks,'output_rgb_frames':recon,'planned_output_length_matches_input':True})
result={'scope':'Pure actual VAE frame-count planning methods; no model or image reconstruction executed','parameters':p.__dict__,'rows':rows};(ROOT/'VAE_FRAME_PLAN.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
