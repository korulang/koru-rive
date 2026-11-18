import kr/rive
import kr/rive/rivgen_hello
import std/io
kr/rive/rivgen_hello:spec() : spec_text
|> kr/rive:fromgraph(spec: spec_text)
| loaded r |> kr/rive:opsdump(r, ab: 3, frame: 10) |> kr/rive:free(r)
| failed e |> std/io:print.ln("module path failed {{ e:s }}")
