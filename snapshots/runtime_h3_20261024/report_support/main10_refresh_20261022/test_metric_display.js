const fs=require('fs'),vm=require('vm'),assert=require('assert');
const root='/workspace/research-user/DevProjects/h3-guidance-schedule-eval-r150-20261021/main10_refresh_20261022/';
const html=fs.readFileSync('/workspace/research-user/DevProjects/video-motion-alignment/reports/R150_十组引导区间对照_单文件.html','utf8');
const json=html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1];const data=JSON.parse(json);
const script=html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
const elems={data:{textContent:json},outcomes:{innerHTML:''},'metric-scope':{value:'main_all'}};const ctx={document:{getElementById:id=>elems[id]},console};vm.createContext(ctx);vm.runInContext(script.slice(0,script.lastIndexOf('outcomeTable();')),ctx);
function run(s){return vm.runInContext(s,ctx)}
const synthetic={source:{motion_fidelity:{score:1}},native:{motion_fidelity:{score:.8}},early:{motion_fidelity:{score:.9}},fixed:{motion_fidelity:{score:.9}},late:{motion_fidelity:{score:null}},split:{motion_fidelity:{score:NaN}},global_weak:{motion_fidelity:{score:.7}}};ctx.synthetic=synthetic;
assert.deepStrictEqual(Array.from(run("bestMetricRoles(synthetic,'motion_fidelity')")),['early','fixed']);assert(!run("metricCell(synthetic,'source','motion_fidelity')").includes('✓'));assert(run("metricCell(synthetic,'source','motion_fidelity')")==='+0.0000');
assert(run("metricCell(synthetic,'early','motion_fidelity')").startsWith('-0.1000<span'));assert(!run("metricCell(synthetic,'late','motion_fidelity')").includes('✓'));
assert.deepStrictEqual(Array.from(run("bestMetricRoles(synthetic,'quantity_accuracy')")),[]);
assert(run("metricValue({motion_fidelity:{score:.7}},'motion_fidelity',false,.9)")==='-0.2000');
assert(run("metricValue({motion_fidelity:{mean:.8},motion_fidelity_delta_from_reference:{mean:-.15}},'motion_fidelity')")==='-0.1500');
let count=0;
for(const scope of ['main_all','main_IVEBench']){elems['metric-scope'].value=scope;run('outcomeTable()');assert(!elems.outcomes.innerHTML.includes('括号内'));assert(elems.outcomes.innerHTML.includes('主体一致性'));for(const key of Object.keys(data.metric_scopes[scope].native)){if(key==='timing'||key==='motion_fidelity_delta_from_reference')continue;const rows=data.metric_scopes[scope];const vals=data.roles.filter(r=>r!=='source').map(r=>[r,rows[r]?.[key]?.mean]).filter(([,v])=>typeof v==='number');const expected=vals.length?vals.filter(([,v])=>Math.abs(v-Math.max(...vals.map(([,x])=>x)))<=1e-12).map(([r])=>r):[];ctx.rows=rows;ctx.key=key;assert.deepStrictEqual(Array.from(run('bestMetricRoles(rows,key)')),expected);count++}}
for(const c of data.cases.slice(0,10)){ctx.caseRows=c.official_metrics;for(const key of Object.keys(c.official_metrics.native)){const vals=data.roles.filter(r=>r!=='source').map(r=>[r,c.official_metrics[r]?.[key]?.score]).filter(([,v])=>typeof v==='number');const expected=vals.length?vals.filter(([,v])=>Math.abs(v-Math.max(...vals.map(([,x])=>x)))<=1e-12).map(([r])=>r):[];ctx.key=key;assert.deepStrictEqual(Array.from(run('bestMetricRoles(caseRows,key)')),expected);count++}}
assert(html.includes('MF 原始分'));assert(html.includes('MF Δ'));
const result={passed:true,columns_verified:count,synthetic_checks:['highest','tie','missing','NaN','source_excluded','source_delta_zero','custom_reference','mean_pairwise_delta'],video_count:data.cases.length,screenshot_count:data.cases.reduce((n,c)=>n+c.overview.frames.length,0),MF_display:'signed delta only for our methods; raw MF only in external published tables'};
fs.writeFileSync(root+'METRIC_DISPLAY_VALIDATION.json',JSON.stringify(result,null,2));console.log(result);
