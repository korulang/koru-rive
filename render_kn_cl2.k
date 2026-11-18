// koru-native pixel gate: cl2 via window+frames (no offscreen on
// koru-native). Surface backing dumps to /tmp/kn_surface_500x500.bmp
// on close via the koruos-darwin host shim.
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
std/io:print.ln("render_kn_cl2: start")
|> libs/canvas:window.open(width: 500, height: 500, title: "kn cl2")
| win w
    |> libs/canvas:frames(win: w, count: 1)
        ! frame f
            |> libs/canvas:window.clear.color(r: 1.0, g: 1.0, b: 1.0)
            |> kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/component_list_2.riv")
            | loaded r
                |> kr/rive:ops(r, ab: 15, frame: 0)
                    ! op o |> kr/probe:step(o, f)
                    | done n |> std/io:print.ln("ops {{ n:d }}") |> kr/rive:free(r)
            | failed e |> std/io:print.ln("open failed")
        | done dw
            |> libs/canvas:window.close(win: dw)
            |> std/io:print.ln("closed")
| err e |> std/io:print.ln("open failed {{ e:s }}")
