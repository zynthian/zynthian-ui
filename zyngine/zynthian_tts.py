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

import os
import re
import math
import json
import struct
import logging
import alsaaudio
import threading
import subprocess
from time import sleep

import zynconf
import zynautoconnect
from zyngui import zynthian_gui_config

TTS_DATA_PATH = f"{os.environ.get('ZYNTHIAN_DATA_DIR', '/zynthian/zynthian-data')}/tts"
TTS_FLITE_LEX_PATH = f"{TTS_DATA_PATH}/lexicon"
TTS_FLITE_VOICES_PATH = f"{TTS_DATA_PATH}/voices"
TTS_DICT = {
    "\u2610": "un-checked: ",
    "\u2612": "checked: ",
    "ctrl": "control",
    "param": "parameter",
    "*": "", # Ignore asterisk
    "⇥": "Active mode icon. ",
    "⇶": "Multi-timbral mode icon. ",
    "♣": "Sequencer capture icon. ",
    "⏱": "MIDI Clock source icon. ",
    "⌨": "Control driver icon. "
}
TTS_DICT_DEFER = {
    "❤": ". Favourite icon",
    "\u2673": ". Shared by 1 chain",
    "\u267A": ". Shared by many chains"
}
for i in range(2, 8):
    char = chr(0x2672 + i)
    TTS_DICT_DEFER[char] = f". Shared by {i} chains"

ALL_KEYS = list(TTS_DICT) + list(TTS_DICT_DEFER)

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
        self.pending_beep = None
        self._queue = []
        self._cond = threading.Condition() # Queue locking mutex
        self._stop_event = None
        self._process = None
        self._lock = threading.Lock() # Process locking mutex
        self.playing = False
        self.translate_pattern = re.compile("|".join(map(re.escape, sorted(ALL_KEYS, key=len, reverse=True))))

        self.clear_queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._stop_event = threading.Event()
        self._thread.start()
        self.set_volume()
        self.append("ZynVoice enabled")

    def close(self):
        """ Stop background services and cleanup """

        self.stop()

        if self._stop_event:
            self._stop_event.set()
        self._thread.join()
        self._stop_event = None

    def set_busy(self, state):
        """ Set the busy state which periodically pulses a tone
        Args:
            state: True to set busy, else clears busy state.
        """

        if state:
            self.stop()
            if not self.busy_timer:
                self.busy_timer = threading.Timer(1.0, self.cb_busy_timer)
                self.busy_timer.start()
        else:
            if self.busy_timer:
                self.busy_timer.cancel()
                self.busy_timer = None
            elif self.busy:
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
        deferred = []

        def replace_match(m):
            token = m.group(0)
            if token in TTS_DICT_DEFER:
                deferred.append(TTS_DICT_DEFER[token])
                return ""   # remove from inline text
            return TTS_DICT[token]

        def normalize_number(m):
            num = float(m.group(1))
            num = str(int(num)) if num.is_integer() else str(num)
            return f"{num} "

        # Perform token translation
        text = self.translate_pattern.sub(replace_match, text)

        # Normalize whitespace after removals
        text = re.sub(r"\s+", " ", text).strip()

        # Number normalization
        text = re.sub(r"(-?\d+(?:\.\d+)?)", normalize_number, text)

        # Append deferred announcements
        if deferred:
            text += ". " + ". ".join(deferred)

        return text

    def append(self, text: str, replace: bool=True, urgent: bool=False, interrupt=True):
        """ Append text to queue
        Args:
            text: Text to append to queue
            replace: True to replace the queue with this text, else appended to queue
            urgent: True to speak phrase next, else appended to end of queue
            interrupt: True to stop current phrase and speak this phrase immediately
        """

        if not self._stop_event or self.busy:
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
        elif self.voice == "espeak-f":
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

        with self._cond:
            self.pending_beep = (duration, frequency, amplitude)

    def _do_beep(self, cfg):
        try:
            duration, frequency, amplitude = cfg
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
            offset = 0
            samples = bytearray()
            for _ in range(num_samples):
                offset = int(index) % SINE_WAVETABLE_SIZE
                value = [int(amplitude * self.SINE_WAVETABLE[offset])] * channels
                samples += struct.pack(fmt, *value)
                index += step
            # Add tail of waveform - wrong frequency but inperceptible and gives zero crossing
            while offset < len(self.SINE_WAVETABLE):
                value = [int(amplitude * self.SINE_WAVETABLE[offset])] * channels
                samples += struct.pack(fmt, *value)
                offset += 1
            # Send waveform to soundcard
            pcm.write(samples)
        except Exception as e:
            logging.error(f"TTS failed to send tone to soundcard - {e}")
        self.pending_beep = None

    def _worker(self):
        count = 0
        while self._stop_event and not self._stop_event.is_set():
            if self.soundcard:
                with self._cond:
                    while self.paused or self.line >= len(self._queue) and not self._stop_event.is_set():
                        self._cond.wait(timeout=0.1)
                        with self._lock:
                            self.playing = False
                        if self.busy:
                            count += 1
                            if count > 20:
                                count = 0
                                self._do_beep((0.2, 440, 0.5))
                    if self._stop_event.is_set():
                        break

                while not self.playing:
                    with self._lock:
                        self.playing = True
                    sleep(0.4) # Debounce to avoid rapid message interruption

                with self._cond:
                    if self.pending_beep:
                        self._do_beep(self.pending_beep)
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
                    logging.debug(e)
                finally:
                    pass
            else:
                sleep(0.6)

        if self.announce_disable:
            try:
                with self._lock:
                    self._process = subprocess.Popen(self._build_command("ZynVoice disabled"), env={"ALSA_CARD": self.soundcard})
                self._process.wait()
            except Exception as e:
                logging.debug(e)

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
