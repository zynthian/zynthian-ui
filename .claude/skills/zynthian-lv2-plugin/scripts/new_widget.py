#!/usr/bin/env python3
"""Create a zynthian widget (LV2 extension bundle) for an LV2 plugin that already exists.

usage: new_widget.py --uri URI [--symbol NAME] [--builtin] [--half-height] [--dest DIR] [--host HOST | --local]
                     [--package-name NAME] [--github OWNER/REPO] [--no-git] [--force]

  --uri       plugin URI (find it with: zyn_device.sh plugins <filter>)
  --symbol    widget name, [a-z][a-z0-9_]* (default: from the plugin name)
  --builtin   built-in widget: bundle in ~/Zynthian/zynthian-ui/lv2/<symbol>.zyngui.lv2 (a zynthian-ui contribution)
              default: user widget, installed in /zynthian/zynthian-plugins/lv2-widgets
  --half-height  widget uses the lower half of the screen; the list of pages stays visible above it
  --dest      workspace folder (default ~/Zynthian/<symbol>.zyngui): SPEC.md, ports.json and (user widgets) the bundle
  --host      zynthian to read the plugin ports from (default $ZYNTHIAN_HOST or zynthian.lan)
  --local     read the ports with the local lilv instead
  User widgets only (the workspace is the widget's git repo, with a zynthian package in package/, category Widgets):
  --package-name  name in the zynthian-packages catalog (default: "<plugin name> Widget")
  --github    owner/repo on GitHub (default: <gh login>/<symbol>.zyngui)
  --no-git    don't create the git repo

The generic widget shows every output control port of the plugin as a bar. Edit it afterwards.
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(os.path.dirname(HERE), "templates")
UI_DIR = os.path.expanduser("~/Zynthian/zynthian-ui")


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def get_ports(uri, host, local):
    script = os.path.join(HERE, "lv2_ports.py")
    if local:
        cmd = [sys.executable, script, "ports", uri]
        res = subprocess.run(cmd, capture_output=True, text=True)
    else:
        remote = ("bash -c 'source /zynthian/config/zynthian_envars.sh >/dev/null 2>&1; cd /tmp; "
                  f"python3 - ports \"{uri}\"'")
        with open(script) as f:
            res = subprocess.run(["ssh", "-o", "ConnectTimeout=10", "-o", "LogLevel=ERROR", f"root@{host}", remote],
                                 stdin=f, capture_output=True, text=True)
    if res.returncode != 0:
        fail(f"can't read the ports of <{uri}>: {res.stderr.strip()}")
    return json.loads(res.stdout)


def render(path, values):
    with open(path) as f:
        text = f.read()
    for key, value in values.items():
        text = text.replace(f"@@{key}@@", str(value))
    left = re.findall(r"@@[A-Z_]+@@", text)
    if left:
        fail(f"template {path}: unknown placeholders {sorted(set(left))}")
    return text


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--uri", required=True)
    ap.add_argument("--symbol")
    ap.add_argument("--builtin", action="store_true")
    ap.add_argument("--half-height", action="store_true")
    ap.add_argument("--dest")
    ap.add_argument("--host", default=os.environ.get("ZYNTHIAN_HOST", "zynthian.lan"))
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--package-name")
    ap.add_argument("--github")
    ap.add_argument("--no-git", action="store_true")
    args = ap.parse_args()

    info = get_ports(args.uri, args.host, args.local)
    sym = args.symbol or re.sub(r"[^a-z0-9]+", "_", info["name"].lower()).strip("_")
    if not re.match(r"^[a-z][a-z0-9_]*$", sym):
        fail(f"invalid widget symbol '{sym}': use --symbol")

    workspace = os.path.abspath(os.path.expanduser(args.dest or f"~/Zynthian/{sym}.zyngui"))
    if args.builtin:
        bundle = os.path.join(UI_DIR, "lv2", f"{sym}.zyngui.lv2")
        widget_uri = f"http://zynthian.org/plugins/zyngui/{sym}#{sym}"
    else:
        bundle = os.path.join(workspace, f"{sym}.zyngui.lv2")
        widget_uri = f"http://zynthian.org/plugins/zyngui/user/{sym}#{sym}"
    for d in (bundle, workspace):
        if os.path.isdir(d) and os.listdir(d) and not args.force:
            fail(f"{d} exists and isn't empty (use --force)")

    outputs = [p for p in info["ports"] if p["type"] == "control" and p["direction"] == "out"
               and p["symbol"] not in ("latency", "lv2_latency")]
    inputs = [p for p in info["ports"] if p["type"] == "control" and p["direction"] == "in"
              and "notOnGUI" not in p.get("properties", [])]

    def rng(p, key, default):
        return p[key] if p.get(key) is not None else default

    values = {
        "NAME": info["name"], "SYMBOL": sym, "URI": args.uri, "PLUGIN_URI": args.uri, "WIDGET_URI": widget_uri,
        "YEAR": datetime.date.today().year, "MAKER": "Zynthian", "LICENSE": "GPL-3.0-or-later",
        "DESCRIPTION": f"Zynthian widget for {info['name']}.",
        "WIDGET_ROWS": ("        # Half-height widget: the list of pages stays visible above it\n"
                        "        self.rows = max(1, self.rows // 2)\n") if args.half_height else "",
        "MONITORS": "\n".join(f"    {p['symbol']!r}: ({p['name']!r}, {float(rng(p, 'min', 0))}, {float(rng(p, 'max', 1))}, "
                              f"{p.get('unit', '')!r}),"
                              for p in outputs) or "    # This plugin has no output control ports: nothing to monitor",
        "BUNDLE": os.path.basename(bundle), "CATEGORY": "Widgets",
        "CONTROLS_HELP": "<ul>\n" + "\n".join(f"  <li><b>{p['name']}</b>: TODO</li>" for p in inputs) + "\n</ul>",
    }

    write(os.path.join(bundle, "manifest.ttl"),
          f"# Zynthian widget extension bundle for {info['name']}.\n"
          "# It adds a zyngui:widget UI to an existing plugin; it does not declare the plugin.\n"
          + render(os.path.join(TEMPLATES, "zyngui", "zyngui.ttl"), values))
    write(os.path.join(bundle, f"zynthian_widget_{sym}.py"), render(os.path.join(TEMPLATES, "zyngui", "widget.py"), values))
    write(os.path.join(bundle, f"zynthian_widget_{sym}.html"), render(os.path.join(TEMPLATES, "zyngui", "help.html"), values))

    write(os.path.join(workspace, "ports.json"), json.dumps(info, indent=1) + "\n")
    rows_out = "\n".join(f"| `{p['symbol']}` | {p['name']} | {rng(p, 'min', '?')} .. {rng(p, 'max', '?')} | "
                         f"{p.get('unit', '')} | |" for p in outputs) or "| (none) | | | | |"
    rows_in = "\n".join(f"| `{p['symbol']}` | {p['name']} | {rng(p, 'min', '?')} .. {rng(p, 'max', '?')} | "
                        f"{p.get('group', '')} | |" for p in inputs) or "| (none) | | | | |"
    write(os.path.join(workspace, "SPEC.md"), f"""# Widget for {info['name']}: specification

