import kr/rive
import std/io
import std/args
std/args:all(): av
|> std/io:print.ln("probe_eb: {{av[1]:s}}")
|> kr/rive:open(path: av[1])
| loaded r
    |> kr/rive:opsdump(r, ab: 11, frame: 0)
    |> kr/rive:opsdump(r, ab: 28, frame: 0)
    |> kr/rive:opsdump(r, ab: 642, frame: 0)
    |> kr/rive:opsdump(r, ab: 935, frame: 0)
    |> kr/rive:free(r)
| failed e |> std/io:print.ln("OPENFAIL {{ e:s }}")
