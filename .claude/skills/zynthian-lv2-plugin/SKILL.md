---
name: zynthian-lv2-plugin
description: Build LV2 plugins for zynthian with DPF (DSP + native X11 Cairo GUI) and a zynthian UI widget, or create a zynthian UI widget for an LV2 plugin that already exists. Use when the user wants to create, design or iterate on an LV2 plugin, a zynthian widget (zyngui:widget), its native GUI or its help page, including building, installing and testing it on a zynthian.
---

# Zynthian LV2 plugin & widget development

Two kinds of project, same method:

| Case | What gets built | Generator |
|---|---|---|
| **A. New plugin** | DPF project: DSP + native X11 GUI (Cairo) + zynthian widget in the same LV2 bundle | `scripts/new_plugin.py` |
| **B. Widget for an existing plugin** | LV2 extension bundle with a zynthian widget (and help page) for a plugin installed on the zynthian | `scripts/new_widget.py` |

What the plugin or widget does is defined **in the chat**. Your job is to drive that conversation productively:
small concrete decisions, written down in `SPEC.md`, then working code that is built and tested on a zynthian at
every step. Never write large amounts of code before the user has agreed on the part of the spec it implements.

Read the references when you need them (don't load them all upfront):
- `references/zynthian-widget.md`: widget API, data flow (monitors = LV2 output ports), zyngui:widget bundles, help pages, hot reload.
- `references/dpf.md`: DPF project layout, parameters → LV2 ports → zynthian controllers, Cairo UI, build.
- `references/testing.md`: build/install/test on the device, checks, screenshots, the zynthian-operator skill.

Paths below: `$SKILL` = this skill's directory (`~/Zynthian/zynthian-ui/.claude/skills/zynthian-lv2-plugin`,
also linked as `~/.claude/skills/zynthian-lv2-plugin`).

## 1. Frame the project (first answer)

**Model check first**: this work (real-time DSP in C++, DPF, Tk widgets, LV2 metadata) needs a strong model. If
you are running on a Haiku model, say so at the very beginning of your first answer and recommend switching to
Sonnet or Opus (`/model`) before going on; continue only if the user insists. On Sonnet or Opus, say nothing.

Find out which case it is (A or B) and the one-sentence goal. Then propose a plan: the spec topics below, in order,
and say you'll fill `SPEC.md` as decisions are made. Ask **one topic at a time**, offering concrete defaults the
user can accept with a word ("Stereo in/out, 3 controls on one page: OK?"). Don't ask what the code or the
references already answer.

## 2. Spec topics

**Case A (new plugin)**, in this order:
1. **Identity**:
   - **Name: ask the user for it explicitly and wait.** Don't propose one, not even as a default or a
     placeholder: the name is the user's decision and makes them think about what the plugin is. The symbol
     (`[a-z0-9_]`, bundle/binary name) is derived from it.
   - **Maker**: run `scripts/detect_maker.sh` (GitHub account name via `gh`, else the system user's full name,
     else the login) and show it for confirmation.
   - URI (default `https://zynthian.org/plugins/<symbol>`), license (default GPL-3.0-or-later), LV2 category
     (decides the zynthian engine-list category, see references/dpf.md).
2. **I/O**: audio inputs/outputs (mono/stereo), MIDI in/out, synth or effect.
3. **Controls** (LV2 input ports): symbol, name, range, default, unit, type (float, integer, toggle, enum,
   logarithmic), designation, and **pages**: zynthian shows controls 4 per page, grouped by port group. Design the
   pages for the 4 knobs (soft rules 1-3): most used controls on the first page. **Audio effects get a bypass
   control** (see Rules): propose the group it goes in (with mix / dry-wet / level / volume) and count it in that
   page's 4.
4. **Outputs for visualization** (LV2 output control ports): the only data the zynthian widget gets, as floats,
   polled ~30 times/s. Arrays (spectrum, waveform) need one output port per value: keep them small (≤ 64).
   Propose only data **specific to this plugin** (grain positions, LFO phase, gain reduction, detected pitch...).
   **No audio level meters by default**: zynthian already shows input/output levels in the mixer. Add them only if
   the user asks explicitly. A plugin may have no outputs at all: the widget can then show its controls.
