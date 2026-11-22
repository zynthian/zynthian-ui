#!/usr/bin/env python3
"""Describe LV2 plugins with lilv, as JSON. Runs where the plugins are (the zynthian), e.g. through
zyn_device.sh, which sends this file over ssh:  python3 - ports <URI>  /  python3 - plugins [filter]

  ports <URI>       ports (symbol, direction, type, range, properties, group, scale points) and UIs, JSON
  summary <URI>     the same, as text
  plugins [filter]  installed plugins whose URI or name contains filter (case insensitive)
  widget <URI>      zynthian widget resolution (needs zynthian-ui, uses its zynthian_lv2)
"""

import json
import os
import sys

import lilv

NS_LV2 = "http://lv2plug.in/ns/lv2core#"
NS_PPROP = "http://lv2plug.in/ns/ext/port-props#"
NS_PG = "http://lv2plug.in/ns/ext/port-groups#"
NS_UNITS = "http://lv2plug.in/ns/extensions/units#"
NS_ATOM = "http://lv2plug.in/ns/ext/atom#"
NS_RDFS = "http://www.w3.org/2000/01/rdf-schema#"


def node_value(node):
    if node is None:
        return None
    if node.is_float():
        return float(node)
    if node.is_int():
        return float(int(node))
    if node.is_bool():
        return bool(node)
    return str(node)


def plugin_uis(plugin):
    """plugin.get_uis() asserts when the plugin has no UI (lilv returns NULL)"""
    c_uis = lilv.c.plugin_get_uis(plugin.plugin)
    if not c_uis:
        return []
    res = []
    uis = lilv.UIs(plugin.world, c_uis)
    for ui in uis:
        classes = []
        nodes = ui.get_classes()
        for c in nodes:
            classes.append(str(c))
        res.append({"uri": str(ui.get_uri()), "classes": classes, "binary": str(ui.get_binary_uri())})
    return res


def describe_ports(world, plugin):
    uri = world.new_uri
    ports = []
    for i in range(plugin.get_num_ports()):
        port = plugin.get_port_by_index(i)
        direction = "in" if port.is_a(uri(NS_LV2 + "InputPort")) else "out"
        if port.is_a(uri(NS_LV2 + "ControlPort")):
            kind = "control"
        elif port.is_a(uri(NS_LV2 + "AudioPort")):
            kind = "audio"
        elif port.is_a(uri(NS_LV2 + "CVPort")):
            kind = "cv"
        elif port.is_a(uri(NS_ATOM + "AtomPort")):
            kind = "atom"
        else:
            kind = "other"
        info = {"index": i, "symbol": str(port.get_symbol()), "name": str(port.get_name()),
                "direction": direction, "type": kind}
        if kind == "control":
            vdef, vmin, vmax = port.get_range()
            info.update({"min": node_value(vmin), "max": node_value(vmax), "default": node_value(vdef)})
            props = []
            for prop, ns in (("toggled", NS_LV2), ("integer", NS_LV2), ("enumeration", NS_LV2),
                             ("logarithmic", NS_PPROP), ("trigger", NS_PPROP), ("notOnGUI", NS_PPROP)):
                if port.has_property(uri(ns + prop)):
                    props.append(prop)
            info["properties"] = props
            unit = port.get(uri(NS_UNITS + "unit"))
            if unit is not None:
                if unit.is_uri():
                    info["unit"] = str(unit).split("#")[-1]
                else:
                    # Custom unit (blank node): use its symbol
                    usym = world.get(unit, uri(NS_UNITS + "symbol"), None)
                    info["unit"] = str(usym) if usym is not None else "custom"
            prio = port.get(uri(NS_LV2 + "displayPriority"))
            if prio is not None:
                info["display_priority"] = node_value(prio)
            designation = port.get(uri(NS_LV2 + "designation"))
            if designation is not None:
                info["designation"] = str(designation)
            points = []
            sps = port.get_scale_points()
            if sps is not None:
                for sp in sps:
                    points.append([node_value(sp.get_value()), str(sp.get_label())])
            if points:
                info["scale_points"] = sorted(points, key=lambda p: p[0])
        group = port.get(uri(NS_PG + "group"))
        if group is not None:
            # Nodes can't be used as booleans (lilv raises), so compare with None
            name = world.get(group, uri(NS_LV2 + "name"), None)
            if name is None:
                name = world.get(group, uri(NS_RDFS + "label"), None)
            info["group"] = str(name) if name is not None else str(group)
        ports.append(info)
    return ports


ZYN_DESIGNATIONS = {"delay", "attack", "hold", "decay", "sustain", "fade", "release",
                    "cutoffFrequency", "resonance", "drawbar"}
