# Phase 0 design notes — canvas vector verbs (from session reads, 2026-11-16)

## Golden op set the verbs must express (oracle/goldens/*.txt)

Ops emitted by rive-native per frame: `save`, `restore`,
`transform a b c d e f` (Mat2D, 6 floats), `clipPath`,
`drawPath(style,color,thick,join,cap,blend,shader,fillRule)`,
`drawImage`, `modulateOpacity`. Path geometry: verbs
move=0 line=1 quad=2 cubic=4 close=5 (Skia values) + x,y point pairs.
Paint: fill(1)/stroke(0) style, RGBA color, stroke thickness/join/cap,
blend mode, optional shader (gradient/image — v2), fillRule
(even-odd=2 observed).

## Canvas architecture (oshun/canvas/index.macos.kz, ~3076 lines)

- Verbs are `~pub tor name { args }` decls + `~proc name|zig` Zig bodies.
  The part files ARE Zig host code — "Koru" surface, Zig implementation.
- Draw model: CPU emits `GpuInstance` structs (extern struct, 16B-aligned
  fields: rect[4], color[4], border_color[4], uv[4], clip[4], radius,
  border_width, kind, clip_round, silk[4]) into `f.insts` array;
  `instFlush` packs them into a shared MTLBuffer and draws ONE instanced
  quad call (`pso_inst`, 4 verts × n instances) — fragment shader does
  SDF eval per instance kind.
- inst kinds: quad=0 text=1 shadow=2 image=3 glass=5 frost=6 stroke=7
  gradient=8 gradient_radial=9. Kinds 8/9 unimplemented on koru-native —
  "refuses at compile, not silently" is the established loud-fail pattern.
- Non-instance draws (draw.triangle, draw.bezier?) call `instFlush(f)`
  first, then `setRenderPipelineState(f.pso)` + `drawPrimitives` —
  direct vertex path exists alongside instancing.
- Clips: `f.clip_stack` + `f.clip_depth`; `curClip(f)` reads innermost;
  `clipRound(f)` packs rounded-clip. Only rect/roundrect clips today.
- Frame fields seen: device, encoder, pso, pso_inst, insts, clip_stack,
  clip_depth, text.atlas, images.texture, scene_tex, time, vp_w, vp_h,
  flushed, plus window/surface plumbing elsewhere in file.
- Opaque-handle precedent: `image.load { path } | img i64 | err string`,
  `image.free { tex: i64 }`, `font.load` — i64 pointer handles with free
  verbs. Path handle should follow this shape.

## Proposed verb surface (v1, matches golden ops)

Path construction (handle lifecycle = the obligation story):
- `path.open {} | p *Path<open!> | err string` — allocates recording path
- `path.move { p: *Path<open!>, x, y }` — stays open!
- `path.line { p: *Path<open!>, x, y }`
- `path.quad { p: *Path<open!>, cx, cy, x, y }` (control + end)
- `path.cubic { p: *Path<open!>, c1x, c1y, c2x, c2y, x, y }`
- `path.close { p: *Path<open!> }`
- `path.end { p: *Path<!open> } -> *Path<built!>` — discharge open, issue built
- `path.free { p: *Path<!built> }` — consume

Drawing:
- `draw.path { f: *Frame<frame>, p: *Path<built>, fill_r,g,b,a,
  stroke_r,g,b,a, stroke_w, join, cap, fill_rule, even_odd? }`
  — or split `draw.path.fill` / `draw.path.stroke`? DECIDE: golden paint
  carries style+color+thickness together → single verb with both paint
  param sets, zero-values = off, mirrors draw.panel precedent.
- `transform.push { f: *Frame<frame>, a,b,c,d,e,f6: f64 }` /
  `transform.pop { f: *Frame<frame> }` — CTM stack on Frame.
  v1 impl: CPU-bake into path points at draw.path/clip.push.path emit
  (no shader change); honest scope note in verb doc.
- `clip.push.path { f: *Frame<frame>, p: *Path<built> }` — arbitrary
  clip; needs clip representation upgrade (today clip_stack entries are
  rect[4]+radius — path clip needs either stencil or rasterized mask;
  DECIDE: v1 may do scissor-from-bbox + fragment path-test is NOT
  possible in instanced quad model → likely needs the direct-draw path
  with stencil, OR defer clip.push.path to v1.5 and land
  transform.push/pop + draw.path first).

