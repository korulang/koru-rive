import kr/rive
import std/io
import std/args
import std/string
std/args:all(): av
|> kr/rive:open(path: av[1])
| loaded r
    |> std/string:parse-int(av[2])
        | ok abi
            |> std/string:parse-int(av[3])
                | ok fri
                    |> kr/rive:opsdump(r, ab: abi, frame: fri)
                    |> kr/rive:free(r)
                | err e |> std/io:print.ln("bad frame arg")
        | err e |> std/io:print.ln("bad ab arg")
| failed e |> std/io:print.ln("open failed {{ e:s }}")
