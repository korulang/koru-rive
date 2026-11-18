import kr/rive
import std/io
import std/args
std/args:all(): av
|> std/io:print.ln("probe_ltm: {{av[1]:s}}")
|> kr/rive:open(path: av[1])
| loaded r |> kr/rive:opsdump(r, ab: 5, frame: 0) |> kr/rive:free(r)
| failed e |> std/io:print.ln("OPENFAIL {{ e:s }}")
