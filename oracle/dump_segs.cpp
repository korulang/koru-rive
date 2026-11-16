// Dump ContourMeasure segment table for follow_path_shapes' closed
// PointsPath (obj123) in WORLD space — ground truth for pathMeasureAt.
// Build: same recipe as dump.cpp (librive.a + no_op_factory + -fno-rtti)
#include "rive/math/raw_path.hpp"
#include "rive/math/contour_measure.hpp"
#include "rive/math/vec2d.hpp"
#include <cstdio>
using namespace rive;
int main() {
  // local pts (19): move + 6 cubics x3 — last cubic end = (0,0) start
  static const float lp[] = {
    0,0,
    44.0547f,0.4688f, 55.8047f,15.9805f, 63.9141f,45.6484f,
    72.0234f,75.3164f, 42.1328f,73.5781f, 29.5703f,80.6914f,
    17.0078f,87.8047f, 15.0859f,117.5078f, 29.5703f,129.0977f,
    44.0547f,140.6875f, 71.0078f,163.5547f, 35.5039f,171.6094f,
    0.0f,179.6641f, -55.8164f,170.3906f, -65.3438f,129.0977f,
    -74.8711f,87.8047f, -44.0547f,-0.4688f, 0.0f,0.0f };
  // world transform (Shape122): sx=.8042 sy=.6655 tx=403.9445 ty=293.0111
  RawPath path;
  path.rewind();
  auto W = [](float x, float y) { return Vec2D{x * 0.8042f + 403.9445f, y * 0.6655f + 293.0111f}; };
  path.move(W(lp[0], lp[1]));
  int i = 2;
  for (int c = 0; c < 6; c++) {
    path.cubic(W(lp[i], lp[i+1]), W(lp[i+2], lp[i+3]), W(lp[i+4], lp[i+5]));
    i += 6;
  }
  path.close();
  ContourMeasureIter iter(&path);
  while (auto cm = iter.next()) { cm->dump(); }
  return 0;
}
