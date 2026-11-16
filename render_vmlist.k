// CLI-authored fixture: Feed artboard of fixtures/vmlist/rive_smoke.riv, 400x600.
import libs/canvas
import kr/probe
import kr/rive
import std/io
std/io:print.ln("render_vmlist: start")
|> libs/canvas:offscreen.open(width: 400, height: 600, scale: 1.0)
| surf s
    |> libs/canvas:offscreen.clear.color(s, r: 1.0, g: 0.0, b: 1.0)
    |> libs/canvas:offscreen.frame(s)
        ! frame f
            |> kr/rive:open(path: "/Users/larsde/src/koru-rive/fixtures/vmlist/rive_smoke.riv")
            | loaded r
                |> kr/rive:ops(r, ab: 0, frame: -1)
                    ! op o |> kr/probe:step(o, f)
                    | done n |> std/io:print.ln("ops {{ n:d }}") |> kr/rive:free(r)
            | failed e |> std/io:print.ln("open failed")
        | done _
    |> libs/canvas:offscreen.snap(s, path: "/tmp/vmlist_ours.bmp")
    |> libs/canvas:offscreen.close(s)
    |> std/io:print.ln("snapped")
| err e |> std/io:print.ln("init failed: {{ e:s }}")
