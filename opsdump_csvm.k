import kr/rive
import std/io
import std/args
std/args:all(): av
|> kr/rive:open(path: av[1])
| loaded r |> kr/rive:opsdump(r, ab: 15, frame: 0) |> kr/rive:free(r)
| failed e |> std/io:print.ln("OPENFAIL {{ e:s }}")
