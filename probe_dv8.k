// data_viz_demo: opsdump every artboard by object index, one run.
import kr/rive
import std/io
import std/args
std/args:all(): av
|> std/io:print.ln("probe_dv8: {{av[1]:s}}")
|> kr/rive:open(path: av[1])
| loaded r
    |> kr/rive:opsdump(r, ab: 315, frame: 0)
    |> kr/rive:opsdump(r, ab: 390, frame: 0)
    |> kr/rive:opsdump(r, ab: 653, frame: 0)
    |> kr/rive:opsdump(r, ab: 927, frame: 0)
    |> kr/rive:opsdump(r, ab: 1166, frame: 0)
    |> kr/rive:opsdump(r, ab: 1537, frame: 0)
    |> kr/rive:opsdump(r, ab: 1897, frame: 0)
    |> kr/rive:opsdump(r, ab: 2066, frame: 0)
    |> kr/rive:free(r)
| failed e |> std/io:print.ln("OPENFAIL {{ e:s }}")
