import kr/rive
import std/io
import std/args

std/args:all(): av
|> kr/rive:open(path: av[1])
| loaded r |> kr/rive:inspect(r) |> kr/rive:paths(r) |> kr/rive:transforms(r) |> kr/rive:pathops(r) |> kr/rive:drawops(r) |> kr/rive:free(r)
| failed e |> std/io:print.ln("open failed: {{ e:s }}")