## Metal implementation sketch (the hard part)

Arbitrary path fill needs tessellation: flatten quad/cubic → line
segments (de Casteljau, tolerance ~0.25px) → polygon → ear-clip
triangulation → vertex buffer → draw with pso (non-instanced path,
instFlush first like draw.triangle). Stroke: offset-curve tessellation
is the hard version; v1 could do stroke via inst_stroke-style thick
quads only for quads? NO — honest v1: fill only + stroke via tessellated
stroke outline (or defer stroke, fillRule+fill first). DECIDE at write
time; fill-first is the steelman.

## koru-native part

Same decl signatures; bodies refuse loudly (compileError/panic naming
the missing rasterizer path — SDF model can't do arbitrary paths;
polygon coverage is its own project per commission phase 4).

## Still open

- Exact `part` decl mechanics for adding verbs (read index.kz part
  blocks + how index.macos.kz/index.koru-native.kz join).
- Whether Frame struct lives in a shared header both parts see
  (transform stack + clip_depth fields must exist in both).
- Zig-side path storage: page_allocator vector of verb/point pairs,
  i64 handle = pointer (image.load precedent).

---

## OUTCOME — phase 0 landed differently than sketched (oshun 36d20fc + 1910d4c)

The sketch assumed Metal tessellation + phantom handles. What shipped:

- **Backend: CoreGraphics rasterization, not Metal tessellation.** The
  sketch's hard part (ear-clipping, stroke offset curves, stencil fill
  rules) is CG's home turf — `CGPath` → `CGBitmapContext` → BGRA pixels →
  the SAME atlas→instanced-quad pipeline `draw.image` already proves.
  Fill rules, joins, caps, AA come correct for free; a native tessellator
  remains the documented optimization, not a correctness gap. One real
  bug found en route: `CGContextDrawPath` consumes the CONTEXT's current
  path — a standalone `CGPath` is inert until `CGContextAddPath`.
- **Handles: i64, not phantom.** `path.open` mints a 1-based index into a
  module-level `PathData` registry — `image.load`'s custody shape. The
  `*Path<open!>`→`*Path<built!>` phantom ladder is still the aspiration
  but the declaration mechanics for custom phantom types were never
  located in-tree; i64 is proven syntax. Upgrade is signature-level.
- **Transform stack: per-frame CTM on `Frame`.** `transform.push/pop`
  hold `[6]f64` affines (16 deep, loud panic on overflow/underflow —
  NOT clip.push's silent drop). Consumed by `draw.path` rasterization
  only; retrofitting CTM onto the ~50 primitive verbs is contract work,
  documented as such — not hidden.
- **clip.push.path: deliberately absent.** Rect `clip_stack` cannot
  express arbitrary path clips; doing it right needs mask/stencil
  infrastructure (rasterize clip → mask texture → shader-side test).
  Named gap, not worked around.
- **koru-native: zero new decls** → compile-time refusal, the
  `draw.gradient` precedent.

### Verbs shipped (macOS part only)

```
path.open {} -> i64
path.move/line { p, x, y }   path.quad { p, cx, cy, x, y }
path.cubic { p, c1x,c1y,c2x,c2y,x,y }   path.close { p }
path.reset { p }   path.free { p }
transform.push { f, a,b,c,d,e,g }   transform.pop { f }
draw.path { f, p, fr,fg,fb,fa, sr,sg,sb,sa, sw, join, cap, evenodd }
```

join: 0=miter 1=round 2=bevel; cap: 0=butt 1=round 2=square (CG numbering).
evenodd != 0 selects even-odd fill (Rive fillRule=2). Zero paint alpha
disables that paint — draw.panel's border convention.

### Verified

`canvas/tests/path_probe.k` — koruc -c + full build + run; snap BMP
pixel-read: fills, stroke, quad/cubic, CTM translate+scale+nested push,
evenodd vs nonzero all at expected positions/colors. NOT yet verified:
hidpi raster scale (1.0 unit=1px), clip.push.path, gradient shaders,
per-frame re-raster cost under animation load.
