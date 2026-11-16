// Reproduces the rive_card component path: 320x320 surface, artboard scaled
// by 320/500 exactly as components/rive_card.kz does. Cleared to MAGENTA so
// any uncovered area is unmissable.
import libs/canvas
import kr/probe
import kr/rive
import std/io
std/io:print.ln("render_card: start")
|> libs/canvas:offscreen.open(width: 320, height: 320, scale: 1.0)
| surf s
    |> libs/canvas:offscreen.clear.color(s, r: 1.0, g: 0.0, b: 1.0)
    |> libs/canvas:offscreen.frame(s)
        ! frame f
            |> libs/canvas:transform.push(f, a: 0.64, b: 0.0, c: 0.0, d: 0.64, e: 0.0, g: 0.0)
            |> kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/component_list_follow_path.riv")
            | loaded r
                |> kr/rive:ops(r, ab: 18, frame: 0)
                    ! op o |> kr/probe:step(o, f)
                    | done n |> std/io:print.ln("ops {{ n:d }}") |> kr/rive:free(r)
            | failed e |> std/io:print.ln("open failed")
        | done _
    |> libs/canvas:offscreen.snap(s, path: "/tmp/ours_card_t1.bmp")
    |> libs/canvas:offscreen.close(s)
    |> std/io:print.ln("snapped")
| err e |> std/io:print.ln("init failed: {{ e:s }}")
