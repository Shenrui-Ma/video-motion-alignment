
const D=JSON.parse(document.getElementById('data').textContent);
const roles=D.roles, labels={source:'参考视频',native:'普通编辑',early:'1–9 步',fixed:'7–15 步',late:'12–20 步',split:'1–4＋16–20 步',global_weak:'全程弱引导'};
const arms=['early','late','split','global_weak'];
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const verdict=x=>({PASS_CORE_EDIT:'编辑成功',PARTIAL_EDIT:'部分完成／有副作用',FAIL_CORE_EDIT:'编辑失败',FAIL_POSITION_EDIT:'位置编辑失败'}[x]||x||'待审阅');
const signed=(value,digits=2)=>{if(value==null)return'未测';const v=Number(Number(value).toFixed(digits));return(v>0?'+':'')+v};
function outcomeTable(){
 const rank=D.ranking;
 const rows=rank.rows.map((r,i)=>'<tr class="'+(i===0?'best':'')+'"><td>'+(i+1)+'</td><td>'+labels[r.role]+'</td><td>'+r.mean_absolute_frames.toFixed(2)+'</td><td>'+r.edit_passed+' / '+r.edit_total+'</td></tr>').join('');
 const nativePassed=D.cases.filter(c=>c.control_verdicts.native==='PASS_CORE_EDIT').length;
 const nativeRow='<tr><td>—</td><td>普通编辑</td><td>'+rank.native_mean_absolute_frames.toFixed(2)+'</td><td>'+nativePassed+' / '+D.cases.length+'</td></tr>';
 document.getElementById('outcomes').innerHTML='<h2>引导效果排名</h2><p>按7组时间偏移任务的平均绝对偏移排序，越小越好。</p><div class="scroll"><table class="ranking"><tr><th>排名</th><th>编辑方式／引导区间</th><th>平均绝对偏移（帧）↓</th><th>编辑成功</th></tr>'+rows+nativeRow+'</table></div>';
}
function eventCell(c,e,r){
 if(e.measurement_kind==='previously_reviewed_broad_phase_interval')return'未测';
 const value=c.event_offsets[e.id][r];
 return value==null?'动作未出现':signed(value)+' 帧';
}
function lagCell(c,r){const v=c.arm_offsets[r];return v==null?'未测':signed(v)+' 帧'}
function bindPlayer(player, fps, frameCount){
 const video=player.querySelector('video'), play=player.querySelector('.play'), slider=player.querySelector('.seek'), output=player.querySelector('output');
 const previous=player.querySelector('.previous'), next=player.querySelector('.next');
 const clamp=f=>Math.max(0,Math.min(frameCount-1,Math.round(f)));
 const frame=()=>clamp(Math.floor(video.currentTime*fps+1e-4));
 slider.max=frameCount-1;
 function update(){const f=frame();slider.value=f;output.value=`${f} / ${frameCount-1} 帧 · ${(f/fps).toFixed(2)}s`;play.textContent=video.paused?'播放':'暂停';play.setAttribute('aria-label',video.paused?'播放对比视频':'暂停对比视频')}
 function seek(f){video.pause();video.currentTime=clamp(f)/fps;update()}
 function ready(){[play,slider,previous,next].forEach(x=>x.disabled=false);update()}
 [play,slider,previous,next].forEach(x=>x.disabled=true);
 slider.oninput=()=>seek(Number(slider.value));
 previous.onclick=()=>seek(frame()-1);next.onclick=()=>seek(frame()+1);
 play.onclick=()=>{if(video.paused){if(video.ended)video.currentTime=0;video.play().catch(error=>{update();if(error.name!=='AbortError')output.value='播放失败，请重试'})}else video.pause()};
 video.addEventListener('loadedmetadata',ready);
 for(const event of ['timeupdate','seeked','play','pause','ended'])video.addEventListener(event,update);
 video.addEventListener('error',()=>{output.value='视频加载失败'});
 if(video.readyState>=1)ready();else update();
}
function table(c){const head='<tr><th>评估项</th>'+roles.map(r=>'<th>'+labels[r]+'</th>').join('')+'</tr>';let rows='';
 rows+='<tr><td>编辑结果</td>'+roles.map(r=>'<td>'+(r==='source'?'参考':r==='native'||r==='fixed'?verdict(c.control_verdicts[r]):verdict(c.arms[r].review?.task_verdict))+'</td>').join('')+'</tr>';
 for(const e of c.events)rows+='<tr><td>'+esc(e.label)+'</td>'+roles.map(r=>'<td>'+eventCell(c,e,r)+'</td>').join('')+'</tr>';
 if(!c.events.length)rows+='<tr><td>手臂动作延后（帧）</td>'+roles.map(r=>'<td>'+lagCell(c,r)+'</td>').join('')+'</tr>';
 if(c.mean_absolute_offset.native!=null)rows+='<tr><td>平均绝对偏移 ↓</td>'+roles.map(r=>'<td>'+(c.mean_absolute_offset[r]==null?'未测':c.mean_absolute_offset[r].toFixed(2)+' 帧')+'</td>').join('')+'</tr>';
 rows+='<tr><td>MF（参考值 / Δ）</td>'+roles.map(r=>{const value=r==='native'||r==='fixed'?c.old_MF[r]:c.arms[r]?.score;if(r==='source')return'<td>'+c.source_MF.toFixed(4)+'</td>';if(value==null)return'<td>待评分</td>';const delta=value-c.source_MF;return'<td>'+(delta>0?'+':'')+delta.toFixed(4)+'</td>'}).join('')+'</tr>';
 return'<div class="scroll"><table>'+head+rows+'</table></div>'}
