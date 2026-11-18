import libs/canvas
import kr/probe
import kr/rive
import std/build
import std/io
std/build:requires {
    exe.linkSystemLibrary("koruos_shim");
    exe.linkSystemLibrary("objc");
    exe.linkFramework("Metal");
    exe.linkFramework("Foundation");
    exe.linkFramework("CoreFoundation");
    exe.linkFramework("CoreGraphics");
    exe.linkFramework("ImageIO");
}
std/io:print.ln("render_kn_clip: start")
|> libs/canvas:window.open(width: 500, height: 500, title: "kn clip")
| win w
    |> libs/canvas:frames(win: w, count: 1)
        ! frame f
            |> libs/canvas:window.clear.color(r: 0.10196078, g: 0.10196078, b: 0.14901961)
            |> kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/clip_tests.riv")
            | loaded r
                |> kr/rive:ops(r, ab: 42, frame: -1)
                    ! op o |> kr/probe:step(o, f)
                    | done n2 |> std/io:print.ln("ops {{ n2:d }}") |> kr/rive:free(r)
            | failed e |> std/io:print.ln("open failed")
        | done dw
            |> libs/canvas:window.close(win: dw)
            |> std/io:print.ln("closed")
| err e |> std/io:print.ln("open failed {{ e:s }}")
