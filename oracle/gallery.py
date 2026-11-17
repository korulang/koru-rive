#!/usr/bin/env python3
"""gallery.py — standing ours|ref contact sheet for koru-rive gates.

Every visual gate gets a pair image Lars can eyeball. Manifest maps each gate
to ours/ref file candidates (oracle/images/ preferred, /tmp fallback, newest
mtime wins). Output: oracle/images/pair_<gate>.png + oracle/gallery.html.

Usage: uv run --with pillow --with numpy python gallery.py
"""
import glob, html, os, sys
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(ROOT, "images")
TMP = "/tmp"

# gate -> (ours candidates, ref candidates, verdict label, note)
GATES = [
    ("hw",        ["ours_hw_t1.bmp", "ours_hw_t1.png"], ["ref_hw_c_t1.png"], "PASS", "hello_world bind pose"),
    ("cdo",       ["ours_cdo_child_t1.bmp"],             ["ref_cdo_child_t1.png"], "PASS", "cdo child artboard"),
    ("dsm",       ["ours_dsm_t1.png", "ours_dsm_c_t1.bmp"], ["ref_dsm_c_t1.png"], "PASS", "dsm bind pose (SM-name artifact resolved)"),
    ("dsm_row",   ["ours_dsm_row_bind.bmp", "ours_dsm_row_fit.bmp"], ["ref_dsm_row_t1.png", "ref_dsm_row_bind.png"], "PASS", "dsm bound row"),
    ("clfp",      ["ours_clfp_c_t1.bmp", "ours_clfp_c_t1.png"], ["ref_clfp_c_t1.png"], "PASS", "clfp Main t1"),
    ("clfp_item", ["ours_clfp_item_t1.bmp", "ours_clfp_item_vm_t1.bmp", "ours_clfp_item_f0.bmp"],
                   ["ref_clfp_item_t1.png", "ref_clfp_item_vm_t1.png", "ref_clfp_item_bind_t1.png"], "PASS", "clfp Item VM-bound"),
    ("cl1_item",  ["ours_cl1_item.bmp"],                  ["ref_cl1_item_t1.png"], "PASS", "cl1 Item per-row VM"),
    ("cl1_main",  ["ours_cl1_main*.bmp", "ours_cl1*.bmp"], ["ref_cl1_main_t1.png"], "PASS", "cl1 Main scroll+layout"),
    ("clv",       ["ours_clv*.bmp", "ours_clv*.png", "clv_ours.bmp"], ["ref_clv_t1.png", "ref_clv_t15.png"], "PASS", "clv clipped viewport absolute layout"),
    ("cl2",       ["ours_cl2_t1.bmp", "cl2_ours.bmp"], ["ref_cl2_t1.png"], "PASS", "cl2 NumberToList synthetic grid + flexWrap"),
    ("cl2_t10",   ["ours_cl2_t10.bmp"], ["ref_cl2_t10.png"], "PASS", "cl2 color keyframes animate item fill at t10"),
    ("clfp_hover",["ours_clfp_item_hover.bmp"], ["ref_clfp_item_hover.png"], "PASS", "clfp Item SM listener Hover:true@5 -> transition crossfade"),
    ("kn_sm_input",["ours_kn_sm_hover.bmp"], ["ref_clfp_item_hover.png"], "PASS", "NATIVE raster SM-input class: clfp Item Hover:true@5 (render_kn_sm_input.k)"),
    ("clip",      ["ours_clip_t1.bmp"],                   ["ref_clip_t1.png"], "PASS", "clip_tests Hidden-Path-Visible-Path"),
    ("cin",       ["ours_cin_t1.bmp"],                    ["ref_cin_t1.png"], "LIMIT", "custom_image_name — image decode LIVE, browser drops alpha (spec-correct)"),
    ("iba",       ["ours_iba_t1.bmp"],                    ["ref_iba_t1.png"], "LIMIT", "in_band_asset — 1x1 grayscale PNG, vacuous both sides"),
    ("lwti",      ["ours_lwti_t1.bmp"],                   ["ref_lwti_t1.png"], "LIMIT", "library_with_text_and_image — type-544 formula token, out-of-scope"),
    ("deam",      ["ours_deam_t1.bmp"],                   ["ref_deam_t1.png"], "LIMIT", "databind_external_artboard_main — VM-data class"),
    ("hff",       ["ours_hff_t1.bmp"],                    ["ref_hff_t1.png"], "LIMIT", "hosted_font_file — hosted font 404"),
    ("dcpo",      ["ours_dcpo_t1.bmp"],                   ["ref_dcpo_t1.png"], "LIMIT", "drawable_custom_properties_other — vacuous"),
    ("mesh",      ["ours_mesh_t1.bmp", "ours_mesh_noaa.bmp", "ours_mesh_paa.bmp"],
                   ["ref_clfp_c_t1.png", "ref_mesh*.png"], "NOTE", "mesh path — placement exact, AA verified pixel no-op"),
]

