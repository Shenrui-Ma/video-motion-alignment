
const chart=document.getElementById('chart');
const previous=document.getElementById('previous');
const next=document.getElementById('next');
function updateButtons(){previous.disabled=chart.scrollLeft<=1;next.disabled=chart.scrollLeft>=chart.scrollWidth-chart.clientWidth-1}
function move(direction){chart.scrollBy({left:direction*Math.max(346,chart.clientWidth*.8),behavior:'smooth'})}
previous.addEventListener('click',()=>move(-1));
next.addEventListener('click',()=>move(1));
chart.addEventListener('scroll',updateButtons,{passive:true});
window.addEventListener('resize',updateButtons);
chart.addEventListener('keydown',event=>{if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();move(event.key==='ArrowLeft'?-1:1)}});
let drag=null;
chart.addEventListener('pointerdown',event=>{if(event.pointerType==='mouse'&&event.button===0){drag={id:event.pointerId,x:event.clientX,left:chart.scrollLeft};chart.setPointerCapture(event.pointerId)}});
chart.addEventListener('pointermove',event=>{if(drag&&event.pointerId===drag.id){chart.scrollLeft=drag.left-(event.clientX-drag.x)}});
function endDrag(event){if(drag&&event.pointerId===drag.id){if(chart.hasPointerCapture(event.pointerId))chart.releasePointerCapture(event.pointerId);drag=null}}
chart.addEventListener('pointerup',endDrag);
chart.addEventListener('pointercancel',endDrag);
chart.addEventListener('lostpointercapture',()=>{drag=null});
updateButtons();
