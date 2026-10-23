#!/usr/bin/env node
// Render a lesson in a real browser at desktop and phone widths before publishing.
// Usage: node scripts/check_lesson_render.mjs <day> [screenshot-dir]
// Needs Playwright with Chromium; set PLAYWRIGHT_MODULE to its path if it is not resolvable.
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { extname, join, normalize, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const day = Number(process.argv[2]);
const outDir = resolve(process.argv[3] || join(root, '.render-check'));
if (!Number.isInteger(day) || day < 1) {
  console.error('usage: node scripts/check_lesson_render.mjs <day> [screenshot-dir]');
  process.exit(2);
}

const require = createRequire(import.meta.url);
function loadPlaywright() {
  const candidates = [process.env.PLAYWRIGHT_MODULE, 'playwright', '/opt/node22/lib/node_modules/playwright'].filter(Boolean);
  for (const name of candidates) {
    try { return require(name); } catch { /* try the next location */ }
  }
  console.error('Playwright is not available. Install it or set PLAYWRIGHT_MODULE.');
  process.exit(2);
}
const { chromium } = loadPlaywright();

const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png' };
const server = createServer(async (request, response) => {
  const path = normalize(decodeURIComponent(new URL(request.url, 'http://x').pathname)).replace(/^([/\\])+/, '');
  const file = join(root, path || 'index.html');
  if (!file.startsWith(root)) { response.writeHead(403).end(); return; }
  try {
    const body = await readFile(file);
    response.writeHead(200, { 'Content-Type': types[extname(file)] || 'application/octet-stream' }).end(body);
  } catch {
    response.writeHead(404).end('not found');
  }
});
await new Promise((done) => server.listen(0, '127.0.0.1', done));
const base = `http://127.0.0.1:${server.address().port}/`;
await mkdir(outDir, { recursive: true });

const problems = [];
const pad = String(day).padStart(2, '0');
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
// Fonts and the Wikimedia image come from the network; their failures are not lesson errors.
const ignorable = (text) => /fonts\.(googleapis|gstatic)|upload\.wikimedia\.org|ERR_NAME_NOT_RESOLVED|ERR_INTERNET_DISCONNECTED|net::ERR_/.test(text);

for (const [label, width, height] of [['desktop', 1280, 900], ['mobile', 375, 812]]) {
  const page = await browser.newPage({ viewport: { width, height } });
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => { if (message.type() === 'error' && !ignorable(message.text())) errors.push(message.text()); });

  await page.goto(`${base}lesson.html?day=${day}`, { waitUntil: 'networkidle' }).catch(() => {});
  await page.waitForTimeout(1500);
  if (await page.$('.missing-lesson')) problems.push(`${label}: lesson page says Day ${day} is not published`);
  if (day > 1) {
    const frame = await page.$('.lesson-demo iframe');
    if (!frame) problems.push(`${label}: demo iframe is missing`);
    else {
      const demo = await frame.contentFrame();
      const canvas = demo && (await demo.evaluate(() => {
        const c = document.querySelector('canvas');
        if (!c) return null;
        const r = c.getBoundingClientRect();
        let painted = false;
        try {
          const ctx = c.getContext('2d');
          const data = ctx && ctx.getImageData(0, 0, Math.min(c.width, 64), Math.min(c.height, 64)).data;
          painted = !!data && data.some((value, index) => index % 4 === 3 && value !== 0);
        } catch { painted = true; /* WebGL or tainted canvas: size check only */ }
        return { width: r.width, height: r.height, painted, overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth };
      }).catch((error) => ({ error: error.message })));
      if (!canvas) problems.push(`${label}: demo has no canvas`);
      else if (canvas.error) problems.push(`${label}: demo could not be inspected (${canvas.error})`);
      else {
        if (canvas.width < 100 || canvas.height < 100) problems.push(`${label}: demo canvas is too small (${Math.round(canvas.width)}×${Math.round(canvas.height)})`);
        if (!canvas.painted) problems.push(`${label}: demo canvas looks blank`);
        if (canvas.overflow > 1) problems.push(`${label}: demo scrolls sideways by ${canvas.overflow}px`);
      }
    }
  }
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (overflow > 1) problems.push(`${label}: lesson page scrolls sideways by ${overflow}px`);
  for (const error of errors) problems.push(`${label}: script error — ${error}`);
  await page.screenshot({ path: join(outDir, `day-${pad}-${label}.png`), fullPage: true });
  await page.close();
}

// The home page builds its lesson list from curriculum.json, so the lesson must be published there.
const home = await browser.newPage({ viewport: { width: 1280, height: 900 } });
await home.goto(base, { waitUntil: 'networkidle' }).catch(() => {});
const listed = await home.evaluate(async (d) => {
  const curriculum = await (await fetch('./curriculum.json')).json();
  return curriculum.lessons.some((lesson) => lesson.day === d && lesson.status === 'published');
}, day).catch(() => false);
if (!listed) problems.push(`home: Day ${day} is not published in curriculum.json`);
await home.close();

await browser.close();
server.close();
console.log(`screenshots: ${outDir}`);
if (problems.length) {
  console.log('FAIL');
  for (const problem of problems) console.log(` - ${problem}`);
  process.exit(1);
}
console.log(`ok   Day ${day} renders on desktop and mobile without errors`);