function draw(c,i){const section=document.createElement('section');section.className='task';section.id='case-'+i;
 const link=document.createElement('a');link.href='#'+section.id;link.textContent=`${i+1}. ${c.title}`;document.getElementById('nav').appendChild(link);
 section.innerHTML='<h2>'+esc(c.title)+'</h2>';
 if(c.pending){section.innerHTML+='<div class="pending">'+esc(c.reason)+'</div>';return section}
 section.innerHTML+='<p class="muted">'+esc(c.dataset)+' · '+c.geometry.valid_frames+' 有效帧 · 24 fps'+(c.preservation?' · 动作保持性检验':'')+'</p>';
 if(c.overview){section.innerHTML+='<div class="toolbar"><label>同帧截图 <select class="frame"></select></label><button class="zoom">放大／适应宽度</button><button class="full">视频全屏</button></div><div class="viewport shots"><img alt="七列同帧对照，黑底中文标签"></div><div class="player"><div class="player-screen"><video preload="metadata" playsinline></video></div><div class="playbar"><button class="play" disabled>播放</button><button class="previous" aria-label="上一帧" disabled>上一帧</button><input class="seek" type="range" min="0" step="1" value="0" aria-label="视频帧进度" disabled><button class="next" aria-label="下一帧" disabled>下一帧</button><output aria-label="当前帧与时间"></output></div></div>';
 const select=section.querySelector('.frame');for(const f of c.overview.frames){const op=document.createElement('option');op.value=f.url;op.textContent='第 '+f.frame+' 帧';op.selected=f.frame===c.overview.default_frame;select.appendChild(op)}const img=section.querySelector('img');if(select.value)img.src=select.value;select.onchange=()=>img.src=select.value;
 const video=section.querySelector('video');video.src=c.overview.video;
 }else section.innerHTML+='<p class="pending">完整七列视频将在本组各版本到齐后显示。</p>';
 section.innerHTML+=table(c);
 section.innerHTML+='<p class="summary">'+esc(c.display_summary)+'</p>';
 const actualSchedules=Object.fromEntries(arms.filter(a=>c.arms[a].schedule_parameters).map(a=>[labels[a],c.arms[a].schedule_parameters]));
 if(Object.keys(actualSchedules).length)section.innerHTML+='<details><summary>实际引导步、强度与 σ 积分跨度</summary><p class="notes">下列参数来自各成片运行记录。actual_routed_steps_zero_based 使用从 0 开始的采样步编号；physical_query_window 是从 0 开始的物理视频帧范围。</p><pre>'+esc(JSON.stringify(actualSchedules,null,2))+'</pre></details>';
 section.innerHTML+='<details><summary>提示词、参考图与测量说明</summary><p>'+esc(c.prompt_source_label)+'；'+(c.reference_image?'使用人物参考图':'无人物参考图')+'。</p><pre>'+esc(c.prompt)+'</pre><p class="notes">表内时差为对应动作时间之差。动作未出现时单独标出。采样时间取实际 sampler wall，含捕获和审计回调；成片后的离线评分另计。手臂延后沿冻结 50–65 帧窗口、confidence 0.3；0.5 与其他窗口保留在原离线记录。各任务沿用其真实历史提示词、输入和噪声条件。</p></details>';
 // Bind after assembling the section because innerHTML append recreates media nodes.
 if(c.overview){const sel=section.querySelector('.frame'),img=section.querySelector('img'),player=section.querySelector('.player');const chosen=c.overview.frames.find(f=>f.frame===c.overview.default_frame);if(chosen){sel.value=chosen.url;img.src=chosen.url}sel.onchange=()=>img.src=sel.value;section.querySelector('.zoom').onclick=()=>section.querySelector('.shots').classList.toggle('zoom');section.querySelector('.full').onclick=async()=>{if(document.fullscreenElement===player)await document.exitFullscreen();else if(player.requestFullscreen)await player.requestFullscreen();else if(player.webkitRequestFullscreen)player.webkitRequestFullscreen()};bindPlayer(player,c.geometry.fps,c.geometry.valid_frames)}
 return section}
outcomeTable();
[...D.cases].sort((a,b)=>Number(a.preservation)-Number(b.preservation)).forEach((c,i)=>document.getElementById('cases').appendChild(draw(c,i)));
