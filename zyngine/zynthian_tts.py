# -*- coding: utf-8 -*-
# ****************************************************************************
# ZYNTHIAN PROJECT: Zynthian TTS (zynthian_tts)
#
# zynthian text to speech class
#
# Copyright (C) 2026 Brian Walton <riban@zynthian.org>
#                    Fernando Moyano <jofemodo@zynthian.org>
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

import logging
import threading
import subprocess
from collections import deque
import os
import re
import json
from time import sleep
import alsaaudio

import zynconf
from zyngui import zynthian_gui_config
import zynautoconnect
from zyngine.zynthian_signal_manager import zynsigman

TTS_CONFIG_PATH = f"{os.environ.get('ZYNTHIAN_CONFIG_DIR', '/zynthian/config')}/tts"
TTS_FLITE_LEX_PATH = f"{TTS_CONFIG_PATH}/lexicon"
TTS_FLITE_VOICES_PATH = f"{TTS_CONFIG_PATH}/voices"
TTS_DICT = {
    "\u2610": "un-checked",
    "\u2612": "checked",
}

class zynthian_tts:
    def __init__(self, state_manager):
        self.state_manager = state_manager
        with open(f"{TTS_FLITE_VOICES_PATH}/voices.json") as f:
            txt = f.read()
        self.voices = json.loads(txt)

        self.set_speed(zynthian_gui_config.tts_speed)
        self.set_soundcard(zynthian_gui_config.tts_soundcard)
        self.set_voice(zynthian_gui_config.tts_voice)

        self.busy = False
        self.busy_timer = None
        self._queue = deque()
        self._cond = threading.Condition() # Queue locking mutex
        self._stop_event = None
        self._process = None
        self._current_text = None
        self._lock = threading.Lock() # Process locking mutex
        self.playing = False
        self.translate_pattern = re.compile("|".join(map(re.escape, TTS_DICT)))

    def enable(self):
        """ Enable TTS and start background thread """

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
        self.set_volume()
        self.append("Narration enabled")
        zynsigman.register_queued(zynsigman.S_STATE_MAN, self.state_manager.SS_BUSY, self.cb_busy)

        # Auto configure Narrator button
        for key, value in os.environ.items():
            if value == "TTS_TOGGLE_ENABLE":
                if key.startswith("ZYNTHIAN_WIRING_CUSTOM_SWITCH_") and key.endswith("__UI_LONG"):
                    key = key.replace("__UI_LONG", "__UI_SHORT")
                    self.wiring_short = {key: os.environ.get(key)}
                    zynconf.save_config({key: "TTS_TOGGLE_PLAYBACK"}, False)
                    self.state_manager.send_cuia("RELOAD_WIRING_LAYOUT")

    def disable(self):
        """ Disable TTS and stop background thread"""

        zynsigman.unregister(zynsigman.S_STATE_MAN, self.state_manager.SS_BUSY, self.cb_busy)
        self.stop()
        self.append("Narration disabled")

        def do_disable():
            if self._stop_event:
                self._stop_event.set()
            self._thread.join()
            self._stop_event = None

        threading.Timer(0.2, do_disable).start()
        try:
            zynconf.save_config(self.wiring_short, False)
        except:
            pass

    def is_running(self):
        return self._stop_event is not None

    def get_voice_name(self):
        return self.voices[self.voice]

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
        zynconf.save_config({"ZYNTHIAN_TTS_SOUNDCARD": card}, False)
        zynautoconnect.enable_audio_output_device(card, False)

    def set_voice(self, voice):
        """ Set the voice
        Args:
            voice: Name of voice or espeak-m or espeak-f for espeak male/female
                   May be integer index of voice
        """

        if isinstance(voice, int):
            self.voice = list(self.voices)[voice]
        else:
            self.voice = voice
        zynthian_gui_config.tts_voice = self.voice
        zynconf.save_config({"ZYNTHIAN_TTS_VOICE": self.voice}, False)

    def set_speed(self, speed: float):
        """ Set the speech speed
        Args:
            speed: Normalised speed, i.e. 1.0 for default
        """

        speed = max(min(2.0, speed), 0.1)
        zynthian_gui_config.tts_speed = self.speed = speed
        zynconf.save_config({"ZYNTHIAN_TTS_SPEED": str(zynthian_gui_config.tts_speed)}, False)

    def translate(self, text):
        def normalize_number(m):
            # Enforce numeric handling with trailing decimal zeros removed
            num = float(m.group(1))
            num = str(int(num)) if num.is_integer() else str(num)
            return f"{num} "

        text = self.translate_pattern.sub(lambda m : TTS_DICT[m.group(0)], text) # tech dictionary
        text = re.sub(r"(-?\d+\.\d+)", normalize_number, text)

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
        if self.voice == "espeak-m":
            return [
                "espeak-ng",
                "-v", f"en+m1",
                "-s", str(int(self.speed * 200)),
                text
            ]
        if self.voice == "espeak-f":
            return [
                "espeak-ng",
                "-v", f"en+f1",
                "-s", str(int(self.speed * 200)),
                text
            ]
        else:  # flite
            return [
                "flite",
                "-voice", f"{TTS_FLITE_VOICES_PATH}/{self.voice}",
                "--setf", f"duration_stretch={1.0 / self.speed}",
                "-add_lex", TTS_FLITE_LEX_PATH,
                "-t", f"{text}"
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
                    with self._lock:
                        self.playing = False
                    if self.busy:
                        count += 1
                        if count > 20:
                            count = 0
                            self.beep()
                if self._stop_event.is_set():
                    break

            while not self.playing:
                with self._lock:
                    self.playing = True
                sleep(0.4) # Debounce to avoid rapid message interruption

            with self._cond:
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

    def set_volume(self, volume=None):
        """ Attempt to set the volume of the soundcard
        Args:
            volume: Volume [0..100] or None to get from config
        Returns: True on success
        Note: Uses best guess at volume control name
        """

        if volume is None:
            volume = zynthian_gui_config.tts_volume
        try:
            idx = alsaaudio.cards().index(self.soundcard)
            mixers = alsaaudio.mixers(cardindex=idx)
            for name in ["Master", "PCM", "Speaker", "Headphone"]:
                if name in mixers:
                    mixer = alsaaudio.Mixer(control=name, cardindex=idx)
                    mixer.setvolume(min(max(volume, 0), 100))
                    zynthian_gui_config.tts_volume = volume
                    zynconf.save_config({"ZYNTHIAN_TTS_SOUNDCARD": volume}, False)
                    return True
        except:
            pass
        return False
