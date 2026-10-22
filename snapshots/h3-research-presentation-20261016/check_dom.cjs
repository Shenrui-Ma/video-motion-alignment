// Offline DOM execution only. No browser, local HTTP server, or resource loader.
const fs = require('fs');
const assert = require('assert');
const {JSDOM} = require('/Users/researcher/DevProjects/openclaw/node_modules/jsdom');
const path = '/Users/researcher/Downloads/H3_动作时序研究_方法与实验_单文件_20261016.html';
const html = fs.readFileSync(path, 'utf8');
const dom = new JSDOM(html, {runScripts:'outside-only'});
const w=dom.window, d=w.document;
w.fetch=()=>{throw Error('Network disabled in offline check')};
w.XMLHttpRequest=class {constructor(){throw Error('Network disabled')}};
w.WebSocket=class {constructor(){throw Error('Network disabled')}};
// jsdom has no media decoder. These shims exercise UI state, not playback.
w.HTMLMediaElement.prototype.pause=function(){};
w.HTMLMediaElement.prototype.load=function(){};
const ids=[...d.querySelectorAll('[id]')].map(e=>e.id);
assert.equal(new Set(ids).size,ids.length,'duplicate ids');
for(const e of d.querySelectorAll('a[href^="#"]')) assert(d.getElementById(e.hash.slice(1)));
assert.equal(d.querySelectorAll('script[src],link[rel="stylesheet"],iframe').length,0);
for(const e of d.querySelectorAll('script:not([type])')) w.eval(e.textContent);
let count=0;
for(const node of d.querySelectorAll('[data-node]')){
 node.click();assert(node.classList.contains('active'));assert(d.getElementById('detail-body').textContent.length>30);count++;
}
for(const [key,on,probe] of [['full',9,0],['stop11',6,0],['native_observer',4,0],['r19',6,0]]){
 d.querySelector(`[data-schedule="${key}"]`).click();
 assert.equal(d.querySelectorAll('.step').length,20);assert.equal(d.querySelectorAll('.step.on').length,on);assert.equal(d.querySelectorAll('.step.probe').length,probe);count++;
}
for(const key of ['full','native_observer','stop11','roi','uniform','plus4','minus4']){
 const sel=d.getElementById('case-select');sel.value=key;sel.dispatchEvent(new w.Event('change'));
 for(const mode of ['normal','slow','poster']){
  d.querySelector(`[data-mode="${mode}"]`).click();const poster=mode==='poster';
  const e=d.getElementById(poster?'frame-view':'player');assert(e.getAttribute('src').startsWith(poster?'data:image/png;base64,':'data:video/mp4;base64,'));assert.notEqual(e.style.display,'none');
  assert(d.getElementById('download-video').getAttribute('download').startsWith(key));count++;
 }
}
d.getElementById('matrix-route').click();assert.equal(d.querySelectorAll('.cell.selected').length,6);
d.getElementById('matrix-native').click();assert.equal(d.querySelectorAll('.cell.weak').length,72);count+=2;
for(const id of ['r25-video','r25-frame055','r25-frame086']) assert(d.getElementById(id).getAttribute('src').startsWith('data:'));
for(const button of d.querySelectorAll('[data-fresh]')){
 button.click(); assert.equal(button.getAttribute('aria-pressed'),'true');
 for(const id of ['fresh-video','fresh-frame070','fresh-frame105']) assert(d.getElementById(id).getAttribute('src').startsWith('data:'));
 count++;
}
const result={status:'pass',interaction_checks:count,external_assets:0,network:'disabled',scope:'offline DOM and control state; no browser layout or media playback',built_utc:new Date().toISOString()};
fs.writeFileSync(__dirname+'/dom_check.json',JSON.stringify(result,null,2));console.log(result);w.close();
