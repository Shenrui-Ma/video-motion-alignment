const fs=require('fs'),vm=require('vm'),assert=require('assert');
function el(){return {events:{},disabled:false,addEventListener(n,f){this.events[n]=f}}}
const chart=Object.assign(el(),{scrollLeft:0,scrollWidth:2796,clientWidth:1000,capture:null,scrollBy({left}){this.scrollLeft=Math.min(this.scrollWidth-this.clientWidth,Math.max(0,this.scrollLeft+left));this.events.scroll()},setPointerCapture(id){this.capture=id},hasPointerCapture(id){return this.capture===id},releasePointerCapture(){this.capture=null}});
const previous=el(),next=el();
const context={document:{getElementById:id=>({chart,previous,next})[id]},window:{addEventListener(){}}};
vm.runInNewContext(fs.readFileSync(__dirname+'/interaction.js','utf8'),context);
assert.equal(previous.disabled,true); assert.equal(next.disabled,false);
next.events.click(); assert.equal(chart.scrollLeft,800);assert.equal(previous.disabled,false);
previous.events.click();assert.equal(chart.scrollLeft,0);
chart.events.pointerdown({pointerType:'mouse',button:0,pointerId:1,clientX:300});
chart.events.pointermove({pointerId:1,clientX:150});assert.equal(chart.scrollLeft,150);
chart.events.pointerup({pointerId:1});assert.equal(chart.capture,null);
let prevented=false;chart.events.keydown({key:'ArrowRight',preventDefault(){prevented=true}});assert(prevented);assert.equal(chart.scrollLeft,950);
chart.scrollLeft=1796;chart.events.scroll();assert.equal(next.disabled,true);
console.log('Navigation buttons, mouse drag, release, keyboard, boundary state passed.');
