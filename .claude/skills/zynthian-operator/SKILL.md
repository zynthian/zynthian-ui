---
name: zynthian-operator
description: Operate a zynthian UI (real device, virtual zynthian container or local desktop UI) by sending CUIAs over its websocket and reading the screen state as text. Use when you need to navigate the zynthian UI, check what a view shows, or reproduce/test a UI behaviour, instead of taking screenshots.
---

# Zynthian operator

Drive the zynthian UI with `scripts/zynctl.py` (in this skill's directory). It sends CUIAs over the UI websocket
(port 8370) and reads the `screen_state` feedback, so every step returns the resulting view as text.
This is much cheaper and more reliable than screenshots: use screenshots only for views that report no list.

```
python3 ~/.claude/skills/zynthian-operator/scripts/zynctl.py [--host HOST] [--full] STEP ...
```

Steps run in order on one connection; each one prints what changed, and the full state is printed at the end:

| Step | Meaning |
|---|---|
| `state` | Print the current view (default when no steps are given) |
| `CUIA[:a,b]` | Send a CUIA: `ARROW_DOWN`, `SELECT:4`, `ZYNSWITCH:3,S`, `SCREEN_ADMIN` |
| `pick:LABEL` | Highlight the list item LABEL (exact, or unique case-insensitive substring). No action is performed |
| `open:LABEL` | `pick:LABEL` + `SELECT_ACTION`: performs the item's action |
| `wait:MS` | Wait and collect changes (slow actions: loading presets, engines) |
| `chains` | Print the chain list: id, mixer index, name, type, MIDI channel, zmop, mixer strip |
| `dpm[:S]` | Watch the audio levels of every chain for S seconds (default 1) |
| `dpm_global[:S]` | Watch the main bus levels only |
| `noteon:N[,VEL]` / `noteoff:N` | Play a MIDI note on the active chain (makes sound!) |
| `cuias[:cat,...]` | Print CUIAs from the zynthian-ui code, by category (no connection needed) |

Batch several steps in one call: `zynctl.py CHAIN_OPTIONS "pick:Add Audio-FX processor"`.
Lists longer than 30 items show a window around the selection; add `--full` for the whole list.

## Hosts

| Host | What | `--host` |
|---|---|---|
| Real device | The user's instrument | `zynthian.lan` (default, or `ZYNTHIAN_HOST`) |
| Virtual zynthian | LXC test container | `zynthian-pc.local` |
| Local desktop UI | Started from `~/Zynthian/zynthian-ui` | `localhost` |

The UI must run code with the `screen_state` websocket feedback (zynthian-ui commit 40f5a4a1 or later).

## Screen state

`state` prints the view name, the title (breadcrumb) and its lists, with the selection marked `>`:

```
screen: chain_options | title: 1#Noize Mak3r/Chain Options
  zyngui_selector: 9 items, selected 1
   [0] > PROCESSORS
  >[1] Add MIDI-FX processor
```

- Items starting with `> ` are section headers: they can't be selected.
- Composite views nest their parts: `zyngui_chain_control` has `chain_blocks` (left column, only while shown)
  and `zyngui_selector` (right). `zyngui_engine` has `categories` (left) and its engine list.
- Confirmation dialogs report `zyngui_confirm` (`text`). Other fullscreen modals (info, loading, keyboard)
  only report the screen name for now.
- Grid menus report `zyngui_selector_grid` (button titles as items, plus `columns`).
- Views without a list (mixer, launcher, sequencer, widgets, controller pages) only report the screen and
  the title: take a screenshot if you need to see them.

## Audio levels (DPM)

`dpm` and `dpm_global` read the `dpm_state` / `dpm_global` websocket feedback (zynthian-ui db2c8863 or later)
and print dBFS per chain: current A/B (left/right) and the max peak hold during the window:

```
zynctl.py noteon:60,80 dpm:1 noteoff:60
dpm_state over 1.0s, dBFS (A/B now | A/B peak hold max):
      main:  -7.9  -6.5 |  -2.9  -2.2
   chain 1:  -8.6  -7.2 |  -3.6  -2.9
```

- `-inf` is silence (-72dBFS or less). 0.0 is full scale: peaks at 0 mean clipping.
- Rows are chain **ids** (main bus = 0). Not the number before "#" in titles like "1#Noize Mak3r": that's
  the MIDI channel. Use `chains` to map ids to names, MIDI channels and mixer positions.
- To set levels use the `MIXER` CUIA (category `mixer`, `zynctl.py cuias:mixer`): its `chain_index` is the
  strip position in the mixer (display order, -1 for the main bus), **not** the chain id: take it from the
  `index` column of `chains`. Check the result with `dpm` afterwards.
- Peak hold lasts ~2 s, so a `dpm` right after a sound still shows its peak.
- Measuring needs sound: play notes with `noteon`/`noteoff` (active chain), or ask the user to play.
  Always send the `noteoff`.

## Navigation CUIAs

Generated from the zynthian-ui docstrings (`zynctl.py cuias:navigation`; add `screens` for direct view jumps,
or no filter for all the categories: transport, tempo, mixer, zs3, midi, tts, display, system, hardware):

```
ZYNPOT(index, delta): Turn an encoder. Encoder 3 is the select encoder: on list views it moves the selection. The other encoders change the controllers shown on the current view.
ZYNPOT_ABS(index, value): Set the controller of an encoder to an absolute value (0.0-1.0), if the current view supports it.
ZYNSWITCH(index, action=S|B|L|P|R): Push a switch. 0 -> Menu/Layer, 1 -> Back, 2 -> Snapshot, 3 -> Select. S/B/L = short/bold/long, P/R = press/release. Prefer the specific CUIAs.
ARROW_UP(), ARROW_DOWN(), ARROW_RIGHT(), ARROW_LEFT(): Push the arrow buttons.
BACK(): Push the BACK button.
SELECT_ACTION(t?=S|B|L|P): Push the SEL button: performs the action of the selected item, same as ZYNSWITCH 3. Use SELECT to highlight an item before.
BOLD_SELECT_ACTION(): Bold-push the SEL button: normally shows contextual options.
SELECT(index): Highlight a list item without performing its action. Indexes are the positions in the state's items.
MENU(): Show contextual menu.
Z2_ZYNPOT_TOUCH(index): Touch an encoder (Z2). While MIDI learning, it selects the controller to learn.
V5_ZYNPOT_SWITCH(index, action=S|B|L): Push an encoder's switch (V5).
```

Useful direct jumps (category `screens`): `SCREEN_MIXER`, `SCREEN_ADMIN`, `SCREEN_CHAIN_MANAGER`, `SCREEN_SNAPSHOT`,
`SCREEN_ZS3`, `MAIN_MENU`, `CHAIN_CONTROL`, `CHAIN_OPTIONS`, `BANK_PRESET`, `ADD_CHAIN`.

## How views behave

Fill this in as you learn it (keep it short).

- **mixer** (home view): ARROW_UP/DOWN change the volume of the selected strip (the title shows it as a
  toast, e.g. "Volume: -0.32dB (MDA ePiano)"). Don't use arrows here unless that's the goal.
- **chain_control**: right side is the embedded view (control pages, chain options, MIDI/audio config).
  ARROW_UP/DOWN move its list. `MENU` shows the chain blocks on the left; then ARROW_LEFT/RIGHT move through
  the blocks and open each one on the right. `BACK` hides the blocks. Without blocks, LEFT/RIGHT switch chain.
  `SELECT` isn't supported here: `pick:` moves with the arrows instead (selecting a control page is harmless).
- **engine** (processor type list, opened from "Add ... processor"): ARROW_UP/DOWN move the engine list,
  ARROW_LEFT/RIGHT change the category. `BACK` leaves without adding anything.
- **Grid menus** (`main_menu`, `add_chain`, reported as `zyngui_selector_grid` with `columns`): buttons in
  rows of `columns`; ARROW_LEFT/RIGHT move by one, ARROW_UP/DOWN by a row. `pick:` works (SELECT is supported).
  Empty cells are reported as "" so indexes match the buttons.
- **Confirmation dialog** (`confirm`, reported as `zyngui_confirm` with the question `text`): `SELECT_ACTION`
  answers Yes (performs the action), `BACK` answers No. Read the text before answering; Yes needs the user's OK
  whenever the action changes the setup.
- **Lists in general**: `SELECT_ACTION` performs the item; `BOLD_SELECT_ACTION` opens its options.

## Rules

- The real device is the user's instrument. Navigating and highlighting is fine; anything that changes the
  setup (adding/removing chains or processors, loading/saving snapshots or ZS3, presets, MIDI learn, mixer
  levels, power/reboot/restart) needs the user's explicit request. Follow each CUIA's "AI Guidance".
- Prefer `pick:` before `SELECT_ACTION`, and check the printed selection before performing an action.
  `open:` refuses to act when the label is ambiguous or not found.
- Notes make sound on the user's speakers: only play them when the user asked for a level check or agreed.
  Level changes (MIXER) change the setup: only on the user's request.
- Leave the UI where you found it (usually the mixer): end with `BACK`s or `SCREEN_MIXER`.
- Never run the test suite on the device (it once overwrote /zynthian/config).
- Undocumented CUIAs are not in the list on purpose: stubs or broken ones.

## Extending

- CUIA list: it comes from the `cuia_*` docstrings in `zyngui/zynthian_gui.py` (`Category:` tag, `AI Context:`,
  `Keyword Args:`), parsed by `zynagent/zynagent_tools.py`. Document CUIAs there as you learn them.
- View state: views implement `state_key` / `get_state(what)` and send the `SS_GUI_VIEW_*` zynsignals
  (see `zynthian_gui_selector.py`). Views without it only report screen and title.
