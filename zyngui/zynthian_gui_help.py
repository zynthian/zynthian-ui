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
import tkinter
from tkinterweb import HtmlFrame
from bs4 import BeautifulSoup
from pathlib import Path

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
        self.tts_knobs = []
        self.link = None
        self.links = []
        self.link_timer = None
        self.path = self.ui_dir + "/help"

        # Main Frame
        self.main_frame = HtmlFrame(zynthian_gui_config.top,
                                    width=zynthian_gui_config.display_width,
                                    height=zynthian_gui_config.display_height,
                                    vertical_scrollbar=False,
                                    messages_enabled=False)
        self.main_frame.grid_propagate(False)
        self.link_text = tkinter.Label(self.main_frame,
                                    font=zynthian_gui_config.font_topbar,
                                    bg=zynthian_gui_config.color_ctrl_bg_off,
                                    fg=zynthian_gui_config.color_ctrl_tx_off)
        self.loading_overlay = tkinter.Label(self.main_frame,
                                    font=zynthian_gui_config.font_topbar,
                                    bg=zynthian_gui_config.color_panel_bd,
                                    fg=zynthian_gui_config.color_ctrl_tx_off
                                    )
        # Patch HtmlFrame widget
        self.main_frame.event_generate = self.main_frame.html.event_generate
        # Bind events
        self.main_frame.on_done_loading(self.done_loading)
        self.main_frame.on_link_click(self.link_cb)
        self.main_frame.bind("<Button-1>", self.cb_touch_push)
        self.main_frame.bind("<ButtonRelease-1>", self.cb_touch_release, add="+")
        self.main_frame.bind("<Button-4>", self.cb_scroll_wheel)
        self.main_frame.bind("<Button-5>", self.cb_scroll_wheel)
        self.main_frame.bind("<B1-Motion>", self.cb_touch_motion)

    def done_loading(self):
        self.loading_overlay.place_forget()
        self.link_text.place_forget()
        self.zyngui.show_screen("help")
        if self.zyngui.tts:
            self.tts_info()

    def create_index(self):
        files = list(Path(f"{self.ui_dir}/help/core").glob("*.html")) + \
                list(Path(f"{self.ui_dir}/help/{zynthian_gui_config.layout['name']}").glob("*.html"))
        items = []
        files.sort(key=lambda f: f.name)
        for file in files:
            with open(file, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")
                # Try <title> first
                title_tag = soup.find("title")
                title = title_tag.get_text(strip=True) if title_tag else None
                # Fallback to <h1>
                if not title:
                    h1 = soup.find("h1")
                    title = h1.get_text(strip=True) if h1 else file.stem
                items.append((title, file._str))

        # Build index HTML
        html_output = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Index</title>
            <link rel="stylesheet" href="{self.ui_dir}/help/style.css">
        </head>
        <body>
            <h1>Index of zynthian help</h1>
        """

        for title, filename in items:
            html_output += f'<a href="{filename}">{title}</a><br>\n'
        html_output += """
        </body>
        </html>
        """
        return html_output

    def load_file(self, fpath):
        try:
            if fpath == "index:":
                html = self.create_index()
            else:
                with open(fpath) as f:
                    html = f.read()
            self.soup = BeautifulSoup(html, "html.parser")
            if fpath != "index:":
                with open(f"{self.ui_dir}/help/header.html") as f:
                    header_html = f.read()
                self.soup.body.insert(0, BeautifulSoup(header_html, "html.parser"))
                html = str(self.soup)

            # Extract hyperlinks
            self.link = None
            self.links = []
            for link in self.soup.find_all("a"):
                href = link.get("href")
                text = link.get_text(strip=True)
                self.links.append((href, text))
                link.insert_before("Link: ")

            self.path = os.path.dirname(fpath)
            self.loading_overlay.place(relwidth=1, relheight=1) # Avoid showing until fully rendered
            self.main_frame.load_html(html, base_url=f"file://{self.path}/")
            return True
        except Exception as e:
            logging.error(f"Can't load HTML file => {e}")
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

    def link_cb(self, url):
        self.zyngui.show_help(fpath=url)

    def zynpot_cb(self, i, dval):
        if i == 3:
            self.main_frame.yview_scroll(dval, "units")
            return True
        elif i == 2:
            if self.zyngui.tts:
                if dval > 0:
                    self.zyngui.tts._tts.next()
                else:
                    self.zyngui.tts._tts.prev()
            return True
        elif i == 0:
            if self.links:
                if self.link is None:
                    self.link = 0
                else:
                    self.link = min(max(0, self.link + dval), len(self.links) - 1)
                if self.link_timer is not None:
                    self.main_frame.after_cancel(self.link_timer)
                text = self.links[self.link][1]
                self.link_text.config(text=f"Link: {text}")
                self.link_text.place(relx=1.0, rely=0.0, anchor="ne")
                self.link_timer = self.main_frame.after(2000, self.link_text.place_forget)
                if self.zyngui.tts:
                    self.zyngui.tts.announce(f"Link: {text}")
            return True

    def cuia_v5_zynpot_switch(self, params):
        return self.switch(*params)

    def switch(self, i, t):
        if self.zyngui.tts:
            if i == 2:
                if t =='S':
                    self.zyngui.cuia_tts_toggle_pause()
                    return True
                elif t == 'B':
                    self.tts_controller_info()
                    return True
        if i == 0 and t =='S':
            if self.link is None:
                fpath = "index:"
            else:
                fpath = self.links[self.link][0]
                if len(fpath.split(":")) == 1:
                    fpath = f"{self.path}/{fpath}"

            self.zyngui.show_help(fpath=fpath)
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
        if self.zyngui.tts:
            self.zyngui.tts._tts.prev()

    def arrow_right(self):
        if self.zyngui.tts:
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
            else:
                return None

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
        if not self.zyngui.tts:
            return
        self.zyngui.tts.announce(f"Help page.")
        try:
            # Parse knob info
            self.tts_knobs = []
            knob_action_container = self.soup.find("div", class_="knobs_action_container")
            if knob_action_container:
                press_actions = ["Rotate to ", "Press to", "Bold press to"]
                for knob_idx in range(1, 5):
                    knob_action_div = self.soup.find("div", class_=f"knob_action_{knob_idx}")
                    if not knob_action_div:
                        continue
                    knob_text = f"Knob {knob_idx}. "
                    for i, action in enumerate(knob_action_div.find_all("div")):
                        if i > 2:
                            break
                        action_text = action.get_text()
                        if action_text and action_text != "---":
                            knob_text += f"{press_actions[i]} {action.get_text()}. "
                    self.tts_knobs.append(knob_text)
                knob_action_container.decompose()

            # Ensure brief pause after each header and paragraph
            for tag in self.soup.find_all(["p", "br", "h1", "h2", "h3"]):
                 tag.insert_after(". ")
            text = self.soup.get_text(separator=" ", strip=True).replace("\n", "")
            for line in text.split(". "):
                self.zyngui.tts.announce(line, False, False, False)
        except:
            pass

    def tts_controller_info(self):
        self.zyngui.tts.announce("Knob actions.")
        for tts in self.tts_knobs:
            self.zyngui.tts.announce(tts, False, False, False)
# -------------------------------------------------------------------------------
