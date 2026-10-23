#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Carla GUI switcher
#
# Small desktop app to show/hide the native GUI of the plugins currently hosted
# by the zynthian Carla engine (zynthian_engine_carla.py).
#
# Usage:
#   zynthian_carla_gui.py                  => window with a Show/Hide button per plugin
#   zynthian_carla_gui.py list             => list hosted plugins
#   zynthian_carla_gui.py show|hide|toggle <id|name>
#
# Environment: ZYNTHIAN_CARLA_SOCKET (default /tmp/zynthian-carla.sock)
# ******************************************************************************

import os
import sys
import json
import socket

SOCKET_PATH = os.environ.get("ZYNTHIAN_CARLA_SOCKET", "/tmp/zynthian-carla.sock")


def request(cmd, **args):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(10)
        s.connect(SOCKET_PATH)
        s.sendall((json.dumps(dict(args, cmd=cmd)) + "\n").encode())
        data = b""
        while not data.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
    resp = json.loads(data)
    if not resp.get("ok"):
        raise RuntimeError(resp.get("err", "unknown error"))
    return resp["res"]


def find_plugin(ident):
    plugins = request("list")
    for p in plugins:
        if str(p["id"]) == ident:
            return p
    matches = [p for p in plugins if ident.lower() in p["name"].lower() or ident.lower() in str(p["jackname"]).lower()]
    if len(matches) == 1:
        return matches[0]
    raise RuntimeError(f"'{ident}' doesn't match exactly one plugin")


def run_cli(argv):
    cmd = argv[0]
    if cmd == "list":
        for p in request("list"):
            state = "-" if not p["has_gui"] else ("shown" if p["shown"] else "hidden")
            print(f"{p['id']}\t{p['name']}\t{p['jackname']}\t{state}")
    elif cmd == "params" and len(argv) > 1:
        p = find_plugin(argv[1])
        res = request("layout", id=p["id"])
        print(f"# Save as {res['file']} after editing", file=sys.stderr)
        print(json.dumps(res["layout"], indent=2))
    elif cmd in ("show", "hide", "toggle") and len(argv) > 1:
        p = find_plugin(argv[1])
        print(request(cmd, id=p["id"]))
    else:
        print(__doc__ if __doc__ else "")
        return 2
    return 0


def run_window():
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("Zynthian Carla plugins")
    root.minsize(360, 120)
    status = tk.StringVar()
    frame = ttk.Frame(root, padding=8)
    frame.pack(fill="both", expand=True)
    ttk.Label(root, textvariable=status, foreground="#888").pack(side="bottom", anchor="w", padx=8, pady=4)
    rows = {}

    def toggle(pid):
        try:
            request("toggle", id=pid)
        except Exception as e:
            status.set(str(e))
        refresh(False)

    def refresh(reschedule=True):
        try:
            plugins = request("list")
            status.set(f"{len(plugins)} plugin(s) hosted")
        except Exception as e:
            plugins = []
            status.set(f"Carla engine not available ({e})")
        ids = set()
        for p in plugins:
            ids.add(p["id"])
            text = f"{p['name']}  [{p['jackname']}]"
            btn_text = "Hide GUI" if p["shown"] else "Show GUI"
            if p["id"] not in rows:
                f = ttk.Frame(frame)
                f.pack(fill="x", pady=2)
                lbl = ttk.Label(f)
                lbl.pack(side="left", fill="x", expand=True)
                btn = ttk.Button(f, width=10, command=lambda pid=p["id"]: toggle(pid))
                btn.pack(side="right")
                rows[p["id"]] = (f, lbl, btn)
            f, lbl, btn = rows[p["id"]]
            lbl.config(text=text)
            btn.config(text=btn_text, state="normal" if p["has_gui"] else "disabled")
        for pid in list(rows):
            if pid not in ids:
                rows.pop(pid)[0].destroy()
        if reschedule:
            root.after(1000, refresh)

    refresh()
    root.mainloop()


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            sys.exit(run_cli(sys.argv[1:]))
        run_window()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
