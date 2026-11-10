// Run with PUPPETEER_MODULE=/path/to/puppeteer-core/lib/puppeteer/puppeteer-core.js
// after building and serving build/web on localhost:8000. Rebuilds a temporary
// package change, then restores the source and rebuilds the original package.
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
const { default: puppeteer } = await import(process.env.PUPPETEER_MODULE);
const browser = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome-stable',
  headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage();
const responses = [];
page.on('response', r => responses.push({ url: r.url(), cached: r.fromServiceWorker() }));
page.on('pageerror', e => console.error(e));
const ready = async () => page.waitForFunction(() => !document.querySelector('#choose').disabled,
  { timeout: 120000 });
const caches = () => page.evaluate(() => window.caches.keys());
const source = new URL('../mc_pack_converter/job.py', import.meta.url);
const original = readFileSync(source, 'utf8');
let modified = false;
const build = () => execFileSync('.venv/bin/python', ['tools/build_web.py'], { stdio: 'inherit' });
try {
  await page.goto('http://localhost:8000/');
  await ready();
  const first = await caches();
  assert.equal(first.length, 1);
  responses.length = 0;
  await page.reload();
  await ready();
  const big = responses.filter(r => /\.(wasm|zip|whl)$/.test(r.url));
  assert.ok(big.length >= 5, JSON.stringify(responses));
  assert.ok(big.every(r => r.cached), JSON.stringify(big));
  console.log('Second load: runtime, stdlib, Pillow, numpy and converter served by service worker', big);
  await page.setOfflineMode(true);
  await page.reload();
  await ready();
  console.log('Offline reload: Choose a pack enabled');
  await page.setOfflineMode(false);
  modified = true;
  assert.ok(original.includes('DEFAULT_TARGET = "26.3"'));
  writeFileSync(source, original.replace('DEFAULT_TARGET = "26.3"', 'DEFAULT_TARGET = "26.2"'));
  build();
  responses.length = 0;
  await page.reload();
  await ready();
  const second = await caches();
  assert.equal(second.length, 1);
  assert.notEqual(second[0], first[0]);
  assert.equal(await page.$eval('#targets button[aria-pressed="true"]',
    button => button.textContent), '26.2');
  console.log('Rebuilt package executed in Python; old cache removed:', second);
} finally {
  await browser.close();
  if (modified) {
    writeFileSync(source, original);
    build();
  }
}
