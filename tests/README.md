# Tests

```
./run_tests.sh                 # everything that can run here (same as CI): ~90 s with the native libraries built
./run_tests.sh -k controller   # extra arguments go to pytest
./run_tests.sh gui             # under xvfb, so tests marked `gui` run without a display
./run_tests.sh native          # only tests/native; builds the native libraries first if needed
```

Setup once: `pip install -r requirements-dev.txt` (inside the project `venv`). For the native layer:
`tests/native/build_native.sh` (needs cmake, gcc, the JACK/liblo/sndfile/samplerate/rubberband/nlohmann-json dev
packages and `jackd`).

**The hermetic layers (unit, integration, architecture) need no hardware, JACK server, display or built `.so`
files, and never start a process or touch `/zynthian`.** Tests that need any of those carry a marker and skip
with a reason when it is missing.

### Running on a Zynthian

Safe, and the same command: `./run_tests.sh` (it uses `/zynthian/venv` when the checkout has no `venv`; a plain
`python3` over ssh lacks `jack` & co). pytest-timeout is optional there: without it the `timeout` setting is
accepted and ignored.

This is enforced, not just intended. A run on a device once **overwrote `/zynthian/config/zynthian_envars.sh`**,
`wiring-profiles/v5` and `jalv/plugins.json` with the bootstrap's stubs: root's shell exported
`ZYNTHIAN_CONFIG_DIR=/zynthian/config` and the bootstrap only *defaulted* the directories. Now:

* `tests/bootstrap.py` drops **every** inherited `ZYNTHIAN_*` variable (kept: the suite's own `ZYNTHIAN_TEST_*`
  switches; the dropped ones are in `bootstrap.INHERITED_ZYNTHIAN_ENV`) and pins all the directories, `SYS_DIR`,
  `SW_DIR` and `HELP_DIR` included, to the sandbox. The suite behaves the same on a device, a desktop with
  `zynthian_envars.sh` sourced, and CI.
* `tests/write_guard.py` (a Python audit hook) refuses, *before* anything is touched, every write, delete, rename,
  mkdir, chmod... under `/zynthian`, `/boot`, `/etc`, `/usr`, `/opt`, `/lib`, `/var/lib` and the inherited
  `ZYNTHIAN_*_DIR` paths, unless the target is in a more specific allowed root: the sandbox, the temp dir or this
  repository (on a device it lives in `/zynthian/zynthian-ui`). It also covers the hard-coded `/zynthian/...` paths
  of the production code, which no environment variable redirects. The refused operation raises `WriteGuardError`
  and the test **fails** even when production code swallows the exception; violations outside a test fail the
  session and are listed in a "write guard" summary section.
* Not covered: writes from native code (the C/C++ libraries in `tests/native`, which write only where the test
  tells them) and from child processes that don't import `tests.bootstrap`.
* `tests/integration/test_harness_isolation.py` checks all of it, including a fresh interpreter started with a
  fake device environment whose config files must stay byte-identical.

Current state: **786 passed, 31 xfailed** (817 tests) in ~95 s on this machine. Every xfail is
`strict` and documents a known defect (see "Defects found", below); fixing one turns its test red until the marker
is removed. Python line coverage of `zyngine`, `zynconf`, `zynautoconnect` and `zynlibs`: 39 % (C code is covered by
the native tests, not measured).

## Why the harness is the biggest part

Nothing in zynthian-ui can be imported without side effects:

* `zyngine/__init__` star-imports every engine → `zynautoconnect` → `zyngui` → `zynthian_gui_config`,
  which reads ~57 environment variables and config files at import time.
* Importing loads the real `libzyn*.so` files through ctypes; early in development this started a real
  `jackd` and grabbed USB MIDI hardware.

So `tests/bootstrap.py`, `tests/conftest.py` and `tests/fakes/` do most of the work. The test suite changes **no
production code**; the problems below are worked around and documented, not fixed.

## Layout

Directories classify by *scope*, markers by *environment need* (`unit`, `integration`, `gui`, `jack`, `native`,
`hardware`; see `pyproject.toml` and `pytest_collection_modifyitems` in `tests/conftest.py`).

| Directory | What | Needs | Tests |
|---|---|---|---:|
| `tests/unit/` | One module in isolation: controller, MIDI filter, signal manager, zynconf, the fakes themselves | nothing | 146 |
| `tests/integration/` | The real state manager / chain manager / legacy snapshot converter / ctrldev drivers on the fakes; import smoke tests; isolation of the harness itself | nothing | 335 |
| `tests/architecture/` | Static rules: core must not import `zyngui`; dual-use library/CLI scripts stay runnable | nothing | 12 |
| `tests/native/` | The **real** compiled libraries on a private `jackd -d dummy` | built libraries + `jackd` | 263 |
| `tests/gui/` | Tk plumbing | a display (`xvfb-run`) | 2 |
| `tests/hardware/` | Real Zynthian box (empty) | `ZYNTHIAN_TEST_HARDWARE=1` | 0 |

