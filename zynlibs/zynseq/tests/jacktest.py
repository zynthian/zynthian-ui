#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: JACK test environment
#
# Helpers for integration tests running against a private JACK server that uses
# the dummy backend, so no audio hardware is needed. Process cycles are run in
# freewheel mode, as fast as possible, so tests are fast and deterministic: time
# is measured in frames, not wall clock.
#
# Copyright (C) 2026 Fernando Moyano <jofemodo@zynthian.org>
#
# ******************************************************************************
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
#
# ******************************************************************************

import os
import time
import threading
import subprocess
from collections import deque

import jack
import numpy as np


class JackTestServer:
    """Private jackd instance using the dummy backend

    JACK_DEFAULT_SERVER is set to the server name, so libraries that open the
    default server (e.g. zynseq) connect to this one.
    """

    def __init__(self, name="zyntest", rate=48000, period=256):
        self.name = name
        self.rate = rate
        self.period = period
        self.proc = None

    def start(self, timeout=10):
        if self.proc:
            return
        self.proc = subprocess.Popen(["jackd", "--no-realtime", "-n", self.name, "-d", "dummy",
                                      "-r", str(self.rate), "-p", str(self.period)],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.environ["JACK_DEFAULT_SERVER"] = self.name
        # Wait for server, silencing libjack errors while it is starting
        jack.set_error_function(lambda msg: None)
        try:
            tend = time.monotonic() + timeout
            while True:
                try:
                    jack.Client("zyntest_probe", servername=self.name, no_start_server=True).close()
                    return
                except jack.JackError:
                    if self.proc.poll() is not None or time.monotonic() > tend:
                        self.stop()
                        raise RuntimeError(f"Can't start jackd server '{self.name}'")
                    time.sleep(0.05)
        finally:
            jack.set_error_function()

    def stop(self):
        if self.proc:
            # Clients still open (e.g. libraries without close function) report errors when server stops
            jack.set_error_function(lambda msg: None)
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
            self.proc = None

    def seconds(self, secs):
        """Convert seconds to frames"""
        return int(round(secs * self.rate))


class TestClient:
    """JACK client calling process(frame, nframes) on each cycle

    frame is the frame time (since server start) of the first frame in the cycle.
    """

    def __init__(self, server, name):
        self.server = server
        self.client = jack.Client(name, servername=server.name, no_start_server=True)
        self.frame_time = 0  # Frame time of the last processed cycle
        self.discontinuities = 0  # Quantity of frame time jumps, e.g. cycles lost by xruns
        self._next_frame = None
        self._stall = 0
        self.client.set_process_callback(self._process)

    def _process(self, nframes):
        self.frame_time = self.client.last_frame_time
        if self._next_frame is not None and self.frame_time != self._next_frame:
            self.discontinuities += 1
        self._next_frame = self.frame_time + nframes
        self.process(self.frame_time, nframes)
        if self._stall:
            time.sleep(self._stall)
            self._stall = 0

    def stall(self, secs):
        """Block the next process cycle for some time, to cause an xrun (only when not in freewheel mode)"""
        self._stall = secs

    def process(self, frame, nframes):
        pass

    def activate(self):
        self.client.activate()

    def close(self):
        self.client.deactivate()
        self.client.close()


class FreewheelRunner(TestClient):
    """Run process cycles in freewheel mode for a given quantity of frames"""

    def __init__(self, server, name="zyntest_runner"):
        super().__init__(server, name)
        self.target = None
        self.done = threading.Event()

    def process(self, frame, nframes):
        if self.target is not None and frame + nframes >= self.target:
            self.done.set()

    def run(self, nframes, timeout=60):
        self.done.clear()
        self.target = self.frame_time + nframes
        self.client.set_freewheel(True)
        try:
            if not self.done.wait(timeout):
                raise TimeoutError(f"Freewheel run of {nframes} frames timed out")
        finally:
            self.client.set_freewheel(False)
            self.target = None

    def run_seconds(self, secs, timeout=60):
        self.run(self.server.seconds(secs), timeout)


class MidiSource(TestClient):
    """Send scheduled MIDI events at exact frame times

    Events are (frame, bytes) tuples, using absolute frame times. Events scheduled
    in the past are sent at the start of the cycle and counted in 'late'.
    """

    def __init__(self, server, name="zyntest_midi_src"):
        super().__init__(server, name)
        self.port = self.client.midi_outports.register("out")
        self.lock = threading.Lock()
        self.events = deque()
        self.late = 0

    def schedule(self, events):
        with self.lock:
            # Stable sort keeps order of events with the same frame time
            self.events = deque(sorted(list(self.events) + list(events), key=lambda ev: ev[0]))

    def clear(self):
        with self.lock:
            self.events.clear()
            self.late = 0

    def process(self, frame, nframes):
        self.port.clear_buffer()
        end = frame + nframes
        with self.lock:
            while self.events and self.events[0][0] < end:
                f, data = self.events.popleft()
                if f < frame:
                    self.late += 1
                    f = frame
                self.port.write_midi_event(f - frame, data)


class Recorder(TestClient):
    """Record MIDI events and audio clicks, and call per-cycle hooks

    midi[port] is a list of (frame, bytes) of received MIDI events.
    clicks[port] is a list of (frame, length) of audio "clicks": non-silent sample
    runs, e.g. metronome beats.
    Hooks are called on each cycle as hook(frame, nframes), e.g. to sample the
    state of the library under test, after it has processed the cycle (the hooks
    run after the library if the recorder is connected to its outputs).
    """

    def __init__(self, server, name="zyntest_recorder", midi_ports=(), audio_ports=()):
        super().__init__(server, name)
        self.midi_ports = {name: self.client.midi_inports.register(name) for name in midi_ports}
        self.audio_ports = {name: self.client.inports.register(name) for name in audio_ports}
        self.hooks = []
        self.lock = threading.Lock()
        self.clear()

    def clear(self):
        with self.lock:
            self.midi = {name: [] for name in self.midi_ports}
            self.clicks = {name: [] for name in self.audio_ports}
            self._click_start = {name: None for name in self.audio_ports}
            self._sound_prev = {name: False for name in self.audio_ports}

    def process(self, frame, nframes):
        with self.lock:
            for name, port in self.midi_ports.items():
                for offset, data in port.incoming_midi_events():
                    self.midi[name].append((frame + offset, bytes(data)))
            for name, port in self.audio_ports.items():
                sound = np.frombuffer(port.get_buffer(), dtype=np.float32) != 0
                prev = np.concatenate(([self._sound_prev[name]], sound[:-1]))
                for i in np.flatnonzero(sound != prev):
                    if sound[i]:
                        self._click_start[name] = frame + i
                    elif self._click_start[name] is not None:
                        start = self._click_start[name]
                        self.clicks[name].append((start, frame + i - start))
                        self._click_start[name] = None
                self._sound_prev[name] = bool(sound[-1])
            for hook in self.hooks:
                hook(frame, nframes)
