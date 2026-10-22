
(() => {
const root=document.getElementById('h3-disclosure-timeline');
const canvas=root.querySelector('.timeline-canvas');
const stage=root.querySelector('.timeline-stage');
const svg=root.querySelector('.timeline-edges');
const config={"nodes": [{"id": "question", "x": 24, "width": 210, "title": "问题：短动作修复"}, {"id": "weight", "x": 334, "width": 220, "title": "方法：局部参考加权"}, {"id": "timing", "x": 654, "width": 220, "title": "问题：动作时间对齐"}, {"id": "operator", "x": 974, "width": 260, "title": "方法：同时间 Attention"}, {"id": "public", "x": 1334, "width": 240, "title": "实验：公开数据测试"}, {"id": "schedules", "x": 1674, "width": 240, "title": "实验：引导区间对照"}, {"id": "weak", "x": 2014, "width": 250, "title": "方法：全程弱引导"}, {"id": "early_latent", "x": 754, "width": 270, "title": "方法：latent 自动启停"}, {"id": "rgb", "x": 1124, "width": 300, "title": "方法：姿态检测自动启停"}, {"id": "latent", "x": 1524, "width": 290, "title": "方法：latent 运动检测"}, {"id": "rope", "x": 874, "width": 300, "title": "方法：RoPE 时间对齐"}, {"id": "spatial", "x": 1259, "width": 280, "title": "方法：空间对应修正"}, {"id": "reciprocal", "x": 1624, "width": 310, "title": "方法：双向时间 Attention"}], "main": ["question", "weight", "timing", "operator", "public", "schedules", "weak"], "upper": ["early_latent", "rgb", "latent"], "lower": ["rope", "spatial", "reciprocal"], "edges": [{"from": "question", "to": "weight", "side": "horizontal", "main": true, "label": ""}, {"from": "weight", "to": "timing", "side": "horizontal", "main": true, "label": ""}, {"from": "timing", "to": "operator", "side": "horizontal", "main": true, "label": ""}, {"from": "operator", "to": "public", "side": "horizontal", "main": true, "label": "扩大测试"}, {"from": "public", "to": "schedules", "side": "horizontal", "main": true, "label": ""}, {"from": "schedules", "to": "weak", "side": "horizontal", "main": true, "label": ""}, {"from": "operator", "to": "early_latent", "side": "up", "label": "尝试自动控制", "offset": -68}, {"from": "early_latent", "to": "rgb", "side": "horizontal", "label": ""}, {"from": "rgb", "to": "latent", "side": "horizontal", "label": ""}, {"from": "operator", "to": "rope", "side": "down", "label": ""}, {"from": "public", "to": "spatial", "side": "down", "label": ""}, {"from": "schedules", "to": "reciprocal", "side": "down", "label": ""}]};
const cards=Object.fromEntries(config.nodes.map(n=>[n.id,root.querySelector('[data-node="'+n.id+'"]')]));
const ns='http://www.w3.org/2000/svg';
let restoring=false,drag=null,scrollTimer;
const restoreToggles=new Map();
function drawEdge(x1,y1,x2,y2,main,label,offset=0){
 const line=document.createElementNS(ns,'line');
 for(const [k,v] of Object.entries({x1,y1,x2,y2}))line.setAttribute(k,v);
 if(main)line.setAttribute('class','main-edge');svg.appendChild(line);
 const theta=Math.atan2(y2-y1,x2-x1),arrow=document.createElementNS(ns,'polygon');
 const points=[[x2,y2],[x2-7*Math.cos(theta)+3.5*Math.sin(theta),y2-7*Math.sin(theta)-3.5*Math.cos(theta)],[x2-7*Math.cos(theta)-3.5*Math.sin(theta),y2-7*Math.sin(theta)+3.5*Math.cos(theta)]];
 arrow.setAttribute('points',points.map(p=>p.join(',')).join(' '));if(main)arrow.setAttribute('class','main-edge');svg.appendChild(arrow);
 if(label){const text=document.createElementNS(ns,'text');text.setAttribute('x',(x1+x2)/2+offset);text.setAttribute('y',(y1+y2)/2-12);text.setAttribute('text-anchor','middle');text.textContent=label;svg.appendChild(text);}
}
function layout(){
 const boxes=Object.fromEntries(config.nodes.map(n=>[n.id,{...n,height:cards[n.id].offsetHeight}]));
 const topBottom=Math.max(...config.upper.map(id=>12+boxes[id].height));
 const mainHeight=Math.max(...config.main.map(id=>boxes[id].height));
 const axis=topBottom+90+mainHeight/2;
 for(const id of config.upper)boxes[id].y=12;
 for(const id of config.main)boxes[id].y=axis-boxes[id].height/2;
 const bottom=axis+mainHeight/2+90;
 for(const id of config.lower)boxes[id].y=bottom;
 const height=Math.max(...Object.values(boxes).map(n=>n.y+n.height))+18;
 stage.style.height=height+'px';svg.setAttribute('height',height);svg.replaceChildren();
 for(const n of Object.values(boxes)){cards[n.id].style.left=n.x+'px';cards[n.id].style.top=n.y+'px';}
 for(const e of config.edges){
  const a=boxes[e.from],b=boxes[e.to];let x1,y1,x2,y2;
  if(e.side==='horizontal'){x1=a.x+a.width;y1=a.y+a.height/2;x2=b.x-3;y2=b.y+b.height/2;}
  else if(e.side==='up'){x1=a.x+20;y1=a.y;x2=b.x+b.width/2;y2=b.y+b.height+3;}
  else{x1=a.x+a.width/2;y1=a.y+a.height;x2=b.x+b.width/2;y2=b.y-3;}
  drawEdge(x1,y1,x2,y2,e.main,e.label,e.offset||0);
 }
}
function save(){if(!restoring&&window.openai?.setWidgetState)window.openai.setWidgetState({modelContent:{expandedNodes:config.nodes.filter(n=>cards[n.id].open).map(n=>n.title)},privateContent:{version:2,openIds:config.nodes.filter(n=>cards[n.id].open).map(n=>n.id),scrollLeft:canvas.scrollLeft}}).catch(()=>{});}
for(const card of Object.values(cards))card.addEventListener('toggle',()=>{layout();if(restoreToggles.has(card)){const expected=restoreToggles.get(card);restoreToggles.delete(card);if(expected===card.open)return;}save();});
const observer=new ResizeObserver(layout);for(const card of Object.values(cards))observer.observe(card);
canvas.addEventListener('scroll',()=>{clearTimeout(scrollTimer);scrollTimer=setTimeout(save,160);},{passive:true});
canvas.addEventListener('pointerdown',e=>{if(e.target.closest('details'))return;if(e.pointerType==='mouse'&&e.button===0){drag={id:e.pointerId,x:e.clientX,left:canvas.scrollLeft};canvas.setPointerCapture(e.pointerId);canvas.classList.add('dragging');}});
canvas.addEventListener('pointermove',e=>{if(drag&&drag.id===e.pointerId)canvas.scrollLeft=drag.left+drag.x-e.clientX;});
function end(e){if(drag&&drag.id===e.pointerId){drag=null;canvas.classList.remove('dragging');if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);save();}}
canvas.addEventListener('pointerup',end);canvas.addEventListener('pointercancel',end);canvas.addEventListener('lostpointercapture',()=>{drag=null;canvas.classList.remove('dragging');});
function restore(state){restoring=true;const value=state?.privateContent;const ids=value?.version===2?value.openIds||[]:[];for(const n of config.nodes){const card=cards[n.id],open=ids.includes(n.id);if(card.open!==open){restoreToggles.set(card,open);card.open=open;}}layout();canvas.scrollLeft=value?.version===2?Number(value.scrollLeft)||0:0;restoring=false;}
window.addEventListener('openai:set_globals',e=>{if(e.detail?.globals?.widgetState)restore(e.detail.globals.widgetState);});
restore(window.openai?.widgetState);
})();
