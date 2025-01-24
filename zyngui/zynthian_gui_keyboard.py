#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI keyboard Class
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
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
from threading import Timer
# import tkinter.font as tkFont

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zyngui import zynthian_gui_config

# ------------------------------------------------------------------------------
# Zynthian Onscreen Keyboard GUI Class
# ------------------------------------------------------------------------------

OSK_NUMPAD = 0
OSK_QWERTY = 1


# Class implements renaming dialog
class zynthian_gui_keyboard():

    # Function to initialise class
    #  function: Callback function called when <Enter> pressed
    def __init__(self):
        self.zyngui = zynthian_gui_config.zyngui
        self.columns = 10  # Quantity of columns in keyboard grid
        self.rows = 5  # Quantity of rows in keyboard grid
        self.shift = 0  # 0=Normal, 1=Shift, 2=Shift lock
        self.alt = False  # False=Normal, True=alternante char table (symbols)
        self.buttons = []  # Array of [rectangle id, label id] for buttons in keyboard layout
        self.selected_button = 45  # Index of highlighted button
        self.mode = OSK_QWERTY  # Keyboard layout mode
        self.ctrl_order = zynthian_gui_config.layout['ctrl_order']
        self.last_key = None # Last pressed key

        # Geometry vars
        self.width = zynthian_gui_config.screen_width
        self.height = zynthian_gui_config.screen_height - zynthian_gui_config.topbar_height


        # Fonts
        self.font_button = (zynthian_gui_config.font_family, int(1.2*zynthian_gui_config.font_size))

        # Create main frame
        self.main_frame = tkinter.Frame(zynthian_gui_config.top,
                                        width=zynthian_gui_config.screen_width,
                                        height=zynthian_gui_config.screen_height,
                                        bg=zynthian_gui_config.color_bg)
        self.main_frame.grid_propagate(False)

        # Display string being edited
        self.text_canvas = tkinter.Canvas(self.main_frame, width=self.width, height=zynthian_gui_config.topbar_height)
        self.text_label = self.text_canvas.create_text(self.width / 2, zynthian_gui_config.topbar_height / 2,
                                                       font=zynthian_gui_config.font_topbar,
                                                       # font=tkFont.Font(family=zynthian_gui_config.font_topbar[0],
                                                       # size= int(zynthian_gui_config.topbar_height * 0.8))
                                                       )
        self.text_canvas.grid(column=0, row=0, sticky="nsew")

        # Display keyboard grid
        self.key_canvas = tkinter.Canvas(self.main_frame, width=self.width, height=self.height, bg="grey")
        self.key_canvas.grid_propagate(False)
        self.key_canvas.grid(column=0, row=1, sticky="nesw")
        self.set_mode(OSK_QWERTY)

        self.hold_timer = Timer(0.8, self.bold_press)
        self.keypress_queue = []
        self.shown = False

    # Function to populate keyboard with keys for requested mode
    #  mode: OSK mode [OSK_NUMPAD | OSK_QWERTY]
    def set_mode(self, mode):
        self.mode = mode
        self.key_canvas.delete('all')
        self.buttons = []
        if mode == OSK_NUMPAD:
            self.columns = 6
            self.rows = 4
            span = 2
        else:
            self.columns = 10
            self.rows = 5
            span = 1
        self.key_width = (self.width - 2) / self.columns
        self.key_height = (self.height - 2) / self.rows
        for row in range(self.rows - 1):
            for col in range(0, self.columns, span):
                self.add_button("", col, row, span)
        row = row + 1
        # Add special keys
        self.btn_cancel = self.add_button('Cancel', 0, row, 2)
        if mode == OSK_NUMPAD:
            self.btn_space = self.add_button('0', 2, row, span)
            self.btn_delete = self.add_button('Del', 4, row, 1)
            self.btn_enter = self.add_button('Enter', 5, row, 1)
        else:
            self.btn_shift = self.add_button('⬆️', 2, row, 1)
            self.btn_alt = self.add_button('Alt', 3, row, 1)
            self.btn_space = self.add_button(' ', 4, row, 3)
            self.btn_delete = self.add_button('Del', 7, row, 1)
            self.btn_enter = self.add_button('Enter', 8, row, 2)
        self.highlight_box = self.key_canvas.create_rectangle(
            0, 0, self.key_width, self.key_height, outline="red", width=2)
        self.refresh_keys()

    # Function to draw keyboard
    def refresh_keys(self):
        if self.mode == OSK_NUMPAD:
            self.keys = ['1', '2', '3',
                         '4', '5', '6',
                         '7', '8', '9']
        elif self.alt:
            if self.shift:
                self.keys = ['\\', '|', '@', '/', '*', '=', '\"', '\'', '?', '¡',
                             'Ä', 'Ë', 'Ï', 'Ö', 'Ü', 'Â', 'Ê', 'Î', 'Ô', 'Û',
                             'Ñ', 'Ç', 'Ẅ', 'Ŵ', 'Ĉ', 'Ÿ', 'Ŷ', 'Ŝ', 'Ĝ', 'Ḧ',
                             'Ĥ', 'Ĵ', 'Ẑ', 'Ẍ', '{', '}', '~', '^', ':', '_']
            else:
                self.keys = ['á', 'é', 'í', 'ó', 'ú', 'à', 'è', 'ì', 'ò', 'ù',
                             'ä', 'ë', 'ï', 'ö', 'ü', 'â', 'ê', 'î', 'ô', 'û',
                             'ñ', 'ç', 'ẅ', 'ŵ', 'ẗ', 'ÿ', 'ŷ', 'ŝ', 'ĝ', 'ḧ',
                             'ĥ', 'ĵ', 'ẑ', 'ẍ', 'ĉ', '}', '~', '^', ':', '_']
        else:
            if self.shift:
                self.keys = ['!', '£', '$', '€', '%', '&', '(', ')', '+', '-',
                             'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P',
                             'A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', '[',
                             'Z', 'X', 'C', 'V', 'B', 'N', 'M', '<', '>', ']']
            else:
                self.keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0',
                             'q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p',
                             'a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', ';',
                             'z', 'x', 'c', 'v', 'b', 'n', 'm', ',', '.', '#']
        self.key_canvas.itemconfig("keycaps", text="")
        for index in range(len(self.keys)):
            self.key_canvas.itemconfig(self.buttons[index][1],
                                       text=self.keys[index],
                                       tags=("key:%d" % (index), "keycaps"))

    # Function to add a button to the keyboard
    #  label: Button label
    #  col: Column to add button
    #  row: Row to add button
    #  colspan: Column span [Default: 1]
    #  returns: Index of key in self.buttons[]
    def add_button(self, label, col, row, colspan=1):
        index = len(self.buttons)
        tag = "key:%d" % (index)
        r = self.key_canvas.create_rectangle(1 + self.key_width * col,
                                             1 + self.key_height * row,
                                             self.key_width * (col + colspan) - 1,
                                             self.key_height * (row + 1) - 1,
                                             tags=(tag),
                                             fill="black")
        l = self.key_canvas.create_text(1 + self.key_width * (col + colspan / 2),
                                        1 + self.key_height * (row + 0.5),
                                        text=label,
                                        fill="white",
                                        font=self.font_button,
                                        tags=(tag))
        self.key_canvas.tag_bind(tag, "<Button-1>", self.on_key_press)
        self.key_canvas.tag_bind(tag, "<ButtonRelease-1>", self.on_key_release)
        self.buttons.append([r, l])
        return index

    # Function to handle bold touchscreen press and hold
    def bold_press(self):
        self.deferred_key_press(self.last_key, True)
        if self.last_key != self.btn_delete:
            self.hold_timer = Timer(0.2, self.bold_press)
            self.hold_timer.start()


    # Function to handle key press
    #  event: Mouse event
    def on_key_press(self, event=None):
        tags = self.key_canvas.gettags(self.key_canvas.find_withtag(tkinter.CURRENT))
        if not tags:
            return
        dummy, index = tags[0].split(':')
        self.last_key = int(index)
        if self.last_key not in [self.btn_enter, self.btn_cancel]:
            self.deferred_key_press(self.last_key)
            self.hold_timer = Timer(0.8, self.bold_press)
            self.hold_timer.start()

    # Function to handle key release
    #  event: Mouse event
    def on_key_release(self, event=None):
        self.hold_timer.cancel()
        if self.last_key in [self.btn_enter, self.btn_cancel]:
            self.deferred_key_press(self.last_key)

    def deferred_key_press(self, key, bold=False):
        self.keypress_queue.append((key, bold))

    # Function to execute a key press
    #  key: Index of key
    #  bold: True if long / bold press
    def execute_key_press(self, key, bold=False):
        # TODO: Use button ID for special function to allow localisation
        self.selected_button = key
        shift = self.shift
        if key < len(self.keys):
            self.text = self.text + self.keys[key]
        elif key == self.btn_enter:
            self.zyngui.close_screen("keyboard")
            self.function(self.text)
            return
        elif key == self.btn_cancel:
            self.zyngui.cuia_back()
            return
        elif key == self.btn_delete:
            if bold:
                self.text = ""
            else:
                self.text = self.text[:-1]
        elif key == self.btn_space:
            if self.mode == OSK_NUMPAD:
                self.text = self.text + "0"
            else:
                self.text = self.text + " "
        elif key == self.btn_alt:
            self.alt = not self.alt
            if self.alt:
                self.key_canvas.itemconfig(self.buttons[self.btn_alt][0], fill="red")
            else:
                self.key_canvas.itemconfig(self.buttons[self.btn_alt][0], fill="black")
            self.refresh_keys()

        if key == self.btn_shift:
            self.shift += 1
            if self.shift > 2:
                self.shift = 0
        elif self.shift == 1:
            self.shift = 0

        if self.max_len:
            self.text = self.text[:self.max_len]

        if shift != self.shift:
            if self.shift == 1:
                self.key_canvas.itemconfig(self.buttons[self.btn_shift][0], fill="grey")
            elif self.shift == 2:
                self.key_canvas.itemconfig(self.buttons[self.btn_shift][0], fill="red")
            else:
                self.key_canvas.itemconfig(self.buttons[self.btn_shift][0], fill="black")
            self.refresh_keys()

        self.text_canvas.itemconfig(self.text_label, text=self.text)
        self.highlight(key)

    # Function to highlight key
    def highlight(self, key):
        box = self.key_canvas.bbox(self.buttons[key][0])
        if box:
            self.key_canvas.coords(self.highlight_box, box[0]+1, box[1]+1, box[2], box[3])

    # Function to hide dialog
    def hide(self):
        if self.shown:
            self.shown = False
            self.keypress_queue = []
            self.main_frame.grid_forget()

    # Function to show keyboard screen
    #  function: Function to call when "Enter" selected
    #  text: Text to display (Default: empty)
    #  max_len: Maximum quantity of characters in text (Default: no limit)
    def show(self, function, text="", max_len=None):
        if self.zyngui.test_mode:
            logging.warning("TEST_MODE: {}".format(self.__class__.__module__))

        self.keypress_queue = []
        self.function = function
        self.text = text
        if max_len:
            self.text = text[:max_len]
        self.max_len = max_len
        self.text_canvas.itemconfig(self.text_label, text=self.text)
        if not self.shown:
            self.selected_button = self.btn_enter
            self.shift = 0
            self.highlight(self.selected_button)
            self.setup_zynpots()
            self.refresh_keys()
            self.main_frame.grid(row=0, column=zynthian_gui_config.main_screen_column)
            self.shown = True

    # Function to register encoders
    def setup_zynpots(self):
        if zynthian_gui_config.num_zynpots > 3:
            lib_zyncore.setup_behaviour_zynpot(3, 1)
            lib_zyncore.setup_behaviour_zynpot(1, 1)

    # Function to handle zynpots events
    def zynpot_cb(self, i, dval):
        if not self.shown:
            return
        if i == self.ctrl_order[2]:
            self.cursor_vmove(dval)
        elif i == self.ctrl_order[3]:
            self.cursor_hmove(dval)

    def cursor_hmove(self, dval):
        key = self.selected_button + dval
        if key >= len(self.buttons):
            key = 0
        elif key < 0:
            key = len(self.buttons) - 1
        self.selected_button = key
        self.highlight(key)

    def cursor_vmove(self, dval):
        key = self.selected_button + self.columns * dval
        if self.mode == OSK_NUMPAD:
            if dval < 0 and self.selected_button < 3:
                key = self.selected_button + 9
            elif dval > 0 and self.selected_button > 8:
                if self.selected_button == self.btn_enter:
                    key = self.selected_button - 10
                else:
                    key = self.selected_button - 9
            else:
                if self.selected_button == self.btn_enter:
                    key = self.selected_button - 4
                else:
                    key = self.selected_button + 3 * dval
        else:
            if dval < 0:
                # Check first row - wrap to last row
                if self.selected_button in [0, 1]:
                    key = self.btn_cancel
                elif self.selected_button == 2:
                    key = self.btn_shift
                elif self.selected_button in range(3, 7):
                    key = self.btn_space
                elif self.selected_button == 7:
                    key = self.btn_delete
                elif self.selected_button in [8, 9]:
                    key = self.btn_enter
                # Check last row
                elif self.selected_button == self.btn_cancel:
                    key = (self.rows - 2) * self.columns
                elif self.selected_button == self.btn_shift:
                    key = (self.rows - 2) * self.columns + 2
                elif self.selected_button == self.btn_space:
                    key = (self.rows - 2) * self.columns + 3
                elif self.selected_button == self.btn_delete:
                    key = (self.rows - 2) * self.columns + 7
                elif self.selected_button == self.btn_enter:
                    key = (self.rows - 2) * self.columns + 8
            elif dval > 0:
                # Check penultimate row
                if self.selected_button in [30, 31]:
                    key = self.btn_cancel
                elif self.selected_button in [32]:
                    key = self.btn_shift
                elif self.selected_button in [33, 34, 35, 36]:
                    key = self.btn_space
                elif self.selected_button in [37]:
                    key = self.btn_delete
                elif self.selected_button in [38, 39]:
                    key = self.btn_enter
                # Check last row
                elif self.selected_button == self.btn_cancel:
                    key = 0
                elif self.selected_button == self.btn_shift:
                    key = 2
                elif self.selected_button == self.btn_space:
                    key = 3
                elif self.selected_button == self.btn_delete:
                    key = 7
                elif self.selected_button == self.btn_enter:
                    key = 8
        self.selected_button = key
        self.highlight(key)

    # Function to handle CUIA ARROW_UP
    def arrow_up(self):
        self.cursor_vmove(-1)

    # Function to handle CUIA ARROW_DOWN
    def arrow_down(self):
        self.cursor_vmove(1)

    # Function to handle CUIA ARROW_RIGHT
    def arrow_right(self):
        self.cursor_hmove(1)

    # Function to handle CUIA ARROW_LEFT
    def arrow_left(self):
        self.cursor_hmove(-1)

    # Function to handle select switch event
    def switch_select(self, typ="S"):
        self.execute_key_press(self.selected_button, typ == "B")

    # We are hijacking plot_zctrls that is called from the control thread
    # to execute deferred keypressed from touch
    def plot_zctrls(self):
        while self.keypress_queue:
            item = self.keypress_queue.pop()
            self.execute_key_press(item[0], item[1])

    # Function to refresh the loading screen => not used!
    def refresh_loading(self):
        pass

# ------------------------------------------------------------------------------