`tests/jacktest.py` holds the JACK helpers shared by the native tests (`JackTestServer`, `FreewheelRunner`,
`MidiSource`, `Recorder`, `TestClient`).

## What is tested

### Unit (146)
| File | Tests | Covers |
|---|---:|---|
| `test_controller.py` | 57 | Value ranges, labels, `set_value`, CC/OSC mapping (incl. a characterization of the single-label range collapse) |
| `test_midi_filter.py` | 48 | `MidiFilterRule` parsing and the exact `zyncore` calls each rule produces |
| `test_signal_manager.py` | 19 | Register, send, queue |
| `test_fake_zyncore.py` | 12 | The fakes themselves (recording, `restype` defaults, reset, router constants vs `zynmidirouter.h`) |
| `test_zynconf.py` | 10 | Envars files: `save_config` (in place, new vars before "Directory Paths", escaping), `load_plain_envars`, round trip, `update_midi_profile`, MIDI profile path, external storage |

### Integration (335)
| File | Tests | Covers |
|---|---:|---|
| `test_imports.py` | 182 | Every core module imports; 14 import-first in a fresh interpreter (2 circular-import xfails); harness hermeticity |
| `test_state_manager.py` | 14 | Construction, chains, signals, `get_state` vs schema, snapshot round trip, slow-update callbacks |
| `test_chain_manager.py` | 19 | Chain order, `move_chain` (main stays last, signal), navigation limits, MIDI channels (free / by channel / set), MIDI and audio howl-round detection |
| `test_legacy_snapshot.py` | 25 | Each schema step on small synthetic snapshots: future schema refused, fractional versions, V0 layers → chains (+ note range), V2 CC pass-through, V4 mixer strips → processors / MIDI learn, V5 MIDI-learn key format and the gain → fader-position law |
| `test_legacy_snapshot_corpus.py` | 15 | Every real snapshot found converts (the public zynthian-data examples; add your own with `ZYNTHIAN_TEST_SNAPSHOT_DIRS`) |
| `test_harness_isolation.py` | 19 | The suite is safe on a real Zynthian: directories pinned to the sandbox, inherited `ZYNTHIAN_*` ignored (fresh interpreter with a fake device environment), every kind of write to a protected location refused (see "Running on a Zynthian") |
| `test_ctrldev_drivers.py` | 61 | **Every controller driver** (31): discovered by the manager, declares its devices, and survives its whole life (init, ~1300 MIDI messages incl. SysEx, refresh, state save/restore, light off, end) without raising, sending feedback only to its own output, leaving no signal handler or foreground thread behind |

### Architecture (12)
`test_layering.py` ratchet (16 core files import `zyngui`; new ones fail, stale entries fail), no GUI toolkit in core,
`zynconf` is a leaf. `test_cli_scripts.py`: dual-use scripts (`zynthian_lv2.py`) keep a Python shebang as first line,
the exec bit on disk and as `100755` in git, and a `__main__` guard (never executed).

### Native (263, `tests/native/`)
The hermetic layer can only check *which calls* Python makes; these tests run the **real libraries** and check
what they do with real MIDI / audio through JACK.

| File | Tests | Library | Covers |
|---|---:|---|---|
| `test_zynmidirouter.py` | 32 | `libzyncore.so` (zyncoder TOUCH_ONLY) | Router ports, channel routing, active-chain mode, note-offs after chain change, routes, note range / transpose, drop flags, filters, the production `MidiFilterRule` parser on the real router, UI capture, direct send; fake constants = real |
| `zynseq/test_ext_clock.py` | 16 | `libzynseq.so` | External MIDI clock PLL: tempo, phase error, jitter, lost/delayed pulses, xruns, MIDI START |
| `zynseq/test_pattern.py` | 38 | `libzynseq.so` | Pattern editing, CC / program change, undo/redo, state round trip |
| `zynseq/test_sequence.py` | 22 | `libzynseq.so` | Tracks, overlap/force, channels, modes, repeat; **playback** checked frame by frame on the output port; transport; stop modes; start at sync point |
| `zynseq/test_legacy_sequences.py` | 6 | `libzynseq.so` | Snapshot V3→V4: RIFF sequencer data of the public example snapshots converted by the real `convertToJson`, every pattern block kept, result accepted by `setState` |
| `zynseq/test_fake_parity.py` | 3 | `libzynseq.so` | The fake's defaults (`getPPQN` 1920, tempo, bpb) equal the real library's |
| `zynsmf/test_smf.py` | 37 | `libzynsmf.so` | SMF parsing, event cursor, tempo/duration, editing, save/reload, mute, transpose |
| `zynsmf/test_player.py` | 12 | `libzynsmf.so` | Player and recorder: ports, play states vs transport, loop, end of song, recording timing |
| `zynaudioplayer/test_player.py` | 28 | `libzynaudioplayer.so` | Players, codecs, file info, play states, levels / gain / track routing, position, crop, loop, speed, notifications, save (real time) |
| `zynmixer/test_channel_mixer.py` | 59 | `libzynmixer.so` | Strips and ports, fader law (dB ↔ position, unity at 0.75, headroom), gain, mute, balance, phase, mono, M/S, reset, summing, click-free level ramps, solo / PFL trunks, toggles, constant-power AB crossfader, pre/post-fader effect sends, peak meters, meter config |
| `zynmixer/test_mixbus.py` | 8 | `libzynmixer_mixbus.so` | Main and aux buses, normalisation to main, fader order, PFL trunk level |
| `zynmixer/test_exit.py` | 2 | `libzynmixer.so` | A process using the mixer exits cleanly (a child process; see defect 31) |

