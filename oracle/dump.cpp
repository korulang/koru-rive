// oracle/dump — emit the golden command-stream for a .riv file.
//
// usage: dump <file.riv> [frames] [dt]
//   frames: number of advance+draw steps per animation/state machine (default 30)
//   dt:     seconds per step (default 1/30)
//
// Prints a text stream: FILE/ARTBOARD/SM/ANIM headers then the recorded
// Renderer op sequence per sampled frame.

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "rive/animation/state_machine_instance.hpp"
#include "rive/artboard.hpp"
#include "rive/file.hpp"
#include "record.hpp"

using namespace rive;

static std::vector<uint8_t> readFile(const char* path)
{
  FILE* fp = fopen(path, "rb");
  if (!fp)
  {
    fprintf(stderr, "cannot open %s\n", path);
    exit(2);
  }
  fseek(fp, 0, SEEK_END);
  long n = ftell(fp);
  fseek(fp, 0, SEEK_SET);
  std::vector<uint8_t> bytes((size_t)n);
  if (fread(bytes.data(), 1, (size_t)n, fp) != (size_t)n)
  {
    fprintf(stderr, "short read %s\n", path);
    exit(2);
  }
  fclose(fp);
  return bytes;
}

int main(int argc, char** argv)
{
  if (argc < 2)
  {
    fprintf(stderr, "usage: dump <file.riv> [frames] [dt]\n");
    return 2;
  }
  int frames = argc > 2 ? atoi(argv[2]) : 30;
  float dt = argc > 3 ? (float)atof(argv[3]) : (1.0f / 30.0f);

  oracle::RecordingFactory factory;
  auto bytes = readFile(argv[1]);
  ImportResult result;
  auto file = File::import(bytes, &factory, &result, nullptr);
  if (result != ImportResult::success || !file)
  {
    fprintf(stderr, "import failed result=%d\n", (int)result);
    return 1;
  }

  printf("FILE artboards=%zu\n", file->artboardCount());
  oracle::RecordingRenderer renderer;

  for (size_t ai = 0; ai < file->artboardCount(); ai++)
  {
    auto artboard = file->artboard(ai);
    if (!artboard)
    {
      continue;
    }
    printf("ARTBOARD %zu name=%s\n", ai, artboard->name().c_str());

    // Pass 1: static pose.
    {
      auto inst = artboard->instance();
      inst->advance(0.0f);
      renderer.out += "--- static t=0 ---\n";
      inst->draw(&renderer);
    }

    // Pass 2: each state machine advanced on its own fresh instance.
    auto probe = artboard->instance();
    size_t smCount = probe->stateMachineCount();
    for (size_t si = 0; si < smCount; si++)
    {
      auto inst = artboard->instance();
      auto sm = inst->stateMachineAt(si);
      if (!sm)
      {
        continue;
      }
      char hdr[128];
      snprintf(hdr, sizeof(hdr), "--- sm%zu ---\n", si);
      renderer.out += hdr;
      for (int f = 0; f < frames; f++)
      {
        sm->advanceAndApply(dt);
        inst->advance(dt);
        char mark[64];
        snprintf(mark, sizeof(mark), "--- frame %d t=%.4f ---\n", f, (f + 1) * dt);
        renderer.out += mark;
        inst->draw(&renderer);
      }
    }
  }

  printf("%s", renderer.out.c_str());
  return 0;
}
