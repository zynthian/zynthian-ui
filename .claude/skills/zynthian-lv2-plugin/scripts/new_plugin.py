#!/usr/bin/env python3
"""Create the boilerplate of a DPF LV2 plugin with native X11 (Cairo) GUI and zynthian widget.

usage: new_plugin.py spec.json [--dest DIR] [--no-git] [--force] [--check]

  spec.json   see ../templates/spec.example.json (only name, symbol and I/O are required)
  --dest      project folder (default ~/Zynthian/<symbol>)
  --no-git    don't create the git repo nor add DPF (submodule) - for tests
  --force     write into an existing non-empty folder
  --check     only validate the spec and print the soft-rule warnings (see SKILL.md)

The result builds as-is (passthrough DSP, generic GUI and widget). Edit the code afterwards: this is a one-shot
generator, it doesn't update an existing project.
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(os.path.dirname(HERE), "templates")

DPF_URL = "https://github.com/DISTRHO/DPF.git"
DPF_COMMIT = "4238e1c7f0351bbe488d79f0899c540543ac7583"  # 2025-10-23, validated with this skill's templates

HINTS = {
    "automatable": "kParameterIsAutomatable",
    "boolean": "kParameterIsBoolean",
    "integer": "kParameterIsInteger",
    "logarithmic": "kParameterIsLogarithmic",
    "trigger": "kParameterIsTrigger",
    "hidden": "kParameterIsHidden",
}
SYMBOL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# LV2 parameter designations zynthian understands (built-in envelope / filter / drawbar widgets)
NS_PARAM = "http://lv2plug.in/ns/ext/parameters#"
DESIGNATIONS = {"delay", "attack", "hold", "decay", "sustain", "fade", "release",
                "cutoffFrequency", "resonance", "drawbar"}
DESIGNATION_ALIASES = {"cutoff": "cutoffFrequency", "cutoff_frequency": "cutoffFrequency"}
# Names that usually deserve a designation (soft rule 3)
DESIGNATION_HINTS = [(re.compile(r"(^|[^a-z])(att|attack)([^a-z]|$)"), "attack"),
                     (re.compile(r"(^|[^a-z])(dec|decay)([^a-z]|$)"), "decay"),
                     (re.compile(r"(^|[^a-z])(sus|sustain)([^a-z]|$)"), "sustain"),
                     (re.compile(r"(^|[^a-z])(rel|release)([^a-z]|$)"), "release"),
                     (re.compile(r"(^|[^a-z])(cut|cutoff|freq_cutoff)([^a-z]|$)"), "cutoffFrequency"),
                     (re.compile(r"(^|[^a-z])(res|reso|resonance|q)([^a-z]|$)"), "resonance")]
# Port group classes (lv2-custom style), spec groups[].class
GROUP_CLASSES = {"envelope": "EnvelopeControls", "filter": "FilterControls",
                 "oscillator": "OscillatorControls", "control": "ControlGroup"}


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def camel(symbol):
    return "".join(part[:1].upper() + part[1:] for part in re.split(r"[_\W]+", symbol) if part)


def cstr(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def cfloat(v):
    s = repr(float(v))
    return s + "f" if ("." in s or "e" in s) else s + ".0f"


def load_spec(path):
    with open(path) as f:
        spec = json.load(f)
    for key in ("name", "symbol"):
        if not spec.get(key):
            fail(f"spec: '{key}' is required")
    sym = spec["symbol"]
    if not re.match(r"^[a-z][a-z0-9_]*$", sym):
        fail("spec: symbol must match [a-z][a-z0-9_]* (used for the bundle, binaries and the widget module)")
    spec.setdefault("class", camel(sym))
    spec.setdefault("uri", f"https://zynthian.org/plugins/{sym}")
    if not spec.get("maker"):
        res = subprocess.run([os.path.join(HERE, "detect_maker.sh")], capture_output=True, text=True)
        spec["maker"] = res.stdout.strip() or "Zynthian"
        print(f"maker: '{spec['maker']}' (detected; set \"maker\" in the spec to change it)")
    spec.setdefault("brand_id", "Zynt")
    spec.setdefault("unique_id", ("z" + camel(sym))[:4].ljust(4, "x"))
    spec.setdefault("description", spec["name"])
    spec.setdefault("license", "GPL-3.0-or-later")
    spec.setdefault("homepage", "https://zynthian.org")
    spec.setdefault("version", [0, 1, 0])
    spec.setdefault("lv2_category", "lv2:UtilityPlugin")
    spec.setdefault("midi_input", False)
    spec.setdefault("midi_output", False)
    spec.setdefault("is_synth", False)
    spec.setdefault("groups", [])
    spec.setdefault("params", [])
    spec.setdefault("outputs", [])
    spec.setdefault("port_extras", {})
    spec.setdefault("ui", {})
    spec["ui"].setdefault("width", 640)
    spec["ui"].setdefault("height", 320)
    for key in ("audio_inputs", "audio_outputs"):
        if key not in spec:
            fail(f"spec: '{key}' is required")
    for key in ("brand_id", "unique_id"):
        if not re.match(r"^[A-Za-z0-9]{4}$", spec[key]):
            fail(f"spec: {key} must be 4 alphanumeric characters")
    if not spec["params"] and not spec["outputs"]:
        fail("spec: at least one param or output is needed")

    group_syms = [g["symbol"] for g in spec["groups"]]
    for g in spec["groups"]:
        if g.get("class") and g["class"] not in GROUP_CLASSES:
            fail(f"spec: group {g['symbol']}: unknown class '{g['class']}' (valid: {', '.join(GROUP_CLASSES)})")
    seen = set()
    for kind in ("params", "outputs"):
        for p in spec[kind]:
            for key in ("symbol", "name", "min", "max", "def"):
                if key not in p:
                    fail(f"spec: {kind} entry {p.get('symbol', '?')}: '{key}' is required")
            if not SYMBOL_RE.match(p["symbol"]) or p["symbol"] in seen:
                fail(f"spec: invalid or duplicated symbol '{p['symbol']}'")
            seen.add(p["symbol"])
            if not p["min"] <= p["def"] <= p["max"] or p["min"] == p["max"]:
                fail(f"spec: {p['symbol']}: needs min <= def <= max and min < max")
            if p.get("group") and p["group"] not in group_syms:
                fail(f"spec: {p['symbol']}: unknown group '{p['group']}'")
            for h in p.get("hints", []):
                if h not in HINTS:
                    fail(f"spec: {p['symbol']}: unknown hint '{h}' (valid: {', '.join(HINTS)})")
            if p.get("enum") and len(p["enum"]) != int(p["max"] - p["min"]) + 1:
                fail(f"spec: {p['symbol']}: enum needs max - min + 1 labels (values min, min+1, ...)")
            if "logarithmic" in p.get("hints", []) and p["min"] <= 0:
                fail(f"spec: {p['symbol']}: logarithmic needs min > 0")
            if p.get("designation"):
                p["designation"] = DESIGNATION_ALIASES.get(p["designation"], p["designation"])
                if p["designation"] not in DESIGNATIONS:
                    fail(f"spec: {p['symbol']}: unknown designation '{p['designation']}' "
                         f"(valid: {', '.join(sorted(DESIGNATIONS))})")
    spec.setdefault("widget", {})
    spec["widget"].setdefault("half_height", False)
    return spec


def soft_rule_warnings(spec):
    """Soft rules: deviations are reported, not refused (the user may have good reasons)"""
    warnings = []
    controls = [p for p in spec["params"] if "hidden" not in p.get("hints", [])]
    ungrouped = [p["symbol"] for p in controls if not p.get("group")]
    if ungrouped:
        warnings.append(f"rule 1: controls without group (they end up on generic 'Params' pages): {', '.join(ungrouped)}")
    for g in spec["groups"]:
        n = sum(1 for p in controls if p.get("group") == g["symbol"])
        if n == 0:
            continue
        if n <= 2:
            warnings.append(f"rule 2: group '{g['symbol']}' has {n} control(s): merge it with related controls (4 per page)")
        elif n > 4 and n % 4:
            warnings.append(f"rule 2: group '{g['symbol']}' has {n} controls: pages of 4 -> last page has {n % 4}")
    for p in controls:
        if p.get("designation"):
            continue
        text = f"{p['symbol']} {p['name']}".lower()
        for rx, des in DESIGNATION_HINTS:
            if rx.search(text):
                warnings.append(f"rule 3: '{p['symbol']}' looks like {des}: add \"designation\": \"{des}\" "
                                f"(zynthian shows its envelope/filter widget on that page)")
                break
    env = {}
    for p in controls:
        if p.get("designation") in ("attack", "decay", "sustain", "release"):
            env.setdefault(p.get("group"), []).append(p["designation"])
    for group, des in env.items():
        missing = {"attack", "decay", "sustain", "release"} - set(des)
        if missing and len(des) >= 2:
            warnings.append(f"rule 3: envelope in group '{group}' lacks {', '.join(sorted(missing))}")
    return warnings


def param_defs(spec):
    """ParamDefs.hpp: parameter & port group table shared by DSP and GUI"""
    groups = spec["groups"]
    group_idx = {g["symbol"]: i for i, g in enumerate(groups)}
    allp = [(p, False) for p in spec["params"]] + [(p, True) for p in spec["outputs"]]
    out = [
        "/*",
        f" * {spec['name']} - parameters and port groups, shared by DSP (Plugin.cpp) and GUI (UI.cpp).",
        " * Symbols are stable API (presets, snapshots, MIDI learn, zynthian widget): don't rename them lightly.",
        " * Control pages in zynthian = port groups (4 controls per page).",
        " */",
        "",
        "#pragma once",
        "",
        '#include "DistrhoDetails.hpp"',
        "",
        "START_NAMESPACE_DISTRHO",
        "",
        "enum ParamId : uint32_t {",
    ]
    for i, (p, is_out) in enumerate(allp):
        out.append(f"    kParam{camel(p['symbol'])} = {i},{'  // output' if is_out else ''}")
    out += ["    kParamCount", "};", "", "enum GroupId : uint32_t {"]
    for i, g in enumerate(groups):
        out.append(f"    kGroup{camel(g['symbol'])} = {i},")
    out += ["    kGroupCount", "};", "",
            "struct GroupDef {", "    const char* symbol;", "    const char* name;", "};", "",
            "struct ParamDef {",
            "    const char* symbol;", "    const char* name;", "    const char* unit;",
            "    float min, max, def;", "    uint32_t hints;", "    int32_t group;  // GroupId or -1",
            "    const char* const* enumLabels;", "    uint32_t enumCount;", "};", ""]
    for p, _ in allp:
        if p.get("enum"):
            labels = ", ".join(cstr(label) for label in p["enum"])
            out.append(f"static const char* const kEnum{camel(p['symbol'])}[] = {{ {labels} }};")
    out += ["", "static const GroupDef kGroups[kGroupCount > 0 ? static_cast<uint32_t>(kGroupCount) : 1u] = {"]
    if groups:
        for g in groups:
            out.append(f"    {{ {cstr(g['symbol'])}, {cstr(g['name'])} }},")
    else:
        out.append('    { "", "" }')
    out += ["};", "", "static const ParamDef kParams[kParamCount] = {"]
    for p, is_out in allp:
        hints = [HINTS[h] for h in p.get("hints", []) if h != "automatable"]
        hints.insert(0, "kParameterIsAutomatable")
        if is_out:
            hints.append("kParameterIsOutput")
        group = group_idx.get(p.get("group"), -1)
        enum = f"kEnum{camel(p['symbol'])}, {len(p['enum'])}" if p.get("enum") else "nullptr, 0"
        out.append(f"    {{ {cstr(p['symbol'])}, {cstr(p['name'])}, {cstr(p.get('unit', ''))}, "
                   f"{cfloat(p['min'])}, {cfloat(p['max'])}, {cfloat(p['def'])}, "
                   f"{' | '.join(hints)}, {group}, {enum} }},")
    meters = [f"kParam{camel(p['symbol'])}" for p in spec["outputs"] if p.get("meter")]
    out += ["};", "",
            "// Outputs filled by the demo meters in Plugin.cpp (peak dB of the audio outputs)",
            f"static const uint32_t kMeterCount = {len(meters)};",
            f"static const uint32_t kMeterParams[kMeterCount > 0 ? kMeterCount : 1] = {{ {', '.join(meters) or '0'} }};",
            "", "END_NAMESPACE_DISTRHO", ""]
    return "\n".join(out)


def top_makefile(spec):
    sym = spec["symbol"]
    return f"""#!/usr/bin/make -f
