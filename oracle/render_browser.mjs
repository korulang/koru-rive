// Render a .riv through a chosen Rive WEB runtime in headless Chrome.
//
//   node render_browser.mjs <mod> <tick> <out.png> [size]
//     mod: rive_canvas (Canvas2D backend) | rive_webgl (WebGL2 backend)
//
// Both packages are the same version, so the comparison isolates the
// RENDERER BACKEND, not version drift -- the mistake of comparing three
// builds of one package.
//
// Determinism: requestAnimationFrame and performance.now are replaced before
// the runtime loads, so `tick` is an exact number of 1/30 s steps rather than
// a race against wall-clock time.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright-core';
import { PNG } from 'pngjs';

const [mod, tickArg, out, sizeArg, abArg, smArg] = process.argv.slice(2);
const tick = parseInt(tickArg, 10);
const size = parseInt(sizeArg || '500', 10);
const ROOT = '/tmp/rive_oracle';
const EXPECTED = process.env.RIVE_EXPECT || '2.37.0';
const versions = {};
for (const m of ['rive_canvas', 'rive_webgl']) {
  try { versions[m] = JSON.parse(fs.readFileSync(`${ROOT}/node_modules/${m}/package.json`)).version; }
  catch (e) { versions[m] = 'MISSING'; }
}
if (versions.rive_canvas !== versions.rive_webgl) {
  console.error(`REFUSING: backends are different versions (${versions.rive_canvas} vs ${versions.rive_webgl}); ` +
                `the comparison would confound backend with version drift.`);
  process.exit(4);
}
if (EXPECTED !== 'any' && versions[mod] !== EXPECTED) {
  console.error(`REFUSING: ${mod} is ${versions[mod]}, expected ${EXPECTED}. Rive rendering is version-dependent; ` +
                `pin it (RIVE_EXPECT=any to override deliberately).`);
  process.exit(4);
}
const FIXTURE = process.env.RIVE_FIXTURE || '/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/component_list_follow_path.riv';

const AB = abArg || 'Main';
const SM = smArg === undefined ? 'State Machine 1' : smArg;
const SMPROP = SM ? `stateMachines: ${JSON.stringify(SM)},` : '';
const ABPROP = AB ? `artboard: ${JSON.stringify(AB)},` : '';
const PAGE = (m) => `<!doctype html><html><body style="margin:0;background:transparent">
<script>
  window.__rafQueue=[]; window.__fakeNow=0; window.__DT=1000/30;
  performance.now = () => window.__fakeNow;
  window.requestAnimationFrame = cb => { window.__rafQueue.push(cb); return 1; };
  window.cancelAnimationFrame = () => {};
  window.__pump = n => { for (let i=0;i<n;i++){ window.__fakeNow += window.__DT;
    const q=window.__rafQueue; window.__rafQueue=[]; for (const cb of q) cb(window.__fakeNow); } };
</script>
<script src="/node_modules/${m}/rive.js"></script>
<script>
(async () => {
  const params = new URLSearchParams(location.search);
  const tick = parseInt(params.get('tick')||'1');
  const size = parseInt(params.get('size')||'500');
  const canvas = document.createElement('canvas');
  canvas.width = size; canvas.height = size; canvas.style.display='block';
  document.body.appendChild(canvas);
  const { Rive, Layout, Fit, Alignment } = window.rive;
  const buf = await (await fetch('/fixture.riv')).arrayBuffer();
  window.__ready = new Promise((res, rej) => {
    const r = new Rive({
      buffer: buf, canvas,
      ${ABPROP}
      ${SMPROP}
      autoplay: true, shouldDisableRiveListeners: true,
      layout: new Layout({ fit: Fit.Contain, alignment: Alignment.Center }),
      onLoad: () => {
        r.resizeDrawingSurfaceToCanvas();
        // Optional ViewModel binding. Without this the component list has no
        // data and Rive draws no rows -- which is exactly the ambiguity for
        // component_list_default_state_machine.
        if (params.get('bind') === '1') {
          try {
            // Bind by artboard name if possible, else the first ViewModel.
            // Hardcoding a VM name is how the dsm probe first read blank.
            let vm = null;
            for (const n of [${JSON.stringify(AB)}, 'Main', 'Default']) {
              if (vm) break;
              try { vm = r.viewModelByName ? r.viewModelByName(n) : null; } catch (e) {}
            }
            for (let i = 0; !vm && i < 64; i++) {
              try { vm = r.viewModelByIndex ? r.viewModelByIndex(i) : null; } catch (e) { break; }
            }
            let inst = null;
            if (vm) {
              try { inst = vm.instanceByName ? vm.instanceByName('Default') : null; } catch (e) {}
              if (!inst) { try { inst = vm.defaultInstance ? vm.defaultInstance() : null; } catch (e) {} }
              if (!inst) { try { inst = vm.instance ? vm.instance() : null; } catch (e) {} }
            }
            if (inst) { r.bindViewModelInstance(inst); window.__bound = true; }
            else window.__bound = 'no-instance(vm=' + !!vm + ')';
          } catch (e) { window.__bound = 'err:' + e.message; }
        }
        window.__pump(tick); r.draw(); window.__redraw = () => r.draw(); res('ok');
      },
      onLoadError: (e) => rej(new Error(JSON.stringify(e))),
    });
  });
})();
</script></body></html>`;

