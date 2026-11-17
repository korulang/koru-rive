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
std/io:print.ln("kn metal probe")
|> libs/canvas:window.open(width: 64, height: 64, title: "kn metal")
| win w
    |> libs/canvas:frames(win: w, count: 1)
        ! frame f
            |> libs/canvas:window.clear.color(r: 1.0, g: 1.0, b: 1.0)
            |> libs/canvas:metal.tri(f, r: 0.0, g: 0.0, b: 1.0)
            |> libs/canvas:window.snap(path: "/tmp/kn_metal.txt")
        | done dw
            |> libs/canvas:window.close(win: dw)
| err e |> std/io:print.ln("open failed {{ e:s }}")
