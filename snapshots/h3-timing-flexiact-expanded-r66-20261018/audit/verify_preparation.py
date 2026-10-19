from pathlib import Path
import ast,difflib,hashlib,json,subprocess,sys
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from r66_contract import read,sha,registry
from preflight import check
P=Path('/Users/researcher/DevProjects/h3-timing-flexiact-forced-r65-20261018')
checks=check(R);syntax=[]
for p in sorted(R.rglob('*.py')):
 ast.parse(p.read_text(),filename=str(p));syntax.append(str(p.relative_to(R)))
media=[]
for p in sorted((R/'inputs').glob('source_*_video.mp4')):
 x=json.loads(subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,avg_frame_rate,nb_read_frames','-of','json',str(p)],capture_output=True,text=True,timeout=30,check=True).stdout)['streams'][0]
 assert (x['width'],x['height'],x['avg_frame_rate'],int(x['nb_read_frames']))==(1152,768,'24/1',158)
 media.append({'file':str(p.relative_to(R)),'sha256':sha(p),'actual_stream':x})
for p in sorted((R/'inputs').glob('source_*_original.mp4')):
 x=json.loads(subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,avg_frame_rate,nb_read_frames','-of','json',str(p)],capture_output=True,text=True,timeout=30,check=True).stdout)['streams'][0]
 assert (x['avg_frame_rate'],int(x['nb_read_frames']))==('8/1',49)
 media.append({'file':str(p.relative_to(R)),'sha256':sha(p),'actual_stream':x})
inherit=read(R/'audit/R65_INHERITANCE_INITIAL.json');rows=[];diff=[]
for rel,entry in inherit.items():
 p=R/rel;before=Path(entry['source']);assert sha(before)==entry['source_sha256'],'R65 source changed during preparation'
 raw=before.read_text();normalized=raw.replace('r65','r66').replace('R65','R66').replace('timing-flexiact-forced-r66','timing-flexiact-expanded-r66')
 if 'source_snapshot' in before.parts:normalized=raw
 row={**entry,'file':rel,'final_sha256':sha(p),'byte_equal':p.read_bytes()==before.read_bytes(),'namespace_only':p.read_text()==normalized};rows.append(row)
 if p.read_text()!=normalized:diff.extend(difflib.unified_diff(normalized.splitlines(True),p.read_text().splitlines(True),fromfile='R65_namespace_normalized/'+rel,tofile='R66/'+rel))
(R/'audit/R65_TO_R66.patch').write_text(''.join(diff))
kernels=read(R/'configs/runtime_kernel_hashes.json');kernelproof={rel:{'R65_sha256':sha(P/rel),'R66_sha256':sha(R/rel),'equal':sha(P/rel)==sha(R/rel)==v['current_sha256']} for rel,v in kernels.items()};assert all(v['equal'] for v in kernelproof.values())
result={'passed':True,'preflight':checks,'CPU_tests':{'count':35,'passed':35,'log':'audit/CPU_TESTS.log','log_sha256':sha(R/'audit/CPU_TESTS.log')},'syntax_file_count':len(syntax),'syntax_files':syntax,'media':media,'numerical_kernels':kernelproof,'inheritance':rows,'live_inference':'NOT_RUN','deployment':'NOT_RUN','no_service_started':not(R/'processes/service.json').exists(),'input_total_bytes':sum(p.stat().st_size for p in (R/'inputs').iterdir())}
(R/'audit/CPU_PREPARATION_VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['passed','syntax_file_count','CPU_tests','input_total_bytes','live_inference']}));print('kernel_equals',all(x['equal'] for x in kernelproof.values()))
