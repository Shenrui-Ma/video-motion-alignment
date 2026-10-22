const fs=require('fs'),vm=require('vm'),assert=require('assert');
const fragment=fs.readFileSync('/Users/researcher/.codex/visualizations/2026/10/07/01a11535-f9e3-7093-831f-b1a2e74d0fa0/h3-research-branches-detailed.html','utf8');
const config=JSON.parse(fs.readFileSync(__dirname+'/CONFIG.json','utf8'));
const original=JSON.parse(fs.readFileSync(__dirname+'/LAYOUT.json','utf8'));
const script=fragment.match(/<script>([\s\S]*?)<\/script>/)[1];new vm.Script(script);
class El {
 constructor(){this.events={};this.attrs={};this.style={};this.children=[];this.open=false;this.textContent='';this.scrollLeft=0;this.classes=new Set();this.classList={add:s=>this.classes.add(s),remove:s=>this.classes.delete(s)};}
 addEventListener(k,f){this.events[k]=f;}
 setAttribute(k,v){this.attrs[k]=v;}
 appendChild(e){this.children.push(e);}
 replaceChildren(){this.children=[];}
 setPointerCapture(){} hasPointerCapture(){return true;} releasePointerCapture(){}
}
const cards=Object.fromEntries(config.nodes.map(n=>{const el=new El();const box=original.nodes.find(b=>b.id===n.id);el.style.width=n.width+'px';Object.defineProperty(el,'offsetHeight',{get:()=>box.height+(el.open?500:0)});return [n.id,el];}));
const canvas=new El(),stage=new El(),svg=new El();
const elements={'.timeline-canvas':canvas,'.timeline-stage':stage,'.timeline-edges':svg};
let saves=0;const events={};
const ctx={document:{getElementById:id=>{assert.equal(id,'h3-disclosure-timeline');return {querySelector:s=>elements[s]||cards[s.match(/data-node="([^"]+)"/)[1]]};},createElementNS:()=>new El()},window:{openai:{setWidgetState(){saves++;return Promise.resolve();}},addEventListener:(k,f)=>{events[k]=f;}},ResizeObserver:class {constructor(f){this.f=f;}observe(){}},setTimeout:()=>0,clearTimeout(){}};
vm.runInNewContext(script,ctx);
assert.equal(saves,0);assert(Object.values(cards).every(c=>!c.open));
function check(){
 const boxes=config.nodes.map(n=>({...n,y:parseFloat(cards[n.id].style.top),height:cards[n.id].offsetHeight}));
 for(let i=0;i<boxes.length;i++)for(const b of boxes.slice(i+1)){const a=boxes[i];assert(!(Math.min(a.x+a.width,b.x+b.width)>Math.max(a.x,b.x)&&Math.min(a.y+a.height,b.y+b.height)>Math.max(a.y,b.y)),a.id+' '+b.id);}
 const lines=svg.children.filter(n=>Object.hasOwn(n.attrs,'x1'));assert.equal(lines.length,17);
 for(const line of lines){const {x1,y1,x2,y2}=line.attrs;for(const b of boxes)for(let j=1;j<100;j++){const t=j/100,x=x1+(x2-x1)*t,y=y1+(y2-y1)*t;assert(!(x>b.x+1&&x<b.x+b.width-1&&y>b.y+1&&y<b.y+b.height-1),'edge crosses '+b.id);}}
}
check();const collapsed=parseFloat(stage.style.height);
for(const c of Object.values(cards)){c.open=true;c.events.toggle();check();c.open=false;c.events.toggle();check();}
for(const c of Object.values(cards)){c.open=true;c.events.toggle();}check();assert(parseFloat(stage.style.height)>collapsed);
events['openai:set_globals']({detail:{globals:{widgetState:{privateContent:{version:3,openIds:['operator'],scrollLeft:400}}}}});
const previousSaves=saves;for(const [id,c] of Object.entries(cards))if(id!=='operator')c.events.toggle();assert.equal(saves,previousSaves);check();assert.equal(canvas.scrollLeft,400);
canvas.events.pointerdown({target:{closest:()=>cards.operator},pointerType:'mouse',button:0});assert(!canvas.classes.has('dragging'));
canvas.events.pointerdown({target:{closest:()=>null},pointerType:'mouse',button:0,pointerId:1,clientX:300});canvas.events.pointermove({pointerId:1,clientX:200});assert.equal(canvas.scrollLeft,500);canvas.events.pointerup({pointerId:1});assert(!canvas.classes.has('dragging'));
assert.equal((fragment.match(/<details /g)||[]).length,18);assert(!/<details[^>]+\sopen(?:[ >])/.test(fragment));
for(const word of ['前一阶段','后一阶段','偏移统计','算法参数与完整实验记录','验收','落盘'])assert(!fragment.includes(word),word);
assert.equal(svg.children.filter(n=>n.textContent).length,4);
console.log(JSON.stringify({native_details:18,all_collapsed_by_default:true,each_node_expansion:true,all_nodes_expansion:true,no_overlap_or_arrow_crossings:true,drag_excludes_nodes:true,state_restore_no_resave:true,arrow_labels:4}));
