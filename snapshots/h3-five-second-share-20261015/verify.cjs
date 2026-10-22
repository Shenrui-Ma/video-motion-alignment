const { chromium } = require('/Users/researcher/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const assert = require('assert/strict');
const { pathToFileURL } = require('url');

(async () => {
  const work = __dirname;
  const download = '/Users/researcher/Downloads';
  const folder = path.join(download, 'H3_四组5秒对比_便携版_20261015');
  const standalone = path.join(download, 'H3_四组5秒对比_单文件版_20261015.html');
  const manifest = JSON.parse(fs.readFileSync(path.join(folder, 'manifest.json')));
  const text = fs.readFileSync(standalone, 'utf8');
  const embedded = [...text.matchAll(/src="data:video\/mp4;base64,([^"]+)"/g)];
  assert.equal(embedded.length, 4);
  embedded.forEach((m, i) => assert.equal(crypto.createHash('sha256').update(Buffer.from(m[1], 'base64')).digest('hex'), manifest.videos[i].sha256));
  const isolated = fs.mkdtempSync(path.join(os.tmpdir(), 'h3-share-offline-'));
  const copy = path.join(isolated, 'comparison.html');
  fs.copyFileSync(standalone, copy);
  const browser = await chromium.launch({executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true});
  const context = await browser.newContext({viewport: {width: 1440, height: 1100}, offline: true});
  const page = await context.newPage();
  const errors = [], network = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('request', r => { if (/^https?:/.test(r.url())) network.push(r.url()); });
  const results = {};
  try {
    for (const [name, file] of [['portable_folder', path.join(folder, 'index.html')], ['isolated_single_html', copy]]) {
      await page.goto(pathToFileURL(file).href);
      await page.waitForFunction(() => [...document.querySelectorAll('video')].length === 4 && [...document.querySelectorAll('video')].every(v => v.readyState >= 2));
      const media = await page.locator('video').evaluateAll(vs => vs.map(v => ({duration: v.duration, width: v.videoWidth, height: v.videoHeight, error: v.error?.message || null})));
      media.forEach(v => { assert.equal(v.duration, 5.875); assert.equal(v.width, 1968); assert.equal(v.height, 416); assert.equal(v.error, null); });
      await page.locator('#play').click();
      await page.waitForFunction(() => [...document.querySelectorAll('video')].every(v => !v.paused && v.currentTime > 0.15));
      await page.locator('#pause').click();
      assert(await page.locator('video').evaluateAll(vs => vs.every(v => v.paused)));
      await page.locator('#speed').selectOption('0.5');
      assert(await page.locator('video').evaluateAll(vs => vs.every(v => v.playbackRate === 0.5)));
      await page.locator('#speed').selectOption('1');
      await page.locator('#loop').check();
      assert(await page.locator('video').evaluateAll(vs => vs.every(v => v.loop)));
      await page.locator('#loop').uncheck();
      await page.locator('#restart').click();
      assert(await page.locator('video').evaluateAll(vs => vs.every(v => v.currentTime === 0)));
      assert(await page.locator('[data-download]').evaluateAll(as => as.every(a => a.href !== '#' && a.download.endsWith('.mp4'))));
      await page.locator('video').evaluateAll(vs => vs.forEach(v => v.currentTime = 55 / 24));
      await page.waitForFunction(() => [...document.querySelectorAll('video')].every(v => !v.seeking));
      await page.screenshot({path: path.join(work, name + '_desktop.png'), fullPage: true});
      await page.setViewportSize({width: 390, height: 844});
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({path: path.join(work, name + '_mobile.png'), fullPage: true});
      await page.setViewportSize({width: 1440, height: 1100});
      results[name] = {media, play_pause_seek_speed_loop_download: 'pass', mobile_horizontal_overflow: false};
    }
    await page.goto(pathToFileURL(path.join(download, 'H3_Musk真人书记舞_未加权与三倍_20261014/index.html')).href);
    await page.waitForFunction(() => document.querySelector('video').readyState >= 2);
    await page.locator('video').first().evaluate(v => {v.currentTime = 55 / 24});
    await page.waitForFunction(() => !document.querySelector('video').seeking);
    await page.screenshot({path: path.join(work, 'reference_desktop.png'), fullPage: false});
    assert.deepEqual(errors, []);
    assert.deepEqual(network, []);
    results.external_requests = network;
    results.browser_errors = errors;
    results.embedded_video_hashes_match_originals = true;
    results.single_html_test = 'Only the HTML file was copied into a new empty directory; browser network disabled; all four videos decoded and played.';
    fs.writeFileSync(path.join(work, 'verification.json'), JSON.stringify(results, null, 2));
    console.log(JSON.stringify(results, null, 2));
  } finally {
    await browser.close();
    fs.rmSync(isolated, {recursive: true, force: true});
  }
})().catch(e => {console.error(e); process.exitCode = 1});
