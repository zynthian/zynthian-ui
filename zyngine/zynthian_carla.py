#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Carla plugin management
#
# Counterpart of zynthian_lv2.py for plugins hosted by Carla. It scans the plugin
# directories with Carla's discovery tool and registers every plugin as an engine
# "CA/<plugin name>" in the engine config file, so plugins can be selected like any
# other engine. zynthian_engine_carla hosts them all in one Carla instance.
#
# Usage (from the zynthian-ui directory):
#   python3 -m zyngine.zynthian_carla scan [TYPE ...]     => print discovered plugins
#   python3 -m zyngine.zynthian_carla engines [TYPE ...]  => scan and update the engine config
# Options: --remove-duplicates registers a plugin that is available in several formats only
# once, using the first available format of LV2, CLAP, VST3, VST2, DSSI, LADSPA.
# --keep-duplicates (default) registers every format. The default can be changed with
# "remove_duplicates": true in the config file below.
# TYPE is one of LV2 LADSPA DSSI VST2 VST3 CLAP (default: all). LV2 plugins are also
# provided by the Jalv engines, so they are listed twice while both engines are enabled.
#
# Extra search paths can be set with the usual environment variables (LADSPA_PATH,
# DSSI_PATH, LV2_PATH, VST_PATH, VST3_PATH, CLAP_PATH) or in
# $ZYNTHIAN_CONFIG_DIR/carla/config.json: {"types": [...], "paths": {"VST3": ["/dir"]}}
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or any later version.
# ******************************************************************************

import os
import re
import sys
import json
import time
import hashlib
import logging
import subprocess

CARLA_CONFIG_FILE = "{}/carla/config.json".format(os.environ.get('ZYNTHIAN_CONFIG_DIR', '/zynthian/config'))

DEFAULT_TYPES = ["LV2", "LADSPA", "DSSI", "VST2", "VST3", "CLAP"]

# type => (environment variable, default directories, file extension, items are directories)
PLUGIN_FORMATS = {
    "LADSPA": ("LADSPA_PATH", ["/usr/lib/ladspa", "/usr/local/lib/ladspa", "~/.ladspa",
                               "/zynthian/zynthian-plugins/ladspa"], ".so", False),
    "DSSI": ("DSSI_PATH", ["/usr/lib/dssi", "/usr/local/lib/dssi", "~/.dssi",
                           "/zynthian/zynthian-plugins/dssi"], ".so", False),
    "LV2": ("LV2_PATH", ["/usr/lib/lv2", "/usr/local/lib/lv2", "~/.lv2",
                         "/zynthian/zynthian-plugins/lv2"], ".lv2", True),
    "VST2": ("VST_PATH", ["/usr/lib/vst", "/usr/local/lib/vst", "~/.vst",
                          "/zynthian/zynthian-plugins/vst"], ".so", False),
    "VST3": ("VST3_PATH", ["/usr/lib/vst3", "/usr/local/lib/vst3", "~/.vst3",
                           "/zynthian/zynthian-plugins/vst3"], ".vst3", True),
    "CLAP": ("CLAP_PATH", ["/usr/lib/clap", "/usr/local/lib/clap", "~/.clap",
                           "/zynthian/zynthian-plugins/clap"], ".clap", True)
}

LIB_DIR_CANDIDATES = [
    "/usr/lib/carla", "/usr/local/lib/carla", "/usr/lib/x86_64-linux-gnu/carla",
    "/usr/lib/aarch64-linux-gnu/carla", "/usr/lib/arm-linux-gnueabihf/carla",
    "/usr/lib64/carla", "/zynthian/zynthian-sw/carla/bin"
]

# Carla plugin hints (see CarlaBackend.h)
PLUGIN_IS_SYNTH = 0x004
PLUGIN_HAS_CUSTOM_UI = 0x008

CARLA_CAT_TO_ENGCAT = {
    "synth": "Synth",
    "delay": "Delay",
    "eq": "Filter & EQ",
    "filter": "Filter & EQ",
    "distortion": "Distortion",
    "dynamics": "Dynamics",
    "modulator": "Modulation",
    "utility": "Other",
    "other": "Other",
    "none": "Other"
}

DISCOVERY_TIMEOUT = 60

