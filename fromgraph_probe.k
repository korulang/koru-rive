import kr/rive
import std/io
kr/rive:fromgraph(spec: "G 0 B 0")
| loaded r |> kr/rive:inspect(r) |> kr/rive:free(r)
| failed e |> std/io:print.ln("fromgraph failed: {{ e:s }}")
