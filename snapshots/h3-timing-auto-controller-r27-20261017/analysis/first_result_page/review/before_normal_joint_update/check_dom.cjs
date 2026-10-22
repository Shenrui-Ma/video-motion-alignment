const fs=require('fs'),assert=require('assert'),crypto=require('crypto');
const {JSDOM}=require('/Users/researcher/DevProjects/openclaw/node_modules/jsdom');
const html=fs.readFileSync('/Users/researcher/Downloads/H3_自动动作窗口_初步结果_20261017.html','utf8');
const dom=new JSDOM(html,{runScripts:'outside-only'}),w=dom.window,d=w.document;
w.fetch=()=>{throw Error('offline')};w.XMLHttpRequest=class{constructor(){throw Error('offline')}};w.requestAnimationFrame=()=>0;
w.HTMLMediaElement.prototype.pause=function(){};w.HTMLMediaElement.prototype.play=function(){return Promise.resolve()};
for(const s of d.querySelectorAll('script'))w.eval(s.textContent);
assert.equal(d.querySelectorAll('video').length,4);assert.equal(d.querySelectorAll('#rows tr').length,20);assert.equal(d.querySelectorAll('#rows .on').length,1);
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
assert(d.body.textContent.includes('正式20个在线观察重放'));
const videos=[...d.querySelectorAll('video')];videos.forEach((v,i)=>{assert(v.src.startsWith('data:video/mp4;base64,'));const sha=crypto.createHash('sha256').update(Buffer.from(v.src.split(',')[1],'base64')).digest('hex');assert.equal(sha,manifest.assets[i].sha256)});
d.getElementById('seek').value=55;d.getElementById('seek').dispatchEvent(new w.Event('input'));videos.forEach(v=>assert.equal(v.currentTime,55/24));
d.getElementById('next').click();videos.forEach(v=>assert.equal(v.currentTime,56/24));d.getElementById('prev').click();videos.forEach(v=>assert.equal(v.currentTime,55/24));d.getElementById('reset').click();videos.forEach(v=>assert.equal(v.currentTime,0));
d.getElementById('speed').value='0.5';d.getElementById('speed').dispatchEvent(new w.Event('change'));videos.forEach(v=>assert.equal(v.playbackRate,.5));
const result={passed:true,embedded_assets:4,asset_sha_exact:true,decision_rows:20,selected_denoising_index:4,fixed_metric_rows:8,fixed_metrics_match_actual_summary:true,whole_scan_rows:3,common_support_rows:4,UNKNOWN_retained:true,seek_buttons_and_speed:true,external_runtime_assets:0,scope:'offline DOM/control-state and byte checks; browser layout and actual media playback unassessed'};fs.writeFileSync(__dirname+'/DOM_CHECK.json',JSON.stringify(result,null,2));console.log(result);w.close();
