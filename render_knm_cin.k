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
std/io:print.ln("render_knm_cin")
|> libs/canvas:window.open(width: 500, height: 500, title: "knm cin")
| win w
    |> libs/canvas:frames(win: w, count: 1)
        ! frame f
            |> libs/canvas:metal.paths(on: 1)
            |> libs/canvas:window.clear.color(r: 1.0, g: 1.0, b: 1.0)
            |> libs/canvas:transform.push(f, a: 1.0, b: 0.0, c: 0.0, d: 1.0, e: 0.0, g: 0.0)
            |> kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/custom_image_name.riv")
            | loaded r
                |> kr/rive:ops(r, ab: 3, frame: -1)
                    ! op o |> kr/probe:step(o, f)
                    | done n |> std/io:print.ln("ops {{ n:d }}") |> libs/canvas:transform.pop(f) |> kr/rive:free(r)
            | failed e |> std/io:print.ln("open failed")
        | done dw
            |> libs/canvas:window.close(win: dw)
| err e |> std/io:print.ln("open failed {{ e:s }}")
