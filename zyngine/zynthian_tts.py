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
import os
import re
import json
from time import sleep
import alsaaudio
import math
import struct

import zynconf
from zyngui import zynthian_gui_config
import zynautoconnect
from zyngine.zynthian_signal_manager import zynsigman

TTS_DATA_PATH = f"{os.environ.get('ZYNTHIAN_DATA_DIR', '/zynthian/zynthian-data')}/tts"
TTS_FLITE_LEX_PATH = f"{TTS_DATA_PATH}/lexicon"
TTS_FLITE_VOICES_PATH = f"{TTS_DATA_PATH}/voices"
TTS_DICT = {
    "\u2610": "un-checked",
    "\u2612": "checked",
}
SINE_WAVETABLE_SIZE = 1024

class zynthian_tts:
    SINE_WAVETABLE = [int(32767 * math.sin(2 * math.pi * i / SINE_WAVETABLE_SIZE)) for i in range(SINE_WAVETABLE_SIZE)]

    def __init__(self):
        self.set_soundcard(zynthian_gui_config.tts_soundcard)
        self.set_speed(zynthian_gui_config.tts_speed)
        self.set_voice(zynthian_gui_config.tts_voice)

        self.line = 0 # The current index of queue being played (since last clear)
        self.paused = False
        self.busy = False
        self.busy_timer = None
        self.announce_disable = True
        self._queue = []
        self._cond = threading.Condition() # Queue locking mutex
        self._stop_event = None
        self._process = None
        self._lock = threading.Lock() # Process locking mutex
        self.playing = False
        self.translate_pattern = re.compile("|".join(map(re.escape, TTS_DICT)))

        self.clear_queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._stop_event = threading.Event()
        self._thread.start()
        self.set_volume()
        self.append("Narrator enabled")
        zynsigman.register_queued(zynsigman.S_STATE_MAN, zynsigman.SS_BUSY, self.cb_busy)

    def close(self):
        """ Stop background services and cleanup """

        zynsigman.unregister(zynsigman.S_STATE_MAN, zynsigman.SS_BUSY, self.cb_busy)
        self.stop()

        if self._stop_event:
            self._stop_event.set()
        self._thread.join()
        self._stop_event = None

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
        Returns: Name of soundcard or None on failure
        """

        soundcards = zynautoconnect.get_alsa_audio_devices(True, "tts")
        if card in soundcards:
            self.soundcard = card
        else:
            if soundcards:
                self.soundcard = soundcards[0]
            else:
                self.soundcard = None

        if self.soundcard:
            zynthian_gui_config.tts_soundcard = self.soundcard
            zynconf.save_config({"ZYNTHIAN_TTS_SOUNDCARD": self.soundcard}, False)
            zynautoconnect.enable_audio_output_device(self.soundcard, False)
        return self.soundcard

    def set_voice(self, voice):
        """ Set the voice
        Args:
            voice: Name of voice or espeak-m or espeak-f for espeak male/female
                   May be integer index of voice
        """

        if isinstance(voice, int):
            self.voice = list(self.get_voices())[voice]
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
            if replace:
                self.clear_queue()
            with self._cond:
                if urgent:
                    if self.line:
                        self.line -= 1
                    self._queue.insert(self.line, text)
                else:
                    self._queue.append(text)
            if interrupt:
                self.stop(False)

    def clear_queue(self):
        """ Remove all pending items """
        with self._cond:
            self._queue.clear()
            self.paused = False
            self.line = 0

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

    def pause(self, pause=None):
        """ Set or toggle playback pause
        Args:
            pause: True to pause. False to resume. None to toggle.
        """

        if pause is None:
            pause = not self.paused
        if pause:
            if not self.playing:
                return
            self.stop(False)
            self.line = max(0, self.line - 1)
        self.paused = pause

    def next(self):
        with self._lock:
            if self._process and self._process.poll() is None:
                self._process.terminate()
            else:
                self.line = min(len(self._queue), self.line + 1)

    def prev(self):
        with self._lock:
            if self._process and self._process.poll() is None:
                self._process.terminate()
        self.line = max(0, self.line - 2)

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

    def beep(self, duration=0.2, frequency=440, amplitude=0.5):
        """ Sound a beep
        Args:
            duration: Tone duration [Default: 0.2s]
            frequency: Tone frequency [Default: 440 Hz]
            amplitude: Normalised amplitude [Default: 0.5]
        """

        try:
            # Try to open soundcard with low resource parameters
            pcm = alsaaudio.PCM(
                alsaaudio.PCM_PLAYBACK,
                device=f"hw:{self.soundcard}",
                periodsize=1024,
                rate=32000,
                channels=1,
                format=alsaaudio.PCM_FORMAT_S16_LE
            )
            # Get actual parameters because some soundcards do not support all configurations
            info = pcm.info()
            num_samples = int(info["rate"] * duration)
            step = frequency * SINE_WAVETABLE_SIZE / info["rate"]
            channels = info["channels"]
            fmt = "<" + "h" * channels
            # Create the output waveform
            index = 0.0
            samples = bytearray()
            for _ in range(num_samples):
                value = [int(amplitude * self.SINE_WAVETABLE[int(index) % SINE_WAVETABLE_SIZE])] * channels
                samples += struct.pack(fmt, *value)
                index += step
            # Add tail of waveform - wrong frequency but inperceptible and gives zero crossing
            while index < len(self.SINE_WAVETABLE):
                value = int(amplitude * self.SINE_WAVETABLE[int(index) % SINE_WAVETABLE_SIZE])
                samples += struct.pack(fmt, *value)
                index += 1
            # Send waveform to soundcard
            pcm.write(samples)
        except Exception as e:
            logging.error(f"TTS failed to send tone to soundcard - {e}")

    def _worker(self):
        count = 0
        while self._stop_event and not self._stop_event.is_set():
            with self._cond:
                while self.paused or self.line >= len(self._queue) and not self._stop_event.is_set():
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
                try:
                    text = self._queue[self.line]
                    self.line += 1
                except:
                    text = ""
                    self.playing = False

            try:
                with self._lock:
                    self._process = subprocess.Popen(self._build_command(text), env={"ALSA_CARD": self.soundcard})
                self._process.wait()
            except Exception as e:
                print(f"TTS error: {e}")
            finally:
                pass

        if self.announce_disable:
            try:
                with self._lock:
                    self._process = subprocess.Popen(self._build_command("Narrator disabled"), env={"ALSA_CARD": self.soundcard})
                self._process.wait()
            except Exception as e:
                print(f"TTS error: {e}")

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

    # ------------------------------------------------
    # Class methods
    # ------------------------------------------------

    @classmethod
    def get_voices(cls):
        try:
            with open(f"{TTS_FLITE_VOICES_PATH}/voices.json") as f:
                txt = f.read()
            return json.loads(txt)
        except:
            return {}
