// CLI-authored fixture: fixtures/vmlist/rive_smoke.riv — RML -> rive CLI -> .riv.
// Dialect check: does the decoder read CLI-produced .riv?
import kr/rive
import std/io

kr/rive:open(path: "/Users/larsde/src/koru-rive/fixtures/vmlist/rive_smoke.riv")
| loaded r
    |> kr/rive:inspect(r)
    |> kr/rive:opsdump(r, ab: 0, frame: -1)
    |> kr/rive:free(r)
| failed e |> std/io:print.ln("open failed: {{ e:s }}")
