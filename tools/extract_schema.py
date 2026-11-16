import re, os, glob, json

GEN = "/Users/larsde/src/koru-rive/rive-cpp/include/rive/generated"
OUT = "/Users/larsde/src/koru-rive/rive/schema.json"

def camel(s):
    return ''.join(w.capitalize() for w in s.split('_'))

classes = {}
for path in glob.glob(os.path.join(GEN, "**/*_base.hpp"), recursive=True):
    cls = camel(os.path.basename(path)[:-len(".hpp")])
    src = open(path).read()
    tk = re.search(r'static const u?int\d*_t typeKey = (\d+)', src)
    props = dict(re.findall(r'static const uint16_t (\w+PropertyKey) = (\d+)', src))
    props = {k[:-len("PropertyKey")]: int(v) for k, v in props.items()}
    if cls in classes:  # name collision across dirs — suffix with dir
        cls = camel(os.path.basename(path)[:-len(".hpp")]) + "_" + str(abs(hash(path)) % 1000)
    classes[cls] = {"typeKey": int(tk.group(1)) if tk else None, "props": props}

reg = open(os.path.join(GEN, "core_registry.hpp")).read()
start = reg.index("static int propertyFieldId")
end = reg.index("static int propertyFieldId") + 400000
body = reg[start:end]
# cut at the function's closing — find the LAST return before '};' or next static
# safer: split on 'return XType::id;' and process each preceding case-run
FIELD = {"CoreIdType":0,"CoreUintType":0,"CoreIntType":0,"CoreFractionalIndexType":0,
         "CoreStringType":1,"CoreBytesType":1,"CoreDoubleType":2,"CoreColorType":3,"CoreBoolType":4}
parts = re.split(r'return (\w+)::id;', body)
key2field, key2name = {}, {}
# parts[0] is preamble; then alternating (type, caseText)
for i in range(0, len(parts)-1, 2):
    cases, typ = parts[i], parts[i+1]
    fid = FIELD.get(typ)
    if fid is None: continue
    for cm in re.finditer(r'case\s+(\w+)::(\w+)\s*:', cases):
        cls, prop = cm.group(1), cm.group(2)
        pname = prop[:-len("PropertyKey")] if prop.endswith("PropertyKey") else prop
        info = classes.get(cls)
        if not info: continue
        k = info["props"].get(pname)
        if k is None: continue
        key2field[k] = fid
        disp = f"{cls[:-4] if cls.endswith('Base') else cls}.{pname}"
        key2name.setdefault(k, disp)

tk2name = {v["typeKey"]: (k[:-4] if k.endswith("Base") else k) for k, v in classes.items() if v["typeKey"] is not None}
print(f"classes={len(classes)} typeKeys={len(tk2name)} propKeys={len(key2field)} nameMap={len(key2name)}")
json.dump({"typeKeys": tk2name, "propField": key2field, "propNames": key2name}, open(OUT, "w"))
