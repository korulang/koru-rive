# Layout-feature census — 601 .riv files (2026-11-18)

Instrument: `census_all.k` — open+inspect every .riv in repo, stderr
object dumps split per file, prop-key tally. Raw matrix: /tmp/layout_matrix.json.

## Type presence (files containing >=1)

| type | files |
|---|---:|
| LayoutComponentStyle (420) | 468 |
| LayoutComponent (409) | 286 |
| ForegroundLayoutDrawable (513) | 14 |
| LayoutParticipant (1066) | 21 |
| GridTrack (1058) | 14 |
| GridItemPlacement (1068) | 7 |

## Feature matrix (prop key -> files exercising it)

| feature | key | files | verdict |
|---|---|---:|---|
| flexDirection | 598 | 104 | CORE — row/column |
| layoutAlignmentType | 632 | 67 | CORE |
| gapVertical/Horizontal | 499/498 | 62/57 | CORE |
| padding (4 sides) | 512-515 | 56-59 | CORE |
| flexWrap | 604 | 32 | COMMON |
| positionType absolute | 597 | 31 | COMMON |
| corner radii | 640-643 | 28 | COMMON (paint, not solver) |
| position offsets | 516-519 | 11-23 | COMMON |
| margins | 508-511 | 5-11 | MINORITY |
| NodeStyle fixed w/h | 1066/1067 | 5/7 | MINORITY |
| borders | 504-507 | ~0 | UNUSED |
| justifyItems (grid) | 1045 | ~0 | UNUSED |
| flexBasis | 523 | 1 | UNUSED |
| aspectRatioAxis | 546 | 1 | UNUSED |
| direction RTL | 599 | 6 | MINORITY |
| basisUnits | 705 | 5 | MINORITY |
| overflow | 605 | ~0 | UNUSED |
| min/max sizing | 500-503 | ~0 | UNUSED |

## Solver scope verdict

Flex row/column + gap + padding + alignment + wrap + absolute position
covers ~95% of authored usage. **Grid is real but minority** (14-21
files: GridTrack/GridItemPlacement/LayoutParticipant). Exotic flex
(flexBasis, aspectRatio, min/max, borders, justifyItems, overflow) is
effectively unexercised — defer. RTL direction: 6 files, defer.

Implementation order by evidence: (1) flex direction+gap+padding+align
solve, (2) wrap, (3) absolute position, (4) grid tracks, (5) everything
else on demand.
