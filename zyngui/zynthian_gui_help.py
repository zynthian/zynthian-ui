# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Help view class
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
from tkinterweb import HtmlFrame
import tkinter

# Zynthian specific modules
from zyngui import zynthian_gui_config

# ------------------------------------------------------------------------------
# Zynthian help view GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_help:

    ui_dir = os.environ.get('ZYNTHIAN_UI_DIR', "/zynthian/zynthian-ui")

    # Scale for touch swipe action after-roll
    touch_swipe_roll_scale = [1, 0, 1, 1, 2, 2, 2, 4, 4, 4, 4, 4]  # 1, 0, 1, 0, 1, 0, 1, 0,

    def __init__(self):
        self.shown = False
        self.zyngui = zynthian_gui_config.zyngui

        self.touch_motion_step = int(1.8 * zynthian_gui_config.font_size)
        self.touch_swipe_speed = 0
        # Set approx. here to avoid errors. Set accurately when list item selected
        self.touch_motion_last_dy = 0
        self.touch_swiping = False
        self.touch_push_ts = 0
        self.fpath = None
        self.tts_title = ""

        # Main Frame
        self.main_frame = HtmlFrame(zynthian_gui_config.top,
                                    width=zynthian_gui_config.display_width,
                                    height=zynthian_gui_config.display_height,
                                    vertical_scrollbar=False,
                                    messages_enabled=False)
        self.main_frame.grid_propagate(False)
        # Patch HtmlFrame widget
        self.main_frame.event_generate = self.main_frame.html.event_generate
        # Bind events
        self.main_frame.on_done_loading(self.done_loading)
        self.main_frame.bind("<Button-1>", self.cb_touch_push)
        self.main_frame.bind("<ButtonRelease-1>", self.cb_touch_release)
        self.main_frame.bind("<Button-4>", self.cb_scroll_wheel)
        self.main_frame.bind("<Button-5>", self.cb_scroll_wheel)
        self.main_frame.bind("<B1-Motion>", self.cb_touch_motion)

    def done_loading(self):
        self.zyngui.show_screen("help")

    def load_file(self, fpath):
        if os.path.isfile(fpath):
            try:
                self.main_frame.load_file("file:///" + self.ui_dir + "/" + fpath, force=True, insecure=True)
                self.fpath = fpath
                self.tts_title = f"{self.fpath.split('/')[-1][:-5]} help"
                return True
            except Exception as e:
                logging.error(f"Can't load HTML file => {e}")
        self.fpath = None
        return False

    def build_view(self):
        return True

    def hide(self):
        if self.shown:
            self.shown = False
            self.main_frame.place_forget()

    def show(self):
        if not self.shown:
            self.shown = True
            self.main_frame.grid_propagate(False)
            self.main_frame.place(x=0, y=0)
            if self.zyngui.tts:
                self.zyngui.tts.announce(f"View: {self.tts_title}", replace="True", interrupt=True)

    def zynpot_cb(self, i, dval):
        if i == 3:
            self.main_frame.yview_scroll(dval, "units")
        elif i == 2:
            if self.zyngui.tts._tts.playing or self.zyngui.tts._tts.paused:
                if dval > 0:
                    self.zyngui.tts._tts.next()
                else:
                    self.zyngui.tts._tts.prev()
        return True

    def switch(self, i, t):
        if i == 2 and t =='S':
            self.zyngui.cuia_tts_toggle_pause()
            return True

    def refresh_loading(self):
        pass

    def switch_select(self, t='S'):
        pass

    def arrow_up(self):
        self.main_frame.yview_scroll(-4, "units")

    def arrow_down(self):
        self.main_frame.yview_scroll(4, "units")

    def arrow_left(self):
        if self.zyngui.tts and self.zyngui.tts._tts.playing or self.zyngui.tts._tts.paused:
            self.zyngui.tts._tts.prev()

    def arrow_right(self):
        if self.zyngui.tts and self.zyngui.tts._tts.playing or self.zyngui.tts._tts.paused:
            self.zyngui.tts._tts.next()

    # --------------------------------------------------------------------------
    # Keyboard & Mouse/Touch Callbacks
    # --------------------------------------------------------------------------

    def cb_touch_push(self, event):
        if self.zyngui.cb_touch(event):
            return "break"
        self.touch_push_ts = event.time  # Timestamp of initial touch
        # logging.debug("LISTBOX PUSH => %s" % (self.listbox_push_ts))
        self.touch_y0 = event.y  # Touch y-coord of initial touch
        self.touch_x0 = event.x  # Touch x-coord of initial touch
        # True if swipe action in progress (disables press action)
        self.touch_swiping = False
        self.touch_swipe_speed = 0  # Speed of swipe used for rolling after release
        return "break"  # Don't select entry on push

    def cb_touch_motion(self, event):
        dy = self.touch_y0 - event.y
        offset_y = int(dy / self.touch_motion_step)
        if offset_y:
            self.touch_swiping = True
            self.main_frame.yview_scroll(offset_y, "units")
            self.touch_swipe_dir = abs(dy) // dy
            self.touch_y0 = event.y + self.touch_swipe_dir * (abs(dy) % self.touch_motion_step)
            # Use time delta between last motion and release to determine speed of swipe
            self.touch_push_ts = event.time

    def cb_touch_release(self, event):
        if self.zyngui.cb_touch_release(event):
            return "break"

        dts = (event.time - self.touch_push_ts)/1000
        if self.touch_swiping:
            self.touch_swipe_nudge(dts)
        else:
            # X-Swipe to close
            dx = self.touch_x0 - event.x
            if abs(dx) > 50:
                self.zyngui.cuia_back()

    def cb_scroll_wheel(self, event):
        dval = 1 if event.num else -1
        self.main_frame.yview_scroll(dval, "units")

    def touch_swipe_nudge(self, dts):
        self.touch_swipe_speed = int(len(self.touch_swipe_roll_scale) - ((dts - 0.02) / 0.06) * len(self.touch_swipe_roll_scale))
        self.touch_swipe_speed = min(
            self.touch_swipe_speed, len(self.touch_swipe_roll_scale) - 1)
        self.touch_swipe_speed = max(self.touch_swipe_speed, 0)

    def swipe_update(self):
        if self.touch_swipe_speed > 0:
            self.touch_swipe_speed -= 1
            self.main_frame.yview_scroll(self.touch_swipe_dir * self.touch_swipe_roll_scale[self.touch_swipe_speed], "units")

    def plot_zctrls(self):
        self.swipe_update()


    # --------------------------------------------------------------------------
    # Narrator TTS
    # --------------------------------------------------------------------------

    def tts_info(self):
        from bs4 import BeautifulSoup

        self.zyngui.tts.announce(f"View: {self.tts_title}")
        try:
            with open(self.fpath) as f:
                html = f.read()
            soup = BeautifulSoup(html, "html.parser")
            for div in soup.select("div.knobs_action_container"):
                div.decompose()  # removes the whole section
            text = soup.get_text(separator=" ", strip=True)
            for line in text.split(". "):
                self.zyngui.tts.announce(line, False, False, False)
        except:
            pass


# -------------------------------------------------------------------------------
