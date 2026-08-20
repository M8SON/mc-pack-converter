// Loads a real, rendered report the way a browser would and asserts the
// page's own JS runs without throwing and that tiles actually render.
//
// test_report.py's checks are substring greps over app.js's text; none of
// them would catch render() throwing. A jsdom load exercising exactly this
// was done by hand during QA after the background-image fix (whole-branch
// review finding 9) and was not in the suite -- this puts it there.
import { JSDOM } from "jsdom";
import fs from "node:fs";

const fail = (m) => { console.error("FAIL: " + m); process.exitCode = 1; };

const html = fs.readFileSync(process.argv[2], "utf8");
const errors = [];

const dom = new JSDOM(html, { runScripts: "dangerously", resources: "usable" });
// render() runs from a DOMContentLoaded listener; jsdom does not let an
// exception thrown there propagate out of the constructor, it reports it
// through the virtualConsole instead.
dom.virtualConsole.on("jsdomError", (e) => errors.push(e));
const win = dom.window;

await new Promise((r) => setTimeout(r, 300));

if (errors.length)
  fail("the page's JS threw:\n" + errors.map((e) => e.stack || String(e)).join("\n"));

const doc = win.document;
const headline = doc.getElementById("headline").textContent;
const details = doc.getElementById("details").textContent;
const tileCount = doc.querySelectorAll(".tile").length;

if (!headline) fail("headline was not rendered");
if (!/^\d+ errors, \d+ warnings, \d+ notes$/.test(details))
  fail(`#details did not render the severity summary, got: ${JSON.stringify(details)}`);
if (tileCount === 0) fail("no tiles rendered onto the page");

if (!process.exitCode)
  console.log(`boot ok: headline=${JSON.stringify(headline)} details=${JSON.stringify(details)} tiles=${tileCount}`);
process.exit(process.exitCode || 0);
