# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Software Update Progress Class
#
# Shows the software update progress while an update is running. The screen is
# rendered by zynthian-sys/sbin/zynthian_update_progress.py, the same code that
# draws it on the framebuffer when the UI is stopped during the update.
#
# Copyright (C) 2026 Brian Walton <riban@zynthian.org>
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
import sys
import logging
import tkinter
import importlib.util
from time import monotonic, time
from PIL import ImageTk

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_fullscreen_modal import zynthian_gui_fullscreen_modal

# Exists while an update is running (created/removed by the update scripts)
UPDATE_RUNNING_FILE = "/run/zynthian_update/running"
REFRESH_PERIOD_MS = 500
# Time showing the final state before closing the screen
CLOSE_DELAY = 3
# Max time waiting for the update to start (UPDATE_RUNNING_FILE created)
START_TIMEOUT = 30


def update_running():
    return os.path.isfile(UPDATE_RUNNING_FILE)


def load_progress_module():
    sys_dir = os.environ.get("ZYNTHIAN_SYS_DIR", "/zynthian/zynthian-sys")
    fpath = f"{sys_dir}/sbin/zynthian_update_progress.py"
    # Don't leave a __pycache__ in the zynthian-sys repository
    dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location("zynthian_update_progress", fpath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        logging.error(f"Can't load update progress renderer '{fpath}': {e}")
        return None
    finally:
        sys.dont_write_bytecode = dont_write_bytecode

# ------------------------------------------------------------------------------
# Zynthian Software Update Progress GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_update_progress(zynthian_gui_fullscreen_modal):

    def __init__(self):
        super().__init__()
        self.zyngui = zynthian_gui_config.zyngui
        self.canvas = tkinter.Canvas(self,
                                     width=self.width,
                                     height=self.height,
                                     bg="#000000",
                                     bd=0,
                                     highlightthickness=0)
        self.canvas.grid(sticky="nsew")
        self.image_id = None
        self.photo = None
        self.module = None
        self.renderer = None
        self.state = None
        self.timer = None
        self.finish_time = None
        self.show_time = 0
        self.started = False
        # Last stage message and hint announced by ZynVoice
        self.tts_message = None
        self.tts_hint = None

    def show(self):
        if not self.shown:
            # Reload each time: zynthian-sys may have been updated
            self.module = load_progress_module()
            if self.module:
                self.renderer = self.module.ProgressScreen(self.width, self.height)
                self.state = self.module.ProgressState()
            self.finish_time = None
            self.show_time = monotonic()
            self.started = False
            if self.state:
                self.tts_message = self.state.message
            self.tts_hint = None
            if self.zyngui.tts:
                self.zyngui.tts._tts.set_progress(0)
                self.zyngui.tts.announce("Software update in progress. Do not power off.")
        super().show()
        if self.timer is None:
            self.refresh()

    def hide(self):
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None
        if self.shown and self.zyngui.tts:
            self.zyngui.tts._tts.set_progress(None)
        super().hide()

    # --------------------------------------------------------------------------
    # ZynVoice: each stage change is spoken and a regular beep (pitch rising
    # with the percent complete) indicates the update is still running.
    # --------------------------------------------------------------------------

    def tts_update(self):
        if not self.zyngui.tts or not self.state:
            return
        tts = self.zyngui.tts
        if self.state.finished:
            tts._tts.set_progress(None)
        else:
            tts._tts.set_progress(self.state.percent)
        if self.state.message != self.tts_message:
            self.tts_message = self.state.message
            self.tts_hint = None
            # Replace any pending stage but let the current phrase finish
            tts.announce(self.tts_message, replace=True, interrupt=False)
        # Long stage hints (not the "still working" idle hint: the beep tells that)
        if self.state.hint and self.state.hint != self.tts_hint:
            self.tts_hint = self.state.hint
            tts.announce(self.tts_hint, replace=False, interrupt=False)

    def tts_info(self):
        """ Announce the current update status (TTS_TOGGLE_PLAYBACK) """
        if not self.zyngui.tts:
            return
        if not self.state:
            self.zyngui.tts.announce("Software update in progress. Do not power off.")
            return
        text = self.state.message
        if not self.state.finished:
            text += f". {self.state.percent} percent complete"
            minutes = int((time() - self.state.start_time) / 60)
            if minutes > 0:
                text += f". Running for {minutes} minute{'s' if minutes > 1 else ''}"
            if self.state.hint:
                text += f". {self.state.hint}"
            text += ". Do not power off."
        self.zyngui.tts.announce(text)

    def refresh(self):
        self.timer = None
        if not self.shown:
            return
        running = update_running()
        if running:
            self.started = True
        if self.module:
            try:
                # Before the update starts, the log is from a previous update
                if self.started:
                    self.state.read_log()
                    self.tts_update()
                self.photo = ImageTk.PhotoImage(self.renderer.render(self.state))
                if self.image_id is None:
                    self.image_id = self.canvas.create_image(0, 0, anchor='nw', image=self.photo)
                else:
                    self.canvas.itemconfig(self.image_id, image=self.photo)
            except Exception as e:
                logging.error(f"Can't render update progress: {e}")
        if running:
            self.finish_time = None
        elif not self.started:
            # Waiting for the update to start
            if monotonic() - self.show_time > START_TIMEOUT:
                logging.error("The software update didn't start!")
                self.zyngui.close_update_progress()
                return
        else:
            # Show the final state for a moment, then close
            if self.finish_time is None:
                self.finish_time = monotonic()
            elif monotonic() - self.finish_time > CLOSE_DELAY:
                self.zyngui.close_update_progress()
                return
        self.timer = self.after(REFRESH_PERIOD_MS, self.refresh)

    # Ignore user input while updating. When it has finished, any button closes the screen.
    def zynpot_cb(self, i, dval):
        pass

    def refresh_loading(self):
        pass

    def zyncoder_read(self):
        pass

    def switch(self, i, t='S'):
        if not update_running():
            self.zyngui.close_update_progress()
        return True

    def switch_select(self, t='S'):
        if not update_running():
            self.zyngui.close_update_progress()

    def back_action(self):
        # True => handled (screen stays)
        return update_running()

# -------------------------------------------------------------------------------