How it works:
* **Build:** `tests/native/build_native.sh [path/to/zyncoder]` builds out of tree into `tests/native/build/`
  (git-ignored): `libzyncore.so` by calling `build_zyncore.sh` (TOUCH_ONLY layout: real router, no wiringPi / I2C),
  and the zynlibs (Release, with `-Wno-unused-result` because their `-Werror` fails on hardened compilers). Source
  trees and their own `build/` are untouched. `ONLY="zynseq zynsmf"` builds some; `ZYNTHIAN_TEST_<NAME>_LIB` overrides
  a library path. A test whose library is missing skips.
* **JACK:** one private `jackd --no-realtime -d dummy` per session (unique name). It is *not* stopped at the end of
  the session: the libraries close their clients from C exit handlers, which crash if the server is gone. It dies
  with the pytest process instead (`PR_SET_PDEATHSIG`), so none is ever left behind. MIDI and mixer tests run in
  **freewheel** (deterministic, frame-exact, milliseconds); zynaudioplayer runs in real time (its file thread cannot
  keep up with freewheel).
* **Loading:** `ctypes.CDLL(path)` directly (bypassing the `LoadLibrary` patch of the other layers), once per
  session per library (global state); fixtures reset what they need. Every ctypes signature is declared in the
  folder's `conftest.py`. The mixer opens its JACK client from a library constructor at load time.
* **Corpus:** the public example snapshots come from the zynthian-data repo: `../zynthian-data` or
  `ZYNTHIAN_TEST_DATA_REPO` (CI does a sparse checkout of just `snapshots/`).
* **Mutation-validated:** deliberate bugs in scratch copies of the C/C++ sources (5 router, 4 zynseq) and of Python
  (3 core behaviours, 5 CLI-script properties) were each caught by the test aimed at them.

## How the hermetic layer works

`tests/bootstrap.py` runs before any production import: it creates a throw-away sandbox (`ZYNTHIAN_*_DIR`, minimal
config), sets `JACK_NO_START_SERVER=1`, stubs third-party modules that are *missing*, installs `FakeZyncore` as
`zyncoder.zyncore` (an empty `zyncoder` package is provided when the `zyncoder` symlink dangles, as in a clean
clone), and patches `ctypes.cdll.LoadLibrary` so every `libzyn*.so` is a recording fake.

* `tests/fakes/zyncore.py` – any attribute is a recording callable (default `0`, or `b""`/`0.0` following the
  `restype` the wrapper set): `zyncore.calls_to("set_midi_filter_event_ignore") == [(0xB, 3, 5)]`,
  `zyncore.set_return(...)`. Router constants mirror `zynmidirouter.h` and are checked against the real library.
* `tests/fakes/native.py` – the other libraries; defaults (zynseq PPQN 1920, tempo 120, ...) are checked against the
  real libraries by `test_fake_parity.py`.
* `tests/integration/conftest.py` – `state_manager` (the real one), `fake_autoconnect`, `fake_subprocess`.
* The ctrldev tests replace `multiprocessing` process starts (a driver forks a JACK step-sync process) and refuse
  any other process start.

## Writing tests

* Prefer the smallest layer. Characterization tests are fine for legacy behaviour; say so in the docstring.
* Known defect: `@pytest.mark.xfail(strict=True, raises=..., reason=...)` (pin the exception when you can, so a
  *different* failure is not mistaken for the known one). The ctrldev contract keeps its list in `KNOWN_BROKEN`.
* `test_layering.py` is a ratchet: remove entries from `KNOWN_CORE_TO_UI_IMPORTS` as you fix them, never add.
* New controller driver: nothing to do, `test_ctrldev_drivers.py` picks it up.
* New dual-use script: add it to `CLI_SCRIPTS` in `test_cli_scripts.py`.

## Defects found (each has a strict xfail unless stated)

