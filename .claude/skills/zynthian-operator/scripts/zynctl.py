#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zynctl: drive a zynthian UI over its websocket and print the screen state as compact text.

Usage: zynctl.py [--host HOST] [--port PORT] [--full] [--settle MS] [STEP ...]

Steps run in order on one connection. After each step the client waits until the
"screen_state" feedback settles and prints what changed; the full state is printed at the end.

  state                  Print the current state (default when no steps are given)
  CUIA[:a,b,...]         Send a CUIA, e.g. ARROW_DOWN, SELECT:4, ZYNSWITCH:3,S, SCREEN_ADMIN
  pick:LABEL             Highlight the list item whose label is LABEL (exact, else unique case-insensitive substring)
  open:LABEL             pick:LABEL, then SELECT_ACTION (performs the item's action)
  wait:MS                Wait MS milliseconds, collecting state changes
  dpm[:SECONDS]          Watch the audio levels (DPM) of every chain for SECONDS (default 1)
  dpm_global[:SECONDS]   Watch the main bus levels only
  chains                 Print the chain list (id, mixer index, name, type, MIDI channel, mixer strip)
  noteon:NOTE[,VEL]      Send a MIDI note-on to the active chain (velocity default 100). Makes sound!
  noteoff:NOTE           Send the MIDI note-off
  cuias[:cat1,cat2]      Print the CUIA list (from zynthian_gui.py docstrings), filtered by category

Environment: ZYNTHIAN_HOST (default zynthian.lan), ZYNTHIAN_WS_PORT (8370),
ZYNTHIAN_UI_DIR (default ~/Zynthian/zynthian-ui, used by "cuias").
"""

import io
import os
import sys
import json
import time
import types
import argparse
import contextlib

try:
	import websocket
except ImportError:
	sys.exit("zynctl: python module 'websocket-client' is required (pip install websocket-client)")

# Views that hold the navigable list, in priority order (path inside the screen state)
LIST_PATHS = [
	("zyngui_engine",),
	("zyngui_selector",),
	("zyngui_selector_grid",),
	("zyngui_chain_control", "zyngui_selector"),
]


def parse_arg(a):
	for conv in (int, float):
		try:
			return conv(a)
		except ValueError:
			pass
	return a


def merge(dst, src):
	for k, v in src.items():
		if v is None:
			dst.pop(k, None)
		elif isinstance(v, dict) and isinstance(dst.get(k), dict):
			merge(dst[k], v)
		else:
			dst[k] = v


def get_path(state, path):
	node = state
	for k in path:
		if not isinstance(node, dict) or k not in node:
			return None
		node = node[k]
	return node


class ZynCtl:

	def __init__(self, host, port, settle_ms, full):
		self.url = f"ws://{host}:{port}"
		self.settle = settle_ms / 1000
		self.full = full
		self.state = {}
		try:
			self.ws = websocket.create_connection(self.url, timeout=5)
		except Exception as e:
			sys.exit(f"zynctl: can't connect to {self.url}: {e}")
		self.ws.send("/subscribe screen_state")
		self.collect(min_wait=0.3)

	def close(self):
		try:
			self.ws.send("/unsubscribe *")
			self.ws.close()
		except Exception:
			pass

	def collect(self, min_wait=0.0, max_wait=4.0):
		"""Receive messages until no "screen_state" message arrives for the settle period. Returns the changes."""
		changes = []
		start = time.monotonic()
		last = start
		while True:
			now = time.monotonic()
			if now - start >= max_wait:
				break
			if now - last >= self.settle and now - start >= min_wait:
				break
			self.ws.settimeout(max(0.01, min(self.settle, max_wait - (now - start))))
			try:
				msg = self.ws.recv()
			except websocket.WebSocketTimeoutException:
				continue
			except Exception as e:
				sys.exit(f"zynctl: connection lost: {e}")
			data = json.loads(msg)
			if "error" in data:
				print(f"! {data['error']}")
			ss = data.get("screen_state")
			if ss is None:
				continue
			if "screen" in ss:
				self.state = {}
			merge(self.state, ss)
			changes.append(ss)
			last = time.monotonic()
		return changes

	# ------------------------------------------------------------------
	# DPM (audio levels)
	# ------------------------------------------------------------------

	@staticmethod
	def level_db(level):
		"""Feedback level (0.0 = -72dBFS or less, 1.0 = 0dBFS, linear in dB) => dBFS text"""
		if level is None or level <= 0.0:
			return " -inf"
		return f"{(level - 1.0) * 72.0:5.1f}"

	def watch_dpm(self, stream, secs):
		"""Subscribe to a DPM stream for some seconds. Returns {key: (last levels, max levels)}"""
		self.ws.send(f"/subscribe {stream}")
		last, peak = {}, {}
		end = time.monotonic() + secs
		while time.monotonic() < end:
			self.ws.settimeout(max(0.01, end - time.monotonic()))
			try:
				data = json.loads(self.ws.recv())
			except websocket.WebSocketTimeoutException:
				continue
			except Exception as e:
				sys.exit(f"zynctl: connection lost: {e}")
			if "screen_state" in data:
				ss = data["screen_state"]
				if "screen" in ss:
					self.state = {}
				merge(self.state, ss)
			value = data.get(stream)
			if value is None:
				continue
			if stream == "dpm_global":
				value = {"main": value}
			for k, v in value.items():
				if v is None:
					last.pop(k, None)
					continue
				last[k] = v
				peak[k] = [max(a, b) for a, b in zip(peak.get(k, v), v)]
		self.ws.send(f"/unsubscribe {stream}")
		return {k: (last[k], peak.get(k, last[k])) for k in last}

	def render_dpm(self, stream, secs):
		levels = self.watch_dpm(stream, secs)
		if not levels:
			return f"! no {stream} data received (UI without DPM feedback?)"
		out = [f"{stream} over {secs}s, dBFS (A/B now | A/B peak hold max):"]
		for k in sorted(levels, key=lambda x: (x != "0" and x != "main", int(x) if x.isdigit() else -1)):
			cur, pk = levels[k]
			name = "main" if k in ("0", "main") else f"chain {k}"
			out.append(f"  {name:>8}: {self.level_db(cur[0])} {self.level_db(cur[1])} | {self.level_db(pk[2])} {self.level_db(pk[3])}")
		return "\n".join(out)

	def render_chains(self):
		self.ws.send("/subscribe chain_state")
		state = None
		end = time.monotonic() + 3
		while state is None and time.monotonic() < end:
			self.ws.settimeout(max(0.01, end - time.monotonic()))
			try:
				data = json.loads(self.ws.recv())
			except websocket.WebSocketTimeoutException:
				continue
			state = data.get("chain_state")
		self.ws.send("/unsubscribe chain_state")
		if state is None:
			return "! no chain_state received (UI without chain feedback?)"
		out = [f"chains (active: {state.get('active')}); index = MIXER chain_index; mixer = chan/bus strip:"]
		for c in state.get("chains", []):
			mixer = c.get("mixer")
			mx = f"{'bus' if mixer['bus'] else 'chan'}{mixer['strip']}" if mixer else "-"
			mark = ">" if c.get("id") == state.get("active") else " "
			title = f" \"{c['title']}\"" if c.get("title") and c["title"] != c.get("name") else ""
			out.append(f" {mark}id {c['id']:>2} | index {c['index']:>2} | {c['name']}{title} | {c['type']} | "
				f"midi {c['midi_chan'] if c['midi_chan'] is not None else '-'} | zmop {c['zmop_index'] if c['zmop_index'] is not None else '-'} | {mx}")
		return "\n".join(out)

	def cuia(self, name, args=()):
		self.ws.send(json.dumps({"cuia": name.upper(), "args": list(args)}))
		return self.collect(min_wait=self.settle)

	# ------------------------------------------------------------------
	# Text rendering
	# ------------------------------------------------------------------

	def list_node(self):
		for path in LIST_PATHS:
			node = get_path(self.state, path)
			if isinstance(node, dict) and "items" in node:
				return path, node
		return None, None

	@staticmethod
	def item_label(node, i):
		items = node.get("items") or []
		return items[i] if i is not None and 0 <= i < len(items) else None

	def render_list(self, name, node, indent="  "):
		items = node.get("items") or []
		sel = node.get("selected")
		extra = "".join(f", {k} {v}" for k, v in node.items() if k not in ("items", "selected") and not isinstance(v, dict))
		out = [f"{indent}{name}: {len(items)} items, selected {sel}{extra}"]
		lo, hi = 0, len(items)
		if not self.full and len(items) > 30:
			c = sel if isinstance(sel, int) else 0
			lo, hi = max(0, c - 12), min(len(items), c + 13)
		if lo > 0:
			out.append(f"{indent}  ... {lo} above")
		for i in range(lo, hi):
			out.append(f"{indent}{'>' if i == sel else ' '}[{i}] {items[i]}")
		if hi < len(items):
			out.append(f"{indent}  ... {len(items) - hi} below")
		return out

	def render_state(self):
		s = self.state
		out = [f"screen: {s.get('screen')} | title: {s.get('title', '')}"]

		def walk(node, name, indent):
			if "items" in node:
				out.extend(self.render_list(name, node, indent))
				for k, v in node.items():
					if isinstance(v, dict):
						walk(v, k, indent + "  ")
			else:
				out.append(f"{indent}{name}:")
				for k, v in node.items():
					if isinstance(v, dict):
						walk(v, k, indent + "  ")
					elif k not in ("items", "selected"):
						out.append(f"{indent}  {k}: {v}")

		for k, v in s.items():
			if isinstance(v, dict):
				walk(v, k, "  ")
		if len(out) == 1 and s.get("screen"):
			out.append("  (no list reported for this view: use a screenshot if needed)")
		return "\n".join(out)

	def render_changes(self, changes):
		"""One-line summary of the changes caused by a step"""
		if not changes:
			return "no change"
		if any("screen" in c for c in changes):
			return f"screen -> {self.state.get('screen')} | {self.state.get('title', '')}"
		parts = []
		flat = {}
		for c in changes:
			merge(flat, json.loads(json.dumps(c)))

		def walk(node, path):
			for k, v in node.items():
				if isinstance(v, dict):
					walk(v, path + (k,))
				elif k == "selected":
					full = get_path(self.state, path)
					label = self.item_label(full, v) if isinstance(full, dict) else None
					parts.append(f"{'/'.join(path) or 'state'} selected {v}" + (f": {label}" if label else ""))
				elif k == "items":
					parts.append(f"{'/'.join(path)} list changed ({len(v)} items)")
				elif k == "title":
					parts.append(f"title: {v}")
				else:
					parts.append(f"{'/'.join(path + (k,))}: {v}")
		walk(flat, ())
		return "; ".join(parts)

	# ------------------------------------------------------------------
	# Steps
	# ------------------------------------------------------------------

	def find_item(self, label):
		path, node = self.list_node()
		if not node:
			return None, None, "no list on this view"
		items = node.get("items") or []
		if label in items:
			return path, items.index(label), None
		low = label.lower()
		matches = [i for i, it in enumerate(items) if low in str(it).lower()]
		if len(matches) == 1:
			return path, matches[0], None
		if not matches:
			return path, None, f"no item matches '{label}'"
		return path, None, f"'{label}' is ambiguous: " + ", ".join(f"[{i}] {items[i]}" for i in matches[:8])

	def pick(self, label):
		path, index, err = self.find_item(label)
		if err:
			return False, err
		node = get_path(self.state, path)
		if node.get("selected") == index:
			return True, f"already selected [{index}] {node['items'][index]}"
		if len(path) == 1:
			# The view owns the list: highlight it directly
			changes = self.cuia("SELECT", [index])
		else:
			# Embedded list (e.g. chain_control): SELECT isn't supported, move with the arrows
			changes = []
			for _ in range(60):
				node = get_path(self.state, path)
				cur = node.get("selected") if node else None
				if cur is None or cur == index:
					break
				changes += self.cuia("ARROW_DOWN" if cur < index else "ARROW_UP")
				if get_path(self.state, path) is None:
					break
		node = get_path(self.state, path)
		if node and node.get("selected") == index:
			return True, f"selected [{index}] {node['items'][index]}"
		return False, f"couldn't select '{label}' (now: {self.render_changes(changes)})"

	def run_step(self, step):
		name, _, arg = step.partition(":")
		key = name.lower()
		if key == "state":
			return None
		if key == "wait":
			changes = self.collect(min_wait=float(arg or 500) / 1000, max_wait=float(arg or 500) / 1000 + 4)
			return f"wait {arg or 500}ms: {self.render_changes(changes)}"
		if key == "chains":
			return self.render_chains()
		if key == "noteon":
			note, _, vel = arg.partition(",")
			self.ws.send(json.dumps({"midi": "note_on", "note": int(note), "vel": int(vel or 100)}))
			return f"note on {note} vel {vel or 100}"
		if key == "noteoff":
			self.ws.send(json.dumps({"midi": "note_off", "note": int(arg)}))
			return f"note off {arg}"
		if key in ("dpm", "dpm_global"):
			stream = "dpm_state" if key == "dpm" else "dpm_global"
			return self.render_dpm(stream, float(arg or 1))
		if key == "pick":
			ok, msg = self.pick(arg)
			return msg if ok else f"! {msg}"
		if key == "open":
			ok, msg = self.pick(arg)
			if not ok:
				return f"! {msg} (not opened)"
			changes = self.cuia("SELECT_ACTION", ["S"])
			return f"{msg}; SELECT_ACTION: {self.render_changes(changes)}"
		args = [parse_arg(a) for a in arg.split(",")] if arg else []
		changes = self.cuia(name, args)
		return f"{name.upper()}{(':' + arg) if arg else ''}: {self.render_changes(changes)}"


def print_cuias(categories):
	ui_dir = os.path.expanduser(os.environ.get("ZYNTHIAN_UI_DIR", "~/Zynthian/zynthian-ui"))
	sys.path.insert(0, os.path.join(ui_dir, "zynagent"))
	sys.modules.setdefault("pyliblo3", types.ModuleType("pyliblo3"))
	try:
		with contextlib.redirect_stdout(io.StringIO()):
			import zynagent_tools
			tools = zynagent_tools.generate_zynthian_cuia_tools(categories=categories or None)
	except Exception as e:
		sys.exit(f"zynctl: can't generate the CUIA list from {ui_dir}: {e}")
	for x in tools:
		props = x["parameters"]["properties"]
		req = x["parameters"]["required"]
		args = ", ".join(
			f"{k}{'' if k in req else '?'}" + (f"={'|'.join(v['enum'])}" if v.get("enum") else "")
			for k, v in props.items())
		print(f"{x['name'].upper()}({args}): {x['description']}")


def main():
	ap = argparse.ArgumentParser(description="Drive a zynthian UI over websocket", add_help=True)
	ap.add_argument("--host", default=os.environ.get("ZYNTHIAN_HOST", "zynthian.lan"))
	ap.add_argument("--port", type=int, default=int(os.environ.get("ZYNTHIAN_WS_PORT", 8370)))
	ap.add_argument("--settle", type=int, default=250, help="ms without state changes to consider a step done")
	ap.add_argument("--full", action="store_true", help="print whole lists (default: window around the selection)")
	ap.add_argument("steps", nargs="*")
	a = ap.parse_args()

	steps = a.steps or ["state"]
	if steps[0].lower().startswith("cuias"):
		_, _, cats = steps[0].partition(":")
		print_cuias([c for c in cats.split(",") if c])
		return

	z = ZynCtl(a.host, a.port, a.settle, a.full)
	try:
		for step in steps:
			res = z.run_step(step)
			if res:
				print(res)
		print(z.render_state())
	finally:
		z.close()


if __name__ == "__main__":
	main()
