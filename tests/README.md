# Tests

```
./run_tests.sh                 # hermetic suite, same as CI (≈12 s)
./run_tests.sh -k controller   # extra arguments go to pytest
./run_tests.sh gui             # under xvfb, so tests marked `gui` run without a display
./run_tests.sh native          # real zyncore router on a dummy jackd (builds the lib if needed), then legacy zynseq tests
```

Setup once: `pip install -r requirements-dev.txt` (inside the project `venv`).

**The default run needs no hardware, no JACK server, no display, no built `.so` files, and never
starts a process or touches `/zynthian`.** If a test needs one of those it must carry a marker.

Current state: 367 passed (335 hermetic + 32 native), 1 skipped (`moderngl_window` not installed), 2 xfailed
(strict, circular import). The 32 `tests/native` tests run only when the real library is built and `jackd` is
installed (otherwise they skip with a reason).

## Why the harness is the biggest part

Nothing in zynthian-ui can be imported without side effects:

* `zyngine/__init__` star-imports every engine → `zynautoconnect` → `zyngui` → `zynthian_gui_config`,
  which reads ~57 environment variables and config files at import time.
* Importing loads the real `libzyn*.so` files through ctypes. Early in development this started a real
  `jackd` and grabbed USB MIDI hardware.

So `tests/bootstrap.py`, `tests/conftest.py` and `tests/fakes/` do most of the work. Phase 0 changes **no
production code**; the blockers below are worked around, not fixed.

## Layout and categories

Directories classify by *scope*, markers classify by *environment need*.

| Directory | What | Needs | Tests |
|---|---|---|---:|
| `tests/unit/` | One module in isolation (controller, MIDI filter, signal manager, the fakes themselves) | nothing | 136 |
| `tests/integration/` | Real state manager + chain manager wired together, native layer faked; import smoke tests | nothing | 193 |
| `tests/architecture/` | Static (`ast`) layering rules: core must not import `zyngui`. Imports nothing, so it cannot be affected by side effects | nothing | 7 |
| `tests/native/` | The **real** `libzyncore.so` (ZynMidiRouter) on a private `jackd -d dummy` | cmake + gcc + libjack-dev + `jackd` | 32 |
| `tests/gui/` | Tk tests | a display (`xvfb-run`) | 2 |
| `tests/hardware/` | Real Zynthian box (empty for now) | `ZYNTHIAN_TEST_HARDWARE=1` | 0 |

Markers (see `pyproject.toml`): `unit`, `integration`, `gui`, `jack`, `native`, `hardware`.
Tests carrying `gui`/`jack`/`native`/`hardware` are skipped, with a reason, unless their environment
is present (`pytest_collection_modifyitems` in `tests/conftest.py`). That keeps the default run, and CI,
hermetic. No test uses `jack`, `native` or `hardware` yet.

## What is tested

### Unit (136)
| File | Tests | Covers |
|---|---:|---|
| `test_controller.py` | 57 | Value ranges, labels, `set_value`, CC/OSC mapping. Includes a characterization test: a controller with a single label collapses its range to 127..127, so `set_value()` never changes anything (`test_single_label_range_collapses_to_value_max`, may be a bug). |
| `test_midi_filter.py` | 48 | `MidiFilterRule` string parsing and the exact `zyncore` calls each rule produces. |
| `test_signal_manager.py` | 19 | Register, send and queue behaviour. |
| `test_fake_zyncore.py` | 12 | The fake itself (recording, `restype` defaults, `reset_fake`, router constants vs `zynmidirouter.h`), so a broken fake cannot give false passes. |

### Integration (193)
* `test_imports.py` (182):
  * every core module imports in-process (165; a missing third-party module gives a skip);
  * 14 modules imported *first* in a fresh interpreter, which exposes the circular import. Two cases are
    `xfail(strict)` (`zynthian_chain_manager`, `zynthian_legacy_snapshot`);
  * 3 harness hermeticity checks (JACK autostart blocked, native libs are fakes, state manager uses the
    fake zyncore).