def resolve(cands):
    best = None
    for c in cands:
        hits = []
        for d in (IMG, TMP):
            hits += glob.glob(os.path.join(d, c))
        for h in hits:
            if os.path.isfile(h) and (best is None or os.path.getmtime(h) > os.path.getmtime(best)):
                best = h
    return best

def load(p):
    im = Image.open(p).convert("RGBA")
    return im

def composite(ours_p, ref_p, out_p, label):
    o, r = load(ours_p), load(ref_p)
    h = max(o.height, r.height)
    w = o.width + r.width + 8
    canvas = Image.new("RGBA", (w, h + 18), (24, 24, 28, 255))
    dr = ImageDraw.Draw(canvas)
    dr.text((4, 2), "OURS", fill=(255, 255, 255, 255))
    dr.text((o.width + 12, 2), "REF (browser rive_canvas)", fill=(255, 255, 255, 255))
    canvas.paste(o, (0, 18))
    canvas.paste(r, (o.width + 8, 18))
    canvas.convert("RGB").save(out_p)
    return (o.width, h)

def main():
    rows, missing = [], []
    for gate, oc, rc, verdict, note in GATES:
        op, rp = resolve(oc), resolve(rc)
        if not op or not rp:
            missing.append((gate, op, rp))
            rows.append((gate, None, verdict, note + "  [MISSING: ours=%s ref=%s]" % (bool(op), bool(rp))))
            continue
        out = os.path.join(IMG, "pair_%s.png" % gate)
        composite(op, rp, out, gate)
        rows.append((gate, "images/pair_%s.png" % gate, verdict, note))
    # html
    parts = ["<!doctype html><meta charset=utf-8><title>koru-rive gallery</title>",
             "<style>body{background:#18181c;color:#eee;font:14px/1.5 system-ui;margin:24px}",
             "h1{font-size:20px}h2{margin:28px 0 8px;font-size:15px;color:#9cf}",
             ".g{display:inline-block;margin:0 16px 24px 0;vertical-align:top}",
             ".g img{border:1px solid #444;display:block}",
             ".v{font-weight:600}.PASS{color:#7f7}.LIMIT{color:#fc6}.NOTE{color:#aaa}</style>",
             "<h1>koru-rive — ours | ref gallery</h1<p>Generated by oracle/gallery.py — regenerate after any visual change.</p>"]
    cur = None
    for gate, img, verdict, note in rows:
        v = "PASS" if verdict == "PASS" else ("LIMIT" if verdict == "LIMIT" else "NOTE")
        if v != cur:
            cur = v
            parts.append("<h2>%s</h2>" % ("pixel gates" if v == "PASS" else ("limitations (honest)" if v == "LIMIT" else "notes")))
        if img:
            parts.append('<div class=g><img src=%s width=640><div><b>%s</b> <span class="v %s">%s</span><br><small>%s</small></div></div>'
                         % (img, gate, v, verdict, html.escape(note)))
        else:
            parts.append('<div class=g><div><b>%s</b> <span class="v %s">%s</span><br><small>%s</small></div></div>'
                         % (gate, v, verdict, html.escape(note)))
    open(os.path.join(ROOT, "gallery.html"), "w").write("\n".join(parts))
    print("gallery.html written; %d gates, %d missing assets" % (len(rows), len(missing)))
    for g, o, r in missing:
        print("  missing:", g, "ours=%s ref=%s" % (o, r))

if __name__ == "__main__":
    main()
