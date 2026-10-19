// Verify scientific field mapping without launching a browser.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const data = JSON.parse(fs.readFileSync(path.join(__dirname, 'DATA.json'), 'utf8'));
const template = fs.readFileSync(path.join(__dirname, 'template.html'), 'utf8');
const functions = template.slice(template.indexOf('function numeric('), template.indexOf('function stopPlayers('));
const context = vm.createContext({esc: x => String(x ?? '')});
vm.runInContext(functions, context);
vm.runInContext(template.slice(template.indexOf('function alignmentMark('), template.indexOf('function renderTask(')), context);
const columns = id => context.metricColumns(data.versions[id]);
let checks = 0;
for (const [id, expected] of [
  ['r110_short_0114_promptcontrol', [0.7359279804303016, 0.8005679031912835]],
  ['flex_r90_one_leg__movie_man_9_prompt_control', [0.47081440687179565, 0.6634675860404968]],
  ['flex_r98_human2animal_1__game_man_4_task_repair', [0.6816202998161316, 0.523982584476471]],
  ['r111_long_0174_spatial', [0.9424339285679327, 0.9299472259756664, 0.9076388987771494]],
]) {
  assert.equal(JSON.stringify(columns(id).values), JSON.stringify(expected)); checks++;
}
const samplerHTML = context.metricHTML(data.versions.r106_short_0252_sampler_control, {bench: 'IVEBench'});
assert.equal((samplerHTML.match(/class="event-row"/g) || []).length, 3); checks++;
const defaults = data.tasks.filter(t => t.priority).sort((a,b)=>a.priority-b.priority).map(t => t.current);
assert.deepEqual(defaults, ['flex_r116_human2animal_1__game_man_4_fixed','r99_short_0210','r99_short_0230','r99_short_0352','r117_short_0114_framing_prompt','r108_short_0392']); checks++;
for (const t of data.tasks) {
  assert(t.versions.includes(t.current));
  for (const id of t.versions) assert(data.versions[id]);
}
checks++;
const fitness = data.tasks.find(t => t.source === 'fitness' && t.target === 'game_man_4');
assert(!fitness.versions.includes(defaults[0])); checks++;
for (const v of Object.values(data.versions)) {
  const c = context.metricColumns(v);
  assert.equal(c.labels.length, c.values.length);
  for (const n of c.values) assert(n == null || (typeof n === 'number' && Number.isFinite(n)));
  const rendered = context.metricHTML(v, {bench: 'IVEBench'});
  assert(!rendered.includes('NaN'));
}
checks++;
for (const bench of ['FlexiAct','IVEBench']) {
 const tasks=data.tasks.filter(t=>t.bench===bench);
 for(let i=1;i<tasks.length;i++)assert(tasks[i-1].latest_run>=tasks[i].latest_run);
}
checks++;
for(const v of Object.values(data.versions)){
 assert(v.title.includes(' — '));
 assert(v.still_frame>=0 && v.still_frame<v.frames);
 assert(v.players.every(p=>data.asset_types[p.still]==='image/jpeg'));
 assert([true,false,null].includes(v.alignment_native));
 assert([true,false,null].includes(v.alignment_guided));
}
checks++;
assert(template.indexOf('class=\"still-shell\"') < template.indexOf('class=\"player-shell\"'));
assert(template.indexOf('class=\"version-row\"') > template.indexOf('class=\"under\"'));
assert(!template.includes('下一步：'));
checks++;
const promptAlignment = context.alignmentHTML(data.versions.flex_r90_one_leg__movie_man_9_prompt_control);
assert(promptAlignment.includes('原提示词普通编辑'));
assert(promptAlignment.includes('改写提示词普通编辑'));
assert(!promptAlignment.includes('引导编辑'));
assert(!promptAlignment.includes('待生成')); checks++;
const nativeAlignment = context.alignmentHTML(data.versions.flex_r105_crouch__movie_man_4_native);
assert(nativeAlignment.includes('尚无成片')); checks++;
const long0174 = data.tasks.find(t => t.source === 'long_0174');
assert.equal(long0174.current, 'r115_long_0174_matched_one_bin'); checks++;
console.log(JSON.stringify({passed: true, checks, versions: Object.keys(data.versions).length}));
