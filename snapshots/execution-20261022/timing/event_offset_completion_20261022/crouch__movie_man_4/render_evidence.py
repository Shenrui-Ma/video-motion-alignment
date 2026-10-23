import json,subprocess,pathlib,sys
ROOT=pathlib.Path('/workspace/research-user/DevProjects/video-motion-alignment/execution-20261022')
J=json.load(open(ROOT/'metrics/manifest.json'))['jobs']
case,role=sys.argv[1:3]; ids=list(range(0,147 if case.startswith('crouch') else 144,3)) if len(sys.argv)==3 else list(range(int(sys.argv[3]),int(sys.argv[4])+1))
j=next(j for j in J if j['task_id']==case and j['method']==role)
name=role+'_'+str(ids[0])+'_'+str(ids[-1]); folder=str(pathlib.Path(j['target_frames_parent'])/pathlib.Path(j['metadata']['src_video_name']).stem)
remote='/data/research-user/h3_metrics_20261022/tmp_offset_crouch_animation/'+case+'/'+name+'.jpg'
code='''from PIL import Image,ImageDraw
import pathlib,math,json
folder=pathlib.Path(FOLDER);ids=IDS
w,h=220,180;cols=7
out=Image.new('RGB',(w*cols,h*math.ceil(len(ids)/cols)),(25,25,25));d=ImageDraw.Draw(out)
for k,i in enumerate(ids):
 im=Image.open(folder/f'{i+1:06d}.png').convert('RGB');im.thumbnail((w,h-23));x=(k%cols)*w;y=(k//cols)*h
 out.paste(im,(x+(w-im.width)//2,y+23));d.text((x+5,y+4),str(i),fill='white')
pathlib.Path(OUTPUT).parent.mkdir(parents=True,exist_ok=True);out.save(OUTPUT,quality=88)
'''.replace('FOLDER',repr(folder)).replace('IDS',repr(ids)).replace('OUTPUT',repr(remote))
subprocess.run(['ssh','-o','BatchMode=yes','H3_HOST_CONFIGURE_LOCALLY','/data/research-user/h3_metrics_20261022/venv/bin/python -'],input=code,text=True,check=True,stdout=subprocess.DEVNULL)
out=ROOT/'timing/event_offset_completion_20261022'/case/(name+'.jpg')
subprocess.run(['scp','-q','H3_HOST_CONFIGURE_LOCALLY:'+remote,str(out)],check=True)
print(out)
