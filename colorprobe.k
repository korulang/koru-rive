// Baseline: does the canvas itself shift colours, or only the replay draw.path?
import libs/canvas
import std/io
std/io:print.ln("colorprobe")
|> libs/canvas:offscreen.open(width: 500, height: 120, scale: 1.0)
| surf s
    |> libs/canvas:offscreen.clear.color(s, r: 0.0, g: 0.0, b: 0.0)
    |> libs/canvas:offscreen.frame(s)
        ! frame f
            |> libs/canvas:draw.rect(f, x: 0, y: 0, w: 100, h: 120, r: 0.1921, g: 0.1921, b: 0.1921, a: 1.0)
            |> libs/canvas:draw.rect(f, x: 100, y: 0, w: 100, h: 120, r: 0.5019, g: 0.5019, b: 0.5019, a: 1.0)
            |> libs/canvas:draw.rect(f, x: 200, y: 0, w: 100, h: 120, r: 1.0, g: 0.0, b: 0.0, a: 1.0)
            |> libs/canvas:draw.rect(f, x: 300, y: 0, w: 100, h: 120, r: 0.0, g: 0.0, b: 0.0, a: 1.0)
        | done _
    |> libs/canvas:offscreen.snap(s, path: "/tmp/colorprobe.bmp")
    |> libs/canvas:offscreen.close(s)
    |> std/io:print.ln("snapped")
| err e |> std/io:print.ln("init failed: {{ e:s }}")