NAME_HINTS = [(r"(^|[^a-z])(att|attack)([^a-z]|$)", "attack"), (r"(^|[^a-z])(dec|decay)([^a-z]|$)", "decay"),
              (r"(^|[^a-z])(sus|sustain)([^a-z]|$)", "sustain"), (r"(^|[^a-z])(rel|release)([^a-z]|$)", "release"),
              (r"(^|[^a-z])(cut|cutoff)([^a-z]|$)", "cutoffFrequency"),
              (r"(^|[^a-z])(res|reso|resonance)([^a-z]|$)", "resonance")]


def soft_rule_warnings(ports):
    """Soft rules of the zynthian-lv2-plugin skill, on the real ports (zynthian controllers = visible input
    control ports). Deviations are reported, not errors."""
    import re
    controls = [p for p in ports if p["type"] == "control" and p["direction"] == "in"
                and "notOnGUI" not in p.get("properties", [])
                and not p.get("designation", "").endswith(("#enabled", "#freeWheeling"))]
    res = []
    ungrouped = [p["symbol"] for p in controls if not p.get("group")]
    if ungrouped:
        res.append(f"rule 1: {len(ungrouped)} control(s) without port group: {', '.join(ungrouped[:12])}")
    sizes = {}
    for p in controls:
        if p.get("group"):
            sizes[p["group"]] = sizes.get(p["group"], 0) + 1
    for g, n in sizes.items():
        if n <= 2:
            res.append(f"rule 2: group '{g}' has {n} control(s)")
        elif n > 4 and n % 4:
            res.append(f"rule 2: group '{g}' has {n} controls (pages of 4 -> last page has {n % 4})")
    for p in controls:
        des = p.get("designation", "")
        if des.split("#")[-1] in ZYN_DESIGNATIONS:
            continue
        text = f"{p['symbol']} {p['name']}".lower()
        for rx, d in NAME_HINTS:
            if re.search(rx, text):
                res.append(f"rule 3: '{p['symbol']}' ({p['name']}) looks like {d} but has no designation")
                break
    return res


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    world = lilv.World()
    world.load_all()
    plugins = world.get_all_plugins()

    if cmd == "plugins":
        flt = (sys.argv[2] if len(sys.argv) > 2 else "").lower()
        res = []
        for p in plugins:
            uri, name = str(p.get_uri()), str(p.get_name())
            if flt in uri.lower() or flt in name.lower():
                res.append({"uri": uri, "name": name, "class": str(p.get_class().get_label())})
        print(json.dumps(sorted(res, key=lambda r: r["name"].lower()), indent=1))
        return 0

    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    try:
        plugin = plugins[world.new_uri(sys.argv[2])]
    except Exception:
        print(f"Plugin <{sys.argv[2]}> not found in LV2_PATH", file=sys.stderr)
        return 2

    if cmd == "ports":
        print(json.dumps({"uri": str(plugin.get_uri()), "name": str(plugin.get_name()),
                          "class": str(plugin.get_class().get_label()),
                          "bundle": str(plugin.get_bundle_uri()),
                          "ports": describe_ports(world, plugin), "uis": plugin_uis(plugin)}, indent=1))
        return 0

    if cmd == "summary":
        print(f"{plugin.get_name()} <{plugin.get_uri()}>  class: {plugin.get_class().get_label()}")
        print(f"bundle: {plugin.get_bundle_uri()}")
        for p in describe_ports(world, plugin):
            if p["type"] == "control":
                extra = [",".join(p.get("properties", [])), p.get("unit", "")]
                if p.get("group"):
                    extra.append(f"group={p['group']}")
                if "display_priority" in p:
                    extra.append(f"prio={p['display_priority']:g}")
                if p.get("designation"):
                    extra.append("designation=" + p["designation"].split("#")[-1])
                if p.get("scale_points"):
                    extra.append("labels=" + "/".join(label for _, label in p["scale_points"][:6]))
                print(f"  {p['direction']:3} {p['symbol']:24} [{p.get('min')} .. {p.get('max')}] "
                      f"def={p.get('default')} {' '.join(x for x in extra if x)}")
            else:
                print(f"  {p['direction']:3} {p['type']:7} {p['symbol']}")
        warnings = soft_rule_warnings(describe_ports(world, plugin))
        print(f"Soft rules: {'OK' if not warnings else str(len(warnings)) + ' warning(s)'}")
        for w in warnings:
            print(f"  {w}")
        print("UIs:")
        for u in plugin_uis(plugin):
            print(f"  {u['classes'][0].split('#')[-1]:8} {u['uri']}  {u['binary']}")
        return 0

    if cmd == "widget":
        import importlib.util
        ui_dir = os.environ["ZYNTHIAN_UI_DIR"]
        spec = importlib.util.spec_from_file_location("zl", f"{ui_dir}/zyngine/zynthian_lv2.py")
        zl = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(zl)
        print(json.dumps(zl.get_plugin_zyngui_widget(sys.argv[2]), indent=1))
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
