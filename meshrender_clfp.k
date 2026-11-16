// Tier-2 probe: ops -> tessellated Tri soup -> canvas mesh.* verbs.
import libs/canvas
import kr/probe
import kr/rive
import std/io

std/io:print.ln("meshrender: start")
|> libs/canvas:offscreen.open(width: 500, height: 500, scale: 1.0)
| surf s
    |> libs/canvas:offscreen.clear.color(s, r: 1.0, g: 0.0, b: 1.0)
    |> libs/canvas:offscreen.frame(s)
        ! frame f
            |> kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/component_list_follow_path.riv")
            | loaded r
                |> kr/rive:meshops(r, ab: 18, frame: 0)
                    ! mdraw d |> kr/probe:mesh-draw(d, f)
                    ! mtri t |> kr/probe:mesh-tri(t)
                    ! mdone n |> kr/probe:mesh-end(f)
                    ! mclip mc |> kr/probe:mesh-clip(c: mc, f)
                    ! mclippop mp |> kr/probe:mesh-clippop(f)
                    | mend _ |> kr/rive:free(r)
            | failed e |> std/io:print.ln("open failed")
        | done _
    |> libs/canvas:offscreen.snap(s, path: "/tmp/ours_mesh_t1.bmp")
    |> libs/canvas:offscreen.close(s)
    |> std/io:print.ln("meshrender: snapped")
| err e |> std/io:print.ln("offscreen init failed: {{ e:s }}")
