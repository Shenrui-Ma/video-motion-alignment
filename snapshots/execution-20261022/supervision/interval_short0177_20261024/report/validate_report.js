const fs=require('fs'),vm=require('vm'),assert=require('assert');
const file=process.argv[2];if(!file)throw Error('Pass staged R150 HTML path');
const html=fs.readFileSync(file,'utf8');
const json=html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const d=JSON.parse(json),script=html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
new vm.Script(script);
const elems={data:{textContent:json},outcomes:{innerHTML:''},'metric-scope':{value:'main_IVEBench'}};
const ctx={document:{getElementById:id=>elems[id]},console};vm.createContext(ctx);
vm.runInContext(script.slice(0,script.lastIndexOf('outcomeTable();')),ctx);
for(const [scope,n] of Object.entries(d.scope_counts)){
 elems['metric-scope'].value=scope;vm.runInContext('outcomeTable()',ctx);
 assert(elems.outcomes.innerHTML.includes(n*7*9+'项'),scope);
 assert(!elems.outcomes.innerHTML.includes('NaN')&&!elems.outcomes.innerHTML.includes('undefined'),scope);
}
vm.runInContext("for(const c of D.cases){if(!table(c).includes('MF'))throw Error(c.id);officialTable(c)}",ctx);
assert.equal(vm.runInContext("metricValue({instruction_satisfaction:{status:'pending',score:null}},'instruction_satisfaction')",ctx),'未测');
assert.equal(vm.runInContext("metricValue({quantity_accuracy:{status:'not_applicable',score:null}},'quantity_accuracy')",ctx),'N/A');
assert.equal(d.cases.length,15);assert.equal(d.cases.filter(c=>c.main_cohort).length,10);
assert.equal(d.cases.filter(c=>c.dataset==='FlexiAct').length,1);
assert.equal(d.cases.filter(c=>c.display_group==='历史自有素材').length,4);
assert.equal(d.cases[0].source_id,'short_0177');
const flex=d.cases.find(c=>c.source_id==='crouch__movie_man_4');assert(flex.events.length>0&&!flex.main_cohort);
assert(vm.runInContext("officialTable(D.cases.find(c=>c.dataset==='FlexiAct'))",ctx).includes('官方指标'));
for(const c of d.cases){assert(c.overview.video.startsWith('data:video/mp4;base64,'));assert(c.overview.frames.every(f=>f.url.startsWith('data:image/')))}
console.log(JSON.stringify({passed:true,groups:{IVEBench:10,FlexiAct:1,historical:4},all_sample_tables:15,scope_numeric_counts:[630,63,693],flex_events_preserved:flex.events.length}));
