// Path-arg opsdump: ./a.out <file.riv> — dumps ab:0 at frame 0 and frame -1.
import kr/rive
import std/io
import std/args
std/args:all(): av
|> std/io:print.ln("opsdump_both: {{av[1]:s}}")
|> kr/rive:open(path: av[1])
| loaded r
    |> kr/rive:opsdump(r, ab: 5, frame: 0)
    |> kr/rive:opsdump(r, ab: 5, frame: -1)
    |> kr/rive:free(r)
| failed e |> std/io:print.ln("open failed {{ e:s }}")
