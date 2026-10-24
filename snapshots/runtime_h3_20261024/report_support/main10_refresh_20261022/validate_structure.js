const fs=require('fs'),vm=require('vm'),assert=require('assert');
const p='/workspace/research-user/DevProjects/video-motion-alignment/reports/R150_十组引导区间对照_单文件.html';
const html=fs.readFileSync(p,'utf8');const json=html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1];const data=JSON.parse(json);
const script=html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];new vm.Script(script);
const elems={data:{textContent:json},outcomes:{innerHTML:''},'metric-scope':{value:'main_all'}};
const ctx={document:{getElementById:id=>elems[id]},console};vm.createContext(ctx);
vm.runInContext(script.slice(0,script.lastIndexOf('outcomeTable();')),ctx);
vm.runInContext('outcomeTable(); for(const c of D.cases){const t=table(c); if(!t.includes("MF"))throw Error(c.id);officialTable(c)}',ctx);
assert(!elems.outcomes.innerHTML.includes('11.40'));
assert(elems.outcomes.innerHTML.includes('630'));elems['metric-scope'].value='main_IVEBench';vm.runInContext('outcomeTable()',ctx);assert(elems.outcomes.innerHTML.includes('567'));assert(elems.outcomes.innerHTML.includes('9/9'));
assert(data.cases.length===14);
assert(data.cases.slice(0,10).every(c=>c.main_cohort));assert(data.cases.slice(10).every(c=>!c.main_cohort));
assert(script.includes('<video controls preload="metadata" playsinline>'));
const ids=[];for(const c of data.cases){assert(c.overview.video.startsWith('data:video/mp4;base64,'));assert(c.overview.frames.every(f=>f.url.startsWith('data:image/')));assert(c.overview.default_frame>0);ids.push(c.source_id)}
const result={syntax:'pass',metric_tables:'14/14 rendered without error',embedded_videos:14,embedded_screenshots:data.cases.reduce((n,c)=>n+c.overview.frames.length,0),native_controls:true,all_default_frames_nonzero:true,main10_methods:70,numeric_metric_values:630,order:ids};
fs.writeFileSync('/workspace/research-user/DevProjects/h3-guidance-schedule-eval-r150-20261021/main10_refresh_20261022/JS_VALIDATION.json',JSON.stringify(result,null,2));console.log(result);
