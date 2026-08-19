// Loads the real app.js the way pywebview loads it and asserts the page boots
// exactly once, and only once its bridge is actually callable.
//
// pywebview injects api.js first, which sets window.pywebview.api to an EMPTY
// OBJECT, and only later runs _createApi to put the methods on it. A page that
// treats the object's existence as "the bridge is up" boots into a TypeError
// and ends up live but wired to nothing. That shipped once; this stops it.
import fs from "node:fs";
import vm from "node:vm";

const fail = (m) => { console.error("FAIL: " + m); process.exitCode = 1; };
const src = fs.readFileSync(process.argv[2], "utf8");

const el = () => new Proxy(
  { classList: { toggle() {}, add() {}, remove() {} }, querySelectorAll: () => [],
    addEventListener() {}, style: { setProperty() {} },
    textContent: "", innerHTML: "", hidden: false, dataset: {} },
  { set: (t, k, v) => { t[k] = v; return true; } });

const listeners = {};
const ctx = vm.createContext({
  addEventListener: (n, f) => { (listeners[n] ||= []).push(f); },
  setInterval, clearInterval, setTimeout, clearTimeout, console,
  document: { getElementById: el, addEventListener() {}, querySelectorAll: () => [] },
});
ctx.window = ctx;

let ready = 0, targets = 0;

// 1. api.js has run: the object exists, with no methods on it yet.
ctx.window.pywebview = { token: "t", platform: "edgechromium", api: {} };
vm.runInContext(src, ctx);
if (ready !== 0) fail(`booted before the bridge was callable (ready called ${ready}x)`);

// 2. finish.js runs _createApi, then fires the event.
ctx.window.pywebview.api.ready = () => { ready++; return Promise.resolve(true); };
ctx.window.pywebview.api.targets = () => { targets++; return Promise.resolve({ targets: ["26.1.2"], current: "26.1.2" }); };
ctx.window.pywebview.api.poll = () => Promise.resolve(
  { headline: "", details: [], screen: "idle", findings: [], total: 0, done: 0 });
for (const f of listeners["pywebviewready"] || []) f();
if (ready !== 1) fail(`did not boot when the bridge arrived (ready called ${ready}x)`);

// 3. a repeated event must not boot a second time.
for (const f of listeners["pywebviewready"] || []) f();
setTimeout(() => {
  if (ready !== 1) fail(`booted more than once (ready called ${ready}x)`);
  if (targets !== 1) fail(`version list fetched ${targets}x, expected once`);
  if (!process.exitCode) console.log("boot sequence ok");
  // tick() reschedules itself forever, so the event loop never drains on its
  // own -- leave deliberately rather than hanging the test.
  process.exit(process.exitCode || 0);
}, 50);