const MIME = { '.js': 'text/javascript', '.wasm': 'application/wasm', '.json': 'application/json' };
const server = http.createServer((req, res) => {
  const u = new URL(req.url, 'http://x');
  if (u.pathname === '/') {
    res.writeHead(200, { 'content-type': 'text/html' });
    return res.end(PAGE(mod));
  }
  if (u.pathname === '/fixture.riv') {
    res.writeHead(200, { 'content-type': 'application/octet-stream' });
    return res.end(fs.readFileSync(FIXTURE));
  }
  const p = path.join(ROOT, decodeURIComponent(u.pathname));
  if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) {
    res.writeHead(404); return res.end('no');
  }
  res.writeHead(200, { 'content-type': MIME[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const port = server.address().port;

const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true,
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--disable-gpu-sandbox'],
});
const page = await browser.newPage({ viewport: { width: size, height: size } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error' || process.env.RIVE_DEBUG) errors.push(m.type()+': '+m.text()); });

await page.goto(`http://127.0.0.1:${port}/?tick=${tick}&size=${size}&bind=${process.env.BIND_VM === '1' ? 1 : 0}`, { waitUntil: 'load' });
let ready;
try {
  ready = await page.evaluate(() => window.__ready, { timeout: 60000 });
} catch (e) {
  ready = 'timeout';
}
if (ready !== 'ok') {
  console.error('not ready:', ready, errors.slice(0, 3));
  await browser.close(); server.close(); process.exit(3);
}

// Prefer the canvas's own pixels; fall back to a composited screenshot when a
// WebGL context has no preserveDrawingBuffer (toDataURL then returns blank).
// A WebGL context created without preserveDrawingBuffer returns a blank
// toDataURL, so composite instead: redraw, then screenshot the element.
const viaShot = mod === 'rive_webgl';
let buf;
if (viaShot) {
  await page.evaluate(() => window.__redraw && window.__redraw());
  buf = await page.locator('canvas').screenshot({ omitBackground: true });
} else {
  buf = Buffer.from((await page.evaluate(() => document.querySelector('canvas').toDataURL('image/png'))).split(',')[1], 'base64');
}
// Blank guard on the ACTUAL BYTES we are about to write. The old harness wrote
// fully transparent PNGs and exited 0, and every consumer downstream treated
// them as references. Copying a WebGL canvas into a 2D context returns blank
// (no preserveDrawingBuffer), so decode the captured PNG instead.
let stats = { maxA: 0, nonEmpty: 0 };
try {
  const png = PNG.sync.read(buf);
  for (let i = 3; i < png.data.length; i += 4) {
    const a = png.data[i];
    if (a > stats.maxA) stats.maxA = a;
    if (a > 0) stats.nonEmpty++;
  }
} catch (e) {
  console.error('CAPTURE UNDECODABLE: ' + e.message);
  await browser.close(); server.close();
  process.exit(5);
}
if (stats.maxA === 0 || stats.nonEmpty === 0) {
  console.error(`BLANK RENDER: ${mod} tick=${tick} size=${size} ab=${AB} sm=${SM} alphaMax=${stats.maxA}`);
  await browser.close(); server.close();
  process.exit(3);
}
fs.writeFileSync(out, buf);
const bound = await page.evaluate(() => window.__bound || false);
console.log(JSON.stringify({ mod, version: versions[mod], tick, size, out, ab: AB, sm: SM, bound, viaScreenshot: viaShot, alphaMax: stats.maxA, nonEmptyPx: stats.nonEmpty, errors: errors.slice(0, 2) }));
await browser.close();
server.close();
process.exit(0);