# {spec['name']} - DPF based LV2 plugin with native X11 GUI (Cairo) and zynthian widget

include dpf/Makefile.base.mk

PLUGIN = {sym}
PREFIX ?= /usr/local
LV2_DIR ?= $(PREFIX)/lib/lv2

all: dgl plugins gen zyngui

dgl:
ifeq ($(HAVE_CAIRO),true)
\t$(MAKE) -C dpf/dgl cairo
endif

plugins: dgl
\t$(MAKE) all -C plugins/$(PLUGIN)

ifneq ($(CROSS_COMPILING),true)
gen: plugins dpf/utils/lv2_ttl_generator
\t@$(CURDIR)/dpf/utils/generate-ttl.sh

dpf/utils/lv2_ttl_generator:
\t$(MAKE) -C dpf/utils/lv2-ttl-generator
else
gen:
endif

# Add the zynthian widget (zyngui:widget), help page and port extras to the generated bundle
zyngui: gen
\tpython3 tools/zyngui_bundle.py bin/$(PLUGIN).lv2

install: all
\tinstall -d $(DESTDIR)$(LV2_DIR)
\tcp -r bin/$(PLUGIN).lv2 $(DESTDIR)$(LV2_DIR)/

clean:
\t$(MAKE) clean -C dpf/dgl
\t$(MAKE) clean -C dpf/utils/lv2-ttl-generator
\t$(MAKE) clean -C plugins/$(PLUGIN)
\trm -rf bin build

