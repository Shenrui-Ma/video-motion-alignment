from pathlib import Path
import re, json, hashlib
ROOT=Path('/workspace/research-user/DevProjects/video-motion-alignment')
OUT=Path(__file__).resolve().parent
TARGET=ROOT/'reports/H3_后续改进方案_机制与最小实验_20261020.html'
old=TARGET.read_text()
if not (OUT/'before.html').exists():(OUT/'before.html').write_text(old)
# Code-native SVG follows the original figure's typography, colors, matrices and exact insertion point.
svg=['<svg viewBox="0 0 1120 630" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="cv-architecture-title"><title id="cv-architecture-title">跨时刻参考覆盖在一次H3去噪前向中的计算位置</title><defs><marker id="cv-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0 L7 3.5 L0 7Z" fill="#536780"/></marker></defs><rect width="1120" height="630" fill="white"/>']
def text(x,y,s,size=16,color='#172335',bold=False):svg.append(f'<text x="{x}" y="{y}" font-size="{size}" style="fill:{color};font-weight:{650 if bold else 400}">{s}</text>')
def rect(x,y,w,h,fill='#f4f7fb',stroke='#d9e0eb',rx=7):svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}"/>')
def arrow(x1,y1,x2,y2):svg.append(f'<path d="M{x1} {y1} L{x2} {y2}" stroke="#536780" fill="none" stroke-width="1.7" marker-end="url(#cv-arrow)"/>')
text(26,32,'A  一次去噪前向：在50个 DiT blocks 内重复计算',22,bold=True)
text(26,61,'当前实验覆盖全部20个去噪步；下图展开其中一步、其中一层。',16,'#536780')
# Token strips, with actual kind boundaries and queried submatrix.
for x,w,label,c in [(26,135,'文本','#8a97aa'),(175,135,'参考图','#7954bd'),(324,275,'参考视频','#246ac4'),(613,130,'音频','#6d9c9a'),(757,337,'生成视频 latent','#df8423')]:
 text(x,99,label,17,c,True)
 n=max(4,int(w/28))
 for k in range(n):rect(x+k*w/n,111,w/n-4,23,c,'none',2)
rect(26,161,1068,180,'#fff','#d9e0eb')
text(44,189,'主 DiT block',17,bold=True)
for x,w,label,sub,fill in [(44,140,'Q / K / V','投影 → Norm → RoPE','#f0f5fc'),(218,158,'Self-Attention','softmax(QKᵀ / √d)V','#f0f5fc'),(410,255,'参考分支输出修正','O → O′  ·  本方法作用位置','#fff3e6'),(700,130,'out_proj','合并 heads','#f5f0fb'),(864,210,'gate → residual','后续 FFN → 下一层','#f5f0fb')]:
 rect(x,212,w,75,fill);text(x+12,241,label,17,bold=True);text(x+12,268,sub,13,'#536780')
for a,b in [(184,218),(376,410),(665,700),(830,864)]:arrow(a+3,250,b-6,250)
text(45,320,'输入 Q/K/V 来自本层正在计算的特征；参考视频在本层的 K/V 参与额外 Attention。',15,'#536780')
arrow(537,287,537,367)
rect(26,370,1068,228,'#fbfcfe','#d9e0eb')
text(44,400,'B  展开橙色模块：从匹配分数到参考 Value 的加权结果',20,bold=True)
for x,w,label,sub in [(44,215,'① 时间片匹配 C[t,j]','生成 Q 与参考 K 的匹配'),(305,230,'② 联合分配 P[t,j]','时间邻域 + 行列约束'),(581,250,'③ 分别读取参考 Kⱼ / Vⱼ','各时间片内计算空间 Attention'),(877,198,'④ 混合并写回','Σⱼ P[t,j] Aᵢ,ⱼ')]:
 rect(x,422,w,89,'#fff','#cbd9e8');text(x+12,450,label,16,bold=True);text(x+12,478,sub,13,'#536780')