* `test_state_manager.py` (11): construction, add/remove chain, chain-added signal, active chain, chain id
  uniqueness, `get_state` vs the schema (`engine_config` optional), snapshot save/load round-trip, and that
  no real process was started.

### Architecture (7)
`test_layering.py` is a ratchet: 16 core files import `zyngui` today (`KNOWN_CORE_TO_UI_IMPORTS`). A new
violation fails; a stale entry also fails. Also: core must not import GUI toolkits (4 checks) and
`zynconf` must be a leaf package.

### Native: the real ZynMidiRouter (32, `tests/native/`)
The hermetic layer fakes `lib_zyncore`, so it can only check *which calls* Python makes. These tests run the
**real compiled library** and check what the router actually does with MIDI.

* **Build:** `tests/native/build_zyncore.sh [path/to/zyncoder]` configures zyncoder with
  `ZYNTHIAN_WIRING_LAYOUT=TOUCH_ONLY` (the repo's own touch-only layout: real `zynmidirouter.c` + `zynmaster.c`,
  `zyncontrol_none.c`, no wiringPi / I2C / rotaries / switches), out of tree into `tests/native/build/`
  (git-ignored). The zyncoder checkout and its own `build/` are not touched. Override the library with
  `ZYNTHIAN_TEST_ZYNCORE_LIB=/path/libzyncore.so`.
* **JACK:** a private `jackd --no-realtime -d dummy` (unique server name, `JACK_DEFAULT_SERVER` restored at
  the end) started by the tests, using the helpers of `zynlibs/zynseq/tests/jacktest.py`
  (`JackTestServer`, `FreewheelRunner`, `MidiSource`, `Recorder`). Process cycles run in freewheel, so a test
  takes milliseconds and is deterministic. No audio hardware, no real-time privileges.
* **Loading:** `ctypes.CDLL(path)` directly, which bypasses the `LoadLibrary` patch used by the other tests, so
  both worlds coexist in one pytest run. `init_zyncore()` / `end_zyncore()` run around every test, so each
  test starts from a fresh router.
* **Rig** (`tests/native/conftest.py`, fixture `router`): `router.listen("ch0", ...)` records router outputs;
  `router.send(bytes, ..., via="dev0_in")` injects MIDI and returns what each listened output got;
  `router.ui_events()` drains the queue captured for the UI. `listen()` does a handshake because the router
  only learns about JACK connections through an asynchronous callback and skips outputs it thinks are
  unconnected (see "gotchas" below).
