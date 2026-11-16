// *** OUTLIER -- DO NOT USE AS THE ORACLE ***
// This renders through @rive-app/canvas on node-canvas. Compared against two
// independent browser backends (Canvas2D and WebGL2 in headless Chrome) it
// disagrees: at the wave apex it measures 1.50px stroke coverage where both
// browser backends measure 1.00/0.98, and at tick 4 it differs by ~17% of ink.
// Every reference image in /tmp/rive_oracle was produced by this path, which is
// why an entire investigation compared against an artifact. Use
// oracle/render_browser.mjs instead.
//
// Reference renderer: the REAL Rive runtime (@rive-app/canvas), pinned to the
// version that produced the existing reference corpus (2.39.0).
//
//   node oracle/render_ref.mjs <file.riv> <artboard> <ms> <out.png> [size]
//
// Two failure modes this guards against, both observed:
//
//  1. Silent blank output. The old renderer emitted a fully transparent PNG
//     and exited 0. @rive-app/canvas 2.5x calls canvas.addEventListener during
//     load; node-canvas has no such method, the throw aborted the load, and
//     the empty canvas was written anyway. Shim the listener API, disable
//     listeners, and VERIFY the raster is non-empty before writing.
//
//  2. Unpinned version. pnpm/npm will happily float ^2.39 to 2.50, which
//     changes rendering. The version is asserted below.
//
// `ms` is wall-clock in the state machine's own time base, which is inherently
// approximate: the SM advances on requestAnimationFrame ticks. Prefer the
// deterministic path when it is available; treat cross-time comparisons with
// the tick-pairing rule (reference tick T <-> koru frame 2*(T-1)).
import pkg from '@rive-app/canvas';
const { Rive, Layout, Fit, Alignment } = pkg;
import { createCanvas, Canvas } from 'canvas';
import fs from 'fs';

const EXPECTED_RIVE = '2.39.0';
const actual = JSON.parse(fs.readFileSync(new URL('./node_modules/@rive-app/canvas/package.json', import.meta.url))).version;
if (actual !== EXPECTED_RIVE) {
  console.error(`REFUSING: @rive-app/canvas is ${actual}, reference corpus was made with ${EXPECTED_RIVE}. ` +
                `Reference renders are version-dependent; pin it rather than comparing across versions.`);
  process.exit(4);
}

globalThis.HTMLCanvasElement = Canvas;
globalThis.devicePixelRatio = 1;
globalThis.document = {
  createElement: (t) => t === 'canvas' ? createCanvas(2, 2) : {},
  createElementNS: () => ({}),
  addEventListener: () => {}, removeEventListener: () => {},
  hidden: false, visibilityState: 'visible',
};
globalThis.window = globalThis;

// Deterministic time. The SM only advances on requestAnimationFrame ticks, so
// a wall-clock timeout races the tick and sometimes draws nothing (that is why
// ref_f0 was blank and ref_f8 was not). Drive the clock and the rAF queue
// ourselves: `tick` becomes an exact number of 1/30 s steps.
let rafQueue = [];
let fakeNow = 0;
const DT_MS = 1000 / 30;
try { performance.now = () => fakeNow; } catch {}
globalThis.requestAnimationFrame = (cb) => { rafQueue.push(cb); return rafQueue.length; };
globalThis.cancelAnimationFrame = () => {};
function pump(n) {
  for (let i = 0; i < n; i++) {
    fakeNow += DT_MS;
    const q = rafQueue; rafQueue = [];
    for (const cb of q) cb(fakeNow);
  }
}

class Path2D {
  constructor() { this.cmds = []; }
  moveTo(...a) { this.cmds.push(['moveTo', ...a]); }
  lineTo(...a) { this.cmds.push(['lineTo', ...a]); }
  bezierCurveTo(...a) { this.cmds.push(['bezierCurveTo', ...a]); }
  quadraticCurveTo(...a) { this.cmds.push(['quadraticCurveTo', ...a]); }
  arc(...a) { this.cmds.push(['arc', ...a]); }
  arcTo(...a) { this.cmds.push(['arcTo', ...a]); }
  ellipse(...a) { this.cmds.push(['ellipse', ...a]); }
  rect(...a) { this.cmds.push(['rect', ...a]); }
  closePath() { this.cmds.push(['closePath']); }
}
globalThis.Path2D = Path2D;
const ctxproto = Object.getPrototypeOf(createCanvas(1, 1).getContext('2d'));
const replay = (ctx, p) => { for (const [c, ...a] of p.cmds) ctx[c](...a); };
for (const m of ['fill', 'stroke', 'clip']) {
  const orig = ctxproto[m];
  ctxproto[m] = function (a, b) {
    if (a instanceof Path2D) { replay(this, a); return orig.call(this, b); }
    if (b instanceof Path2D) { replay(this, b); return orig.call(this, a); }
    return orig.call(this, a, b);
  };
}

const file = process.argv[2];
const abName = process.argv[3] || 'Main';
const tick = parseInt(process.argv[4] || '0', 10);
const out = process.argv[5] || '/tmp/rive_oracle/ref.png';
const size = parseInt(process.argv[6] || '500', 10);
if (!file || !out) { console.error('usage: render_ref.mjs <file.riv> <artboard> <tick> <out.png> [size]'); process.exit(2); }

const canvas = createCanvas(size, size);
canvas.getBoundingClientRect = () => ({ width: size, height: size, left: 0, top: 0, right: size, bottom: size });
canvas.addEventListener = () => {};
canvas.removeEventListener = () => {};
canvas.setAttribute = () => {};
canvas.focus = () => {};

await new Promise((res, rej) => {
  const rive = new Rive({
    buffer: fs.readFileSync(file),
    canvas,
    artboard: abName,
    stateMachines: 'State Machine 1',
    autoplay: true,
    shouldDisableRiveListeners: true,
    layout: new Layout({ fit: Fit.Contain, alignment: Alignment.Center }),
    onLoad: () => {
      try { rive.resizeDrawingSurfaceToCanvas(); } catch (e) { console.error('resize failed:', e.message); }
      pump(tick);
      try { rive.draw(); } catch (e) { console.error('draw failed:', e.message); }
      res(rive);
    },
    onLoadError: (e) => { console.error('LOADERR', JSON.stringify(e)); rej(new Error('load failed')); },
  });
});

const ctx = canvas.getContext('2d');
const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
let maxA = 0, nonEmpty = 0;
for (let i = 3; i < data.length; i += 4) {
  if (data[i] > maxA) maxA = data[i];
  if (data[i] > 0) nonEmpty++;
}
if (maxA === 0 || nonEmpty === 0) {
  console.error(`BLANK RENDER: ${size}x${size} tick=${tick} artboard=${abName} alphaMax=${maxA}`);
  process.exit(3);
}
fs.writeFileSync(out, canvas.toBuffer('image/png'));
console.log(JSON.stringify({ out, size: [size, size], tick, ab: abName, rive: actual, alphaMax: maxA, nonEmptyPx: nonEmpty }));
process.exit(0);
