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

class zynthian_tts:
    def __init__(self):
        self.engine = "flite"
        self.speed = 1.0
        self.gender = "m"
        self.lang_code = "en"
        self.soundcard = "1"
        self._queue = deque()
        self._cond = threading.Condition()
        self._stop_event = None
        self._process = None
        self._current_text = None
        self._lock = threading.Lock()
        
        self.update_languages()

    def start(self):
        if self._stop_event:
            return
        self.clear_queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._stop_event = threading.Event()
        self._thread.start()

    def shutdown(self):
        """Stop thread completely"""
        self._stop_event.set()
        self.stop()
        with self._cond:
            self._cond.notify_all()
        self._thread.join()
        self._stop_event = None

    def set_soundcard(self, card):
        """ Set the ALSA soundcard to use
        Args:
            card: Soundcard
        """

        self.soundcard = card

    def set_engine(self, engine: str):
        """ Set the TTS engine to use for consequent speech
        Args:
            engine: "Engine name ["e(speak-ng)" | "f(lite)"]
        """

        if engine.startswith("e"):
            self.engine = "espeak-ng"
        elif engine.startswith("f"):
            self.engine = "flite"

    def set_speed(self, speed: float):
        """ Set the speech speed
        Args:
            speed: Normalised speed, i.e. 1.0 for default
        """

        speed = max(min(2.0, speed), 0.1)
        self.speed = speed

    def set_gender(self, gender: str):
        """ Set the gender of the voice
        Args:
            gender: Voice gender ["m(ale)" | "f(emale)"]
        """

        if gender.startswith("m"):
            self.gender = "m"
        elif gender.startswith("f"):
            self.gender = "f"

    def update_languages(self):
        """ Update the local cache of available and installed languages
        """

        import argostranslate.package
        # Stop warnings being logged for translation operations
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        logging.getLogger("utils.info").setLevel(logging.ERROR)
        logging.getLogger("utils").setLevel(logging.ERROR)
        logging.getLogger("argostranslate").setLevel(logging.ERROR)

        argostranslate.package.update_package_index()
        self.language_packages = {} # (package, installed), indexed by lang_code
        for package in argostranslate.package.get_available_packages():
            if package.from_code == "en":
                self.language_packages[package.to_code] = [package, False]
        for lang in argostranslate.package.get_installed_packages():
            self.language_packages[lang.to_code][1] = True

    def get_available_languages(self):
        """ Get a list of available translation languages
        Returns: Dict of language names, indexed by language code
        """

        result = {"en": "English"}
        for package, installed in self.language_packages.values():
            result[package.to_code] = package.to_name
        return result

    def set_language(self, lang_code: str):
        """ Set the language to translate to
        Args:
            lang-code: Language code
        """

        if lang_code == "en":
            self.lang_code = lang_code
            return
        try:
            import argostranslate.translate as at
            self.argos = at

            package, installed = self.language_packages[lang_code]
            if not installed:
                package.install()
                self.language_packages[lang_code][1] = True
            self.lang_code = lang_code
            # Do first translation to prime translator
            self.translate("test")
        except:
            pass

    def translate(self, text):
        text = text.replace("\u2612", "Checked ").replace("\u2610", "Unchecked ")
        if self.lang_code == "en":
            return text
        return self.argos.translate(text, "en", self.lang_code)

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

    def _build_command(self, text: str):
        if self.engine == "espeak-ng":
            return [
                "espeak-ng",
                "-v", f"{self.lang_code}+{self.gender}1",
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

    def _worker(self):
        while self._stop_event and not self._stop_event.is_set():
            with self._cond:
                while not self._queue and not self._stop_event.is_set():
                    self._cond.wait(timeout=0.1)
                if self._stop_event.is_set():
                    break
                text = self._queue.popleft()

            cmd = self._build_command(text)

            try:
                with self._lock:
                    self._current_text = text
                    self._process = subprocess.Popen(cmd, env={**dict(**{}), "ALSA_CARD": self.soundcard})
                self._process.wait()
            except Exception as e:
                print(f"TTS error: {e}")
            finally:
                self._current_text = None
        print("worker ended")


""" Example usage
from zyngine.zynthian_tts import zynthian_tts
tts = zynthian_tts()
tts.start()
with open("/root/sonobus/LICENSE", "r") as f:
    txt = f.read()

for line in txt.split('\n'):
    tts.append(line)

tts.set_speed(0.8)
tts.append("I have stopped this nonsense", replace=True, urgent=False, interrupt=False)
tts.set_engine("espeak-ng")

"""
