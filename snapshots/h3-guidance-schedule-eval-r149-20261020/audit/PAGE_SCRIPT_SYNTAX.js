
"use strict";
const data=JSON.parse(document.getElementById("data").textContent);
const element=(name,cls,text)=>{const e=document.createElement(name);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;};
const range=(v,empty="待审阅")=>Array.isArray(v)?v.join("–"):v===null||v===undefined?empty:String(v);
const score=v=>v===null||v===undefined?"待评分":v.toFixed(4);
function table(headers,rows){const t=element("table"),head=element("tr");headers.forEach(x=>head.append(element("th","",x)));t.append(head);rows.forEach(row=>{const tr=element("tr");row.forEach(x=>tr.append(element("td","",String(x))));t.append(tr);});return t;}
function details(title){const d=element("details");d.append(element("summary","",title));return d;}
for(const c of data.cases){
 const card=element("section",c.overview?"case seven":"case");card.dataset.case=c.source_id;card.append(element("h2","",c.title));
 card.append(element("p","meta",`${c.dataset} · ${c.reference_image}`));
 const toolbar=element("div","toolbar"),select=element("select"),full=element("button","","全屏视频"),status=element("span","status");
 select.setAttribute("aria-label",c.title+"的新引导方案");for(const [key,s]of Object.entries(data.schedules)){const o=element("option","",s.label);o.value=key;select.append(o);}toolbar.append(select,full,status);card.append(toolbar);
 const description=element("p","note"),summary=element("div","summary"),frameButtons=element("div","frame-buttons"),frameView=element("div","frameview"),image=element("img");
 image.alt="四列同一帧对照";frameView.append(image);card.append(description,summary,frameButtons,frameView);
 const viewport=element("div","viewport"),stage=element("div","stage"),video=element("video"),wait=element("div","waiting","待生成"),footer=element("div","footer");
 video.controls=true;video.preload="metadata";video.playsInline=true;video.muted=true;
 ["参考视频","普通编辑","时序引导 7–15","所选新方案"].forEach(x=>footer.append(element("span","",x)));
 stage.append(video,wait,footer);viewport.append(stage);card.append(viewport);
 const playbar=element("div","playbar"),prev=element("button","","上一帧"),next=element("button","","下一帧"),slider=element("input"),time=element("span","note");
 slider.type="range";slider.min=0;slider.max=c.geometry.valid_frames-1;slider.step=1;slider.value=0;slider.setAttribute("aria-label","同帧时间轴");
 playbar.append(prev,slider,next,time);card.append(playbar);
 const tables=element("div","tables"),measurement=details("动作测量说明"),measurementBody=element("div","tables"),technical=details("采样时间与复现参数"),technicalBody=element("div","tables");
 measurement.append(measurementBody);technical.append(technicalBody);card.append(tables,measurement,technical);
 const prompt=details("原始提示词与方法说明");prompt.append(element("p","note",c.prompt_source_label||"沿用历史实验的原始提示词"),element("pre","prompt",c.prompt),element("p","note",data.global_weak_meaning));card.append(prompt);
 let active=null;const fps=c.geometry.fps;function seek(frame){if(!active||!active.video)return;video.pause();video.currentTime=Math.max(0,Math.min(c.geometry.valid_frames-1,frame))/fps;}
 prev.onclick=()=>seek(Math.round(video.currentTime*fps)-1);next.onclick=()=>seek(Math.round(video.currentTime*fps)+1);slider.oninput=()=>seek(+slider.value);
 video.ontimeupdate=()=>{const f=Math.min(c.geometry.valid_frames-1,Math.floor(video.currentTime*fps+0.01));slider.value=f;time.textContent=`第 ${f} 帧 · ${(f/fps).toFixed(3)} s`;};
 full.onclick=()=>{if(video.requestFullscreen)video.requestFullscreen();else if(video.webkitEnterFullscreen)video.webkitEnterFullscreen();};
 function update(){
  const arm=select.value,s=data.schedules[arm],a=c.arms[arm],display=c.overview||a,oldTime=video.currentTime||0,wasPlaying=!video.paused;active=display;video.pause();
  video.hidden=!display.video;wait.hidden=!!display.video;footer.hidden=!!display.video;footer.lastChild.textContent=s.label;status.textContent=a.status;
  full.disabled=prev.disabled=next.disabled=slider.disabled=!display.video;
  if(display.video){video.src=display.video;video.onloadedmetadata=()=>{video.currentTime=Math.min(oldTime,(c.geometry.valid_frames-1)/fps);video.playbackRate=1;if(wasPlaying)video.play().catch(()=>{});};}
  else{video.removeAttribute("src");video.load();time.textContent="待生成";}
  const review=a.review,pending=a.generated?"待审阅":"待生成";
  summary.textContent=review?(review.summary_zh||review.summary||"待审阅"):pending;
  description.textContent=`下方指标对应：${s.label}。`+(arm==="global_weak"?"覆盖全有效视频和全部 20 步，α=0.25。":"共 9 个去噪步，α=1，视频范围与原引导相同。")+(c.overview?"":"其余方案正在生成，当前先展示所选方案的四列对照。");
  const sigma=c.sigma_spans[arm],oldSigma=c.sigma_spans.historical_middle;
  technicalBody.replaceChildren(element("p","note",`${c.source_id} · seed ${c.seed} · ${c.geometry.valid_frames} 有效帧 / ${fps} fps · 所选去噪步 ${s.steps_1based.join("、")}。`),element("p","note",`σ 积分跨度：所选方案 ${sigma.toFixed(5)}，原 7–15 步 ${oldSigma.toFixed(5)}。前三种方案调用次数相同，积分跨度不同。`));
  if(a.step_seconds){technicalBody.append(table(["本次实际时间","秒"],[["完整采样（含审计）",a.sampling_seconds.toFixed(2)],["首步同步间隔",a.step_seconds.first_callback_interval.toFixed(2)],["第 2–20 步同步间隔中位数",a.step_seconds.later_callback_interval_median.toFixed(2)],["第 2–20 步同步间隔范围",a.step_seconds.later_callback_interval_range.map(x=>x.toFixed(2)).join("～")]]),element("p","note",a.sampling_scope),element("p","note",a.step_seconds.scope));}
  else technicalBody.append(element("p","note","采样时间待记录。"));
  measurementBody.replaceChildren();
  const rows=[],eventLabels=Object.fromEntries(c.events.map(e=>[e.id,e.label]));
  if(c.events.length){
   const byId=Object.fromEntries((review?.events||[]).map(e=>[e.id,e]));
   rows.push(...c.events.map(e=>[e.label+"（帧）",range(e.source),range(e.native,"未出现"),range(e.fixed,"未出现"),range(byId[e.id]?.[arm],byId[e.id]?.[arm]===null?"未出现":pending)]));
   measurementBody.append(element("p","note",`帧编号从 0 开始，${fps} 帧约为 1 秒。事件区间来自逐帧观察，记录动作发生的可见过渡范围。缺失动作记“未出现”。`));
  }else{
   const ws=c.historical_window_diagnostics?.windows||[],newWindows=review?.historical_window_diagnostics?.windows||[];
   const main=ws.find(w=>String(w.window)==="50,65"),newMain=newWindows.find(w=>String(w.window)==="50,65")?.[arm];
   rows.push(["手臂动作延后（帧）","—",range(main?.native["0.3"],"无可靠结果"),range(main?.fixed["0.3"],"无可靠结果"),range(newMain?.["0.3"],newMain?.["0.3"]===null?"无可靠结果":a.generated?"待测量":"待生成")]);
   measurementBody.append(element("p","note",`主要数值比较参考第 50–65 帧的手臂方向变化，使用姿态关键点置信度 0.3 及以上的数据。正数表示延后，负数表示提前；${fps} 帧约为 1 秒。置信度是姿态模型对关键点定位的可信程度，表中同时保留 0.5 的结果及另外三个已固定的时间区间。`));
   const detailRows=[];
   for(const w of ws){const nw=newWindows.find(n=>String(n.window)===String(w.window))?.[arm];for(const confidence of ["0.3","0.5"])detailRows.push([range(w.window),confidence,range(w.native[confidence],"无可靠结果"),range(w.fixed[confidence],"无可靠结果"),range(nw?.[confidence],nw?.[confidence]===null?"无可靠结果":a.generated?"待测量":"待生成")]);}
   measurementBody.append(table(["参考视频区间（帧）","关键点置信度下限","普通编辑延后（帧）","原 7–15 延后（帧）","新方案延后（帧）"],detailRows));
  }
  rows.push(["官方 MF","—",score(c.old_MF.native),score(c.old_MF.fixed),score(a.score)]);
  tables.replaceChildren(table(["动作与指标","参考视频","普通编辑","原 7–15 步引导",s.label],rows));
  if(c.source_id===data.cases[0].source_id)tables.append(element("p","note","三组均采用 IVEBench 官方 MF（运动保真度，越高越好）；动作发生时间另由事件帧数或手臂延后帧数评价。"));
  if(a.event_summary){
   const format=v=>v?v.map(x=>x.toFixed(1)).join("～"):"未出现",label=id=>eventLabels[id]||"动作事件";
   measurementBody.append(table(["动作事件","新方案绝对时差（帧）","相对原 7–15 的误差变化（毫秒）"],a.event_summary.events.map(e=>[label(e.id),range(e.statistics?.absolute_error_frames,"未出现"),format(e.statistics?.paired_change_vs_fixed_ms)])));
   measurementBody.append(table(["相邻动作阶段","参考时长（帧）","原 7–15 时长（帧）","新方案时长（帧）","时长误差变化（毫秒）"],a.event_summary.phases.map(p=>[`${label(p.from)} → ${label(p.to)}`,range(p.statistics?.source_duration_frames,"未出现"),range(p.statistics?.fixed_duration_frames,"未出现"),range(p.statistics?.new_duration_frames,"未出现"),format(p.statistics?.paired_duration_error_change_ms)])));
  }
  frameButtons.replaceChildren();image.hidden=!display.frames.length;
  for(const f of display.frames){const b=element("button","",`第 ${f.frame} 帧`);b.onclick=()=>{for(const button of frameButtons.children)button.setAttribute("aria-pressed",String(button===b));image.src=f.url;image.alt=`${c.title} 第 ${f.frame} 帧${c.overview?"七":"四"}列对照`;};frameButtons.append(b);}
  if(display.frames.length)frameButtons.firstChild.click();
 }
 select.onchange=update;document.getElementById("cases").append(card);update();
}
