"""Add archived anime A/B prompt comparisons to the original black/English gallery."""
import json
from pathlib import Path
import renderer_base as r

ROOT=Path(__file__).resolve().parent
ARCHIVE=Path('/Users/researcher/DevProjects/h3-short-event-switching-20261013')

ANIME=[
 dict(key='00_anime_seed2',case='06_anime_eye_insert',seed=2,archive=ARCHIVE,frames=141,
      title='Anime character replacement | seed 2',bounds=[30,52],screens=[[41,42,43]],
      detail=[340,80,640,560],
      note='The brief source hand-to-eye insertion at frames 39-44 is not faithfully preserved. At frames 41-42, A/B keep the hand lower or begin the outward point. The later long eye-side pose is a separate action.'),
 dict(key='05_anime_seed1_supplement',case='06_anime_eye_insert',seed=1,archive=ARCHIVE,frames=141,
      title='Anime character replacement | seed 1 | supplementary',bounds=[18,63],screens=[[41,42,43],[24,25,26]],
      detail=[340,80,640,560],
      note='At source frames 41-42, both outputs keep their hands low. B also introduces an earlier, longer face-adjacent excursion around frames 20-38; that extra excursion does not preserve the target timing and context.'),
]

def render_case(c):
 folder=ROOT/c['key'];folder.mkdir(exist_ok=True)
 paths=[ARCHIVE/'inputs'/f"{c['case']}.mp4"]+[ARCHIVE/'outputs'/f"{c['case']}_{arm}_s{c['seed']}_00001_.mp4" for arm in ['a','b']]
 av=json.loads((ARCHIVE/'analysis/archive_validation.json').read_text())
 expected={x['output_file']:x['output_sha256'] for x in av['formal_runs']}
 for p in paths[1:]:assert r.sha(p)==expected[p.relative_to(ARCHIVE).as_posix()]
 for p in paths:
  pr=r.probe(p);assert int(pr['nb_read_frames'])==141 and pr['avg_frame_rate']=='24/1'
 seqs=[r.decode(p,141) for p in paths]
 rendered=r.render_set(c,seqs,folder)
 full=[]
 for fps,suffix in [(24,'normal'),(6,'quarter_speed')]:
  p=folder/f'full_clip_{suffix}.mp4';pr=r.encode([r.row(seqs,i) for i in range(141)],p,fps)
  full.append({'path':p.relative_to(ROOT).as_posix(),'probe':pr})
 detail=r.render_set(c,[r.decode(p,141,c['detail']) for p in paths],folder,True)
 record={**{k:str(v) if isinstance(v,Path) else v for k,v in c.items()},
         'inputs':[{'path':str(p),'sha256':r.sha(p)} for p in paths],
         'rendered':rendered,'detail_rendered':detail,'full_clip':full,
         'experiment_kind':'previous baseline prompt A vs explicit-event prompt B; no event-emphasis weighting',
         'source_target_frames_inclusive':[39,44],
         'source_decisive_eye_pose_frames_inclusive':[41,42],
         'source_later_separate_long_eye_pose_frames_inclusive':[54,68]}
 print('DONE',c['key'],flush=True)
 return record

def main():
 imported=json.loads((ROOT/'imported_manifest.json').read_text())
 anime=[render_case(c) for c in ANIME]
 cases=[anime[0],*imported['cases'][:3],anime[1],imported['cases'][3]]
 manifest={**imported,'cases':cases,
           'provenance_note':'All displayed results are previously archived generic-prompt A / explicit-event-prompt B baselines. They are not results of the current event-emphasis weighting experiment.',
           'imported_assets_manifest':'IMPORTED_MEDIA_SHA256.json',
           'new_model_inference':False}
 (ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 r.build_html(manifest)
 html=(ROOT/'index.html').read_text()
 html=html.replace('<title>H3 | Same-time motion comparisons</title>','<title>H3 | Anime, live action and breakdance</title>')
 html=html.replace('<h1>H3 | Same-time motion comparisons</h1>','<h1>H3 | Anime, live action and breakdance</h1>')
 intro='<p>Previously archived prompt baselines: A uses a general motion-preservation prompt; B explicitly describes the event and timing. These are not outputs of the ongoing event-emphasis weighting experiment.</p><nav><a href="#00_anime_seed2">Anime</a><a href="#01_black_to_red">Black to red</a><a href="#02_white_to_blue">White to blue</a><a href="#03_breakdance_seed2">Breakdance</a><a href="#05_anime_seed1_supplement">Anime seed 1</a><a href="#04_breakdance_seed1_supplement">Breakdance seed 1</a></nav>'
 html=html.replace('<section id="00_anime_seed2">',intro+'<section id="00_anime_seed2">',1)
 (ROOT/'index.html').write_text(html)
 (ROOT/'README.txt').write_text('H3 黑底英文总展示：动漫、真人与街舞\n\n打开 index.html 查看6组SOURCE / A: appearance edit / B: explicit event对照。主展示依次是动漫seed2、黑裙改红seed1、白衣改蓝seed1、街舞seed2；补充动漫seed1与街舞seed1。\n\n所有展示均为此前封存的普通动作保留提示A与显式事件提示B，不是当前正在进行的事件加权实验结果。本次没有运行模型推理。\n动漫seed2：关键截图41–43帧，原短动作39–44帧、决定性眼旁关系41–42帧；连续展示30–52帧。后置长眼旁动作54–68帧是另一动作，不能当作早期动作修复。\n动漫seed1：连续展示18–63帧；关键图41–43显示原目标时刻不一致，24–26显示B新增提前的脸旁动作。\n每组都保留完整片段正常速度和四分之一速度上下文；动漫完整141帧、24FPS、5.875秒。慢放同帧以6FPS播放，不插帧、不改变各列时间。DETAIL CROP为三列相同固定空间裁切；full_frame保留源/输出原始完整画面。\n两个真人的短窗口证明对应时刻姿态不一致，不能仅凭窗口断定整段遗漏；街舞为大动作内部姿态/相位错位。\n源文件与旧展示目录只读，新目录与压缩包独立。manifest.json记录源/输出SHA与全部媒体参数。\n')

if __name__=='__main__':main()
