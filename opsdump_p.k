import kr/rive
import std/io
import std/args
import std/fmt
std/args:all(): av
|> kr/rive:open(path: av[1])
| loaded r
    |> kr/rive:opsdump(r, ab: std.fmt.parseInt(i64, av[2], 10) catch 0, frame: 0)
    |> kr/rive:free(r)
| failed e |> std/io:print.ln("OPENFAIL {{ e:s }}")