5. **DSP**: the algorithm, in words first; then formulas/pseudocode for the tricky parts. RT-safety rules apply.
6. **State & presets** (only if needed): non-parameter state (files, tables), factory presets.
7. **Zynthian widget**: what it shows (from 4.), full or half height (soft rule 4), layout, whether it reacts to
   knobs/switches itself, colours from the zynthian theme. Pages with envelope/filter designations show zynthian's
   built-in widget instead of this one.
8. **Native X11 GUI** (Cairo): layout, size, controls, meters. It's shown on the VNC display; can be simpler than
   or richer than the widget, decide with the user.
9. **Help page**: what the user needs to know, written as a plain HTML fragment.

**Case B (widget for an existing plugin)**:
1. Plugin URI (find it with `scripts/zyn_device.sh plugins <filter>`), widget symbol, built-in (contribution to
   zynthian-ui `lv2/`) or user widget (`lv2-widgets`, default). A user widget is its own project: a git repo
   (GitHub `<owner>/<symbol>.zyngui`) published as a zynthian package in the Widgets category (step 5).
   **Bundle name: propose the target plugin's name with the `.zyngui.lv2` postfix** (`tuna.zyngui.lv2`; widget
   symbol = plugin name as `[a-z0-9_]`). Older built-in bundles use `-zyngui.lv2`: don't copy that.
2. Read the plugin's ports (`scripts/zyn_device.sh ports <URI>`): what the outputs (monitors) offer, which inputs
   the widget may control. If the data needed isn't there, say so: a widget can't get more than the plugin outputs.
3. Topics 7 and 9 above. Soft rules 1-3 can't be applied in the widget (the plugin's ports are given), but
   `check` reports them. zynthian fixes them for existing plugins with a curated TTL in
   `~/Zynthian/zynthian-data/lv2-custom/<bundle>/` (copied over the installed bundle by `update_zynthian_data.sh`):
   offer it as a separate change in zynthian-data, following the examples there.

Write each decision into `SPEC.md` as it's made (create it from the generated template). Keep it short:
it's the contract, the code follows it.

## 3. Generate the boilerplate

