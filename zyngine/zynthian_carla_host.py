#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Carla headless host
#
# Small helper process that runs a headless Carla engine (JACK driver, one JACK
# client per plugin) and exposes it to zynthian_engine_carla through a line based
# JSON protocol on stdin/stdout.
#
# Protocol (one JSON object per line):
#   request  => {"id": 12, "cmd": "set_param", "h": 1, ...}  ("id" is optional, if
#               it is missing no response is sent)
#   response => {"id": 12, "ok": true, "res": {...}} or {"id": 12, "ok": false, "err": "..."}
#   event    => {"evt": "params", "h": 1, "v": {"3": 0.5}}
#
# Plugins are addressed with stable handles ("h") that are assigned by this helper,
# because Carla re-numbers its plugin ids when a plugin is removed.
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or any later version.
# ******************************************************************************

import os
import sys
import json
import math
import time
import select
import signal
import argparse
import ctypes
import ctypes.util
import threading
import traceback

# ------------------------------------------------------------------------------
# Locate Carla
# ------------------------------------------------------------------------------

IDLE_FAST = 0.02     # Main loop period (s) when native GUI is visible
IDLE_SLOW = 0.25     # Main loop period (s) when native GUI is not visible

PROBE_TYPES = ("VST2", "VST3", "CLAP")
PROBE_COARSE_POINTS = 17
PROBE_FINE_POINTS = 257
PROBE_MAX_ITEMS = 32
PROBE_MAX_NUMERIC_ITEMS = 8
LIB_DIR_CANDIDATES = [
    "/usr/lib/carla",
    "/usr/local/lib/carla",
    "/usr/lib/x86_64-linux-gnu/carla",
    "/usr/lib/aarch64-linux-gnu/carla",
    "/usr/lib/arm-linux-gnueabihf/carla",
    "/usr/lib64/carla",
    "/zynthian/zynthian-sw/carla/bin"
]

SHARE_DIR_CANDIDATES = [
    "/usr/share/carla",
    "/usr/local/share/carla",
    "/zynthian/zynthian-sw/carla/source/frontend"
]


def find_carla_lib_dir():
    cands = []
    if os.environ.get("CARLA_LIB_DIR"):
        cands.append(os.environ["CARLA_LIB_DIR"])
    cands += LIB_DIR_CANDIDATES
    for d in cands:
        if os.path.isfile(os.path.join(d, "libcarla_standalone2.so")):
            return d
    return None


def find_carla_share_dir():
    cands = []
    if os.environ.get("CARLA_SHARE_DIR"):
        cands.append(os.environ["CARLA_SHARE_DIR"])
    cands += SHARE_DIR_CANDIDATES
    for d in cands:
        if os.path.isfile(os.path.join(d, "carla_backend.py")):
            return d
    return None


def find_carla_resources_dir(share_dir):
    for d in (os.path.join(share_dir, "resources"), share_dir):
        if os.path.isdir(d):
            return d
    return share_dir


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

def finite(v, default=0.0):
    try:
        v = float(v)
    except Exception:
        return default
    if math.isnan(v) or math.isinf(v):
        return default
    return v


def to_str(v):
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    if v is None:
        return ""
    return str(v)


# ------------------------------------------------------------------------------
# Host class
# ------------------------------------------------------------------------------

class XWindowAttributes(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int), ("width", ctypes.c_int), ("height", ctypes.c_int),
                ("border_width", ctypes.c_int), ("depth", ctypes.c_int), ("visual", ctypes.c_void_p),
                ("root", ctypes.c_ulong), ("klass", ctypes.c_int), ("bit_gravity", ctypes.c_int),
                ("win_gravity", ctypes.c_int), ("backing_store", ctypes.c_int),
                ("backing_planes", ctypes.c_ulong), ("backing_pixel", ctypes.c_ulong),
                ("save_under", ctypes.c_int), ("colormap", ctypes.c_ulong), ("map_installed", ctypes.c_int),
                ("map_state", ctypes.c_int), ("all_event_masks", ctypes.c_long),
                ("your_event_mask", ctypes.c_long), ("do_not_propagate_mask", ctypes.c_long),
                ("override_redirect", ctypes.c_int), ("screen", ctypes.c_void_p)]