.PHONY: all dgl plugins gen zyngui install clean
"""


def plugin_makefile(spec):
    return f"""#!/usr/bin/make -f
# {spec['name']} - plugin Makefile (DPF)

NAME = {spec['symbol']}

FILES_DSP = Plugin.cpp
FILES_UI = UI.cpp

# Native GUI with the Cairo backend (X11UI)
UI_TYPE = cairo

include ../../dpf/Makefile.plugins.mk

# LV2 with DSP and UI in separate binaries (the DSP never loads GUI libraries)
TARGETS = lv2_sep

all: $(TARGETS)
"""


def render(path, values):
    with open(path) as f:
        text = f.read()
    for key, value in values.items():
        text = text.replace(f"@@{key}@@", str(value))
    left = re.findall(r"@@[A-Z_]+@@", text)
    if left:
        fail(f"template {path}: unknown placeholders {sorted(set(left))}")
    return text


def write(path, text, mode=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    if mode:
        os.chmod(path, mode)


def range_text(p):
    if p.get("enum"):
        return " / ".join(p["enum"])
    return f"{p['min']:g} .. {p['max']:g}"


def ptype(p):
    hints = p.get("hints", [])
    if p.get("enum"):
        return "enum"
    for h in ("boolean", "trigger", "integer", "logarithmic"):
        if h in hints:
            return h
    return "float"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--dest")
    ap.add_argument("--no-git", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--check", action="store_true", help="only validate the spec and print soft-rule warnings")
    args = ap.parse_args()

    spec = load_spec(args.spec)
    warnings = soft_rule_warnings(spec)
    for w in warnings:
        print(f"WARNING (soft {w})")
    if args.check:
        print(f"spec OK, {len(warnings)} soft-rule warning(s)")
        return 0
    sym = spec["symbol"]
    dest = os.path.abspath(os.path.expanduser(args.dest or f"~/Zynthian/{sym}"))
    if os.path.isdir(dest) and os.listdir(dest) and not args.force:
        fail(f"{dest} exists and isn't empty (use --force)")

    midi_in = bool(spec["midi_input"] or spec["is_synth"])
    groups = {g["symbol"]: g["name"] for g in spec["groups"]}
    if midi_in:
        run_args = ",\n             const MidiEvent* const midiEvents, const uint32_t midiEventCount"
        if spec["midi_output"]:
            run_body = ("        // TODO: handle MIDI. Demo: MIDI thru\n"
                        "        for (uint32_t i = 0; i < midiEventCount; ++i)\n"
                        "            writeMidiEvent(midiEvents[i]);\n")
        else:
            run_body = ("        // TODO: handle MIDI events (midiEvents[i].frame, .size, .data)\n"
                        "        (void)midiEvents;\n        (void)midiEventCount;\n")
    else:
        run_args, run_body = "", ""

    values = {
        "NAME": spec["name"], "SYMBOL": sym, "CLASS": spec["class"], "URI": spec["uri"],
        "PLUGIN_URI": spec["uri"], "WIDGET_URI": spec["uri"] + "#zyngui",
        "MAKER": spec["maker"], "BRAND_ID": spec["brand_id"], "UNIQUE_ID": spec["unique_id"],
        "DESCRIPTION": spec["description"].replace('"', "'"), "LICENSE": spec["license"],
        "HOMEPAGE": spec["homepage"], "VERSION": ", ".join(str(int(v)) for v in spec["version"]),
        "LV2_CATEGORY": spec["lv2_category"], "YEAR": datetime.date.today().year,
        "AUDIO_IN": int(spec["audio_inputs"]), "AUDIO_OUT": int(spec["audio_outputs"]),
        "IS_SYNTH": int(bool(spec["is_synth"])), "MIDI_IN": int(midi_in), "MIDI_OUT": int(bool(spec["midi_output"])),
        "UI_WIDTH": int(spec["ui"]["width"]), "UI_HEIGHT": int(spec["ui"]["height"]),
        "WIDGET_ROWS": ("        # Half-height widget: the list of pages stays visible above it\n"
                        "        self.rows = max(1, self.rows // 2)\n") if spec["widget"]["half_height"] else "",
        "RUN_MIDI_ARGS": run_args, "RUN_MIDI_BODY": run_body.rstrip("\n"),
        "MONITORS": "\n".join(f"    {p['symbol']!r}: ({p['name']!r}, {float(p['min'])}, {float(p['max'])}, "
                              f"{p.get('unit', '')!r})," for p in spec["outputs"]),
        "CONTROLS_HELP": "<ul>\n" + "\n".join(
            f"  <li><b>{p['name']}</b> ({range_text(p)} {p.get('unit', '')}): TODO</li>" for p in spec["params"]) + "\n</ul>",
        "IDENTITY_STATUS": "AGREED", "IO_STATUS": "AGREED",
        "IO": (f"- Audio: {spec['audio_inputs']} in, {spec['audio_outputs']} out\n"
               f"- MIDI: {'in' if midi_in else 'no input'}, {'out' if spec['midi_output'] else 'no output'}"
               f"{' (synth)' if spec['is_synth'] else ''}"),
        "CONTROLS_TABLE": "\n".join(
            f"| {groups.get(p.get('group'), '-')} | `{p['symbol']}` | {p['name']} | {range_text(p)} | {p['def']:g} | "
            f"{p.get('unit', '')} | {ptype(p)} | {p.get('designation', '')} |" for p in spec["params"]) or "| | | | | | | | |",
        "OUTPUTS_TABLE": "\n".join(
            f"| `{p['symbol']}` | {p['name']} | {range_text(p)} | {p.get('unit', '')} | "
            f"{'demo: peak level of the audio output' if p.get('meter') else 'TODO'} |" for p in spec["outputs"])
        or "| | | | | |",
    }

    os.makedirs(dest, exist_ok=True)
    pdir = os.path.join(dest, "plugins", sym)
    write(os.path.join(pdir, "DistrhoPluginInfo.h"), render(os.path.join(TEMPLATES, "plugin", "DistrhoPluginInfo.h"), values))
    write(os.path.join(pdir, "Plugin.cpp"), render(os.path.join(TEMPLATES, "plugin", "Plugin.cpp"), values))
    write(os.path.join(pdir, "UI.cpp"), render(os.path.join(TEMPLATES, "plugin", "UI.cpp"), values))
    write(os.path.join(pdir, "ParamDefs.hpp"), param_defs(spec))
    write(os.path.join(pdir, "Makefile"), plugin_makefile(spec))
    write(os.path.join(dest, "Makefile"), top_makefile(spec))

    zdir = os.path.join(dest, "zyngui")
    write(os.path.join(zdir, f"zynthian_widget_{sym}.py"), render(os.path.join(TEMPLATES, "zyngui", "widget.py"), values))
    write(os.path.join(zdir, f"zynthian_widget_{sym}.html"), render(os.path.join(TEMPLATES, "zyngui", "help.html"), values))
    write(os.path.join(zdir, "zyngui.ttl"), render(os.path.join(TEMPLATES, "zyngui", "zyngui.ttl"), values))
    extras = {"_comment": "Extra TTL statements per port symbol (or 'group:<symbol>'), added after the build. "
                          "See references/dpf.md of the zynthian-lv2-plugin skill."}
    for p in spec["params"]:
        if p.get("designation"):
            extras.setdefault(p["symbol"], []).append(f"lv2:designation <{NS_PARAM}{p['designation']}>")
    for g in spec["groups"]:
        if g.get("class"):
            extras.setdefault(f"group:{g['symbol']}", []).append(f"a <{NS_PARAM}{GROUP_CLASSES[g['class']]}>")
    for key, lines in spec["port_extras"].items():
        extras.setdefault(key, []).extend(lines)
    write(os.path.join(zdir, "port_extras.json"), json.dumps(extras, indent=2) + "\n")

    write(os.path.join(dest, "tools", "zyngui_bundle.py"),
          open(os.path.join(TEMPLATES, "tools", "zyngui_bundle.py")).read(), 0o755)
    write(os.path.join(dest, "SPEC.md"), render(os.path.join(TEMPLATES, "SPEC.md"), values))
    write(os.path.join(dest, "README.md"), render(os.path.join(TEMPLATES, "README.md"), values))
    write(os.path.join(dest, ".gitignore"), "/bin/\nbuild/\n__pycache__/\n*.o\n*.d\n")
    spec_out = {k: v for k, v in spec.items() if not k.startswith("_")}
    write(os.path.join(dest, "spec.json"), json.dumps(spec_out, indent=2) + "\n")

    if not args.no_git:
        def git(*cmd, cwd=dest):
            subprocess.run(["git", *cmd], cwd=cwd, check=True)
        if not os.path.isdir(os.path.join(dest, ".git")):
            git("init", "-q")
        if not os.path.isdir(os.path.join(dest, "dpf", "distrho")):
            git("submodule", "add", "-q", DPF_URL, "dpf")
            git("checkout", "-q", DPF_COMMIT, cwd=os.path.join(dest, "dpf"))
            git("submodule", "update", "-q", "--init", "--recursive", cwd=os.path.join(dest, "dpf"))
            git("add", "dpf")

    print(f"Created {dest}")
    print(f"  plugin {spec['name']} <{spec['uri']}>, {len(spec['params'])} controls, {len(spec['outputs'])} outputs")
    print(f"Next: review SPEC.md, then build on the zynthian: zyn_device.sh build {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