As soon as identity, I/O and a first list of controls/outputs are agreed (don't wait for the full spec):

```
# Case A: write spec.json (see $SKILL/templates/spec.example.json), then
python3 $SKILL/scripts/new_plugin.py spec.json --dest ~/Zynthian/<symbol>
# Case B:
python3 $SKILL/scripts/new_widget.py --uri <URI> --symbol <name> [--builtin] [--host zynthian.lan]
```

`new_plugin.py` creates a git repo with DPF as a git submodule pinned to a tested commit (never copy DPF's sources
into the plugin repo; update the pin only deliberately, after building and testing), a GitHub Actions workflow (builds the bundle for x86_64 and arm64 on every push, in the zynthian OS Debian
release; publishes a rolling `latest` prerelease and `v*` releases), a parameter table shared by DSP and GUI
(`plugins/<symbol>/ParamDefs.hpp`), a passthrough DSP, a generic Cairo GUI (a bar per control and output), a
generic widget (a bar per output, or the current page's controls when there are no outputs), help page, `SPEC.md`
a `Makefile` that also adds the widget to the bundle, and `package/` (the zynthian package, step 5). Outputs marked `"meter": true` get demo level-meter code:
only when the user asked for meters. It builds and runs as-is: build and test it once before changing anything, so later failures are yours.
After generating, **edit the code directly**; the generator is for the first skeleton only.
`new_widget.py` (user widgets) creates the workspace as a git repo with the bundle, `SPEC.md`, `ports.json`,
`README.md` and `package/`.

## 4. Iterate: build → install → test, in small steps

Order for case A: DSP and ports first (the widget and GUI depend on them), then the widget, then the native GUI,
then help. Each step ends with a test on the zynthian (`references/testing.md`):

```
$SKILL/scripts/zyn_device.sh build ~/Zynthian/<symbol>      # rsync + make on the device (aarch64)
$SKILL/scripts/zyn_device.sh install ~/Zynthian/<symbol>    # copy + reload LV2 data (1st time: + engines DB)
$SKILL/scripts/zyn_device.sh check <URI>                    # ports, UIs, widget resolution
```

Widget-only changes don't need a restart nor a reinstall: copy the files and show the widget again (hot reload).
DSP/port changes need the processor reloaded: chain options → "Reload <plugin>". See `references/testing.md`.

## 5. Publish as a zynthian package

Every plugin project and user-widget repo has a `package/` folder (generated): its entry in the zynthian package
catalog ([zynthian-packages](https://github.com/zynthian/zynthian-packages), installed from webconf), copied as is to
`Plugins/<Package>/` (plugins) or `Widgets/<Package>/` (widget bundles):

| File | Content |
|---|---|
| `info.yml` | title (= package name), `version` ("X.Y.Z", only for a release: webconf offers an update when the catalog's is newer), icon, author, license (= the plugin's; default GPL-3.0-or-later, with its text in the repo's `LICENSE`, written by the generators for GPL v3: other licenses need their own `LICENSE`), source_url, size (installed), content (install path), description (first line short, `<br/>`, blank line, extended description in simple HTML) |
| `<Package>.sh` | A few lines: it sets `PACKAGE_TYPE` (`lv2_plugin` / `lv2_widget`), `GITHUB`, `VERSION` (`"vX.Y.Z"` for a release, `""` while there is no release), `SYMBOL` + `PLUGIN_URI` (plugins) or `BUNDLE` (widgets), and calls `zynpackage_main` of the **zynthian-packages library** (`zynpackage_lib.sh`, at the root of that repo), which implements `install` / `uninstall` / `installed` / `git_version` / `git_repo`. Plugins: the CI bundle for the device arch from the release `VERSION`, or from the rolling `latest` build when empty, into `zynthian-plugins/lv2`, then `zyngine_tool.py -r ENABLE <URI>`. Widgets: the bundle from the tag `VERSION` (or the last commit when empty) into `zynthian-plugins/lv2-widgets`. Keep it plain: new behaviour goes into the library, not into each script. The script needs the zynthian-packages catalog on the machine (`$ZYNTHIAN_DIR/zynthian-packages`): test it on a zynthian, or with `ZYNTHIAN_DIR` pointing to a folder with a clone (the header of the generated script says so) |
| `Art/zui_control_widget_<symbol>.png` | Screenshot of the widget in the zynthian UI (800×480): the package image |

**When the repo is pushed to GitHub for the first time**, prepare the package and then ask the user (the operator)
to send the PR to zynthian-packages (offer to prepare it: fork, branch with `package/` copied to
`<Category>/<Package>/`, `gh pr create`; never touch `packages.json`, CI regenerates it):
1. CI green (plugins). **Releases: recommend tagging before the package PR**, and explain why: with a release
   tag the package installs that exact version and webconf shows the version and offers updates when it changes;
   without one it installs the latest build (no version, every push is an "update"). Ask for the tag
   (`vX.Y.Z` = the plugin's version in the code: spec `version`, `getVersion()`), and when the user agrees:
   `git tag vX.Y.Z && git push --tags`, wait for the CI release (plugins), then
   `python3 $SKILL/scripts/package_version.py <dir>` (checks the tag, the plugin version and the release bundles;
   sets `VERSION` in the script and `version` in `info.yml`). If the user prefers no release yet, leave the package
   as generated (latest build) and say that a tag is the recommended way; remind once more when the package is
   updated later.
2. `info.yml`: extended description (from the help page), author and license confirmed with the user; size with
   `zyn_device.sh package <dir>` (plugins: after `build`).
3. Screenshot: show the widget on the zynthian (zynthian-operator skill; adding the processor needs the user's OK),
   `zyn_device.sh shot`, look at it, then `zyn_device.sh package <dir> <png>` copies it to `Art/`.
4. Commit `package/` in the repo; write the PR URL in `SPEC.md`.

After that, **no more PRs unless files in `package/` change**: compare with the catalog
(`git -C ~/Zynthian/zynthian-packages pull`, then `diff -r package ~/Zynthian/zynthian-packages/<Category>/<Package>`)
and propose a PR only when they differ. A new release is a new tag (bump the version in the code first, CI checks that
it matches), `package_version.py` and so a package PR (the version changes). Latest-build packages need no PRs for
new builds.

## Soft rules (apply when they make sense)

Defaults that make plugins feel native on zynthian. Propose designs that follow them; when the user's idea doesn't
fit, point out the rule and the trade-off once, then follow the user's decision and note it in `SPEC.md`.
`new_plugin.py` and `zyn_device.sh check` print a warning for each deviation.

1. **Group all the controls in LV2 port groups.** Each group is a page of controls in zynthian, with its name.
   Ungrouped controls end up on generic "Params" pages.
2. **Groups of 4 controls** (one page per group, one control per knob). Bigger groups: multiples of 4 (8 = two
   pages). Avoid groups of 1 or 2: merge related controls instead (e.g. cutoff + resonance + env amount + key
   tracking). Groups of 3 are acceptable when nothing fits as a fourth.
3. **Standard LV2 designations** where they apply (spec key `designation`): `attack`, `decay`, `sustain`,
   `release` (also `delay`, `hold`, `fade`), `cutoffFrequency`, `resonance`. zynthian then shows its built-in
   **envelope** / **filter** widget on that page. So an ADSR group of exactly 4 gets an envelope graph for free.
4. **Half-height widget** when the widget is simple (a few meters, a value or two, a small graph): it uses the
   lower half of the screen and the list of pages stays visible above it (spec `"widget": {"half_height": true}`,
   `new_widget.py --half-height`). Suggest it, and ask the user when it isn't obvious.

## Rules

- **The zynthian is the user's instrument.** Ask before the first build/install on it in a session; install only
  the plugin/widget being developed; never run the zynthian-ui test suite there; don't add/remove chains or load
  snapshots unless asked. Follow the zynthian-operator skill's rules when driving the UI.
- **First copy of a plugin bundle to the device → run `regenerate_engines_db.sh`** and enable the plugin (regenerate
  adds it disabled). `zyn_device.sh install` does both, only when the plugin isn't in the engines DB yet; updates
  don't need it.
- **Audio effects (audio in → process → audio out, not synths) have a native bypass parameter** (spec
  `"designation": "bypass"`, boolean, default 0 = processing), in the most fitting group: the one with mix level,
  dry/wet, volume or similar controls. DPF exports it as the LV2 port `lv2_enabled` (`lv2:designation lv2:enabled`,
  inverted: 1 = enabled), which zynthian uses as the processor's bypass (chain view, "inline"/"bypass" labels)
  instead of its own JACK-routing bypass. `new_plugin.py` adds one if the spec lacks it (in the mix/level group,
  else the last one) and puts it in its group (DPF doesn't export groups of designated ports). The DSP crossfades to
  the dry input (template code, ~10 ms): keep it click-free.
- **DSP must be RT-safe**: no allocation, locks, I/O or logging in `run()`; precompute in `activate()` /
  `sampleRateChanged()`; smooth parameter changes that would click.
- **The plugin must work without any UI**: zynthian runs jalv headless (invalid `DISPLAY`); the native GUI only
  appears on the VNC display. Never rely on the GUI to compute anything.
- **Zero idle cost** in the widget: create Tk canvas items once, update coords/text only when a value changed, no
  threads, no polling of your own (the UI already calls `refresh_gui()` every ~32 ms while visible).
- **Symbols are API**: port symbols are used by zynthian presets, snapshots, MIDI learn and the widget. Settle them
  early; renaming later breaks saved state.
- Keep `SPEC.md`, the help page and the code consistent at each step; mention what's left open.
- Commit in the plugin repo at each working step (the user decides about pushing). Once the repo is on GitHub,
  each push builds it in CI: check the run (`gh run list`, `gh run view --log-failed`) after pushing; a red build
  is fixed before going on. Releases: tag `vX.Y.Z` (matching `version` in the code; CI checks it) only when the user agrees, but recommend it
  before the first package PR (step 5).
