
(() => {
const root=document.getElementById('h3-detailed-research-timeline');
const canvas=root.querySelector('.timeline-canvas');
const previous=root.querySelector('[data-action="previous"]'),next=root.querySelector('[data-action="next"]');
const starts=[0, 282, 584, 866, 1198, 1550, 1862];
let drag=null;
function sync(){previous.disabled=canvas.scrollLeft<=1;next.disabled=canvas.scrollLeft>=canvas.scrollWidth-canvas.clientWidth-1}
function save(){if(window.openai?.setWidgetState)window.openai.setWidgetState({modelContent:null,privateContent:{scrollLeft:canvas.scrollLeft}}).catch(()=>{})}
function move(direction){
 const here=canvas.scrollLeft;
 const target=direction>0?starts.find(x=>x>here+4):[...starts].reverse().find(x=>x<here-4);
 canvas.scrollLeft=target??(direction>0?canvas.scrollWidth:0);sync();save();
}
previous.addEventListener('click',()=>move(-1));next.addEventListener('click',()=>move(1));
canvas.addEventListener('scroll',sync,{passive:true});
canvas.addEventListener('pointerdown',e=>{if(e.pointerType==='mouse'&&e.button===0){drag={id:e.pointerId,x:e.clientX,left:canvas.scrollLeft};canvas.setPointerCapture(e.pointerId);canvas.classList.add('dragging')}});
canvas.addEventListener('pointermove',e=>{if(drag&&drag.id===e.pointerId)canvas.scrollLeft=drag.left+drag.x-e.clientX});
function end(e){if(drag&&drag.id===e.pointerId){drag=null;canvas.classList.remove('dragging');if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);sync();save()}}
canvas.addEventListener('pointerup',end);canvas.addEventListener('pointercancel',end);
canvas.addEventListener('lostpointercapture',()=>{drag=null;canvas.classList.remove('dragging')});
new ResizeObserver(sync).observe(canvas);
function restore(state){canvas.scrollLeft=Number(state?.privateContent?.scrollLeft)||0;sync()}
window.addEventListener('openai:set_globals',e=>{if(e.detail?.globals?.widgetState)restore(e.detail.globals.widgetState)});
restore(window.openai?.widgetState);
})();
