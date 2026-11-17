import libs/canvas
import std/build
import std/io
std/build:requires {
    exe.linkSystemLibrary("koruos_shim");
    exe.linkSystemLibrary("objc");
    exe.linkFramework("Metal");
    exe.linkFramework("Foundation");
    exe.linkFramework("CoreFoundation");
}
std/io:print.ln("kn metal path")
|> libs/canvas:window.open(width: 64, height: 64, title: "kn mp")
| win w
    |> libs/canvas:frames(win: w, count: 1)
        ! frame f
            |> libs/canvas:window.clear.color(r: 1.0, g: 1.0, b: 1.0)
            |> libs/canvas:path.open() : p
            |> libs/canvas:path.move(p, x: 8.0, y: 8.0)
            |> libs/canvas:path.line(p, x: 56.0, y: 8.0)
            |> libs/canvas:path.line(p, x: 56.0, y: 56.0)
            |> libs/canvas:path.line(p, x: 8.0, y: 56.0)
            |> libs/canvas:path.close(p)
            |> libs/canvas:metal.pathfill(f, p, r: 1.0, g: 0.0, b: 0.0, a: 1.0, evenodd: 0)
            |> libs/canvas:window.snap(path: "/tmp/kn_mp.txt")
        | done dw
            |> libs/canvas:window.close(win: dw)
| err e |> std/io:print.ln("open failed {{ e:s }}")
