# zynseq integration tests

These tests run the real `libzynseq.so` on a private JACK server, which uses the
**dummy backend** (no audio hardware needed) in **freewheel mode** (process cycles
run as fast as possible). Tests are fast and deterministic because time is measured
in frames, not wall clock: 40 seconds of audio take a fraction of a second.

## Requirements

- `jackd` (jack2)
- Python modules `JACK-Client` and `numpy`
- A built library: `zynlibs/zynseq/build.sh`

The tests start their own server, named `zyntest`, so they don't touch a running
JACK server. On a zynthian it can run alongside the UI, but freewheel keeps a CPU
core busy for a couple of seconds, so avoid running it while playing live.

### Python environment

On a desktop, use the zynthian-ui test venv. Create it from the `zynthian-ui`
directory with:

```
./create_venv.sh
```

It creates `venv` with access to system site-packages and installs
`requirements.txt`, which includes `JACK-Client` and `numpy`.

This venv is only for testing on a desktop. On a zynthian device, the python
environment is the one shared with zynthian-webconf, in `/zynthian`.

## Running

From the `zynthian-ui` directory, on a desktop:

```
./run_tests.sh
```

It activates the venv and runs all tests with `ZYNTEST_LOG=INFO`, which shows the
measured values (tempo range, phase error...). To run them by hand:

```
source venv/bin/activate
python3 -m unittest discover -s zynlibs/zynseq/tests -v
```

## Structure

- `jacktest.py`: Generic helpers, not specific to zynseq, so they can be reused to
  test other libraries:
  - `JackTestServer`: starts/stops the private jackd server.
  - `FreewheelRunner`: processes a given quantity of frames in freewheel mode.
  - `MidiSource`: sends MIDI events at exact frame times.
  - `Recorder`: records MIDI events and audio clicks (e.g. metronome beats) with
    their frame times, and calls per-cycle hooks to sample the library state.
  - All clients count frame time discontinuities (cycles lost by xruns) and can
    `stall()` a cycle to cause an xrun.
- `test_ext_clock.py`: External clock synchronization (PLL) tests. MIDI clock with
  optional jitter is sent to `zynseq:clock_in`. Tests check zynseq's tempo, its MIDI
  clock output phase against the ideal input clock, and metronome beat and bar
  alignment after MIDI START, also with lost clock pulses and xruns.

Xrun tests need real time processing, not freewheel: a client connected to the
library input blocks a cycle, so the library skips cycles as in a real xrun. Don't
block the client sending the events under test: JACK would deliver its previous
buffer again, duplicating events, which doesn't happen with a real MIDI input.

The process order is set by connections: `MidiSource` => library => `Recorder`, so
everything happens in the same cycle and the recorder sees the library output of
the current cycle.
