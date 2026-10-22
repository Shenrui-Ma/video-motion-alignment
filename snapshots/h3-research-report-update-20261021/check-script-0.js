
document.querySelectorAll('.result').forEach(function(panel){var v=panel.querySelector('video');panel.querySelectorAll('[data-rate]').forEach(function(b){b.addEventListener('click',function(){v.playbackRate=Number(b.dataset.rate);});});panel.querySelector('[data-restart]').addEventListener('click',function(){v.currentTime=0;v.play().catch(function(){});});});
document.querySelectorAll('video').forEach(function(v){v.addEventListener('play',function(){document.querySelectorAll('video').forEach(function(other){if(other!==v)other.pause();});});});