* **Covers:** the JACK port set; channel routing (per-chain MIDI channel, active-chain mode with channel
  translation, note-offs released on the original chain after an active-chain change); input => chain
  routes; note range and transpose (octave, semitone, global; note-off uses its note-on's transpose); drop
  flags (CC with per-CC exceptions, PC, notes, SysEx); event filter ignore / map; the **production**
  `MidiFilterRule` text parser driving the real router; UI capture and UI-reserved channels; direct send
  through the internal input. It also checks that the constants hard-coded in `FakeZyncore` equal the real
  library's (`test_fake_zyncore_constants_match_the_real_library`).
* **Validated by mutation:** 5 deliberate bugs patched into a scratch copy of `zynmidirouter.c` (note-off
  transpose, note-range upper bound, orphan note-off release, filter ignore, CC drop logic); each was caught
  by the test aimed at it.
* **Gotchas found while building it:**
  * The port-connect callback is asynchronous, and it was not delivered reliably if freewheel mode was
    switched on straight after connecting (observed: outputs never became "connected"). `listen()` therefore
    waits in real time for a canary event on `mod_out`, which is connected last.
  * `FLAG_ZMOP_NOTERANGE`, `CHAN_TRANSFILTER` and `DIRECTOUT` are on by default, chains start with MIDI
    channel -1 (nothing flows until a test assigns one), and device inputs start in active-chain mode with
    `active_chain = -1`.
  * `zmip_send_*` on a plain device input **segfaults** (see blocker 12), hence the test uses the internal input.
  * The channel in a `MidiFilterRule` text (`IGNORE CH#0 CC#7`) is passed to the library unchanged: it is
    0-based, so `CH#0` is MIDI channel 1.

### GUI (2)
A Tk root opens and processes events; a synthetic event reaches a widget. Plumbing only.

### Coverage honesty
The suite is wide but shallow: over half the tests are import smoke checks, and only ~11 exercise real
engine-core behaviour. Not covered yet: engines, the legacy snapshot converter, `ctrldev` drivers,
`zyngui` screens, MIDI router logic.

## How the hermetic layer works

`tests/bootstrap.py` runs before any production import:

1. Creates a throw-away sandbox (`mkdtemp`, removed at exit) with the `ZYNTHIAN_*_DIR` variables and a
   minimal config (e.g. `wiring-profiles/v5`).
2. Sets `JACK_NO_START_SERVER=1` as a safety net.
3. Stubs third-party modules that are *missing* (lilv, dbus, mididings, ... - real ones are used when
   installed).
4. Installs `FakeZyncore` as `sys.modules["zyncoder.zyncore"]`.
5. Patches `ctypes.cdll.LoadLibrary` so every `libzyn*.so` is a recording fake.

Details:

* `tests/fakes/zyncore.py` – `FakeZyncore` replaces `zyncoder.zyncore.lib_zyncore`. Any attribute is a
  recording callable (default result `0`, or `b""`/`0.0` following the `restype` the wrapper set), so the
  real Python wrapper code runs unchanged. Router constants mirror `zyncoder/zynmidirouter.h`.

  ```python
  def test_x(zyncore):                       # fixture
      MidiFilterRule("IGNORE CH#3 CC#5")
      assert zyncore.calls_to("set_midi_filter_event_ignore") == [(0xB, 3, 5)]
      zyncore.set_return("get_num_zynpots", 4)
  ```
  Helpers: `reset_fake`, `fn`, `set_return`, `calls_to`, `call_count`, `names_called`, `log`, `returns`.
* `tests/fakes/native.py` – every `libzyn*.so` (zynseq, zynmixer, zynsmf, zynaudioplayer, ...) is a fake
  too; the *real* Python wrappers still run, so your code is tested and only the C boundary is faked.
  Access via the `native_libs["libzynseq.so"]` fixture. Defaults: `libzynaudioplayer init→1`,
  `libzynseq getPPQN→96`, `getState` returns minimal JSON, mixer `setMeterConfig→1`.
* Helper names on the fakes must not shadow C symbols (libzynmixer exports `reset`, hence `reset_fake`).
* `tests/conftest.py` pre-imports `zyngine.zynthian_state_manager` to work around the circular import.
* `tests/integration/conftest.py`:
  * `state_manager` builds the real `zynthian_state_manager`;
  * `fake_autoconnect` mocks every `zynautoconnect` function (it is global state needing a live JACK
    client) and pre-sizes `devices_in/out`;
  * `fake_subprocess` blocks and records process creation (the state manager runs
    `powersave_control.sh` during construction).

`ZYNTHIAN_TEST_REAL_ZYNCORE=1` / `ZYNTHIAN_TEST_JACK=1` disable the fakes / the JACK guard for the whole
process. `tests/native` does not need them (it loads the real library explicitly with `ctypes.CDLL`); they
are not exercised and may be removed.

## How the tests were validated

* Mutation sanity check: three production behaviours were deliberately broken on backed-up copies;
  14 tests failed; files restored byte-identical.
* Repeated runs give identical results; also run in a clean venv with only the PyPI packages of
  `requirements-dev.txt` (333 passed, 1 skipped), Python 3.13 only.
* After a run: no `jackd` process, no leftover temp directories.
* The whole flow (fresh venv with only the PyPI packages of `requirements-dev.txt`, build the TOUCH_ONLY
  library from scratch, run everything) gives 367 passed on this machine.
* **Not validated:** the GitHub Actions workflow (`.github/workflows/tests.yml`) has never run on GitHub;
  in particular that `jackd -d dummy` starts on a hosted runner, and that `zynthian/zyncoder` builds there.
  The `ZYNTHIAN_TEST_REAL_ZYNCORE` / `ZYNTHIAN_TEST_JACK` switches below are now unused by `tests/native`.

## Writing tests

* Prefer the smallest layer: a unit test with `zyncore` beats a `state_manager` test.
* Characterization tests are fine and encouraged for legacy behaviour; say so in the docstring when the
  current behaviour looks unintended.
* Known-broken behaviour: `@pytest.mark.xfail(strict=True, reason=...)` - it turns into a failure when
  fixed, reminding you to remove the marker.
* `tests/architecture/test_layering.py` is a ratchet: remove entries from `KNOWN_CORE_TO_UI_IMPORTS` as
  you fix them, never add.

## Known blockers (found while building this; each is a refactoring target)

1. **Core imports UI config.** `zyngine/{state_manager,chain_manager,tts,audio_recorder,legacy_snapshot,
   ctrldev_manager}` and nine `ctrldev` drivers import `zyngui.zynthian_gui_config`, which reads ~57
   environment variables and config files at import time. (Tracked by `test_layering.py`.)
2. **`zyngine/__init__.py` star-imports every engine**, so importing any one core module loads them all
   (≈2 s, and pulls in `alsaaudio`, `pexpect`, `jack`, ...).
3. **Circular import**: `zynthian_chain_manager` and `zynthian_legacy_snapshot` cannot be imported first
   (`test_imports.py`, xfail). `conftest.py` pre-imports the state manager to work around it.
4. **`zynautoconnect` is module-level global state** needing a live JACK client; `zynthian_state_manager()`
   cannot be constructed without it (`fake_autoconnect` mocks every function, and pre-sizes `devices_in/out`).
5. **The state manager shells out** (~28 call sites; `powersave_control.sh` runs during construction).
6. **Constants computed at import from the C library** (`NUM_MIDI_DEVS_IN`, `ZMIP_*_INDEX`, ...); the fake
   mirrors `zyncoder/zynmidirouter.h` (checked by `test_router_constants_match_header`).
7. **Absolute paths**: `zynmixer.py` loads `/zynthian/zynthian-ui/zynlibs/zynmixer/build/*.so`;
   `zynthian_state_manager` defaults to `/zynthian/...`.
8. `zynthian_headless.py` is broken (`import autoconnect`; should be `zynautoconnect`).
9. Packages imported but not in `requirements.txt`: `websocket_server`, `wavio`, `moderngl`/`moderngl_window`,
   `pexpect`, `psutil`, `pyalsaaudio`, `PyYAML`, `scipy`, `pyudev`, ... (they are OS-provided on a Zynthian).
10. Python 3.12+ `SyntaxWarning: invalid escape sequence` in `zynconf/zynthian_config.py`,
    `zynthian_engine_setbfree.py`, `zynthian_engine_sfz.py`, ... (use raw strings; errors in a future Python).
    Hidden in `pyproject.toml` so real warnings stay visible.
11. A controller with a single label collapses its range to 127..127 (characterization test; possibly a bug).
12. **zyncoder bug:** `zmip_send_midi_event()` (and so `zmip_send_note_on/off/ccontrol_change...`) passes the
    input's ring buffer to `jack_ringbuffer_write_space` without a NULL check. Only `FLAG_ZMIP_DIRECTIN` inputs
    (internal, UI) have one, so calling it with a normal device index (0..23) segfaults the process.
    Reproduced with the TOUCH_ONLY build. Not covered by a test (a segfault cannot be `xfail`ed in-process).
13. `ruff` currently reports `F821 undefined name 'logging'` in `zynlibs/zynsmf/zynsmf.py:117` (file modified
    after the suite was first green; the CI lint step fails until `import logging` is added).

## Roadmap

* Native layer: more router coverage (pedals, MIDI learn, tuning pitch-bend, master channel, ZynMaster), and
  the other zynlibs (zynseq, zynmixer...) with the same rig.
* Phase 1: more unit/golden-file tests (legacy snapshot converter, `ctrldev` driver byte tests).
* Phase 2: config object injection to remove the `zyngui` imports from core; the layering ratchet and the
  two circular-import `xfail`s show when it works.
