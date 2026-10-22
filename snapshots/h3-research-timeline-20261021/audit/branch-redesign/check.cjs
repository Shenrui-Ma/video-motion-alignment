const fs=require('fs'),vm=require('vm'),assert=require('assert');
const path='/Users/researcher/.codex/visualizations/2026/10/07/01a11535-f9e3-7093-831f-b1a2e74d0fa0/h3-research-branches.html';
const html=fs.readFileSync(path,'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
new vm.Script(script);
assert(!/<(?:html|head|body)\b|<!doctype|fetch\(|XMLHttpRequest|https?:\/\//i.test(html.replace('http://www.w3.org/2000/svg','')));
class Node{
 constructor(tag){this.tag=tag;this.attrs={};this.children=[];this.events={};this.textContent='';this.scrollLeft=0;this.clientWidth=736;this.classList={add(){},remove(){}}}
 setAttribute(k,v){this.attrs[k]=String(v)}
 appendChild(child){if(child.parent)child.parent.children=child.parent.children.filter(x=>x!==child);child.parent=this;this.children.push(child)}
 replaceChildren(){this.children=[]}
 addEventListener(k,cb){this.events[k]=cb}
 setPointerCapture(){} hasPointerCapture(){return true} releasePointerCapture(){}
}
const svg=new Node('svg'),drawing=new Node('g'),canvas=new Node('div'),zoom=new Node('button'),left=new Node('button'),right=new Node('button');
Object.defineProperty(canvas,'scrollWidth',{get(){return Number(svg.attrs.width)}});
const nodes={'.canvas':canvas,'.diagram':svg,'.drawing':drawing,'[data-action="zoom"]':zoom,'[data-action="left"]':left,'[data-action="right"]':right};
let saves=0,resize;
const ctx={document:{getElementById:id=>{assert.equal(id,'h3-research-branches');return{querySelector:s=>{assert(nodes[s],s);return nodes[s]}}},createElementNS:(_,tag)=>new Node(tag)},window:{openai:{setWidgetState(){saves++;return Promise.resolve()}},addEventListener(){}},ResizeObserver:class{constructor(cb){resize=cb}observe(){}}};
vm.runInNewContext(script,ctx);
assert.equal(svg.attrs.width,'736');
const serialize=n=>({tag:n.tag,attrs:n.attrs,text:n.textContent,children:n.children.map(serialize)});
fs.writeFileSync(__dirname+'/drawing-736.json',JSON.stringify(serialize(drawing),null,2));
assert.equal(drawing.children.filter(n=>n.tag==='rect').length,12);
zoom.events.click();assert.equal(svg.attrs.width,'1104');assert.equal(zoom.textContent,'显示全程');assert(!right.disabled);
right.events.click();assert(canvas.scrollLeft>0);assert(saves>=2);
zoom.events.click();assert.equal(svg.attrs.width,'736');
canvas.clientWidth=320;resize();assert.equal(svg.attrs.width,'736');assert(!right.disabled);
canvas.clientWidth=1024;resize();assert.equal(svg.attrs.width,'1024');
fs.writeFileSync(__dirname+'/drawing-1024.json',JSON.stringify(serialize(drawing),null,2));
console.log(JSON.stringify({javascript_syntax:true,interaction_stub:true,nodes:11,main_nodes:7,branch_nodes:4,external_assets:0,bytes:Buffer.byteLength(html)}));
