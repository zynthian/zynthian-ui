#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Engine Selector Class
#
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
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

import tkinter
import logging

# Zynthian specific modules
from zyngine import *
from zyngine import zynthian_lv2
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector
from zyngui.zynthian_gui_controller import zynthian_gui_controller

# ------------------------------------------------------------------------------
# Zynthian Engine Selection GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_engine(zynthian_gui_selector):

    engine_type_title = {
        "MIDI Synth": "MIDI Instrument",
        "Audio Effect": "Audio Effect",
        "MIDI Tool": "MIDI tool",
        "Audio Generator": "Audio Generator",
        "Special": "Special"
    }

    def __init__(self):
        # Custom layout for GUI engine
        self.layout = {
            'name': 'gui_engine',
            'columns': 2,
            'rows': 4,
            'ctrl_pos': [
                    (0, 1),
                    (1, 1),
                    (2, 1),
                    (3, 1)
            ],
            'list_pos': (0, 0),
            'ctrl_orientation': 'horizontal',
            'ctrl_order': (0, 1, 2, 3),
            'ctrl_width': 0.3
        }
        self.proc_type = None
        self.zsel2 = None
        self.cat_index = 0
        self.engine_cats = None
        self.context_index = {}
        self.show_all = False
        self.info_canvas = None
        super().__init__('Engine', True, False)

        self.chain_manager = self.zyngui.chain_manager
        self.engine_info = self.chain_manager.engine_info
        self.engine_info_dirty = False
        self.xswipe_sens = 10

        # Canvas for engine info
        self.info_canvas = tkinter.Canvas(
            self.main_frame,
            width=1,  # zynthian_gui_config.fw2, #self.width // 4 - 2,
            height=1,  # zynthian_gui_config.fh2, #self.height // 2 - 1,
            bd=0,
            highlightthickness=0,
            bg=zynthian_gui_config.color_bg)
        self.info_canvas.bind('<ButtonRelease-1>', self.cb_info_press)
        # Position at top of column containing selector
        self.info_canvas.grid(
            row=0, column=self.layout['list_pos'][1] + 1, rowspan=2, sticky="news")

        # Marker for category page
        # self.cat_marker_greyline = self.info_canvas.create_rectangle(0, 2, 0.25 * self.width, 4, fill=zynthian_gui_config.color_off)
        # self.cat_marker_marker = self.info_canvas.create_rectangle(0, 0, 0, 0, fill=zynthian_gui_config.color_on)

        # Info layout
        ctrl_width = int(self.layout['ctrl_width'] * self.width)
        star_fs = int(ctrl_width * 0.16)
        # color_star = zynthian_gui_config.color_ml
        color_star = zynthian_gui_config.color_on
        color_star_off = zynthian_gui_config.color_off
        xpos = int(0.1 * star_fs)
        ypos = int(-0.3 * star_fs)
        info_width = ctrl_width - xpos
        """
		self.quality_label = self.info_canvas.create_text(
			xpos,
			ypos,
			anchor=tkinter.NW,
			justify=tkinter.LEFT,
			width=info_width,
			text="Quality:",
			font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size),
			fill=zynthian_gui_config.color_panel_tx)
		ypos += int(1.2 * zynthian_gui_config.font_size)
		"""
        self.quality_stars_bg_label = self.info_canvas.create_text(
            xpos,
            ypos,
            anchor=tkinter.NW,
            justify=tkinter.CENTER,
            width=info_width,
            text="★★★★★",
            # text="✱✱✱✱✱",
            font=(zynthian_gui_config.font_family, star_fs),
            fill=color_star_off)
        self.quality_stars_label = self.info_canvas.create_text(
            xpos,
            ypos,
            anchor=tkinter.NW,
            justify=tkinter.CENTER,
            width=info_width,
            text="",
            font=(zynthian_gui_config.font_family, star_fs),
            fill=color_star)
        ypos += int(1.2 * star_fs)
        """
		self.complexity_label = self.info_canvas.create_text(
			xpos,
			ypos,
			anchor=tkinter.NW,
			justify=tkinter.LEFT,
			width=info_width,
			text="Complex:",
			font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size),
			fill=zynthian_gui_config.color_panel_tx)
		ypos += int(1.2 * zynthian_gui_config.font_size)
		"""
        self.complexity_stars_bg_label = self.info_canvas.create_text(
            xpos,
            ypos,
            anchor=tkinter.NW,
            justify=tkinter.CENTER,
            width=info_width,
            text="⚈⚈⚈⚈⚈",
            font=(zynthian_gui_config.font_family, star_fs),
            fill=color_star_off)
        self.complexity_stars_label = self.info_canvas.create_text(
            xpos,
            ypos,
            anchor=tkinter.NW,
            justify=tkinter.CENTER,
            width=info_width,
            text="",
            font=(zynthian_gui_config.font_family, star_fs),
            fill=color_star)
        ypos += int(1.6 * star_fs)

        self.description_label = self.info_canvas.create_text(
            xpos,
            ypos,
            anchor=tkinter.NW,
            justify=tkinter.LEFT,
            width=info_width,
            text="",
            # font=(zynthian_gui_config.font_family, int(0.8 * zynthian_gui_config.font_size)),
            font=("sans-serif", int(0.8 * zynthian_gui_config.font_size)),
            fill=zynthian_gui_config.color_panel_tx)

        """
		self.description_label = tkinter.Text(self.main_frame,
			width=info_width,
			height=1,
			wrap=tkinter.CHAR,
			font=(zynthian_gui_config.font_family, int(0.8 * zynthian_gui_config.font_size)),
			fg=zynthian_gui_config.color_panel_tx,
			bd=0,
			highlightthickness=0,
			bg=zynthian_gui_config.color_bg,
			padx=2,
			pady=2
		)
		self.description_label.grid(row=0, column=self.layout['list_pos'][1] + 1, rowspan=2, sticky="news")
		"""

    def update_layout(self):
        super().update_layout()
        if self.info_canvas:
            self.info_canvas.configure(height=int(0.5 * self.height))
            # self.description_label.configure(height=int(0.35 * self.height))

    def get_info(self, eng_code=None):
        if not eng_code:
            eng_code = self.list_data[self.index][0]
        try:
            return self.engine_info[eng_code]
        except:
            logging.info(f"Can't get info for engine '{eng_code}'")
            return {"QUALITY": 0, "COMPLEX": 0, "DESCR": ""}

    def update_info(self):
        eng_info = self.get_info()
        quality_stars = "★" * eng_info["QUALITY"]
        self.info_canvas.itemconfigure(
            self.quality_stars_label, text=quality_stars)
        complexity_stars = "⚈" * eng_info["COMPLEX"]
        self.info_canvas.itemconfigure(
            self.complexity_stars_label, text=complexity_stars)
        self.info_canvas.itemconfigure(
            self.description_label, text=eng_info["DESCR"])
        # self.description_label.delete("1.0", tkinter.END)
        # self.description_label.insert("1.0", eng_info["DESCR"])

    def show_details(self, eng_code=None):
        eng_info = self.get_info(eng_code)
        try:
            path = zynthian_lv2.engine_type_title[eng_info["TYPE"]]
        except:
            path = eng_info["TYPE"]
        if self.engine_cats:
            path = path + "/" + eng_info["CAT"]
        text = path + "\n"
        text += "Quality: " + "★" * eng_info["QUALITY"] + "\n"
        text += "Complexity: " + "⚈" * eng_info["COMPLEX"] + "\n\n"
        text += eng_info["DESCR"]
        self.zyngui.screens["details"].setup(eng_info["TITLE"], text)
        self.zyngui.show_screen("details")

    def get_engines_by_cat(self):
        self.chain_manager.get_engine_info()
        self.engine_info = self.chain_manager.engine_info
        self.proc_type = self.zyngui.modify_chain_status["type"]
        self.engines_by_cat = self.chain_manager.filtered_engines_by_cat(
            self.proc_type, all=self.show_all)
        self.engine_cats = list(self.engines_by_cat.keys())
        logging.debug(f"CATEGORIES => {self.engine_cats}")
        # self.engines_by_cat = sorted(self.engines_by_cat.items(), key=lambda kv: "!" if kv[0] is None else kv[0])

    def recall_context_index(self):
        try:
            self.index = self.context_index[self.proc_type +
                                            "#" + str(self.cat_index)]
        except:
            self.index = 0
            self.update_context_index()

    def update_context_index(self):
        self.context_index[self.proc_type + "#" +
                           str(self.cat_index)] = self.index

    def build_view(self):
        self.show_all = False
        self.get_engines_by_cat()
        self.recall_context_index()
        return super().build_view()

    def hide(self):
        try:
            self.context_index[self.zyngui.modify_chain_status["type"]] = self.index
        except:
            pass
        super().hide()

    def fill_list(self):
        self.list_data = []

        if self.proc_type in ("MIDI Tool", "Audio Effect"):
            self.list_data.append(("None", 0, "None", "None"))

        # Show a single category or all
        if self.engine_cats:
            if self.cat_index < 0:
                cats = self.engine_cats
            else:
                if self.cat_index >= len(self.engine_cats):
                    self.cat_index = len(self.engine_cats) - 1
                cats = [self.engine_cats[self.cat_index]]
        else:
            cats = []

        for cat in cats:
            infos = self.engines_by_cat[cat]

            # Add category header when showing several cats...
            if len(cats) > 1:
                self.list_data.append(
                    (None, len(self.list_data), "> {}".format(cat)))

            # Split engines in standalone & plugins
            # standalone = []
            # plugins = []
            # for eng in infos:
            # if eng[0:2] == "JV":
            # plugins.append(eng)
            # else:
            # standalone.append(eng)

            # Local function to add engines to the list
            def add_engines(engines):
                for eng in engines:
                    i = len(self.list_data)
                    info = infos[eng]
                    if self.show_all:
                        if info["ENABLED"]:
                            self.list_data.append(
                                (eng, i, "\u2612 " + info["TITLE"], info["NAME"]))
                        else:
                            self.list_data.append(
                                (eng, i, "\u2610 " + info["TITLE"], info["NAME"]))
                    else:
                        self.list_data.append(
                            (eng, i, info["TITLE"], info["NAME"]))

            # if len(standalone) > 0:
            # self.list_data.append((None, None, "> Standalone"))
            # add_engines(standalone)
            # if len(plugins) > 0:
            # self.list_data.append((None, None, "> Plugins"))
            # add_engines(plugins)

            add_engines(infos)

        # Display help if no engines are enabled ...
        if len(self.list_data) == 0:
            self.list_data.append(
                (None, len(self.list_data), "Bold-push to enable some engines"))
            self.index = 0
            self.update_context_index()

        if not self.show_all:
            self.engine_info_dirty = False

        super().fill_list()

    def select(self, index=None, set_zctrl=True):
        super().select(index, set_zctrl)
        self.update_info()
        self.update_context_index()

    def select_action(self, i, t='S'):
        if t == 'S':
            if i is not None and self.list_data[i][0]:
                engine = self.list_data[i][0]
                if self.show_all:
                    self.engine_info[engine]['ENABLED'] = not self.engine_info[engine]['ENABLED']
                    self.engine_info_dirty = True
                    self.update_list()
                else:
                    self.zyngui.modify_chain_status["engine"] = engine
                    if "chain_id" in self.zyngui.modify_chain_status:
                        # Modifying existing chain
                        if "processor" in self.zyngui.modify_chain_status:
                            # Replacing processor
                            pass
                        else:
                            slot_count = self.chain_manager.get_slot_count(
                                self.zyngui.modify_chain_status["chain_id"], self.zyngui.modify_chain_status["type"])
                            if self.zyngui.modify_chain_status["type"] == "Audio Effect":
                                # Check for fader position
                                post_fader = "post_fader" in self.zyngui.modify_chain_status and self.zyngui.modify_chain_status[
                                    "post_fader"]
                                fader_pos = self.chain_manager.get_chain(
                                    self.zyngui.modify_chain_status["chain_id"]).fader_pos
                                if post_fader and slot_count > fader_pos or not post_fader and slot_count > 0:
                                    ask_parallel = True
                                else:
                                    ask_parallel = False
                            else:
                                ask_parallel = slot_count > 0
                            if ask_parallel:
                                # Adding to slot with existing processor - choose parallel/series
                                self.zyngui.screens['option'].config(
                                    "Chain Mode", {"Series": False, "Parallel": True}, self.cb_add_parallel)
                                self.zyngui.show_screen('option')
                                return
                            else:
                                self.zyngui.modify_chain_status["parallel"] = False
                    else:
                        # Adding engine to new chain
                        self.zyngui.modify_chain_status["parallel"] = False
                        if engine == "AP":
                            # TODO: Better done with engine flag
                            self.zyngui.modify_chain_status["audio_thru"] = False
                        if self.zyngui.modify_chain_status["type"] in ("Audio Effect", "Audio Generator") and not self.zyngui.modify_chain_status["midi_thru"]:
                            self.zyngui.modify_chain_status["midi_chan"] = None
                    self.zyngui.modify_chain()
        elif t == 'B':
            if not self.back_action():
                self.show_all = True
                self.get_engines_by_cat()
                self.update_list()

    def back_action(self):
        if self.show_all:
            if self.engine_info_dirty:
                self.chain_manager.save_engine_info()
                self.engine_info_dirty = False
            self.show_all = False
            self.get_engines_by_cat()
            self.update_list()
            return True
        else:
            return False

    def arrow_right(self):
        self.zynpot_cb(2, 1)

    def arrow_left(self):
        self.zynpot_cb(2, -1)

    def switch(self, swi, t='S'):
        if swi == 2:
            if t == 'S':
                self.show_details()
                return True

    def cb_add_parallel(self, option, value):
        self.zyngui.modify_chain_status['parallel'] = value
        self.zyngui.modify_chain()

    def set_selector(self, zs_hidden=False):
        super().set_selector(zs_hidden)
        self.zselector.zctrl.engine = self
        if self.zsel2:
            self.zsel2.zctrl.set_options({'symbol': "cat_index", 'name': "Category", 'short_name': "Category",
                                         'value_min': 0, 'value_max': len(self.engine_cats) - 1, 'value': self.cat_index})
            self.zsel2.config(self.zsel2.zctrl)
            self.zsel2.show()
        else:
            zsel2_ctrl = zynthian_controller(self, "cat_index", {
                                             'name': "Category", 'short_name': "Category", 'value_min': 0, 'value_max': len(self.engine_cats) - 1, 'value': self.cat_index})
            self.zsel2 = zynthian_gui_controller(zynthian_gui_config.select_ctrl - 1, self.main_frame,
                                                 zsel2_ctrl, zs_hidden, selcounter=True, orientation=self.layout['ctrl_orientation'])
        if not self.zselector_hidden:
            self.zsel2.grid(row=self.layout['ctrl_pos'][2][0],
                            column=self.layout['ctrl_pos'][2][1], sticky="news", pady=(0, 1))

    def plot_zctrls(self):
        super().plot_zctrls()
        if self.zsel2.zctrl.is_dirty:
            self.zsel2.calculate_plot_values()
        self.zsel2.plot_value()

    def set_cat(self, cat_index):
        self.cat_index = cat_index
        self.recall_context_index()
        self.update_list()
        self.set_select_path()

    def zynpot_cb(self, i, dval):
        if not self.shown:
            return False
        # Use secondary selector to move across categories
        if self.zsel2 and self.zsel2.index == i:
            self.zsel2.zynpot_cb(dval)
            if self.cat_index != self.zsel2.zctrl.value:
                self.set_cat(self.zsel2.zctrl.value)
            return True
        else:
            return super().zynpot_cb(i, dval)

    def send_controller_value(self, zctrl):
        if not self.shown:
            return
        if zctrl.symbol == "cat_index":
            if self.cat_index != zctrl.value:
                self.set_cat(zctrl.value)
        if zctrl.symbol == "Engine":
            self.select(zctrl.value)

    def cb_listbox_motion(self, event):
        super().cb_listbox_motion(event)
        dx = self.listbox_x0 - event.x
        offset_x = int(self.xswipe_sens * dx / self.width)
        if offset_x:
            self.swiping = True
            self.listbox_x0 = event.x
            cat_index = self.cat_index + offset_x
            if 0 <= cat_index < len(self.engine_cats):
                self.set_cat(cat_index)

    def cb_info_press(self, event):
        self.show_details()

    def set_select_path(self):
        path = ""
        try:
            path = zynthian_lv2.engine_type_title[self.zyngui.modify_chain_status["type"]]
            # chain = self.chain_manager.chains[self.zyngui.modify_chain_status["chain_id"]].get_name()
            # path = f"{chain}#{path}"
        except:
            pass
        if self.engine_cats:
            path = path + "/" + self.engine_cats[self.cat_index]
        self.select_path.set(path)

# ------------------------------------------------------------------------------
