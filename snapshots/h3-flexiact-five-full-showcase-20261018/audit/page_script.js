
function slow(b){let v=b.closest('section').querySelector('video');v.playbackRate=v.playbackRate===.5?1:.5;b.textContent=v.playbackRate===.5?'1× 正常速度':'0.5× 慢放';v.play()}
function full(b){let v=b.closest('section').querySelector('video');if(v.requestFullscreen)v.requestFullscreen();else if(v.webkitEnterFullscreen)v.webkitEnterFullscreen()}
document.querySelectorAll('video').forEach(v=>v.addEventListener('play',()=>document.querySelectorAll('video').forEach(o=>{if(o!==v)o.pause()})));
