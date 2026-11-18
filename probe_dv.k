// data_viz_demo drop-rule probe: inspect + opsdump at the named artboard.
import kr/rive
import std/io
import std/args
std/args:all(): av
|> std/io:print.ln("probe_dv: {{av[1]:s}}")
|> kr/rive:open(path: av[1])
| loaded r
    |> kr/rive:abnames(r)
    |> kr/rive:inspect(r)
    |> kr/rive:opsdump(r, ab: 315, frame: 0)
    |> kr/rive:free(r)
| failed e |> std/io:print.ln("OPENFAIL {{ e:s }}")
