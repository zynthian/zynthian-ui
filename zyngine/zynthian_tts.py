# -*- coding: utf-8 -*-
# ****************************************************************************
# ZYNTHIAN PROJECT: Zynthian TTS (zynthian_tts)
#
# zynthian text to speech class
#
# Copyright (C) 2026 Fernando Moyano <jofemodo@zynthian.org>
#                    Brian Walton <riban@zynthian.org>
#
# ****************************************************************************
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
# ****************************************************************************

import threading
import subprocess
from collections import deque
import logging

import zynconf
from zyngui import zynthian_gui_config
import zynautoconnect
from zyngine.zynthian_signal_manager import zynsigman

class zynthian_tts:
    def __init__(self, state_manager):
        self.state_manager = state_manager
        self.set_engine(zynthian_gui_config.tts_engine)
        self.set_gender(zynthian_gui_config.tts_gender)
        self.set_speed(zynthian_gui_config.tts_speed)
        self.set_soundcard(zynthian_gui_config.tts_soundcard)
        self.busy = False
        self.busy_timer = None
        self._queue = deque()
        self._cond = threading.Condition()
        self._stop_event = None
        self._process = None
        self._current_text = None
        self._lock = threading.Lock()
        self.playing = False

    def start(self):
        if self._stop_event:
            return
        self.clear_queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._stop_event = threading.Event()
        self._thread.start()
        soundcards = zynautoconnect.get_alsa_audio_devices(True, "tts")
        if self.soundcard not in soundcards:
            if soundcards:
                self.soundcard = soundcards[0]
            else:
                self.soundcard = ""
        self.append("Narration enabled")
        zynsigman.register_queued(zynsigman.S_STATE_MAN, self.state_manager.SS_BUSY, self.cb_busy)

    def shutdown(self):
        """Stop thread completely"""
        zynsigman.unregister(zynsigman.S_STATE_MAN, self.state_manager.SS_BUSY, self.cb_busy)
        self.stop()
        self.append("Narration disabled")
        def do_shutdown():
            self._stop_event.set()
            with self._cond:
                self._cond.notify_all()
            self._thread.join()
            self._stop_event = None
        threading.Timer(0.2, do_shutdown).start()

    def cb_busy(self, state):
        if state:
            if not self.busy_timer:
                self.busy_timer = threading.Timer(1.0, self.cb_busy_timer)
                self.busy_timer.start()
        else:
            if self.busy_timer:
                self.busy_timer.cancel()
                self.busy_timer = None
            else:
                self.beep(0.4, 600)
            self.busy = False

    def cb_busy_timer(self):
        self.busy_timer = None
        self.busy = True

    def set_soundcard(self, card):
        """ Set the ALSA soundcard to use
        Args:
            card: Soundcard
        """

        zynthian_gui_config.tts_soundcard = self.soundcard = card
        zynconf.save_config({"ZYNTHIAN_TTS_SOUNDCARD": card}, True)
        zynautoconnect.enable_audio_output_device(card, False)

    def set_engine(self, engine: str):
        """ Set the TTS engine to use for consequent speech
        Args:
            engine: "Engine name ["e(speak-ng)" | "f(lite)"]
        """

        if engine.startswith("e"):
            self.engine = "espeak-ng"
        elif engine.startswith("f"):
            self.engine = "flite"
        zynthian_gui_config.tts_engine = self.engine
        zynconf.save_config({"ZYNTHIAN_TTS_ENGINE": self.engine}, True)

    def set_speed(self, speed: float):
        """ Set the speech speed
        Args:
            speed: Normalised speed, i.e. 1.0 for default
        """

        speed = max(min(2.0, speed), 0.1)
        zynthian_gui_config.tts_speed = self.speed = speed
        zynconf.save_config({"ZYNTHIAN_TTS_SPEED": str(zynthian_gui_config.tts_speed)}, True)

    def set_gender(self, gender: str):
        """ Set the gender of the voice
        Args:
            gender: Voice gender ["m(ale)" | "f(emale)"]
        """

        if gender.lower().startswith("f"):
            self.gender = "f"
        else:
            self.gender = "m"
        zynthian_gui_config.tts_gender = self.gender
        zynconf.save_config({"ZYNTHIAN_TTS_GENDER": str(zynthian_gui_config.tts_gender)}, True)

    def translate(self, text):
        if text.startswith("-"):
            text = f" {text}"
        for a, b in (
            ("\u2612", "Checked "),
            ("\u2610", "Unchecked "),
            (" & ", " and ")
        ):
            text = text.replace(a, b)
        return text

    def append(self, text: str, replace: bool=True, urgent: bool=False, interrupt=True):
        """ Append text to queue
        Args:
            text: Text to append to queue
            replace: True to replace the queue with this text, else appended to queue
            urgent: True to speak phrase next, else appended to end of queue
            interrupt: True to stop current phrase and speak this phrase immediately
        """

        if not self._stop_event:
            return
        text = text.strip()
        if text:
            text = self.translate(text)
            with self._cond:
                if replace:
                    self._queue.clear()
                if urgent:
                    if interrupt and not replace:
                        self._queue.appendleft(self._current_text)
                    self._queue.appendleft(text)
                else:
                    self._queue.append(text)
                self._cond.notify()
            if interrupt:
                self.stop(False)

    def clear_queue(self):
        """ Remove all pending items """
        with self._cond:
            self._queue.clear()

    def stop(self, clear=True):
        """ Stop playback immediately
        Args:
            clear: True to clear queue, else moves directly to next queued text [Default: True]
        """

        if clear:
            self.clear_queue()
        with self._lock:
            if self._process and self._process.poll() is None:
                self._process.terminate()
        self.playing = False

    def _build_command(self, text: str):
        if self.engine == "espeak-ng":
            return [
                "espeak-ng",
                "-v", f"en+{self.gender}1",
                "-s", str(int(self.speed * 200)),
                text
            ]
        else:  # flite
            return [
                "flite",
                "-voice", "awb" if self.gender=="m" else "slt",
                "--setf", f"duration_stretch={1.0 / self.speed}",
                f"{text} " # Add space to ensure single words are not interpreted as filenames
            ]

    def beep(self, dur=0.1, freq=440):
        """ Sound a beep
        Args:
            freq: Tone frequency
            dur: Tone duration (s)
        """

        subprocess.Popen(
            [
                "play",
                "-n",
                "synth", str(dur),
                "sine", str(freq),
                "gain", "-12"
            ],
            env={"ALSA_CARD": self.soundcard},
            stderr=subprocess.DEVNULL
        )

    def _worker(self):
        count = 0
        while self._stop_event and not self._stop_event.is_set():
            with self._cond:
                while not self._queue and not self._stop_event.is_set():
                    self._cond.wait(timeout=0.1)
                    self.playing = False
                    if self.busy:
                        count += 1
                        if count > 20:
                            count = 0
                            self.beep()
                if self._stop_event.is_set():
                    break
                self.playing = True
                text = self._queue.popleft()

            cmd = self._build_command(text)

            try:
                with self._lock:
                    self._current_text = text
                    self._process = subprocess.Popen(cmd, env={"ALSA_CARD": self.soundcard})
                self._process.wait()
            except Exception as e:
                print(f"TTS error: {e}")
            finally:
                self._current_text = None
