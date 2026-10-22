
(() => {
const root=document.getElementById('h3-disclosure-timeline');
const canvas=root.querySelector('.timeline-canvas');
const stage=root.querySelector('.timeline-stage');
const svg=root.querySelector('.timeline-edges');
const config={"nodes": [{"id": "question", "x": 24, "width": 220, "title": "问题：短动作修复"}, {"id": "weight", "x": 344, "width": 240, "title": "方法：局部参考加权"}, {"id": "timing", "x": 684, "width": 230, "title": "问题：动作时间对齐"}, {"id": "operator", "x": 1014, "width": 270, "title": "方法：同时间 Attention"}, {"id": "fixed_test", "x": 1384, "width": 270, "title": "实验：固定 7–15 步引导"}, {"id": "public", "x": 1754, "width": 280, "title": "实验：公开数据集固定引导"}, {"id": "schedules", "x": 2134, "width": 280, "title": "实验：十组引导区间对照"}, {"id": "weak", "x": 2514, "width": 250, "title": "方法：全程弱引导"}, {"id": "rgb_method", "x": 834.0, "width": 270, "title": "方法：RGB 姿态反馈"}, {"id": "rgb_test", "x": 824.0, "width": 290, "title": "实验：RGB 自动控制"}, {"id": "latent_method", "x": 1194.0, "width": 270, "title": "方法：latent 运动反馈"}, {"id": "latent_test", "x": 1184.0, "width": 290, "title": "实验：latent 检测验证"}, {"id": "spatial_method", "x": 1579.0, "width": 270, "title": "方法：空间对应修正"}, {"id": "spatial_test", "x": 1569.0, "width": 290, "title": "实验：空间对应对照"}, {"id": "rope_method", "x": 1939.0, "width": 270, "title": "方法：RoPE 时间对齐"}, {"id": "rope_test", "x": 1929.0, "width": 290, "title": "实验：RoPE 组合对照"}, {"id": "dual_method", "x": 2319.0, "width": 270, "title": "方法：双向时间 Attention"}, {"id": "dual_test", "x": 2309.0, "width": 290, "title": "实验：双向引导对照"}], "rows": [{"ids": ["rgb_test", "latent_test"], "align": "bottom"}, {"ids": ["rgb_method", "latent_method"], "align": "bottom"}, {"ids": ["question", "weight", "timing", "operator", "fixed_test", "public", "schedules", "weak"], "align": "center"}, {"ids": ["spatial_method", "rope_method", "dual_method"], "align": "top"}, {"ids": ["spatial_test", "rope_test", "dual_test"], "align": "top"}], "rowGap": 72, "edges": [{"from": "question", "to": "weight", "side": "horizontal", "main": true, "label": ""}, {"from": "weight", "to": "timing", "side": "horizontal", "main": true, "label": "调整问题重心"}, {"from": "timing", "to": "operator", "side": "horizontal", "main": true, "label": ""}, {"from": "operator", "to": "fixed_test", "side": "horizontal", "main": true, "label": ""}, {"from": "fixed_test", "to": "public", "side": "horizontal", "main": true, "label": "扩大测试"}, {"from": "public", "to": "schedules", "side": "horizontal", "main": true, "label": ""}, {"from": "schedules", "to": "weak", "side": "horizontal", "main": true, "label": ""}, {"from": "operator", "to": "rgb_method", "side": "up", "label": "尝试自动控制", "offset": -65}, {"from": "operator", "to": "latent_method", "side": "up", "label": ""}, {"from": "rgb_method", "to": "rgb_test", "side": "up", "label": ""}, {"from": "latent_method", "to": "latent_test", "side": "up", "label": ""}, {"from": "public", "to": "spatial_method", "side": "down", "label": ""}, {"from": "public", "to": "rope_method", "side": "down", "label": ""}, {"from": "schedules", "to": "dual_method", "side": "down", "label": "拓展方法", "offset": 65}, {"from": "spatial_method", "to": "spatial_test", "side": "down", "label": ""}, {"from": "rope_method", "to": "rope_test", "side": "down", "label": ""}, {"from": "dual_method", "to": "dual_test", "side": "down", "label": ""}]};
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
 let rowTop=12;
 for(const row of config.rows){
  const rowHeight=Math.max(...row.ids.map(id=>boxes[id].height));
  for(const id of row.ids)boxes[id].y=rowTop+(rowHeight-boxes[id].height)*({top:0,center:.5,bottom:1}[row.align]);
  rowTop+=rowHeight+config.rowGap;
 }
 const height=Math.max(...Object.values(boxes).map(n=>n.y+n.height))+18;
 stage.style.height=height+'px';svg.setAttribute('height',height);svg.replaceChildren();
 for(const n of Object.values(boxes)){cards[n.id].style.left=n.x+'px';cards[n.id].style.top=n.y+'px';}
 for(const e of config.edges){
  const a=boxes[e.from],b=boxes[e.to];let x1,y1,x2,y2;
  if(e.side==='horizontal'){x1=a.x+a.width;y1=a.y+a.height/2;x2=b.x-3;y2=b.y+b.height/2;}
  else if(e.side==='up'){x1=a.x+a.width/2;y1=a.y;x2=b.x+b.width/2;y2=b.y+b.height+3;}
  else{x1=a.x+a.width/2;y1=a.y+a.height;x2=b.x+b.width/2;y2=b.y-3;}
  drawEdge(x1,y1,x2,y2,e.main,e.label,e.offset||0);
 }
}
function save(){if(!restoring&&window.openai?.setWidgetState)window.openai.setWidgetState({modelContent:{expandedNodes:config.nodes.filter(n=>cards[n.id].open).map(n=>n.title)},privateContent:{version:3,openIds:config.nodes.filter(n=>cards[n.id].open).map(n=>n.id),scrollLeft:canvas.scrollLeft}}).catch(()=>{});}
for(const card of Object.values(cards))card.addEventListener('toggle',()=>{layout();if(restoreToggles.has(card)){const expected=restoreToggles.get(card);restoreToggles.delete(card);if(expected===card.open)return;}save();});
const observer=new ResizeObserver(layout);for(const card of Object.values(cards))observer.observe(card);
canvas.addEventListener('scroll',()=>{clearTimeout(scrollTimer);scrollTimer=setTimeout(save,160);},{passive:true});
canvas.addEventListener('pointerdown',e=>{if(e.target.closest('details'))return;if(e.pointerType==='mouse'&&e.button===0){drag={id:e.pointerId,x:e.clientX,left:canvas.scrollLeft};canvas.setPointerCapture(e.pointerId);canvas.classList.add('dragging');}});
canvas.addEventListener('pointermove',e=>{if(drag&&drag.id===e.pointerId)canvas.scrollLeft=drag.left+drag.x-e.clientX;});
function end(e){if(drag&&drag.id===e.pointerId){drag=null;canvas.classList.remove('dragging');if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);save();}}
canvas.addEventListener('pointerup',end);canvas.addEventListener('pointercancel',end);canvas.addEventListener('lostpointercapture',()=>{drag=null;canvas.classList.remove('dragging');});
function restore(state){restoring=true;const value=state?.privateContent;const ids=value?.version===3?value.openIds||[]:[];for(const n of config.nodes){const card=cards[n.id],open=ids.includes(n.id);if(card.open!==open){restoreToggles.set(card,open);card.open=open;}}layout();canvas.scrollLeft=value?.version===3?Number(value.scrollLeft)||0:0;restoring=false;}
window.addEventListener('openai:set_globals',e=>{if(e.detail?.globals?.widgetState)restore(e.detail.globals.widgetState);});
restore(window.openai?.widgetState);
})();
