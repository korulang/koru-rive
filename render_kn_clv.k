import libs/canvas
import kr/probe
import kr/rive
import std/build
import std/io
std/build:requires { exe.linkSystemLibrary("koruos_shim"); }
std/io:print.ln("render_kn_clv: start")
|> libs/canvas:window.open(width: 400, height: 400, title: "kn clv")
| win w
    |> libs/canvas:frames(win: w, count: 1)
        ! frame f
            |> libs/canvas:window.clear.color(r: 1.0, g: 1.0, b: 1.0)
            |> kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/component_list_clipped_viewport.riv")
            | loaded r
                |> kr/rive:ops(r, ab: 25, frame: 0)
                    ! op o |> kr/probe:step(o, f)
                    | done n2 |> std/io:print.ln("ops {{ n2:d }}") |> kr/rive:free(r)
            | failed e |> std/io:print.ln("open failed")
        | done dw
            |> libs/canvas:window.close(win: dw)
            |> std/io:print.ln("closed")
| err e |> std/io:print.ln("open failed {{ e:s }}")
