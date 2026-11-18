// Pixel verification probe. Clears to MAGENTA: after the backdrop fix the
// opaque artboard rect must cover every pixel, so zero magenta may remain.
import libs/canvas
import kr/probe
import kr/rive
import std/io
std/io:print.ln("render_clfp: start")
|> libs/canvas:offscreen.open(width: 500, height: 500, scale: 1.0)
| surf s
    |> libs/canvas:offscreen.clear.color(s, r: 1.0, g: 0.0, b: 1.0)
    |> libs/canvas:offscreen.frame(s)
        ! frame f
            |> kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/hello_world.riv")
            | loaded r
                |> kr/rive:ops(r, ab: 3, frame: 0)
                    ! op o |> kr/probe:step(o, f)
                    | done n |> std/io:print.ln("ops {{ n:d }}") |> kr/rive:free(r)
            | failed e |> std/io:print.ln("open failed")
        | done _
    |> libs/canvas:offscreen.snap(s, path: "oracle/images/ours_hw_t1.bmp")
    |> libs/canvas:offscreen.close(s)
    |> std/io:print.ln("snapped")
| err e |> std/io:print.ln("offscreen init failed: {{ e:s }}")
