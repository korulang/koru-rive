import libs/canvas
import std/build
import std/io
std/build:requires { exe.linkSystemLibrary("koruos_shim"); }
std/io:print.ln("kn path probe")
|> libs/canvas:window.open(width: 64, height: 64, title: "kn")
| win w
    |> libs/canvas:frames(win: w, count: 1)
        ! frame f
            |> libs/canvas:window.clear.color(r: 1.0, g: 1.0, b: 1.0)
            |> libs/canvas:path.open() : p
            |> libs/canvas:path.move(p, x: 4.0, y: 4.0)
            |> libs/canvas:path.line(p, x: 60.0, y: 4.0)
            |> libs/canvas:path.line(p, x: 60.0, y: 60.0)
            |> libs/canvas:path.line(p, x: 4.0, y: 60.0)
            |> libs/canvas:path.close(p)
            |> libs/canvas:draw.path(f, p, fr: 0, fg: 0, fb: 0, fa: 0, sr: 1, sg: 0, sb: 0, sa: 1, sw: 2.0, join: 0, cap: 0, evenodd: 0)
            |> libs/canvas:window.snap(path: "/tmp/kn_probe.txt")
        | done _
| err e
    |> std/io:print.ln("open failed {{e:s}}")
