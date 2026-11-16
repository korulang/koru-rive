import kr/rive
import std/io
import std/args

std/args:all(): av
|> kr/rive:open(path: av[1])
| loaded r
    |> kr/rive:draws(r, ab: 1, frame: 0): out
    |> std/io:print.ln(out)
    |> kr/rive:free(r)
| failed e
    |> std/io:print.ln("open failed")
