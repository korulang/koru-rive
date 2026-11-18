// Path-arg render probe: ./a.out <file.riv> <out.bmp> — ab = Artboard object index (set per fixture; sm_conditions=5), last SM frame.
import libs/canvas
import kr/probe
import kr/rive
import std/io
import std/args
std/args:all(): av
|> std/io:print.ln("render_arg: {{av[1]:s}} -> {{av[2]:s}}")
|> libs/canvas:offscreen.open(width: 500, height: 500, scale: 1.0)
| surf s
    |> libs/canvas:offscreen.clear.color(s, r: 1.0, g: 0.0, b: 1.0)
    |> libs/canvas:offscreen.frame(s)
        ! frame f
            |> kr/rive:open(path: av[1])
            | loaded r
                |> kr/rive:ops(r, ab: 5, frame: -1)
                    ! op o |> kr/probe:step(o, f)
                    | done n |> std/io:print.ln("ops {{ n:d }}") |> kr/rive:free(r)
            | failed e |> std/io:print.ln("open failed")
        | done _
    |> libs/canvas:offscreen.snap(s, path: av[2])
    |> libs/canvas:offscreen.close(s)
    |> std/io:print.ln("snapped")
| err e |> std/io:print.ln("init failed: {{ e:s }}")