FORMAT_PREFERENCE = ["LV2", "CLAP", "VST3", "VST2", "DSSI", "LADSPA"]

# ------------------------------------------------------------------------------
# Discovery
# ------------------------------------------------------------------------------


def find_discovery_tool():
    cands = []
    if os.environ.get("CARLA_LIB_DIR"):
        cands.append(os.environ["CARLA_LIB_DIR"])
    cands += LIB_DIR_CANDIDATES
    for d in cands:
        tool = os.path.join(d, "carla-discovery-native")
        if os.path.isfile(tool):
            return tool
    return None


def is_carla_available():
    return find_discovery_tool() is not None


def load_config():
    try:
        with open(CARLA_CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def get_search_dirs(ptype, config=None):
    env, defaults, ext, is_dir = PLUGIN_FORMATS[ptype]
    dirs = []
    if os.environ.get(env):
        dirs += os.environ[env].split(os.pathsep)
    dirs += defaults
    if config:
        dirs += config.get("paths", {}).get(ptype, [])
    res = []
    for d in dirs:
        d = os.path.expanduser(d)
        if d and os.path.isdir(d) and d not in res:
            res.append(d)
    return res


def find_plugin_files(ptype, config=None):
    env, defaults, ext, is_dir = PLUGIN_FORMATS[ptype]
    files = []
    for root_dir in get_search_dirs(ptype, config):
        for root, dirs, fnames in os.walk(root_dir, followlinks=True):
            if is_dir:
                for d in list(dirs):
                    if d.endswith(ext):
                        files.append(os.path.join(root, d))
                        dirs.remove(d)
                for f in fnames:
                    if ptype == "CLAP" and f.endswith(ext):
                        files.append(os.path.join(root, f))
            else:
                for f in fnames:
                    if f.endswith(ext):
                        files.append(os.path.join(root, f))
    return sorted(set(files))


def parse_discovery_output(text):
    plugins = []
    info = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("carla-discovery::init::"):
            info = {}
        elif line.startswith("carla-discovery::end::"):
            if info is not None:
                plugins.append(info)
            info = None
        elif line.startswith("carla-discovery::") and info is not None:
            try:
                prop, value = line[len("carla-discovery::"):].split("::", 1)
            except ValueError:
                continue
            if prop in ("build", "hints", "uniqueId", "audio.ins", "audio.outs", "cv.ins", "cv.outs",
                        "midi.ins", "midi.outs", "parameters.ins", "parameters.outs"):
                try:
                    info[prop] = int(value)
                except ValueError:
                    pass
            elif prop in ("name", "label", "maker", "category", "filename", "uri"):
                info[prop] = value
    return plugins


def discover_file(tool, ptype, path):
    try:
        res = subprocess.run([tool, ptype.lower(), path], capture_output=True, text=True,
                             timeout=DISCOVERY_TIMEOUT, errors="replace")
    except subprocess.TimeoutExpired:
        logging.warning(f"Discovery of '{path}' timed out")
        return []
    if res.returncode != 0:
        logging.warning(f"Discovery of '{path}' failed (return code {res.returncode})")
        return []
    found = []
    for info in parse_discovery_output(res.stdout):
        info["type"] = ptype
        if ptype == "LV2":
            if info.get("uri"):
                info["label"] = info["uri"]
            elif "/" in info.get("label", ""):
                info["label"] = info["label"].split("/", 1)[1]
            info["filename"] = path
        else:
            info["filename"] = path
        if not info.get("name"):
            continue
        found.append(info)
    return found


def normalize_name(name):
    name = (name or "").lower()
    name = re.sub(r"[\(\[]\s*(lv2|clap|vst3?|vst2|dssi|ladspa)\s*[\)\]]", " ", name)
    name = re.sub(r"\b(lv2|clap|vst3?|vst2|dssi|ladspa)\b", " ", name)
    return re.sub(r"[^a-z0-9]", "", name)


def makers_match(a, b):
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb or na in nb or nb in na:
        return True
    wa = re.split(r"\W+", (a or "").strip().lower())[0]
    wb = re.split(r"\W+", (b or "").strip().lower())[0]
    return bool(wa) and wa == wb


def format_rank(info):
    try:
        return FORMAT_PREFERENCE.index(info["type"])
    except ValueError:
        return len(FORMAT_PREFERENCE)


def remove_duplicates(plugins):
    groups = {}
    for info in plugins:
        groups.setdefault(normalize_name(info.get("name")), []).append(info)
    result = []
    for key, group in groups.items():
        if not key:
            result += group
            continue
        clusters = []
        for info in sorted(group, key=lambda i: (format_rank(i), i["filename"], i.get("label", ""))):
            for cl in clusters:
                if makers_match(cl[0].get("maker"), info.get("maker")):
                    if info["type"] == cl[0]["type"]:
                        cl[1].append(info)
                    break
            else:
                clusters.append([info, [info]])
        for cl in clusters:
            result += cl[1]
    removed = len(plugins) - len(result)
    if removed:
        logging.info(f"{removed} duplicated plugins removed")
    return result


def scan_plugins(types=None, progress=None, remove_dups=None):
    # Returns a list with the info of every plugin found (one entry per plugin, not per file)
    tool = find_discovery_tool()
    if not tool:
        raise RuntimeError("Carla discovery tool not found. Set CARLA_LIB_DIR.")
    config = load_config()
    if not types:
        types = config.get("types", DEFAULT_TYPES)
    plugins = []
    for ptype in types:
        ptype = ptype.upper()
        if ptype not in PLUGIN_FORMATS:
            logging.warning(f"Unknown plugin type '{ptype}'")
            continue
        files = find_plugin_files(ptype, config)
        for i, path in enumerate(files):
            if progress:
                progress(ptype, path, i, len(files))
            plugins += discover_file(tool, ptype, path)
    if remove_dups is None:
        remove_dups = bool(config.get("remove_duplicates", False))
    if remove_dups:
        plugins = remove_duplicates(plugins)
    return plugins

# ------------------------------------------------------------------------------
# Engine info generation
# ------------------------------------------------------------------------------


def get_plugin_engine_type(info):
    audio_in = info.get("audio.ins", 0)
    audio_out = info.get("audio.outs", 0)
    midi_in = info.get("midi.ins", 0)
    midi_out = info.get("midi.outs", 0)
    if info.get("hints", 0) & PLUGIN_IS_SYNTH or info.get("category") == "synth":
        if audio_out > 0:
            return "MIDI Synth"
    if audio_out > 0 and audio_in == 0:
        return "MIDI Synth" if midi_in > 0 else "Audio Generator"
    if audio_in > 0 and audio_out > 0:
        return "Audio Effect"
    if midi_in > 0 and midi_out > 0 and audio_in == audio_out == 0:
        return "MIDI Tool"
    return "Audio Effect"


def get_plugin_engine_cat(info, etype):
    if etype == "Audio Generator":
        return "Generator"
    if etype == "MIDI Tool":
        return "Other"
    cat = CARLA_CAT_TO_ENGCAT.get(info.get("category", "none"), "Other")
    # Carla has no reverb category (reverbs are reported as "delay" or "other"), so use the name
    if cat in ("Delay", "Other") and re.search(r"reverb|verb", info.get("name", ""), re.I):
        cat = "Reverb"
    if etype == "MIDI Synth":
        return "Synth" if cat == "Other" else "Synth"
    if cat == "Synth":
        cat = "Other"
    return cat


def make_unique_titles(plugins):
    plugins = sorted(plugins, key=lambda i: (i["type"], i["filename"], i.get("label", "")))
    counts = {}
    for info in plugins:
        counts[info["name"]] = counts.get(info["name"], 0) + 1
    titles = {}
    result = []
    for info in plugins:
        title = info["name"]
        if counts[title] > 1:
            title = f"{title} ({info['type']})"
        if title in titles:
            titles[title] += 1
            title = f"{title} #{titles[title]}"
        else:
            titles[title] = 1
        result.append((title, info))
    return result


def get_jalv_engine(uri, current):
    for key, eng in current.items():
        if key.startswith("JV/") and eng.get("URL") == uri:
            return eng
    return None


def get_lv2_plugin(uri):
    try:
        from zyngine import zynthian_lv2
        if getattr(zynthian_lv2, "world", None) is None:
            zynthian_lv2.init_lilv()
        return zynthian_lv2.world.get_all_plugins().get_by_uri(uri)
    except Exception as e:
        logging.debug(f"Can't get LV2 plugin {uri} => {e}")
    return None


def get_lv2_description(uri, current):
    eng = get_jalv_engine(uri, current)
    if eng and eng.get("DESCR"):
        return eng["DESCR"]
    plugin = get_lv2_plugin(uri)
    if plugin:
        from zyngine import zynthian_lv2
        return zynthian_lv2.get_plugin_description(plugin)
    return None


def get_lv2_category(uri, current):
    eng = get_jalv_engine(uri, current)
    if eng and eng.get("CAT"):
        return eng["CAT"]
    plugin = get_lv2_plugin(uri)
    if plugin:
        from zyngine import zynthian_lv2
        return zynthian_lv2.get_plugin_cat(plugin)
    return None


def generate_engines(plugins, current=None):
    current = current or {}
    engines = {}
    for title, info in make_unique_titles(plugins):
        key = f"CA/{title}"
        etype = get_plugin_engine_type(info)
        default_descr = f"{info['type']} plugin" + (f" by {info['maker']}" if info.get("maker") else "")
        cat = get_plugin_engine_cat(info, etype)
        auto_cat = cat
        if info["type"] == "LV2":
            default_descr = get_lv2_description(info.get("label"), current) or default_descr
            if etype == "Audio Effect":
                cat = get_lv2_category(info.get("label"), current) or cat
        entry = {
            'ID': hashlib.sha1(key.encode()).hexdigest()[:10],
            'NAME': title,
            'TITLE': title,
            'TYPE': etype,
            'CAT': cat,
            'ENABLED': False,
            'INDEX': 9999,
            'URL': info.get("label") or info["filename"],
            'UI': "UI" if info.get("hints", 0) & PLUGIN_HAS_CUSTOM_UI else None,
            'DESCR': default_descr,
            'QUALITY': 0,
            'COMPLEX': 0,
            'EDIT': 0,
            'CARLA': {
                'type': info["type"],
                'filename': info["filename"],
                'label': info.get("label", ""),
                'uid': info.get("uniqueId", 0),
                'build': info.get("build")
            }
        }
        old = current.get(key)
        if old:
            for field in ('ID', 'TITLE', 'TYPE', 'CAT', 'ENABLED', 'INDEX', 'DESCR', 'QUALITY', 'COMPLEX', 'EDIT'):
                if field in old:
                    if field == 'DESCR' and re.match(r"^[A-Z0-9]+ plugin( by .*)?$", old[field] or ""):
                        continue
                    if field == 'CAT' and old[field] in (auto_cat, CARLA_CAT_TO_ENGCAT.get(info.get("category", "none"))):
                        continue
                    entry[field] = old[field]
        engines[key] = entry
    return engines


def update_engines(types=None, progress=None, remove_dups=None):
    from zyngine import zynthian_lv2
    plugins = scan_plugins(types, progress, remove_dups)
    current = zynthian_lv2.get_engines()
    new = generate_engines(plugins, current)
    merged = {k: v for k, v in current.items() if not k.startswith("CA/")}
    merged.update(new)
    zynthian_lv2.engines = dict(sorted(merged.items(), key=lambda r: r[1]['TITLE'].casefold()))
    zynthian_lv2.save_engines()
    zynthian_lv2.get_engines_by_type()
    return new

# ------------------------------------------------------------------------------
# Main program
# ------------------------------------------------------------------------------


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(module)s: %(message)s', stream=sys.stderr, level=logging.INFO)
    start = time.time()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "engines"
    remove_dups = None
    if "--remove-duplicates" in sys.argv:
        remove_dups = True
    if "--keep-duplicates" in sys.argv:
        remove_dups = False
    types = [a for a in sys.argv[2:] if not a.startswith("--")] or None
    if cmd == "scan":
        for title, info in make_unique_titles(scan_plugins(types, remove_dups=remove_dups)):
            etype = get_plugin_engine_type(info)
            print(f"{info['type']:6} {etype:16} {title}  [{info['filename']}]")
    elif cmd == "engines":
        new = update_engines(types, remove_dups=remove_dups)
        logging.info(f"{len(new)} Carla plugins registered")
    else:
        print(__doc__ if __doc__ else "usage: zynthian_carla.py scan|engines [TYPE ...]")
    logging.info('Command took {}s'.format(int(round(time.time() - start))))