Structural (refactoring targets):
1. Core imports UI config (`zyngui.zynthian_gui_config`, ~57 envars read at import); tracked by `test_layering.py`.
2. `zyngine/__init__.py` star-imports every engine.
3. Circular import: `zynthian_chain_manager` / `zynthian_legacy_snapshot` cannot be imported first.
4. `zynautoconnect` is module-level global state needing a live JACK client.
5. The state manager shells out (~28 call sites; `powersave_control.sh` during construction).
6. Constants computed at import from the C library (`NUM_MIDI_DEVS_IN`, `ZMIP_*_INDEX`).
7. Absolute paths (`/zynthian/zynthian-ui/zynlibs/zynmixer/build/*.so`, `/zynthian/...`).
8. `zynthian_headless.py` imports `autoconnect` (should be `zynautoconnect`). Not tested.
9. Runtime packages missing from `requirements.txt` (OS-provided on a Zynthian). Not tested.
10. Python 3.12 `SyntaxWarning: invalid escape sequence` in several modules (hidden in `pyproject.toml`).

Python:

11. A controller with a single label collapses its range to 127..127 (characterization).
12. ~~`remove_slow_update_callback()`: the loop variable shadows the parameter; nothing is ever removed, re-adding
    duplicates, the duopiano keep-alive keeps running after `end()`.~~ **Fixed** in 7ed6003b; the tests now guard it.
13. `will_midi_howl()` / `will_audio_howl()`: one visited list across branches, so converging paths (no loop) are
    reported as a howl-round and the connection is refused.
14. Legacy snapshots V0: crash without `note_range` (oldest files have `transpose`), and on MOD-UI layers with
    `midi_chan: null` (`zynthian_legacy_snapshot.py:432/452`); 15 such files in a local corpus fail to convert.
15. `convert_state()` leaves `schema_version` unchanged (characterization; harmless for the state manager).
16. Controller drivers (11, `KNOWN_BROKEN` in `test_ctrldev_drivers.py`): launchkey_mini_mk4_37 cannot load
    (`SS_ZCTRL_SET_VALUE` does not exist); riband and launchkey_mk4_37 override `update_seq_state()` with an
    incompatible signature (every refresh raises); launchkey_mini_mk3 calls the removed `zynseq.select_bank()`;
    fostex_mixtab calls `get_param()` without `midi_chan`; launchpad_pro_mk2 leaves `vel` unbound for disabled
    sequences; apc_40_mk2 crashes on a pad over a column without chain; mackiecontrol (pitch bend above channel 8)
    and nanokontrol2 (foreign SysEx) crash on unexpected input; both APC Key25 SooperLooper drivers leave
    self-rescheduling non-daemon `Timer`s running after `end()` (which also blocks process exit).
17. `zynseq.py` appears to call `addPattern` with 6 arguments where the library takes 7 (not verified at runtime).

zyncoder / zynlibs (C/C++):

18. `zmip_send_midi_event()` on a normal device input dereferences NULL and segfaults (no test: in-process crash).
19. zynsmf player emits no MIDI at all (`g_dPosition - nNow`: ticks minus absolute frames → offset out of range).
20. zynsmf tempo lookup returns the next tempo change, so `getTempo()`/`getDuration()` are wrong for non-120 BPM files.
21. zynsmf `load()` returns true for garbage.
22. zynsmf `addTempo()` does not update the tempo map.
23. zynsmf recorder: `case MIDI_NOTE_OFF` falls through into `MIDI_NOTE_ON`; spurious note-offs at stop.
24. zynseq `setStepsPerBeat` never rescales events (shadowed `fScale`).
25. `zynseq.h` declares `load`/`save` that the library does not export. Not tested.
26. zynseq `addNote` accepts notes longer than the pattern (check commented out; characterization).
27. zynaudioplayer: after seeking or setting the crop start while stopped, playback starts at the beginning of the
    file (characterization; intent unclear).
28. zynaudioplayer cannot be loaded when built without optimisation (C99 `inline get_player`); the build uses Release.
29. zynmixer: a new strip starts at 0.75 gain (-2.5 dB): `addStrip()` stores a fader position where a gain is expected.
30. zynmixer: `toggleSolo()` / `togglePFL()` read `mute` instead of `solo` / `pfl`.
31. zynmixer: after any solo, `end()` (atexit) `free()`s JACK port buffers → the process crashes on exit. Proven in a
    child process (`test_exit.py`); the session fixture neutralises it so the suite itself exits cleanly.

## Roadmap

* Native: router pedals / MIDI learn / tuning / master channel; zynseq phrases, scenes, follow actions.
* Engines (most need their external process): base `zynthian_engine` helpers, processor and chain objects.
* Phase 2: config object injection to remove the `zyngui` imports from core; the layering ratchet and the two
  circular-import xfails show when it works.
