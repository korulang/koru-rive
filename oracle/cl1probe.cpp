// cl1 probe v2: replicate unit-test setup EXACTLY — artboardNamed returns
// ArtboardInstance; createDefaultViewModelInstance + bindViewModelInstance.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "rive/artboard.hpp"
#include "rive/artboard_component_list.hpp"
#include "rive/file.hpp"
#include "record.hpp"

using namespace rive;

static std::vector<uint8_t> readFile(const char* path)
{
  FILE* fp = fopen(path, "rb");
  if (!fp) return {};
  fseek(fp, 0, SEEK_END);
  long n = ftell(fp);
  fseek(fp, 0, SEEK_SET);
  std::vector<uint8_t> bytes(n);
  fread(bytes.data(), 1, n, fp);
  fclose(fp);
  return bytes;
}

int main(int argc, char** argv)
{
  if (argc < 2) { fprintf(stderr, "usage: cl1probe <file.riv> [artboardName]\n"); return 2; }
  oracle::RecordingFactory factory;
  auto bytes = readFile(argv[1]);
  ImportResult result;
  auto file = File::import(bytes, &factory, &result, nullptr);
  if (result != ImportResult::success || !file) { fprintf(stderr, "import failed\n"); return 1; }

  const char* want = argc > 2 ? argv[2] : "Main";
  for (size_t ai = 0; ai < file->artboardCount(); ai++)
  {
    auto artboard = file->artboard(ai);
    if (!artboard) continue;
    if (want[0] && artboard->name() != want) continue;
    // EXACT test path: artboardNamed -> ArtboardInstance, bind default VM.
    auto inst = file->artboardNamed(artboard->name());
    auto vmi = file->createDefaultViewModelInstance(inst.get());
    inst->bindViewModelInstance(vmi);
    inst->advance(0.0f);
    // advance a few frames in case list populates over time
    for (int f = 0; f < 5; f++) inst->advance(1.0f/30.0f);
    inst->advance(0.0f);

    // component lists are per-INSTANCE — find them on the instance, not the
    // file-level artboard template (whose m_listItems is always empty).
    auto lists = inst->find<ArtboardComponentList>();
    printf("ARTBOARD %s instanceComponentLists=%zu\n", artboard->name().c_str(), lists.size());
    for (auto* cl : lists)
    {
      int n = cl->itemCount();
      int bound = 0;
      for (int i = 0; i < n; i++)
        if (cl->artboardInstance(i) != nullptr) bound++;
      printf("  list itemCount=%d boundArtboard=%d\n", n, bound);
    }
  }
  return 0;
}
