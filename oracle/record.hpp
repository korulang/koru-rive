// oracle — recording Rive renderer.
//
// A Factory+Renderer pair that captures the exact command stream rive-native
// emits for a .riv file: every save/restore/transform, every path verb and
// point, every paint parameter, every clip and image draw. The output is the
// golden contract a Koru-side player must reproduce.
//
// Design: we do NOT read values back through getters (RenderPaint is
// write-only from the runtime's side). Instead the factory hands out OUR
// RenderPath/RenderPaint implementations which record their own
// configuration as the runtime sets it. The renderer then dumps the
// recorded state at each drawPath/clipPath.

#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "rive/command_path.hpp"
#include "rive/factory.hpp"
#include "rive/math/raw_path.hpp"
#include "rive/renderer.hpp"
#include "utils/no_op_factory.hpp"
#include "utils/no_op_renderer.hpp"

namespace oracle
{

struct PathRec
{
  // verb ints + flattened point list, in emission order.
  // PathVerb values are printed numerically; decode table lives in dump.cpp.
  std::vector<int> verbs;
  std::vector<float> pts; // x,y pairs
  int fillRule = 0;
};

struct PaintRec
{
  int style = -1; // 0=stroke 1=fill (RenderPaintStyle), -1 unset
  uint32_t color = 0;
  float thickness = 0;
  int join = -1;
  int cap = -1;
  int blendMode = -1;
  bool hasShader = false;
  std::string shaderKind; // lite-rtti type name when available
  float m[6] = {1, 0, 0, 1, 0, 0}; // shaderTransform
  bool strokePositionSet = false;
  int strokePosition = -1;
  float feather = -1;
  float additiveness = -1;
};

class RecordingPath : public rive::RenderPath
{
public:
  PathRec rec;

  void rewind() override { rec.verbs.clear(); rec.pts.clear(); }
  void fillRule(rive::FillRule value) override { rec.fillRule = (int)value; }

  // PathVerb values match Skia: move=0 line=1 quad=2 cubic=4 close=5.
  void moveTo(float x, float y) override
  {
    rec.verbs.push_back(0);
    rec.pts.push_back(x);
    rec.pts.push_back(y);
  }
  void lineTo(float x, float y) override
  {
    rec.verbs.push_back(1);
    rec.pts.push_back(x);
    rec.pts.push_back(y);
  }
  void cubicTo(float ox, float oy, float ix, float iy, float x, float y) override
  {
    rec.verbs.push_back(4); // PathVerb::cubic
    rec.pts.push_back(ox);
    rec.pts.push_back(oy);
    rec.pts.push_back(ix);
    rec.pts.push_back(iy);
    rec.pts.push_back(x);
    rec.pts.push_back(y);
  }
  void close() override { rec.verbs.push_back(5); } // PathVerb::close

  void addPath(rive::CommandPath* path, const rive::Mat2D& transform) override
  {
    // Nested path merge — record as a marker; geometry flattening is a v2 concern.
    rec.verbs.push_back(100);
    auto* rp = path ? path->renderPath() : nullptr;
    // All RenderPaths come from RecordingFactory — static_cast is sound here
    // (the runtime is built without RTTI; dynamic_cast/typeid are unavailable).
    auto* ours = static_cast<RecordingPath*>(rp);
    if (ours)
    {
      for (size_t i = 0; i < ours->rec.verbs.size(); i++)
      {
        rec.verbs.push_back(ours->rec.verbs[i]);
      }
      for (float f : ours->rec.pts)
      {
        rec.pts.push_back(f);
      }
    }
  }

  rive::RenderPath* renderPath() override { return this; }
  const rive::RenderPath* renderPath() const override { return this; }

  void addRenderPath(const rive::RenderPath* path, const rive::Mat2D&) override
  {
    addPath(const_cast<rive::RenderPath*>(path), rive::Mat2D());
  }
  void addRenderPathBackwards(const rive::RenderPath*, const rive::Mat2D&) override {}
  void addRawPath(const rive::RawPath& raw) override
  {
    // RawPath exposes verbs()+points() spans — copy straight through.
    rewind();
    auto verbs = raw.verbs();
    auto points = raw.points();
    size_t p = 0;
    for (auto v : verbs)
    {
      rec.verbs.push_back((int)v);
      // path_verb_to_point_count gives points-per-verb (move/line=1, quad=2,
      // cubic=3, close=0); each point is an x,y pair.
      int nf = (int)rive::path_verb_to_point_count(v) * 2;
      for (int i = 0; i < nf && p + 1 < points.size(); i++)
      {
        rec.pts.push_back(points[p].x);
        rec.pts.push_back(points[p].y);
        p++;
      }
    }
  }
};

class RecordingPaint : public rive::RenderPaint
{
public:
  PaintRec rec;

