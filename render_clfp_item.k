// Pixel verification probe. Clears to MAGENTA: after the backdrop fix the
// opaque artboard rect must cover every pixel, so zero magenta may remain.
import libs/canvas
import kr/probe
import kr/rive
import std/io
std/io:print.ln("render_clfp: start")
|> libs/canvas:offscreen.open(width: 500, height: 500, scale: 1.0)
| surf s
    |> libs/canvas:offscreen.clear.color(s, r: 1.0, g: 1.0, b: 1.0)
    |> libs/canvas:offscreen.frame(s)
        ! frame f
            |> libs/canvas:transform.push(f, a: 5.494505, b: 0.0, c: 0.0, d: 5.494505, e: 0.0, g: 107.1428)
            |> kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/component_list_follow_path.riv")
            | loaded r
                |> kr/rive:ops(r, ab: 74, frame: -1)
                    ! op o |> kr/probe:step(o, f)
                    | done n |> std/io:print.ln("ops {{ n:d }}") |> libs/canvas:transform.pop(f) |> kr/rive:free(r)
            | failed e |> std/io:print.ln("open failed")
        | done _
    |> libs/canvas:offscreen.snap(s, path: "/tmp/ours_clfp_item_t1.bmp")
    |> libs/canvas:offscreen.close(s)
    |> std/io:print.ln("snapped")
| err e |> std/io:print.ln("offscreen init failed: {{ e:s }}")
