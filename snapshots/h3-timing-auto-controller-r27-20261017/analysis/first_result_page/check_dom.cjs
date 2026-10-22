const fs=require('fs'),assert=require('assert'),crypto=require('crypto');
const {JSDOM}=require('/Users/researcher/DevProjects/openclaw/node_modules/jsdom');
const html=fs.readFileSync('/Users/researcher/Downloads/H3_自动动作窗口_初步结果_20261017.html','utf8');
const dom=new JSDOM(html,{runScripts:'outside-only'}),w=dom.window,d=w.document;
w.fetch=()=>{throw Error('offline')};w.XMLHttpRequest=class{constructor(){throw Error('offline')}};w.requestAnimationFrame=()=>0;
w.HTMLMediaElement.prototype.pause=function(){};w.HTMLMediaElement.prototype.play=function(){return Promise.resolve()};
for(const s of d.querySelectorAll('script'))w.eval(s.textContent);
assert.equal(d.querySelectorAll('video').length,8);assert.equal(d.querySelectorAll('#videos video').length,4);assert.equal(d.querySelectorAll('#normal-videos video').length,2);assert.equal(d.querySelectorAll('#joint-videos video').length,2);assert.equal(d.querySelectorAll('#rows tr').length,20);assert.equal(d.querySelectorAll('#rows .on').length,1);
assert.equal(d.querySelector('#rows .on td').textContent,'4');
assert.equal(d.querySelectorAll('script[src],link[rel=stylesheet],iframe').length,0);
const manifest=JSON.parse(fs.readFileSync(__dirname+'/manifest.json','utf8'));
assert.equal(crypto.createHash('sha256').update(html).digest('hex'),manifest.sha256);
const outcome=JSON.parse(fs.readFileSync(__dirname+'/../priority_final_outcome/SUMMARY.json','utf8'));
assert.equal(crypto.createHash('sha256').update(fs.readFileSync(__dirname+'/../priority_final_outcome/SUMMARY.json')).digest('hex'),manifest.priority_summary_sha256);
const rows=[...d.querySelectorAll('#metrics tr')];assert.equal(rows.length,8);
const methods=['bad_native','bad_fixed_full','auto'];
const expected=[];for(const window of [[50,65],[69,81],[80,92],[99,111]])for(const feature of ['arm_direction','wrist_relative']){
 expected.push([window.join('–'),feature==='arm_direction'?'双臂方向':'相对手腕',...methods.map(m=>['0.3','0.5'].map(c=>{const r=outcome.fixed[m][c].find(r=>r.window[0]===window[0]&&r.window[1]===window[1]&&r.feature===feature);return r.lag===null?'UNKNOWN':String(r.lag)}).join(' / '))]);
}
rows.forEach((r,i)=>assert.deepEqual([...r.cells].map(x=>x.textContent),expected[i]));
assert.equal(d.querySelectorAll('#scans tr').length,3);assert.equal(d.querySelectorAll('#common tr').length,4);
assert(d.querySelector('#primary-result').textContent.includes('12–13 帧，自动引导后为 1–2 帧'));
assert(d.body.textContent.includes('样本量仍是一条开发视频'));assert(d.body.textContent.includes('UNKNOWN'));
assert(d.body.textContent.includes('同一源视频的两个已见种子'));assert(d.body.textContent.includes('20 个在线观测的数值重放'));assert(!d.body.textContent.includes('正常种子与全新素材的自动控制结果待完成'));
const videos=[...d.querySelectorAll('video')];videos.forEach((v,i)=>{assert(v.src.startsWith('data:video/mp4;base64,'));const sha=crypto.createHash('sha256').update(Buffer.from(v.src.split(',')[1],'base64')).digest('hex');assert.equal(sha,manifest.assets[Number(v.dataset.assetIndex)].sha256)});
d.getElementById('seek').value=55;d.getElementById('seek').dispatchEvent(new w.Event('input'));videos.forEach(v=>assert.equal(v.currentTime,55/24));
d.getElementById('next').click();videos.forEach(v=>assert.equal(v.currentTime,56/24));d.getElementById('prev').click();videos.forEach(v=>assert.equal(v.currentTime,55/24));d.getElementById('reset').click();videos.forEach(v=>assert.equal(v.currentTime,0));
d.getElementById('speed').value='0.5';d.getElementById('speed').dispatchEvent(new w.Event('change'));videos.forEach(v=>assert.equal(v.playbackRate,.5));
const path=require('path');
const normalRoot=path.resolve(__dirname,'../postrun/captured/r27_s05_normal1313_auto');
const gate=JSON.parse(fs.readFileSync(path.join(normalRoot,'RUN_GATE.json')));
assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(normalRoot,'RUN_GATE.json'))).digest('hex'),manifest.normal_gate_sha256);
const normalCase=gate.runtime.cases.find(x=>x.run==='r27_s05_normal1313_auto');assert(normalCase.all_OFF_final_exact);assert.equal(normalCase.NFE,20);assert.equal(normalCase.mask.length,0);
const nr=[...d.querySelectorAll('#normal-rows tr')];assert.equal(nr.length,20);nr.forEach((row,i)=>{assert.equal(row.cells[0].textContent,String(i));assert.equal(row.cells[1].textContent,'native')});
assert(d.querySelector('#normal-result').textContent.includes('Full 触发 0 次'));assert(d.querySelector('#normal-result').textContent.includes('视频／音频 latent'));
const jroot='/Users/researcher/DevProjects/h3-timing-forward-reverse-r30-20261017/analysis/postrun/captured/batch';
const jf=JSON.parse(fs.readFileSync(jroot+'/final/r30_s05_forward_full_reverse_block_6to14/FIXED_WINDOWS.json')).results;
const jrows=[...d.querySelectorAll('#joint-metrics tr')];assert.equal(jrows.length,8);
let jn=0;for(const window of [[50,65],[69,81],[80,92],[99,111]])for(const feature of ['arm_direction','wrist_relative']){
 const actual=[...jrows[jn++].cells].map(x=>x.textContent);const expected=[window.join('–'),feature==='arm_direction'?'双臂方向':'相对手腕',...['N','F','B','FB'].map(m=>['0.3','0.5'].map(c=>{const x=jf[m][c].diagnostics.find(x=>x.window[0]===window[0]&&x.window[1]===window[1]&&x.feature===feature);return x.reliable_lag_frames===null?'UNKNOWN':String(x.reliable_lag_frames)}).join(' / '))];assert.deepEqual(actual,expected);
}
assert.equal(d.querySelectorAll('#joint-common tr').length,6);assert(d.querySelector('#joint-result').textContent.includes('4 / 4 帧'));assert(d.querySelector('#joint-quality').textContent.includes('UNKNOWN'));
assert(d.querySelector('#joint-quality').textContent.includes('未完成连续视频'));
d.querySelector('[data-frame="86"]').click();videos.forEach(v=>assert.equal(v.currentTime,86/24));d.querySelector('[data-control="reset"]').click();videos.forEach(v=>assert.equal(v.currentTime,0));
assert.equal(new Set(videos.map(v=>v.dataset.assetIndex)).size,7);
const oldTemplate=fs.readFileSync(__dirname+'/review/before_normal_joint_update/template.html','utf8');
const oldCSS=oldTemplate.match(/<style>([\s\S]*?)<\/style>/)[1];let newCSS=html.match(/<style>([\s\S]*?)<\/style>/)[1];
newCSS=newCSS.replace('.grid.pair{grid-template-columns:repeat(2,minmax(0,1fr))}','').replace('@media(max-width:550px){.grid,.grid.pair{','@media(max-width:550px){.grid{');assert.equal(newCSS,oldCSS);
const result={passed:true,embedded_assets:7,displayed_videos:8,normal_gate_exact:true,normal_OFF_rows:20,joint_metric_rows:8,joint_metrics_match_actual:true,original_CSS_preserved_with_pair_grid:true,asset_sha_exact:true,decision_rows:20,selected_denoising_index:4,fixed_metric_rows:8,fixed_metrics_match_actual_summary:true,whole_scan_rows:3,common_support_rows:4,UNKNOWN_retained:true,seek_buttons_and_speed:true,external_runtime_assets:0,scope:'offline DOM/control-state and byte checks; browser layout and actual media playback unassessed'};fs.writeFileSync(__dirname+'/DOM_CHECK.json',JSON.stringify(result,null,2));console.log(result);w.close();
