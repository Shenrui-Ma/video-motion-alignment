const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = '/Users/researcher/.codex/visualizations/2026/10/07/01a11535-f9e3-7093-831f-b1a2e74d0fa0/h3-research-branches-detailed.html';
const html = fs.readFileSync(path, 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
new vm.Script(script);
assert(!/<(?:html|head|body)\b|<!doctype|fetch\(|XMLHttpRequest|https?:\/\//i.test(html.replace('http://www.w3.org/2000/svg', '')));
assert.equal((html.match(/<g id=/g) || []).length, 13);
assert.equal((html.match(/<details>/g) || []).length, 13);

class Element {
  constructor() { this.events = {}; this.disabled = false; this.classes = new Set(); this.classList = {add: s => this.classes.add(s), remove: s => this.classes.delete(s)}; }
  addEventListener(name, fn) { this.events[name] = fn; }
}
const canvas = new Element(), previous = new Element(), next = new Element();
canvas.clientWidth = 736;
canvas.scrollWidth = Number(html.match(/class="timeline" width="([0-9.]+)"/)[1]);
let left = 0, capture = null;
Object.defineProperty(canvas, 'scrollLeft', {get: () => left, set: n => {left = Math.max(0, Math.min(n, canvas.scrollWidth - canvas.clientWidth));}});
canvas.setPointerCapture = id => {capture = id;};
canvas.hasPointerCapture = id => capture === id;
canvas.releasePointerCapture = () => {capture = null;};
const elements = {'.timeline-canvas': canvas, '[data-action="previous"]': previous, '[data-action="next"]': next};
let saves = 0, resize;
const windowEvents = {};
const ctx = {
  document: {getElementById(id) {assert.equal(id, 'h3-detailed-research-timeline'); return {querySelector(selector) {assert(elements[selector], selector); return elements[selector];}};}},
  window: {openai: {setWidgetState(state) {saves++; assert.equal(state.privateContent.scrollLeft, left); return Promise.resolve();}}, addEventListener: (name, fn) => {windowEvents[name] = fn;}},
  ResizeObserver: class {constructor(fn) {resize = fn;} observe() {}}
};
vm.runInNewContext(script, ctx);
assert(previous.disabled && !next.disabled);
next.events.click(); assert(left > 0); assert(!previous.disabled);
previous.events.click(); assert.equal(left, 0);
previous.events.click(); assert.equal(left, 0);
for (let i = 0; i < 12; i++) next.events.click();
assert(next.disabled); assert.equal(left, canvas.scrollWidth - 736);
windowEvents['openai:set_globals']({detail: {globals: {widgetState: {privateContent: {scrollLeft: 500}}}}});
assert.equal(left, 500);
canvas.events.pointerdown({pointerType: 'mouse', button: 0, pointerId: 1, clientX: 300});
canvas.events.pointermove({pointerId: 1, clientX: 200});
assert.equal(left, 600); assert(canvas.classes.has('dragging'));
canvas.events.pointerup({pointerId: 1}); assert(!canvas.classes.has('dragging')); assert.equal(capture, null);
canvas.clientWidth = 320; resize(); assert(!next.disabled);
canvas.clientWidth = 4000; canvas.scrollLeft = 0; resize(); assert(previous.disabled && next.disabled);
assert(saves > 3);
console.log(JSON.stringify({javascript_syntax: true, interaction_stub: true, node_count: 13, expanded_records: 13, external_assets: 0, bytes: Buffer.byteLength(html)}));
