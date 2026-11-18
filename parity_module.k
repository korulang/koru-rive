import std/compiler

std/compiler:paths { rivgen_hello_world: ./tools/out/rivgen_hello_world.kz }

import kr/rive
import rivgen_hello_world
import std/io

rivgen_hello_world:spec() : spec_text
|> kr/rive:fromgraph(spec: spec_text)
| loaded r |> kr/rive:opsdump(r, ab: 3, frame: 10) |> kr/rive:free(r)
| failed e |> std/io:print.ln("module path failed {{ e:s }}")
