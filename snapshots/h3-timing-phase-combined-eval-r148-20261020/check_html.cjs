const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require("/Users/researcher/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");
(async () => {
  const browser = await chromium.launch({executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    headless: true, args: ["--disable-gpu", "--allow-file-access-from-files"]});
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
  const errors = [];
  page.on("pageerror", e => errors.push(e.message));
  await page.goto("file://" + path.join(__dirname, "index.html"), {waitUntil: "load"});
  await page.screenshot({path: path.join(__dirname, "HTML_DESKTOP.jpg"), quality: 60, type: "jpeg"});
  const desktop = await page.evaluate(() => ({
    cases: document.querySelectorAll("section").length,
    panels: [...document.querySelectorAll(".four")].map(e=>e.children.length),
    footer_labels: [...document.querySelectorAll("section:first-of-type figcaption")].map(e=>e.textContent),
    new_pending: document.querySelectorAll(".pending").length,
    same_frame_sliders: document.querySelectorAll(".controls input[type=range]").length,
    fullscreen_buttons: document.querySelectorAll(".fullscreen").length,
    width_overflow: document.documentElement.scrollWidth > innerWidth,
    video_nodes: document.querySelectorAll("video").length
  }));
  await page.locator(".comparison .play").first().click();
  await page.waitForFunction(() => document.querySelector("video").currentTime > 0.5, null, {timeout: 10000});
  const playback = await page.evaluate(() => [...document.querySelectorAll("section:first-of-type video")]
    .map(v=>({time:v.currentTime,paused:v.paused,rate:v.playbackRate,error:v.error?.code||null})));
  await page.locator(".comparison .pause").first().click();
  await page.locator(".controls input[type=range]").first().evaluate(e=>{
    e.value=42;e.dispatchEvent(new Event("input",{bubbles:true}));
  });
  await page.waitForFunction(() => [...document.querySelectorAll("section:first-of-type video")]
    .every(v=>!v.seeking && Math.abs(v.currentTime-42/24)<0.001), null, {timeout:10000});
  const seeking = await page.evaluate(() => [...document.querySelectorAll("section:first-of-type video")]
    .map(v=>({time:v.currentTime,paused:v.paused,error:v.error?.code||null})));
  await page.setViewportSize({width: 390, height: 844});
  const mobile = await page.evaluate(() => {
    const c=document.querySelector(".comparison");return {comparison_scrolls:c.scrollWidth>c.clientWidth,
      page_overflows:document.documentElement.scrollWidth>innerWidth};
  });
  await browser.close();
  const syncSpread = Math.max(...playback.map(v=>v.time))-Math.min(...playback.map(v=>v.time));
  const result={desktop,mobile,playback,seeking,sync_spread_seconds:syncSpread,page_errors:errors,
    passed:desktop.cases===5 && desktop.panels.every(n=>n===4) && desktop.new_pending===5 &&
      desktop.same_frame_sliders===5 && desktop.fullscreen_buttons===5 && !desktop.width_overflow &&
      mobile.comparison_scrolls && !mobile.page_overflows && errors.length===0 &&
      playback.every(v=>!v.paused && v.rate===1 && !v.error) && syncSpread<1/24 &&
      seeking.every(v=>v.paused && !v.error && Math.abs(v.time-42/24)<0.001),
    scope:"Prepared page only; no new R148 output is claimed. Browser used existing local files."};
  fs.writeFileSync(path.join(__dirname,"HTML_QA.json"),JSON.stringify(result,null,2)+"\n");
  console.log(JSON.stringify(result));
  if(!result.passed) process.exitCode=1;
})();