class XWindows:
    # Minimal Xlib access (ctypes) to find the windows of the plugin GUIs and read/set their
    # position, so a GUI re-appears where the user left it. Carla destroys the GUI when it is
    # hidden (to use no CPU), so the new window would otherwise open in the default position.

    XA_CARDINAL = 6
    IS_VIEWABLE = 2
    _handler = None

    def __init__(self):
        lib = ctypes.util.find_library("X11")
        if not lib:
            raise RuntimeError("libX11 not found")
        x = self.x = ctypes.CDLL(lib)
        c = ctypes
        x.XOpenDisplay.restype = c.c_void_p
        x.XOpenDisplay.argtypes = [c.c_char_p]
        x.XCloseDisplay.argtypes = [c.c_void_p]
        x.XDefaultRootWindow.restype = c.c_ulong
        x.XDefaultRootWindow.argtypes = [c.c_void_p]
        x.XInternAtom.restype = c.c_ulong
        x.XInternAtom.argtypes = [c.c_void_p, c.c_char_p, c.c_int]
        x.XQueryTree.argtypes = [c.c_void_p, c.c_ulong, c.POINTER(c.c_ulong), c.POINTER(c.c_ulong),
                                 c.POINTER(c.POINTER(c.c_ulong)), c.POINTER(c.c_uint)]
        x.XFree.argtypes = [c.c_void_p]
        x.XGetWindowProperty.argtypes = [c.c_void_p, c.c_ulong, c.c_ulong, c.c_long, c.c_long, c.c_int,
                                         c.c_ulong, c.POINTER(c.c_ulong), c.POINTER(c.c_int),
                                         c.POINTER(c.c_ulong), c.POINTER(c.c_ulong),
                                         c.POINTER(c.POINTER(c.c_ubyte))]
        x.XGetWindowAttributes.argtypes = [c.c_void_p, c.c_ulong, c.POINTER(XWindowAttributes)]
        x.XTranslateCoordinates.argtypes = [c.c_void_p, c.c_ulong, c.c_ulong, c.c_int, c.c_int,
                                            c.POINTER(c.c_int), c.POINTER(c.c_int), c.POINTER(c.c_ulong)]
        x.XMoveWindow.argtypes = [c.c_void_p, c.c_ulong, c.c_int, c.c_int]
        x.XSync.argtypes = [c.c_void_p, c.c_int]
        if XWindows._handler is None:
            XWindows._handler = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_void_p)(lambda d, e: 0)
        x.XSetErrorHandler(XWindows._handler)
        self.dpy = x.XOpenDisplay(None)
        if not self.dpy:
            raise RuntimeError("Can't open the display")
        self.root = x.XDefaultRootWindow(self.dpy)
        self.a_pid = x.XInternAtom(self.dpy, b"_NET_WM_PID", 0)

    def close(self):
        if self.dpy:
            self.x.XCloseDisplay(self.dpy)
            self.dpy = None

    def get_pid(self, win):
        c = ctypes
        atype, afmt = c.c_ulong(), c.c_int()
        nitems, after = c.c_ulong(), c.c_ulong()
        data = c.POINTER(c.c_ubyte)()
        res = self.x.XGetWindowProperty(self.dpy, win, self.a_pid, 0, 1, 0, self.XA_CARDINAL, c.byref(atype),
                                        c.byref(afmt), c.byref(nitems), c.byref(after), c.byref(data))
        pid = None
        if res == 0 and data and nitems.value == 1 and afmt.value == 32:
            pid = c.cast(data, c.POINTER(c.c_long))[0]
        if data:
            self.x.XFree(data)
        return pid

    def is_viewable(self, win):
        attr = XWindowAttributes()
        return bool(self.x.XGetWindowAttributes(self.dpy, win, ctypes.byref(attr))) and \
            attr.map_state == self.IS_VIEWABLE

    def windows(self, pids):
        found = {}
        c = ctypes
        stack = [(self.root, 0)]
        while stack:
            win, depth = stack.pop()
            root, parent = c.c_ulong(), c.c_ulong()
            children = c.POINTER(c.c_ulong)()
            n = c.c_uint()
            if not self.x.XQueryTree(self.dpy, win, c.byref(root), c.byref(parent), c.byref(children), c.byref(n)):
                continue
            kids = [children[i] for i in range(n.value)] if children else []
            if children:
                self.x.XFree(children)
            for k in kids:
                pid = self.get_pid(k)
                if pid in pids:
                    if self.is_viewable(k):
                        found[k] = pid
                elif depth < 2:
                    stack.append((k, depth + 1))
        return found

    def origin(self, win):
        c = ctypes
        if not self.is_viewable(win):
            return None
        x, y, child = c.c_int(), c.c_int(), c.c_ulong()
        if not self.x.XTranslateCoordinates(self.dpy, win, self.root, 0, 0, c.byref(x), c.byref(y), c.byref(child)):
            return None
        return (x.value, y.value)

    def move(self, win, x, y):
        want = (x, y)
        req = (x, y)
        for _ in range(3):
            self.x.XMoveWindow(self.dpy, win, req[0], req[1])
            self.x.XSync(self.dpy, 0)
            time.sleep(0.15)
            now = self.origin(win)
            if now is None or now == want:
                return now
            req = (req[0] + want[0] - now[0], req[1] + want[1] - now[1])
        return self.origin(win)


