import fcntl,hashlib,json,pathlib,zipfile,subprocess,time
b=pathlib.Path(__file__).resolve().parent;lock=open('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock','a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:print('BUSY');raise SystemExit(75)
start=time.time();z=zipfile.ZipFile(b/'downloads/MTBench.zip');rows=json.loads((b/'MTBENCH_ALL_100_PROMPTS.json').read_text());result=[]
for r in rows:
 id=r['id'];base='MTBench/'+id+'/';file=base+'videos/'+id+'.mp4';data=z.read(file);out=b/'candidate_sources'/file;out.parent.mkdir(exist_ok=True,parents=True);out.write_bytes(data)
 mask=base+'masks/'+id+'/00000.png';hasmask=mask in z.namelist()
 if hasmask:
  q=b/'candidate_sources'/mask;q.parent.mkdir(exist_ok=True,parents=True);q.write_bytes(z.read(mask))
 for name in ['prompts.txt','eval_prompts.txt']:(b/'candidate_sources'/base/name).write_bytes(z.read(base+name))
 probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,avg_frame_rate,nb_frames,duration:format=duration','-of','json',str(out)],text=True))
 result.append(dict(r,path=str(out),archive_path=file,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),has_firstframe_mask=hasmask,probe=probe))
(b/'MTBENCH_SOURCE_INVENTORY.json').write_text(json.dumps(result,indent=2));print('sources',len(result),'seconds',time.time()-start);print('timing patterns',sorted(set(str(x['probe']['streams'][0]) for x in result)))