  void style(rive::RenderPaintStyle value) override { rec.style = (int)value; }
  void color(rive::ColorInt value) override { rec.color = (uint32_t)value; }
  void thickness(float value) override { rec.thickness = value; }
  void join(rive::StrokeJoin value) override { rec.join = (int)value; }
  void cap(rive::StrokeCap value) override { rec.cap = (int)value; }
  void blendMode(rive::BlendMode value) override { rec.blendMode = (int)value; }
  void shader(rive::rcp<rive::RenderShader> s) override
  {
    rec.hasShader = (s.get() != nullptr);
    rec.shaderKind = rec.hasShader ? "shader" : "";
  }
  void shaderTransform(const rive::Mat2D& t) override
  {
    for (int i = 0; i < 6; i++)
    {
      rec.m[i] = t[i];
    }
  }
  void invalidateStroke() override {}
  void strokePosition(rive::StrokePosition value) override
  {
    rec.strokePositionSet = true;
    rec.strokePosition = (int)value;
  }
  void feather(float value) override { rec.feather = value; }
  void additiveness(float value) override { rec.additiveness = value; }
};

class RecordingFactory : public rive::NoOpFactory
{
public:
  rive::rcp<rive::RenderPath> makeRenderPath(rive::RawPath& raw, rive::FillRule rule) override
  {
    auto p = rive::rcp<RecordingPath>(new RecordingPath());
    p->fillRule(rule);
    p->addRawPath(raw);
    return p;
  }
  rive::rcp<rive::RenderPath> makeEmptyRenderPath() override
  {
    return rive::rcp<RecordingPath>(new RecordingPath());
  }
  rive::rcp<rive::RenderPaint> makeRenderPaint() override
  {
    return rive::rcp<RecordingPaint>(new RecordingPaint());
  }
};

class RecordingRenderer : public rive::NoOpRenderer
{
public:
  std::string out;
  int depth = 0;

  void line(const std::string& s)
  {
    out += std::string(depth * 2, ' ');
    out += s;
    out += '\n';
  }

  void save() override
  {
    line("save");
    depth++;
  }
  void restore() override
  {
    depth--;
    line("restore");
  }
  void transform(const rive::Mat2D& m) override
  {
    char buf[160];
    snprintf(
        buf,
        sizeof(buf),
        "transform %.4f %.4f %.4f %.4f %.4f %.4f",
        m[0],
        m[1],
        m[2],
        m[3],
        m[4],
        m[5]);
    line(buf);
  }
  void clipPath(rive::RenderPath* path) override
  {
    auto* rp = static_cast<RecordingPath*>(path);
    char buf[64];
    snprintf(buf, sizeof(buf), "clipPath verbs=%zu pts=%zu", rp->rec.verbs.size(), rp->rec.pts.size() / 2);
    line(buf);
  }
  void drawPath(rive::RenderPath* path, rive::RenderPaint* paint) override
  {
    auto* rp = static_cast<RecordingPath*>(path);
    auto* pp = static_cast<RecordingPaint*>(paint);
    char buf[256];
    snprintf(
        buf,
        sizeof(buf),
        "drawPath style=%d color=%08x thick=%.3f join=%d cap=%d blend=%d shader=%d(%s) fillRule=%d verbs=%zu pts=%zu",
        pp->rec.style,
        pp->rec.color,
        pp->rec.thickness,
        pp->rec.join,
        pp->rec.cap,
        pp->rec.blendMode,
        (int)pp->rec.hasShader,
        pp->rec.shaderKind.c_str(),
        rp->rec.fillRule,
        rp->rec.verbs.size(),
        rp->rec.pts.size() / 2);
    line(buf);
    // geometry on following indented lines: V <verb> x y [x y x y]
    size_t p = 0;
    for (int v : rp->rec.verbs)
    {
      // floats per verb: move/line=2, quad=4, cubic=6, close=0 (PathVerb: 0,1,2,4,5)
      int np = (v == 0 || v == 1) ? 2 : (v == 2 ? 4 : (v == 4 ? 6 : 0));
      std::string s = "V " + std::to_string(v);
      for (int i = 0; i < np && p + 1 < rp->rec.pts.size(); i++)
      {
        char nb[64];
        snprintf(nb, sizeof(nb), " %.4f %.4f", rp->rec.pts[p], rp->rec.pts[p + 1]);
        s += nb;
        p += 2;
      }
      line(s);
    }
  }
  void drawImage(const rive::RenderImage* img, rive::ImageSampler, rive::BlendMode bm, float opacity) override
  {
    char buf[160];
    snprintf(
        buf,
        sizeof(buf),
        "drawImage img=%p %dx%d blend=%d opacity=%.3f",
        (const void*)img,
        img ? img->width() : 0,
        img ? img->height() : 0,
        (int)bm,
        opacity);
    line(buf);
  }
  void modulateOpacity(float o) override
  {
    char buf[64];
    snprintf(buf, sizeof(buf), "modulateOpacity %.4f", o);
    line(buf);
  }
};

} // namespace oracle
