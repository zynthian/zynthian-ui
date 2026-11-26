# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Software Update Progress Class
#
# Shows the software update progress while an update is running. The screen is
# rendered by zynthian-sys/sbin/zynthian_update_progress.py, the same code that
# draws it on the framebuffer when the UI is stopped during the update.
#
# Copyright (C) 2015-2026 Fernando Moyano <jofemodo@zynthian.org>
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
import logging
import tkinter
import importlib.util
from time import monotonic
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
    try:
        spec = importlib.util.spec_from_file_location("zynthian_update_progress", fpath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        logging.error(f"Can't load update progress renderer '{fpath}': {e}")
        return None

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
        super().show()
        if self.timer is None:
            self.refresh()

    def hide(self):
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None
        super().hide()

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

    # Ignore user input while updating
    def zynpot_cb(self, i, dval):
        pass

    def zyncoder_read(self):
        pass

    def switch_select(self, t='S'):
        pass

    def back_action(self):
        return True

# -------------------------------------------------------------------------------
