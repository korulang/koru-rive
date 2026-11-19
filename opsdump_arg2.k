// Path-arg opsdump: ./a.out <file.riv> <ab> <frame>
import kr/rive
import std/io
import std/args
import std/parse
std/args:all(): av
|> std/io:print.ln("opsdump_arg2: ab={{av[2]:s}} frame={{av[3]:s}}")
|> kr/rive:open(path: av[1])
| loaded r |> kr/rive:opsdump(r, ab: std/parse:int(av[2]) orelse 0, frame: std/parse:int(av[3]) orelse 0) |> kr/rive:free(r)
| failed e |> std/io:print.ln("open failed {{ e:s }}")