- Plugin: {info['name']} <{args.uri}> ({info['class']})
- Widget: `zynthian_widget_{sym}` · UI URI `{widget_uri}` · {'built-in (zynthian-ui/lv2)' if args.builtin else 'user widget (lv2-widgets)'}
- Bundle: `{bundle}`

## Data available (output control ports, ~30 Hz) — what the widget can show

| Symbol | Name | Range | Unit | Use in the widget |
|---|---|---|---|---|
{rows_out}

## Controls (input control ports) — what the widget may change

| Symbol | Name | Range | Page | Use in the widget |
|---|---|---|---|---|
{rows_in}

## Widget design — TODO
What it shows, layout, colours, knob/switch handling (if any).

## Help page — TODO

## Open questions
-
""")
    if not args.builtin:
        maker = subprocess.run([os.path.join(HERE, "detect_maker.sh")], capture_output=True, text=True).stdout.strip()
        github = args.github
        if not github:
            res = subprocess.run(["bash", "-c", "timeout 10 gh api user --jq .login 2>/dev/null"],
                                 capture_output=True, text=True)
            github = f"{res.stdout.strip() or 'OWNER'}/{sym}.zyngui"
        package = args.package_name or " ".join(w[:1].upper() + w[1:] for w in f"{info['name']} Widget".split())
        if re.search(r'[/"\\]', package):
            fail("--package-name can't contain '/', '\"' or '\\'")
        pvalues = {**values, "PACKAGE": package, "GITHUB": github, "MAKER": maker or "Zynthian",
                   "DESCRIPTION": f"Zynthian widget for the {info['name']} LV2 plugin",
                   "DESCRIPTION_EXTENDED": "TODO: what the widget shows and how to use it (from the help page), simple HTML.",
                   "SIZE": "TODO (zyn_device.sh package)", "CONTENT": f"zynthian-plugins/lv2-widgets/{os.path.basename(bundle)}"}
        pkg = os.path.join(workspace, "package")
        write(os.path.join(pkg, "info.yml"), render(os.path.join(TEMPLATES, "package", "info.yml"), pvalues))
        write(os.path.join(pkg, f"{package}.sh"), render(os.path.join(TEMPLATES, "package", "widget.sh"), pvalues))
        os.makedirs(os.path.join(pkg, "Art"), exist_ok=True)
        write(os.path.join(workspace, ".gitignore"), "__pycache__/\n")
        with open(os.path.join(TEMPLATES, "tools", "package_pr.py")) as f:
            write(os.path.join(workspace, "tools", "package_pr.py"), f.read())
        os.chmod(os.path.join(workspace, "tools", "package_pr.py"), 0o755)
        with open(os.path.join(TEMPLATES, "licenses", "GPL-3.0.txt")) as f:  # values["LICENSE"]: GPL-3.0-or-later
            write(os.path.join(workspace, "LICENSE"), f.read())
        write(os.path.join(workspace, "README.md"),
              f"# {package}\n\n{pvalues['DESCRIPTION']} (<{args.uri}>): a zyngui:widget extension bundle "
              f"(`{os.path.basename(bundle)}`), installed in `/zynthian/zynthian-plugins/lv2-widgets`.\n\n"
              f"Install it from webconf (packages, category Widgets), or copy `{os.path.basename(bundle)}` into "
              "`/zynthian/zynthian-plugins/lv2-widgets/` and show the widget again.\n")
        print(f"package: '{package}' (Widgets), github '{github}', author '{pvalues['MAKER']}'")
        if not args.no_git and not os.path.isdir(os.path.join(workspace, ".git")):
            subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
    print(f"Created widget bundle {bundle}")
    print(f"  {len(outputs)} outputs to monitor, {len(inputs)} controls; workspace {workspace} (SPEC.md, ports.json)")
    if args.builtin:
        print("Next: edit the widget; test it by copying the bundle to the device: zyn_device.sh widget " + bundle)
    else:
        print(f"Next: edit the widget, then: zyn_device.sh widget {bundle}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
