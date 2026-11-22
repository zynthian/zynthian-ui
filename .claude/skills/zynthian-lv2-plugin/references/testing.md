# Building and testing on a zynthian

`$SKILL/scripts/zyn_device.sh` wraps the device side (host: `ZYNTHIAN_HOST`, default `zynthian.lan`, user root,
ssh key auth). Ask the user before the first build/install of a session.

| Command | Does |
|---|---|
| `plugins [filter]` | List installed LV2 plugins (URI, name) matching a filter |
| `ports <URI>` | Ports of a plugin as JSON (symbol, direction, type, range, properties, group, UIs) |
| `build <project_dir>` | rsync the project to `/zynthian/zynthian-sw/plugins/<symbol>` (keeps build dirs) and `make -j4` there |
| `install <project_dir>` | Copy `bin/<symbol>.lv2` to `/zynthian/zynthian-plugins/lv2`, touch `lv2.stamp`. First install only: `regenerate_engines_db.sh` + enable the plugin in the engines DB |
| `widget <bundle_dir>` | Copy a widget extension bundle to `/zynthian/zynthian-plugins/lv2-widgets`, touch `lv2.stamp` |
| `check <URI>` | lilv view of the plugin: ports summary, UIs, zynthian widget resolution (which file wins) |
| `shot [:0\|:1]` | Screenshot of the zynthian display (`:0`) or the VNC display (`:1`, native GUIs) → local PNG path (Read it) |
| `log [minutes]` | Errors/tracebacks and widget/jalv messages from the UI service log |

## Step tests

1. **Build**: `build` must end without errors. Warnings in your code: fix them.
2. **TTL / ports**: `check <URI>`: port symbols, ranges, groups and outputs as in `SPEC.md`; UIs list shows the
   DPF X11UI and the `zyngui:widget`; widget resolution points to the bundle's `.py`.
3. **Install**: `install`; the plugin appears in the engine list (category from the LV2 class), enabled.
4. **In the UI** (drive it with the zynthian-operator skill:
   `python3 ~/Zynthian/zynthian-ui/.claude/skills/zynthian-operator/scripts/zynctl.py ...`):
   - Adding the processor changes the user's setup: only on the user's request (or let them do it).
   - Control pages: names/order of pages and controls, ranges, enum labels (`state` shows the page list).
   - Widget: open its page, `shot` to see it; `log` for widget errors. Feed it signal if it shows levels (ask the
     user to play, or `noteon`/`noteoff` with their OK; use `dpm` to confirm audio flows).
   - Help: `HELP` CUIA on the control view, `shot`.
5. **Native GUI**: needs VNC enabled on the zynthian (webconf → Interface → VNC) and the processor (re)created
   while VNC runs; `shot :1` to see it. Or test it locally with `jalv.gtk3 <URI>` on the desktop (x86 build).
6. **After changes**:
   - widget `.py`: `widget`/`install` again (or just copy the file), then show the widget again: hot reload.
   - help/manifest only: same, `lv2.stamp` is touched by the script.
   - DSP or ports: `build` + `install`, then "Reload <plugin>" in the processor options. If ports changed
     (added/removed/renamed), presets and snapshots of that plugin may not match anymore: tell the user.

## Checks without the UI

- `zyn_device.sh ports <URI>`: what the plugin really exposes (after `install`).
- `ssh root@zynthian.lan lv2info <URI>`: full lilv view.
- jalv text mode for the DSP (careful: it creates a JACK client on the user's system; only with their OK):
  `jalv -n test <URI>` then type `monitors`, `controls`, `set <symbol> <value>`, `quit`.

## Gotchas

- **The first time a plugin bundle is copied to the device, run `regenerate_engines_db.sh`** (`install` does it):
  it adds new plugins to the engines DB (and their presets cache). Not needed when updating a plugin that's already
  in the DB. A plugin in `LV2_PATH` but not in the DB isn't
  offered in the engine list. New plugins are added **disabled**: `install` enables it (marked as user-edited, so
  later regenerations keep it enabled); otherwise enable it in webconf → Engines. Widget-only bundles (lv2-widgets)
  don't need it: they add no plugin.
- **Missing Cairo/X11 `-dev` packages → DPF silently builds no GUI** (no `<symbol>_ui.so`, no error). The CI
  workflow fails on it; locally, check `bin/<symbol>.lv2/` (or `pkg-config --modversion cairo x11`).
- `make gen` runs the plugin to write the TTL: a crash in the plugin constructor breaks the build at that step.
- DPF's own sources print warnings (`libsofd.c` `-Wformat-overflow`): expected, not yours. The first build compiles
  DGL (~20 s on a Pi 5); later builds only your files.
- lilv's Python bindings can't instantiate DPF plugins (no options/URID features): test the DSP with jalv.
- DPF prefixes audio port symbols with `lv2_` (`lv2_audio_in_1`...): only control port symbols are yours.
- Changing a control's range/default doesn't change values saved in snapshots/presets.
- The widget gets monitors only while it's shown in control mode: nothing is polled otherwise (zero idle cost).
- Device clock is UTC: timestamps in logs look off by the timezone offset.