for a,b in [(259,305),(535,581),(831,877)]:arrow(a+4,467,b-7,467)
text(46,548,'O′ᵢ = Oᵢ + 0.25 mᵢ ( Σⱼ P[t,j] Aᵢ,ⱼ − Aᵢ,ref )',23,bold=True)
text(46,577,'mᵢ：原 softmax 分给全部参考视频 token 的概率和。修正发生在 out_proj 之前。',15,'#536780')
text(26,623,'橙色：生成视频及修改位置    蓝色：参考视频    矩阵和时间片在下方展开',14,'#536780')
svg.append('</svg>')
architecture=''.join(svg)
section='''<section id="coverage" data-revised="2026-10-23">
<style>
#coverage .cv-intro{font-size:19px;color:#314f70}#coverage .cv-figure{border:1px solid #d9e0eb;border-radius:10px;background:#fff;overflow:hidden;margin:24px -25px}#coverage .cv-figure svg{display:block;width:100%;height:auto}#coverage .cv-figure svg text{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}#coverage .cv-caption{padding:12px 20px;background:#f8fafc;font-size:14px;color:#52677f;border-top:1px solid #e1e8f0}#coverage .cv-controls{display:flex;flex-wrap:wrap;align-items:center;gap:9px;padding:16px 20px;background:#f6f8fc;border-bottom:1px solid #dde5ef}#coverage button{font:inherit;font-size:14px;border:1px solid #cbd7e5;border-radius:6px;background:white;color:#244365;padding:8px 12px;cursor:pointer}#coverage button[aria-pressed=true]{background:#245faa;color:white;border-color:#245faa}#coverage button:focus-visible{outline:3px solid #e7a54c;outline-offset:2px}#coverage .cv-rowbuttons button{padding:5px 12px}#coverage .cv-rowbuttons{display:flex;flex-wrap:wrap;gap:6px;padding:12px 20px;align-items:center;font-size:14px}#coverage .cv-panelgrid{display:grid;grid-template-columns:1fr 1fr;gap:24px;padding:8px 24px 20px}#coverage .cv-panel h4{font-size:17px;margin:6px 0 10px}#coverage .cv-panel p{font-size:14px;color:#536780;line-height:1.6;margin:10px 0 0}#coverage .cv-heatmap{width:100%;aspect-ratio:1.22;display:block}#coverage .cv-readout{border-top:1px solid #dde5ef;padding:18px 24px;background:#fcfdff}#coverage .cv-readout h4{margin:0 0 12px;font-size:18px}#coverage .cv-route{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}#coverage .cv-ref{border:1px solid #d9e0eb;border-radius:6px;padding:10px 6px;text-align:center;font-size:14px;color:#536780;background:white}#coverage .cv-ref b{display:block;font-size:19px;margin-top:4px;color:#245faa}#coverage .cv-ref.active{background:#eaf2fd;border-color:#6c9bd5}#coverage .cv-sum{font-family:Georgia,"Songti SC",serif;font-size:20px;padding:16px 0 4px;color:#213d62}#coverage .cv-mass{display:flex;height:42px;border-radius:5px;overflow:hidden;margin:12px 0;border:1px solid #d4dfea;font-size:14px;line-height:40px;text-align:center}#coverage .cv-original{width:75%;background:#e7edf5}#coverage .cv-reallocated{width:25%;background:#d9eafc;color:#164e8b}#coverage .cv-small{font-size:14px;color:#536780;line-height:1.7}#coverage details{padding:14px 18px;background:#f7f9fc;border:1px solid #dce4ee;border-radius:6px;margin:20px 0}#coverage summary{font-weight:600;cursor:pointer}#coverage .cv-equation{font:21px/1.8 Georgia,"Songti SC",serif;overflow:auto;padding:14px;background:white;margin:12px 0}#coverage .cv-formulas{display:grid;grid-template-columns:1fr 1fr;gap:12px}#coverage .cv-formulas > div{padding:16px;border:1px solid #dce4ee;border-radius:6px;font-size:16px}#coverage .cv-formulas b{display:block;color:#246ac4;margin-bottom:6px}#coverage .cv-formulas .mathline{font:20px/1.9 Georgia,serif}#coverage .cv-legend{display:flex;gap:20px;padding:0 24px 12px;font-size:13px;color:#536780}#coverage input[type=range]{width:140px;vertical-align:middle;accent-color:#246ac4}#coverage #cv-beta-control[hidden]{display:none}#coverage .cv-empty{fill:#f1f4f8}#coverage .cv-footnote{font-size:14px;color:#536780}
@media(max-width:760px){#coverage .cv-figure{margin:20px 0}#coverage .cv-panelgrid{grid-template-columns:1fr}#coverage .cv-formulas{grid-template-columns:1fr}#coverage .cv-route{grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}#coverage .cv-ref{font-size:12px}#coverage .cv-architecture{overflow:auto}#coverage .cv-architecture svg{min-width:850px}#coverage .cv-controls{padding:12px}#coverage .cv-panelgrid{padding:12px}#coverage .cv-mass{font-size:11px}}
</style>
<h2>4　跨时刻参考覆盖：共同分配相邻参考时间片</h2>
<p class="cv-intro">同时间弱引导让生成时间片 T₃ 读取参考时间片 R₃。跨时刻参考覆盖允许 T₃ 同时读取相邻的 R₁…R₅，并让所有生成时间片一起决定这些参考片段各被使用多少。</p>
<p>目的是在保持时间对应的基础上，为每个生成时刻补充相邻动作阶段的信息。<strong>两种方法都在全部20步去噪中使用 α＝0.25；差别在参考时间片的分配方式。</strong>视频时间片用 T / R 表示，去噪步是模型逐次生成视频的计算过程。</p>
<figure class="cv-figure"><div class="cv-architecture">__ARCH__</div><figcaption class="cv-caption">图 4a｜从一次去噪前向到单个 DiT block。方法根据本层 Q/K 计算时间分配，再修改生成视频的 Attention 输出，随后进入输出投影与 residual。</figcaption></figure>
<h3>4.1　从一个生成时间片，看它读取什么</h3>
<p>下图用六个 latent bins 展示分配。每个 bin 内包含整幅画面的空间 token。左图是由 Q/K 得到的时间匹配概率；右图是实际用于引导的分配矩阵。<strong>点击 T₁…T₆，查看该生成时间片读取哪些参考 bins。</strong></p>
<figure class="cv-figure" id="cv-demo">
<div class="cv-controls" role="group" aria-label="选择引导方法"><button type="button" data-cv-mode="same" aria-pressed="false">同时间弱引导</button><button type="button" data-cv-mode="coverage" aria-pressed="true">跨时刻覆盖 · 已运行</button><button type="button" data-cv-mode="mixed" aria-pressed="false">混合 · 待测试</button><label id="cv-beta-control" hidden>β <input id="cv-beta" type="range" min="0" max="1" step="0.05" value="0.25" aria-label="跨时刻混合比例"><output id="cv-beta-value">0.25</output></label></div>
<div class="cv-rowbuttons" role="group" aria-label="选择生成时间片"><span>生成时间片：</span>__ROWBUTTONS__</div>
<div class="cv-panelgrid"><div class="cv-panel"><h4>① Q/K 的时间匹配概率 C</h4><svg id="cv-raw" class="cv-heatmap" viewBox="0 0 430 350" role="img" aria-label="原始时间匹配概率"></svg><p>每行独立归一化。示例中多个生成时刻都偏向 R₃，导致其他参考片段被读取得较少。</p></div><div class="cv-panel"><h4 id="cv-matrix-title">② 联合分配后的 P</h4><svg id="cv-balanced" class="cv-heatmap" viewBox="0 0 430 350" role="img" aria-label="引导时间分配矩阵"></svg><p id="cv-matrix-note">每行、每列之和均为1；在相邻时间片之间分配，同时保持匹配时刻的期望顺序。</p></div></div>
<div class="cv-legend"><span>行：生成时间 T</span><span>列：参考时间 R</span><span>蓝色越深，比例越高</span></div>
<div class="cv-readout" aria-live="polite"><h4 id="cv-read-title">T₃ 的参考 Attention</h4><div class="cv-route" id="cv-route"></div><div id="cv-expression" class="cv-sum"></div><p id="cv-explanation" class="cv-small"></p>
<div class="cv-mass"><span class="cv-original">参考分支：75% 原有分配</span><span class="cv-reallocated">25% 新分配</span></div><p class="cv-small">α＝0.25：将参考视频原有 Attention 概率的25%按右图重新分配。总参考概率 mᵢ 保持相同；实际修正为两种参考 Attention 输出之差。</p></div>
<figcaption class="cv-caption">图 4b｜可交互的机制示例。图中的数值由合成匹配矩阵计算，用于解释时间分配；实验数据在本节末尾单列。</figcaption>
</figure>
<h3>4.2　联合分配怎样约束时间</h3>
<p>每个生成 bin 的候选范围是对应参考 bin 的前后各2个。模型先计算匹配分数，再求一个分配矩阵 P：每行总和为1，使该生成 bin 得到完整的参考混合；每列总和为1，约束各参考 bin 在整段视频中的累计分配。离对应时刻越远，分配代价越大。若匹配时刻的期望顺序发生反转，再将 P 向同时间分配收缩。</p>
<p>这里的列约束作用于<strong>时间分配矩阵 P</strong>。每个 Query / head 的总参考概率 mᵢ 仍来自原 Attention。P 在每个去噪步、每个 DiT block 重新计算；本层生成视频的各 head 和空间 Query 共用这一时间分配。</p>
<details><summary>展开数学定义与实际计算</summary>
<p>从本层生成视频 Q 中采样最多4个 heads、每个时间片8个空间位置，与参考视频 K 计算匹配。对参考 bin 内所有空间 keys 汇总 softmax 概率，再对采样位置和 heads 平均，得到 C[t,j]。</p>
<div class="cv-equation">min<sub>P≥0</sub> Σ<sub>t,j</sub> P<sub>t,j</sub> [−log C<sub>t,j</sub> + 0.25(t−j)²] + 0.5 Σ<sub>t,j</sub> P<sub>t,j</sub> log P<sub>t,j</sub><br>Σ<sub>j</sub>P<sub>t,j</sub> = 1，Σ<sub>t</sub>P<sub>t,j</sub> = 1，P<sub>t,j</sub> = 0 当 |t−j| &gt; 2</div>
<p>实现用 CPU float64 的阻尼 Newton 求解这个小矩阵，再检查期望参考时间是否按生成时间递增。求解失败时，使用同时间弱引导。随后在 GPU 上对每个候选参考 bin 分别计算 Attention(Qᵢ, Kⱼ, Vⱼ)，按 P[t,j] 加权。</p>
<div class="cv-equation">A<sub>i,j</sub> = softmax(QᵢKⱼᵀ / √d) Vⱼ<br>O′ᵢ = Oᵢ + α mᵢ [Σⱼ P<sub>t,j</sub>A<sub>i,j</sub> − A<sub>i,ref</sub>]</div>
<p>i 表示生成 bin t 内的一个空间 Query 和一个 head；Aᵢ,ref 是该 Query 读取全部参考视频得到的归一化输出。改变的是生成视频对参考视频 Value 的加权组合，写入位置在各 head 的 Attention 输出之后、out_proj 之前。</p>
</details>
<h3>4.3　与全程弱引导怎样结合</h3>
<div class="cv-formulas"><div><b>同时间弱引导</b>引导目标为 Aᵢ,ₜ，只读取对应参考 bin。<div class="mathline">P = I</div></div><div><b>当前跨时刻覆盖</b>引导目标为 ΣⱼP[t,j]Aᵢ,ⱼ，读取相邻参考 bins。<div class="mathline">P = 联合分配矩阵</div></div></div>
<p>二者可以在同一个修正公式里混合：保留一部分同时间 Attention，再加入跨时刻参考信息。上方“混合”按钮展示这一候选。α 继续控制总修正强度，β 控制其中跨时刻分配的占比。</p>
<div class="cv-equation">P<sub>mix</sub> = (1−β) I + β P<br>O′ᵢ = Oᵢ + 0.25 mᵢ [Σⱼ P<sub>mix</sub>[t,j] A<sub>i,j</sub> − A<sub>i,ref</sub>]</div>
<p>β＝0 是同时间弱引导；β＝1 是已运行的跨时刻覆盖。β＝0.25 时，引导目标由75%同时间 Attention 和25%跨时刻 Attention 组成。这个混合版本待测试。</p>
<h3>4.4　已完成的对照结果</h3>
<p>以下为已完成并测得 MF 的前三组，均保持各样例原 prompt、seed、模型和视频几何，全部20步使用 α＝0.25。</p>
<table><thead><tr><th>任务</th><th>普通编辑 MF ↑</th><th>全程弱引导 MF ↑</th><th>跨时刻覆盖 MF ↑</th></tr></thead><tbody><tr><td>机舱人物替换</td><td>0.813284</td><td><strong>0.820370</strong></td><td>0.820087</td></tr><tr><td>饮酒男子戴眼镜</td><td>0.891874</td><td><strong>0.898978</strong></td><td>0.897354</td></tr><tr><td>书本改蓝色</td><td>0.879149</td><td><strong>0.912596</strong></td><td>0.910825</td></tr><tr><td>三组均值</td><td>0.861436</td><td><strong>0.877315</strong></td><td>0.876089</td></tr></tbody></table>
<p><strong>三组的跨时刻覆盖均优于普通编辑，略低于同时间全程弱引导。</strong>两条首测视频各1000次路由全部求解成功；求解器累计耗时分别为3.85秒和3.49秒，采样约59–61秒/步。其余同组实验继续运行。</p>
<p class="cv-footnote">本节更新于2026年10月23日。方法对应 temporal_coverage_v2；图中的合成数值与表中的真实实验结果分别标注。</p>
<script>
(()=>{
const root=document.getElementById('coverage'),n=6;
// Illustrative Q/K preference: several neighboring output bins favor reference bin 3.
const logits=Array.from({length:n},(_,t)=>Array.from({length:n},(_,j)=>-.38*(t-j)**2+(j===2?2.25:0)+.12*Math.cos((t+1)*(j+2))));
const raw=logits.map(row=>{const a=row.map(Math.exp),s=a.reduce((x,y)=>x+y,0);return a.map(x=>x/s)});
let P=logits.map((row,t)=>row.map((v,j)=>Math.abs(t-j)<=2?Math.exp((v-.25*(t-j)**2)/.5):0));
for(let k=0;k<2000;k++){P=P.map(row=>{const s=row.reduce((a,b)=>a+b,0);return row.map(x=>x/s)});const sums=Array.from({length:n},(_,j)=>P.reduce((s,row)=>s+row[j],0));P=P.map(row=>row.map((x,j)=>x/sums[j]));}
const means=P.map(row=>row.reduce((s,x,j)=>s+x*j,0));let gamma=1;for(let i=0;i<n-1;i++)if(means[i+1]<means[i])gamma=Math.min(gamma,1/(1-(means[i+1]-means[i])));
P=P.map((row,t)=>row.map((x,j)=>gamma*x+(1-gamma)*(t===j?1:0)));
let selected=2,mode='coverage';const el=id=>root.querySelector('#'+id),fmt=x=>(100*x).toFixed(1)+'%';
function matrix(){const b=mode==='same'?0:mode==='mixed'?Number(el('cv-beta').value):1;return P.map((row,t)=>row.map((v,j)=>b*v+(1-b)*(t===j?1:0)))}
function heat(id,M){let s='<text x="70" y="20" font-size="13" fill="#536780">参考时间 R →</text>';const size=40,x0=70,y0=43;
for(let j=0;j<n;j++)s+=`<text x="${x0+j*size+20}" y="37" text-anchor="middle" font-size="13">R${j+1}</text>`;
for(let t=0;t<n;t++){s+=`<text x="55" y="${y0+t*size+25}" text-anchor="end" font-size="14" style="fill:${t===selected?'#c4771a':'#536780'};font-weight:${t===selected?700:400}">T${t+1}</text>`;for(let j=0;j<n;j++){const v=M[t][j],a=.04+.9*Math.sqrt(v),fill=`rgb(${Math.round(255-219*a)},${Math.round(255-149*a)},${Math.round(255-59*a)})`;s+=`<rect x="${x0+j*size}" y="${y0+t*size}" width="40" height="40" fill="${fill}" stroke="white"/><text x="${x0+j*size+20}" y="${y0+t*size+25}" text-anchor="middle" font-size="12" style="fill:${v>.4?'white':'#284663'}">${v<.005?'·':Math.round(v*100)}</text>`;}s+=`<text x="326" y="${y0+t*size+25}" font-size="12" style="fill:#536780">Σ ${M[t].reduce((a,b)=>a+b,0).toFixed(1)}</text>`;}
s+=`<rect x="${x0-2}" y="${y0+selected*size-2}" width="244" height="44" rx="3" fill="none" stroke="#df8423" stroke-width="2.5"/>`;
s+='<text x="55" y="309" text-anchor="end" font-size="12">列和</text>';for(let j=0;j<n;j++){const sum=M.reduce((a,row)=>a+row[j],0);s+=`<text x="${x0+j*size+20}" y="309" text-anchor="middle" font-size="13" style="fill:${sum>1.1?'#b36316':'#246ac4'}">${sum.toFixed(2)}</text>`;}s+='<text x="70" y="338" font-size="12" style="fill:#536780">格内数字为百分比；· 表示小于0.5%</text>';el(id).innerHTML=s;}
function render(){const M=matrix(),row=M[selected];heat('cv-raw',raw);heat('cv-balanced',M);el('cv-route').innerHTML=row.map((v,j)=>`<div class="cv-ref ${v>.005?'active':''}">参考 R${j+1}<b>${fmt(v)}</b></div>`).join('');el('cv-read-title').textContent=`T${selected+1} 的参考 Attention：按下列比例混合`;
el('cv-expression').textContent=row.map((v,j)=>v>.0005?`${v.toFixed(3)} Aᵢ,${j+1}`:'').filter(Boolean).join(' + ');
el('cv-explanation').textContent='Aᵢ,ⱼ 表示这个 Query 在参考 Rⱼ 内，对全部空间 token 计算 Attention 后得到的 Value 加权结果。';
el('cv-beta-control').hidden=mode!=='mixed';el('cv-beta-value').value=Number(el('cv-beta').value).toFixed(2);
el('cv-matrix-title').textContent=mode==='same'?'② 对应时间片：P = I':mode==='mixed'?'② 混合分配：(1−β)I + βP':'② 联合分配后的 P';
el('cv-matrix-note').textContent=mode==='same'?'每个生成时间片只在对应参考时间片内计算引导 Attention。':mode==='mixed'?'保留同时间约束，再混入跨时刻分配。行列和保持为1；此配置待实验。':'每行、每列之和均为1；在相邻时间片之间分配，同时保持匹配时刻的期望顺序。';
root.querySelectorAll('[data-cv-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.cvMode===mode)));root.querySelectorAll('[data-cv-row]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.cvRow)===selected)));
}
root.querySelectorAll('[data-cv-mode]').forEach(b=>b.addEventListener('click',()=>{mode=b.dataset.cvMode;render()}));root.querySelectorAll('[data-cv-row]').forEach(b=>b.addEventListener('click',()=>{selected=Number(b.dataset.cvRow);render()}));el('cv-beta').addEventListener('input',render);render();
window.coverageDemo={raw,P,getState:()=>({selected,mode,beta:Number(el('cv-beta').value),matrix:matrix()})};
})();
</script>
</section>'''.replace('__ARCH__',architecture).replace('__ROWBUTTONS__',''.join(f'<button type="button" data-cv-row="{i}" aria-pressed="{str(i==2).lower()}">T{i+1}</button>' for i in range(6)))
new,n=re.subn(r'<section id="coverage".*?</section>',lambda m:section,old,flags=re.S);assert n==1
# Update the one header sentence that incorrectly described every method as untested.
new=new.replace('本文件用于选择下一轮实验。下文四个候选尚未生成实验视频；本轮五组“时序引导＋相位对齐”结果单独展示。架构图中的矩阵与曲线均为机制示意。','本文件保留2026年10月20日的方案讨论。第4节已按2026年10月23日的实现与实验更新；架构图中的矩阵与曲线为机制示意。')
TARGET.write_text(new)
(OUT/'coverage_section.html').write_text(section)
(OUT/'change_record.json').write_text(json.dumps({'target':str(TARGET),'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest(),'scope':['coverage section','header status sentence'],'no_inference_code_changed':True},ensure_ascii=False,indent=2))
print(TARGET, len(new))