def descendant_pids(root_pid):
    children = {}
    for name in os.listdir("/proc"):
        if name.isdigit():
            try:
                with open(f"/proc/{name}/stat") as f:
                    ppid = int(f.read().rsplit(")", 1)[1].split()[1])
                children.setdefault(ppid, []).append(int(name))
            except Exception:
                pass
    pids, todo = {root_pid}, [root_pid]
    while todo:
        for ch in children.get(todo.pop(), []):
            if ch not in pids:
                pids.add(ch)
                todo.append(ch)
    return pids


class CarlaHostProcess:

    def __init__(self, args):
        self.args = args
        self.quit = False
        self.ui_shown = set()
        self.last_cmd = 0.0
        self.mute_pids = {}
        self.enum_cache = {}
        self.ui_windows = {}
        self.ui_pos = {}
        self.host = None
        self.cb = None

        self.proto_out = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8")
        os.dup2(2, 1)
        self.out_lock = threading.Lock()

        self.handles = {}
        self.next_handle = 1
        self.pending = {}
        self.pending_lock = threading.Lock()
        self.echo = {}
        self.stale = {}

    # ---------------------------------------------------------------------------
    # Output
    # ---------------------------------------------------------------------------

    def emit(self, obj):
        try:
            line = json.dumps(obj, separators=(",", ":"), allow_nan=False)
        except ValueError:
            line = json.dumps(obj, separators=(",", ":"), default=str)
        with self.out_lock:
            try:
                self.proto_out.write(line + "\n")
                self.proto_out.flush()
            except Exception:
                self.quit = True

    def log(self, level, msg):
        self.emit({"evt": "log", "level": level, "msg": msg})

    # ---------------------------------------------------------------------------
    # Carla engine
    # ---------------------------------------------------------------------------

    def load_carla(self):
        lib_dir = find_carla_lib_dir()
        share_dir = find_carla_share_dir()
        if not lib_dir or not share_dir:
            raise RuntimeError(f"Carla not found (lib dir: {lib_dir}, share dir: {share_dir}). "
                               "Set CARLA_LIB_DIR and CARLA_SHARE_DIR.")
        sys.path.insert(0, share_dir)
        import carla_backend as cb
        self.cb = cb
        self.lib_dir = lib_dir
        self.share_dir = share_dir
        self.host = cb.CarlaHostDLL(os.path.join(lib_dir, "libcarla_standalone2.so"), False)

    def init_engine(self):
        cb = self.cb
        host = self.host
        host.set_engine_callback(self.engine_callback)
        host.set_engine_option(cb.ENGINE_OPTION_PROCESS_MODE, cb.ENGINE_PROCESS_MODE_MULTIPLE_CLIENTS, "")
        host.set_engine_option(cb.ENGINE_OPTION_TRANSPORT_MODE, cb.ENGINE_TRANSPORT_MODE_JACK, "")
        host.set_engine_option(cb.ENGINE_OPTION_FORCE_STEREO, 0, "")
        host.set_engine_option(cb.ENGINE_OPTION_PREFER_PLUGIN_BRIDGES, 0, "")
        host.set_engine_option(cb.ENGINE_OPTION_PREFER_UI_BRIDGES, 1, "")
        host.set_engine_option(cb.ENGINE_OPTION_UIS_ALWAYS_ON_TOP, 0, "")
        host.set_engine_option(cb.ENGINE_OPTION_MAX_PARAMETERS, self.args.max_params, "")
        host.set_engine_option(cb.ENGINE_OPTION_PATH_BINARIES, 0, self.lib_dir)
        host.set_engine_option(cb.ENGINE_OPTION_PATH_RESOURCES, 0, find_carla_resources_dir(self.share_dir))
        if not host.engine_init("JACK", self.args.name):
            raise RuntimeError("Can't start Carla engine => " + to_str(host.get_last_error()))
        self.emit({"evt": "ready",
                   "name": self.args.name,
                   "sample_rate": finite(host.get_sample_rate()),
                   "buffer_size": int(host.get_buffer_size())})

    def engine_callback(self, handle, action, plugin_id, value1, value2, value3, value_f, value_s):
        # This can be called from any Carla thread => keep it short and never block
        cb = self.cb
        try:
            if action == cb.ENGINE_CALLBACK_PARAMETER_VALUE_CHANGED:
                if time.monotonic() < self.mute_pids.get(plugin_id, 0):
                    return
                h = self.handle_of(plugin_id)
                if h is not None:
                    with self.pending_lock:
                        self.pending[(h, value1)] = float(value_f)
            elif action == cb.ENGINE_CALLBACK_PROGRAM_CHANGED:
                h = self.handle_of(plugin_id)
                if h is not None:
                    self.emit({"evt": "program", "h": h, "index": value1})
            elif action == cb.ENGINE_CALLBACK_MIDI_PROGRAM_CHANGED:
                h = self.handle_of(plugin_id)
                if h is not None:
                    self.emit({"evt": "midi_program", "h": h, "index": value1})
            elif action == cb.ENGINE_CALLBACK_UI_STATE_CHANGED:
                h = self.handle_of(plugin_id)
                if h is not None:
                    # Carla stops the GUI bridge process when the GUI is hidden/closed
                    if value1 == 1:
                        self.ui_shown.add(h)
                    else:
                        self.ui_shown.discard(h)
                    self.emit({"evt": "ui", "h": h, "state": value1})
            elif action in (cb.ENGINE_CALLBACK_RELOAD_PARAMETERS, cb.ENGINE_CALLBACK_RELOAD_PROGRAMS,
                            cb.ENGINE_CALLBACK_RELOAD_ALL):
                h = self.handle_of(plugin_id)
                if h is not None:
                    self.emit({"evt": "reload", "h": h, "what": action})
            elif action == cb.ENGINE_CALLBACK_PLUGIN_UNAVAILABLE:
                h = self.handle_of(plugin_id)
                self.emit({"evt": "unavailable", "h": h, "msg": to_str(value_s)})
            elif action == cb.ENGINE_CALLBACK_ERROR:
                self.log("error", to_str(value_s))
            elif action == cb.ENGINE_CALLBACK_INFO:
                self.log("info", to_str(value_s))
            elif action in (cb.ENGINE_CALLBACK_ENGINE_STOPPED, cb.ENGINE_CALLBACK_QUIT):
                self.emit({"evt": "engine_stopped"})
        except Exception:
            pass

    def handle_of(self, plugin_id):
        for h, pid in self.handles.items():
            if pid == plugin_id:
                return h
        return None

    def pid_of(self, a):
        h = int(a["h"])
        if h not in self.handles:
            raise KeyError(f"unknown plugin handle {h}")
        return self.handles[h]

    # ---------------------------------------------------------------------------
    # Plugin information
    # ---------------------------------------------------------------------------

    def probe_enum(self, pid, index, vmin, vmax, original):
        host = self.host

        def sample(n):
            res = []
            for k in range(n):
                v = vmin + (vmax - vmin) * k / (n - 1)
                host.set_parameter_value(pid, index, v)
                res.append((v, to_str(host.get_parameter_text(pid, index)).strip()))
            return res

        def is_number(t):
            try:
                float(t.split()[0])
                return True
            except (ValueError, IndexError):
                return False

        try:
            texts = [t for _, t in sample(PROBE_COARSE_POINTS)]
            distinct = set(texts)
            if len(distinct) < 2 or len(distinct) >= PROBE_COARSE_POINTS or "" in distinct:
                return None
            fine = sample(PROBE_FINE_POINTS)
            runs = []
            for v, t in fine:
                if runs and runs[-1][0] == t:
                    runs[-1][2] = v
                else:
                    runs.append([t, v, v])
            labels = [r[0] for r in runs]
            if len(set(labels)) != len(labels) or len(runs) < 2 or len(runs) > PROBE_MAX_ITEMS:
                return None
            if all(is_number(t) for t in labels) and len(runs) > PROBE_MAX_NUMERIC_ITEMS:
                return None
            items = [[finite((r[1] + r[2]) / 2), r[0]] for r in runs]
            if len(items) == 2 and is_number(labels[0]) and is_number(labels[1]) and \
                    abs(float(labels[0].split()[0])) < 1e-9 and abs(float(labels[1].split()[0]) - 1.0) < 1e-9:
                items[0][1], items[1][1] = "off", "on"
            return items
        except Exception as e:
            self.log("debug", f"Can't probe parameter {index} => {e}")
            return None
        finally:
            host.set_parameter_value(pid, index, original)

    def describe_params(self, pid):
        cb = self.cb
        host = self.host
        params = []
        pinfo = host.get_plugin_info(pid)
        ptype = int(pinfo["type"])
        names = os.environ.get("ZYNTHIAN_CARLA_PROBE_TYPES")
        types = [t.strip().upper() for t in names.split(",")] if names else PROBE_TYPES
        probe = ptype in [getattr(cb, "PLUGIN_" + t, -1) for t in types]
        plugin_key = (ptype, to_str(pinfo["label"]), to_str(pinfo["maker"]), host.get_parameter_count(pid))
        if probe:
            self.mute_pids[pid] = time.monotonic() + 2.0
        for i in range(host.get_parameter_count(pid)):
            d = host.get_parameter_data(pid, i)
            inf = host.get_parameter_info(pid, i)
            r = host.get_parameter_ranges(pid, i)
            sps = []
            if d["hints"] & cb.PARAMETER_USES_SCALEPOINTS:
                for s in range(inf["scalePointCount"]):
                    sp = host.get_parameter_scalepoint_info(pid, i, s)
                    sps.append([finite(sp["value"]), to_str(sp["label"])])
            elif (probe and d["type"] == cb.PARAMETER_INPUT and not d["hints"] & cb.PARAMETER_IS_READ_ONLY
                  and not d["hints"] & (cb.PARAMETER_IS_BOOLEAN | cb.PARAMETER_IS_INTEGER)):
                key = plugin_key + (i,)
                if key not in self.enum_cache:
                    self.enum_cache[key] = self.probe_enum(
                        pid, i, finite(r["min"]), finite(r["max"], 1.0),
                        finite(host.get_current_parameter_value(pid, i)))
                sps = self.enum_cache[key] or []
            params.append({
                "index": i,
                "type": d["type"],
                "hints": d["hints"],
                "name": to_str(inf["name"]),
                "symbol": to_str(inf["symbol"]),
                "unit": to_str(inf["unit"]),
                "group": to_str(inf["groupName"]),
                "min": finite(r["min"]),
                "max": finite(r["max"], 1.0),
                "def": finite(r["def"]),
                "step": finite(r["step"]),
                "value": finite(host.get_current_parameter_value(pid, i)),
                "scale_points": sps
            })
        if probe:
            self.mute_pids[pid] = time.monotonic() + 1.0
        return params

    def describe_programs(self, pid):
        host = self.host
        programs = [to_str(host.get_program_name(pid, i)) for i in range(host.get_program_count(pid))]
        mprogs = []
        for i in range(host.get_midi_program_count(pid)):
            d = host.get_midi_program_data(pid, i)
            mprogs.append([int(d["bank"]), int(d["program"]), to_str(d["name"])])
        return programs, mprogs

    def describe(self, pid):
        cb = self.cb
        host = self.host
        info = host.get_plugin_info(pid)
        audio = host.get_audio_port_count_info(pid)
        midi = host.get_midi_port_count_info(pid)
        programs, mprogs = self.describe_programs(pid)
        return {
            "type": info["type"],
            "category": info["category"],
            "hints": info["hints"],
            "options_available": info["optionsAvailable"],
            "options_enabled": info["optionsEnabled"],
            "name": to_str(info["name"]),
            "label": to_str(info["label"]),
            "maker": to_str(info["maker"]),
            "has_ui": bool(info["hints"] & cb.PLUGIN_HAS_CUSTOM_UI),
            "audio_ins": audio["ins"], "audio_outs": audio["outs"],
            "midi_ins": midi["ins"], "midi_outs": midi["outs"],
            "custom_data_count": host.get_custom_data_count(pid),
            "programs": programs,
            "midi_programs": mprogs,
            "params": self.describe_params(pid)
        }

    def read_values(self, pid, outputs=False):
        host = self.host
        cb = self.cb
        values = {}
        for i in range(host.get_parameter_count(pid)):
            d = host.get_parameter_data(pid, i)
            is_output = (d["type"] == cb.PARAMETER_OUTPUT)
            if is_output == outputs:
                values[str(i)] = finite(host.get_current_parameter_value(pid, i))
        return values

    # ---------------------------------------------------------------------------
    # Commands
    # ---------------------------------------------------------------------------

    def cmd_ping(self, a):
        return {"time": time.time()}

    def cmd_add_plugin(self, a):
        cb = self.cb
        host = self.host
        ptype = getattr(cb, "PLUGIN_" + str(a["type"]).upper(), None)
        if ptype is None:
            raise RuntimeError(f"Plugin type '{a['type']}' not supported by this Carla build")
        btype = int(a["build"]) if a.get("build") is not None else cb.BINARY_NATIVE
        options = int(a["options"]) if a.get("options") is not None else cb.PLUGIN_OPTIONS_NULL
        count = host.get_current_plugin_count()
        ok = host.add_plugin(btype, ptype, a.get("filename") or None, a["name"], a.get("label") or None,
                             int(a.get("uid", 0)), None, options)
        if not ok:
            raise RuntimeError("Can't load plugin => " + to_str(host.get_last_error()))
        pid = host.get_current_plugin_count() - 1
        if pid < count:
            raise RuntimeError("Plugin was not added")
        h = self.next_handle
        self.next_handle += 1
        self.handles[h] = pid
        try:
            desc = self.describe(pid)
        except Exception:
            self.handles.pop(h, None)
            host.remove_plugin(pid)
            raise
        desc["h"] = h
        return desc

    def cmd_get_info(self, a):
        pid = self.pid_of(a)
        desc = self.describe(pid)
        desc["h"] = int(a["h"])
        return desc

    def cmd_remove_plugin(self, a):
        h = int(a["h"])
        pid = self.pid_of(a)
        if not self.host.remove_plugin(pid):
            raise RuntimeError("Can't remove plugin => " + to_str(self.host.get_last_error()))
        del self.handles[h]
        for hh, pp in self.handles.items():
            if pp > pid:
                self.handles[hh] = pp - 1
        with self.pending_lock:
            for k in [k for k in self.pending if k[0] == h]:
                del self.pending[k]
        return None

    def cmd_set_param(self, a):
        pid = self.pid_of(a)
        idx = int(a["index"])
        val = float(a["value"])
        self.echo[(int(a["h"]), idx)] = (val, time.monotonic())
        self.host.set_parameter_value(pid, idx, val)
        return None

    def cmd_set_active(self, a):
        self.host.set_active(self.pid_of(a), bool(a["on"]))
        return None

    def cmd_set_drywet(self, a):
        self.host.set_drywet(self.pid_of(a), float(a["value"]))
        return None

    def cmd_set_ctrl_channel(self, a):
        self.host.set_ctrl_channel(self.pid_of(a), int(a["chan"]))
        return None

    def values_after_load(self, h, pid):
        values = self.read_values(pid)
        now = time.monotonic()
        with self.pending_lock:
            for k in [k for k in self.pending if k[0] == h]:
                del self.pending[k]
        for sidx, val in values.items():
            self.stale[(h, int(sidx))] = (val, now)
        return {"values": values}

    def cmd_program(self, a):
        pid = self.pid_of(a)
        self.host.set_program(pid, int(a["index"]))
        return self.values_after_load(int(a["h"]), pid)

    def cmd_midi_program(self, a):
        pid = self.pid_of(a)
        self.host.set_midi_program(pid, int(a["index"]))
        return self.values_after_load(int(a["h"]), pid)

    def cmd_reset_params(self, a):
        pid = self.pid_of(a)
        self.host.reset_parameters(pid)
        return self.values_after_load(int(a["h"]), pid)

    def cmd_load_state(self, a):
        pid = self.pid_of(a)
        if not self.host.load_plugin_state(pid, a["path"]):
            raise RuntimeError("Can't load state => " + to_str(self.host.get_last_error()))
        return self.values_after_load(int(a["h"]), pid)

    def cmd_save_state(self, a):
        pid = self.pid_of(a)
        self.host.prepare_for_save(pid)
        if not self.host.save_plugin_state(pid, a["path"]):
            raise RuntimeError("Can't save state => " + to_str(self.host.get_last_error()))
        return None

    def cmd_get_values(self, a):
        pid = self.pid_of(a)
        return {"values": self.read_values(pid)}

    def cmd_monitors(self, a):
        pid = self.pid_of(a)
        return {"values": self.read_values(pid, True)}

    def cmd_show_ui(self, a):
        h = a["h"]
        pid = self.pid_of(a)
        if a["show"]:
            known = None
            try:
                xw = XWindows()
                try:
                    known = set(xw.windows(descendant_pids(os.getpid())))
                finally:
                    xw.close()
            except Exception as e:
                self.log("debug", f"Can't track the GUI window position => {e}")
            self.host.show_custom_ui(pid, True)
            self.ui_shown.add(h)
            if known is not None:
                threading.Thread(target=self.track_ui_window, args=(h, known, a.get("pos")),
                                 name=f"ui_pos_{h}", daemon=True).start()
        else:
            self.update_ui_pos(h)
            self.host.show_custom_ui(pid, False)
            self.ui_shown.discard(h)
        return None

    def update_ui_pos(self, h, xw=None):
        wid = self.ui_windows.get(h)
        if wid is None:
            return
        close = xw is None
        try:
            if close:
                xw = XWindows()
            pos = xw.origin(wid)
        except Exception:
            pos = None
        finally:
            if close and xw:
                xw.close()
        if pos is not None and pos != self.ui_pos.get(h):
            self.ui_pos[h] = pos
            self.emit({"evt": "ui_pos", "h": h, "x": pos[0], "y": pos[1]})

    def track_ui_window(self, h, known, pos):
        self.ui_windows.pop(h, None)
        try:
            xw = XWindows()
        except Exception as e:
            self.log("debug", f"Can't track the GUI window position => {e}")
            return
        try:
            wid = None
            deadline = time.monotonic() + 10
            while wid is None and h in self.ui_shown and time.monotonic() < deadline:
                time.sleep(0.1)
                new = [w for w in xw.windows(descendant_pids(os.getpid())) if w not in known]
                if new:
                    wid = new[0]
            if wid is None:
                return
            self.ui_windows[h] = wid
            if pos:
                xw.move(wid, int(pos[0]), int(pos[1]))
            self.ui_pos[h] = None
            while h in self.ui_shown and not self.quit:
                self.update_ui_pos(h, xw)
                if xw.origin(wid) is None:
                    break
                time.sleep(1.0)
        except Exception as e:
            self.log("debug", f"GUI window tracking stopped => {e}")
        finally:
            xw.close()

    def cmd_quit(self, a):
        self.quit = True
        return None

    # ---------------------------------------------------------------------------
    # Main loop
    # ---------------------------------------------------------------------------

    def handle_line(self, line):
        line = line.strip()
        if not line:
            return
        req_id = None
        try:
            req = json.loads(line)
            req_id = req.get("id")
            func = getattr(self, "cmd_" + str(req.get("cmd")), None)
            if func is None:
                raise RuntimeError(f"unknown command '{req.get('cmd')}'")
            res = func(req)
            if req_id is not None:
                self.emit({"id": req_id, "ok": True, "res": res})
        except Exception as e:
            if req_id is not None:
                self.emit({"id": req_id, "ok": False, "err": str(e)})
            else:
                self.log("error", f"{e}\n{traceback.format_exc()}")

    def flush_params(self):
        with self.pending_lock:
            if not self.pending:
                return
            pending = self.pending
            self.pending = {}
        now = time.monotonic()
        by_handle = {}
        for (h, idx), val in pending.items():
            stale = self.stale.get((h, idx))
            if stale and now - stale[1] < 0.5 and abs(stale[0] - val) < 1e-6:
                continue
            echo = self.echo.get((h, idx))
            if echo:
                if now - echo[1] < 0.5 and abs(echo[0] - val) < 1e-6:
                    continue
                del self.echo[(h, idx)]
            by_handle.setdefault(h, {})[str(idx)] = val
        for h, values in by_handle.items():
            self.emit({"evt": "params", "h": h, "v": values})
        if len(self.echo) > 4096:
            self.echo = {k: v for k, v in self.echo.items() if now - v[1] < 0.5}
        if len(self.stale) > 4096:
            self.stale = {k: v for k, v in self.stale.items() if now - v[1] < 0.5}

    def idle_interval(self):
        if self.ui_shown or time.monotonic() - self.last_cmd < 1.0:
            return IDLE_FAST
        return IDLE_SLOW

    def run(self):
        signal.signal(signal.SIGTERM, lambda s, f: setattr(self, "quit", True))
        signal.signal(signal.SIGINT, lambda s, f: setattr(self, "quit", True))
        try:
            self.load_carla()
            self.init_engine()
        except Exception as e:
            self.emit({"evt": "fatal", "msg": str(e)})
            return 1

        buf = b""
        while not self.quit:
            try:
                r, _, _ = select.select([0], [], [], self.idle_interval())
            except InterruptedError:
                continue
            if r:
                data = os.read(0, 1 << 16)
                if not data:
                    break
                buf += data
                self.last_cmd = time.monotonic()
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    self.handle_line(line.decode("utf-8", errors="replace"))
            try:
                self.host.engine_idle()
            except Exception:
                pass
            self.flush_params()

        self.shutdown()
        return 0

    def shutdown(self):
        watchdog = threading.Timer(5.0, lambda: os._exit(0))
        watchdog.daemon = True
        watchdog.start()
        try:
            self.host.set_engine_about_to_close()
            self.host.remove_all_plugins()
            self.host.engine_close()
        except Exception:
            pass
        watchdog.cancel()


def main():
    parser = argparse.ArgumentParser(description="Headless Carla host for Zynthian")
    parser.add_argument("--name", default="zynthian-carla", help="JACK client name of the engine")
    parser.add_argument("--max-params", type=int, default=200, help="Maximum number of parameters per plugin")
    args = parser.parse_args()
    return CarlaHostProcess(args).run()


if __name__ == "__main__":
    sys.exit(main())