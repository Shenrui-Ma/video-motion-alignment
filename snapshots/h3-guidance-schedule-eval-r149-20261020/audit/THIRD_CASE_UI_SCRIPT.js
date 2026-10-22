
"use strict";
const data=JSON.parse(document.getElementById("data").textContent);
const element=(name,cls,text)=>{const e=document.createElement(name);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;};
const range=v=>Array.isArray(v)?v.join("–"):v===null||v===undefined?"待评／缺失":String(v);
const score=v=>v===null||v===undefined?"待评分":v.toFixed(4);
function table(headers,rows){const t=element("table"),head=element("tr");headers.forEach(x=>head.append(element("th","",x)));t.append(head);rows.forEach(row=>{const tr=element("tr");row.forEach(x=>tr.append(element("td","",String(x))));t.append(tr);});return t;}
for(const c of data.cases){
 const card=element("section","case");card.dataset.case=c.source_id;card.append(element("h2","",c.title));
 card.append(element("p","meta",`${c.dataset} · ${c.source_id} · seed ${c.seed} · ${c.geometry.valid_frames} 有效帧 / ${c.geometry.fps} fps · ${c.reference_image}`));
 const toolbar=element("div","toolbar"),select=element("select"),full=element("button","","全屏视频"),status=element("span","status");
 select.setAttribute("aria-label",c.title+"的新引导方案");for(const [key,s]of Object.entries(data.schedules)){const o=element("option","",s.label);o.value=key;select.append(o);}toolbar.append(select,full,status);card.append(toolbar);
 const viewport=element("div","viewport"),stage=element("div","stage"),video=element("video"),wait=element("div","waiting","等待该方案的实际成片与逐条完成门。"),footer=element("div","footer");
 video.controls=true;video.preload="metadata";video.playsInline=true;video.muted=true;
 ["参考视频","普通编辑","时序引导 7–15","所选新方案"].forEach(x=>footer.append(element("span","",x)));
 stage.append(video,wait,footer);viewport.append(stage);card.append(viewport);
 const playbar=element("div","playbar"),prev=element("button","","上一帧"),next=element("button","","下一帧"),slider=element("input"),time=element("span","note");
 slider.type="range";slider.min=0;slider.max=c.geometry.valid_frames-1;slider.step=1;slider.value=0;slider.setAttribute("aria-label","同帧时间轴");
 playbar.append(prev,slider,next,time);card.append(playbar);
 const summary=element("div","summary"),description=element("p","note"),tables=element("div","tables"),frameButtons=element("div","frame-buttons"),frameView=element("div","frameview"),image=element("img");image.alt="四列同一帧对照";frameView.append(image);
 card.append(summary,description,tables,frameButtons,frameView);
 const prompt=element("details"),heading=element("summary","","原始提示词与方法说明");prompt.append(heading,element("p","note",c.prompt_source_label||"历史实际图逐字复用"),element("pre","prompt",c.prompt),element("p","note",data.global_weak_meaning));card.append(prompt);
 let active=null;const fps=c.geometry.fps;function seek(frame){if(!active||!active.video)return;video.pause();video.currentTime=Math.max(0,Math.min(c.geometry.valid_frames-1,frame))/fps;}
 prev.onclick=()=>seek(Math.round(video.currentTime*fps)-1);next.onclick=()=>seek(Math.round(video.currentTime*fps)+1);slider.oninput=()=>seek(+slider.value);
 video.ontimeupdate=()=>{const f=Math.min(c.geometry.valid_frames-1,Math.floor(video.currentTime*fps+0.01));slider.value=f;time.textContent=`第 ${f} 帧 · ${(f/fps).toFixed(3)} s`;};
 full.onclick=()=>{if(video.requestFullscreen)video.requestFullscreen();else if(video.webkitEnterFullscreen)video.webkitEnterFullscreen();};
 function update(){
  const arm=select.value,s=data.schedules[arm],a=c.arms[arm],oldTime=video.currentTime||0,wasPlaying=!video.paused;active=a;video.pause();
  video.hidden=!a.video;wait.hidden=!!a.video;footer.hidden=!!a.video;footer.lastChild.textContent=s.label;status.textContent=a.status;
  full.disabled=prev.disabled=next.disabled=slider.disabled=!a.video;
  if(a.video){video.src=a.video;video.onloadedmetadata=()=>{video.currentTime=Math.min(oldTime,(c.geometry.valid_frames-1)/fps);video.playbackRate=1;if(wasPlaying)video.play().catch(()=>{});};}
  else{video.removeAttribute("src");video.load();time.textContent="尚无新成片";}
  const review=a.review;summary.textContent=review?(review.summary_zh||review.summary||review.task_verdict||"评审记录已绑定"):a.video?"成片已绑定；等待完整有效帧任务与事件审阅。":"结果待实际生成；历史对照和评价窗口已经冻结。";
  const sigma=c.sigma_spans[arm],oldSigma=c.sigma_spans.historical_middle;
  description.textContent=`${s.label}：${s.steps_1based.length} 个去噪步，sigma 积分跨度 ${sigma.toFixed(5)}（原 7–15：${oldSigma.toFixed(5)}）。`+(a.sampling_seconds?` 实际采样 ${a.sampling_seconds.toFixed(1)} s。${a.sampling_scope}`:" 实际采样时间待记录。");
  tables.replaceChildren(table(["指标","普通编辑","原 7–15","所选新方案"],[["官方 MF",score(c.old_MF.native),score(c.old_MF.fixed),score(a.score)]]));
  if(a.step_seconds){tables.append(table(["本次实际时间","秒"],[["完整采样（含审计）",a.sampling_seconds.toFixed(2)],["首步同步间隔",a.step_seconds.first_callback_interval.toFixed(2)],["第 2–20 步同步间隔中位数",a.step_seconds.later_callback_interval_median.toFixed(2)],["第 2–20 步同步间隔范围",a.step_seconds.later_callback_interval_range.map(x=>x.toFixed(2)).join("～")]]));tables.append(element("p","note",a.step_seconds.scope));}
  if(c.events.length){const byId=Object.fromEntries((review?.events||[]).map(e=>[e.id,e]));tables.append(table(["动作事件（帧）","参考","普通编辑","原 7–15",s.label],c.events.map(e=>[e.label,range(e.source),range(e.native),range(e.fixed),range(byId[e.id]?.[arm])])));}
  else{const ws=c.historical_window_diagnostics?.windows||[],newWindows=review?.historical_window_diagnostics?.windows||[];tables.append(table(["固定姿态窗口","普通 lag（.3 / .5）","原 7–15 lag（.3 / .5）","新方案"],ws.map(w=>{const nw=newWindows.find(n=>String(n.window)===String(w.window))?.[arm];return [range(w.window),`${range(w.native["0.3"])} / ${range(w.native["0.5"])}`,`${range(w.fixed["0.3"])} / ${range(w.fixed["0.5"])}`,nw?`${range(nw["0.3"])} / ${range(nw["0.5"])}`:"待离线评审"];})));tables.append(element("p","note","Sam 这些数值是原 arm_direction 窗口 lag，非人工事件边界。主窗 50–65；另保留三个原回收窗。"));}
  if(a.event_summary){const format=v=>v?v.map(x=>x.toFixed(1)).join("～"):"缺失";tables.append(table(["事件","新方案绝对时差（帧）","相对原 7–15 的误差变化（ms）"],a.event_summary.events.map(e=>[e.id,range(e.statistics?.absolute_error_frames),format(e.statistics?.paired_change_vs_fixed_ms)])));tables.append(table(["相邻阶段","参考时长（帧）","原 7–15 时长","新方案时长","时长误差变化（ms）"],a.event_summary.phases.map(p=>[`${p.from} → ${p.to}`,range(p.statistics?.source_duration_frames),range(p.statistics?.fixed_duration_frames),range(p.statistics?.new_duration_frames),format(p.statistics?.paired_duration_error_change_ms)])));}
  tables.append(element("p","note","MF、事件时差与阶段持续时间分别记录；结论同时包含编辑任务、身份、姿态与重影变化。"));
  frameButtons.replaceChildren();image.hidden=!a.frames.length;
  for(const f of a.frames){const b=element("button","",`同帧截图 ${f.frame}`);b.onclick=()=>{image.src=f.url;image.alt=`${c.title} ${s.label} 第 ${f.frame} 帧四列对照`;};frameButtons.append(b);}
  if(a.frames.length)frameButtons.firstChild.click();
 }
 select.onchange=update;document.getElementById("cases").append(card);update();
}
