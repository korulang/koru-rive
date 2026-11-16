// Row artboard (idx 20) of component_list_default_state_machine.riv, 200x200.
import libs/canvas
import kr/probe
import kr/rive
import std/io
std/io:print.ln("render_row: start")
|> libs/canvas:offscreen.open(width: 500, height: 500, scale: 1.0)
| surf s
    |> libs/canvas:offscreen.clear.color(s, r: 1.0, g: 1.0, b: 1.0)
    |> libs/canvas:offscreen.frame(s)
        ! frame f
            |> libs/canvas:transform.push(f, a: 2.5, b: 0.0, c: 0.0, d: 2.5, e: 0.0, g: 200.0)
            |> kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/component_list_default_state_machine.riv")
            | loaded r
                |> kr/rive:ops(r, ab: 20, frame: 0)
                    ! op o |> kr/probe:step(o, f)
                    | done n |> std/io:print.ln("ops {{ n:d }}") |> libs/canvas:transform.pop(f) |> kr/rive:free(r)
            | failed e |> std/io:print.ln("open failed")
        | done _
    |> libs/canvas:offscreen.snap(s, path: "oracle/images/ours_dsm_row_fit.bmp")
    |> libs/canvas:offscreen.close(s)
    |> std/io:print.ln("snapped")
| err e |> std/io:print.ln("init failed: {{ e:s }}")
