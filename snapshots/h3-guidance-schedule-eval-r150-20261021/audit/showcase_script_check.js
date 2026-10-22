
const D=JSON.parse(document.getElementById('data').textContent);
const roles=D.roles, labels={source:'参考视频',native:'普通编辑',early:'1–9 步',fixed:'7–15 步',late:'12–20 步',split:'1–4＋16–20 步',global_weak:'全程弱引导'};
const arms=['early','late','split','global_weak'];
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const verdict=x=>({PASS_CORE_EDIT:'编辑成功',PARTIAL_EDIT:'部分完成／有副作用',FAIL_CORE_EDIT:'编辑失败',FAIL_POSITION_EDIT:'位置编辑失败'}[x]||x||'待审阅');
function interval(v,s){if(!Array.isArray(v))return'未出现／未能标注';const label=v.join('–');if(!Array.isArray(s))return label;const d=((v[0]+v[1])-(s[0]+s[1]))/2;return`${label}<br><span class="muted">${d>0?'+':''}${d} 帧</span>`}
function eventCell(c,e,r){if(r==='source')return Array.isArray(e.source)?e.source.join('–'):'宽阶段 '+(e.source_phase_interval||[]).join('–');
 if(e.measurement_kind==='previously_reviewed_broad_phase_interval'){if(r==='native')return'原阶段近同步';if(r==='fixed')return'沿用旧全片审核';const a=c.arms[r];return a?.review?'见保持性结论':a?.status||'待生成'}
 if(r==='native'||r==='fixed')return interval(e[r],e.source);const a=c.arms[r];if(!a?.review)return a?.status||'待生成';const n=a.review.events?.find(x=>x.id===e.id);return interval(n?.[r],e.source)}
function lagCell(c,r){if(r==='source')return'0';const review=Object.values(c.arms).find(x=>x.review)?.review;const original=review?.historical_window_diagnostics?.windows?.[0];if(r==='native'||r==='fixed')return original?.[r]?.['0.3']??'未测';
 const a=c.arms[r];return a.review?.historical_window_diagnostics?.windows?.[0]?.[r]?.['0.3']??(a.review?'未测':a.status)}
function table(c){const head='<tr><th>评估项</th>'+roles.map(r=>'<th>'+labels[r]+'</th>').join('')+'</tr>';let rows='';
 rows+='<tr><td>编辑验收</td>'+roles.map(r=>'<td>'+(r==='source'?'参考':r==='native'||r==='fixed'?'历史已审阅':verdict(c.arms[r].review?.task_verdict))+'</td>').join('')+'</tr>';
 for(const e of c.events)rows+='<tr><td>'+esc(e.label)+'</td>'+roles.map(r=>'<td>'+eventCell(c,e,r)+'</td>').join('')+'</tr>';
 if(!c.events.length)rows+='<tr><td>手臂动作延后（帧）</td>'+roles.map(r=>'<td>'+lagCell(c,r)+'</td>').join('')+'</tr>';
 rows+='<tr><td>MF ↑</td>'+roles.map(r=>{const s=r==='source'?null:(r==='native'||r==='fixed'?c.old_MF[r]:c.arms[r].score);return'<td>'+(r==='source'?'—':s==null?'待评分':Number(s).toFixed(4))+'</td>'}).join('')+'</tr>';
 rows+='<tr><td>实际采样时间</td>'+roles.map(r=>'<td>'+(['source','native','fixed'].includes(r)?'—':c.arms[r].sampling_seconds==null?'待生成':(c.arms[r].sampling_seconds/60).toFixed(2)+' 分钟')+'</td>').join('')+'</tr>';
 return'<div class="scroll"><table>'+head+rows+'</table></div>'}
function draw(c,i){const section=document.createElement('section');section.className='task';section.id='case-'+i;
 const link=document.createElement('a');link.href='#'+section.id;link.textContent=`${i+1}. ${c.title}`;document.getElementById('nav').appendChild(link);
 section.innerHTML='<h2>'+esc(c.title)+'</h2>';
 if(c.pending){section.innerHTML+='<div class="pending">'+esc(c.reason)+'</div>';return section}
 section.innerHTML+='<p class="muted">'+esc(c.dataset)+' · '+c.geometry.valid_frames+' 有效帧 · 24 fps'+(c.preservation?' · 动作保持性检验':'')+'</p>';
 if(c.overview){section.innerHTML+='<div class="toolbar"><label>同帧截图 <select class="frame"></select></label><button class="zoom">放大／适应宽度</button><button class="full">视频全屏</button></div><div class="viewport shots"><img alt="七列同帧对照，黑底中文标签"></div><div class="viewport playback"><video controls preload="metadata" playsinline></video></div>';
 const select=section.querySelector('.frame');for(const f of c.overview.frames){const op=document.createElement('option');op.value=f.url;op.textContent='第 '+f.frame+' 帧';select.appendChild(op)}const img=section.querySelector('img');if(select.value)img.src=select.value;select.onchange=()=>img.src=select.value;
 const video=section.querySelector('video');video.src=c.overview.video;section.querySelector('.zoom').onclick=()=>section.querySelectorAll('.viewport').forEach(x=>x.classList.toggle('zoom'));section.querySelector('.full').onclick=()=>{if(video.requestFullscreen)video.requestFullscreen()};
 }else section.innerHTML+='<p class="pending">完整七列视频将在本组各版本到齐后显示。</p>';
 section.innerHTML+=table(c);
 for(const a of arms){const r=c.arms[a].review;if(r?.summary_zh)section.innerHTML+='<p class="summary"><strong>'+labels[a]+'：</strong>'+esc(r.summary_zh)+'</p>'}
 section.innerHTML+='<details><summary>提示词、参考图与测量说明</summary><p>'+esc(c.prompt_source_label)+'；'+(c.reference_image?'使用人物参考图':'无人物参考图')+'。</p><pre>'+esc(c.prompt)+'</pre><p class="notes">帧号从 0 开始；表内时差为标注区间中点之差。动作未出现时保留缺项。采样时间取实际 sampler wall，含捕获和审计回调；成片后的离线评分另计。手臂延后沿冻结 50–65 帧窗口、confidence 0.3；0.5 与其他窗口保留在原离线记录。各任务沿用其真实历史提示词、输入和噪声条件。</p></details>';
 // innerHTML append recreates nodes; install native media controls after all content is assembled.
 if(c.overview){const sel=section.querySelector('.frame'),img=section.querySelector('img'),video=section.querySelector('video');sel.onchange=()=>img.src=sel.value;section.querySelector('.zoom').onclick=()=>section.querySelectorAll('.viewport').forEach(x=>x.classList.toggle('zoom'));section.querySelector('.full').onclick=()=>video.requestFullscreen?.()}
 return section}
D.cases.forEach((c,i)=>document.getElementById('cases').appendChild(draw(c,i)));
