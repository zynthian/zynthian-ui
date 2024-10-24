#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Base Class: Status Bar + Basic layout & events
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

import time
import logging
import tkinter
from threading import Timer
from tkinter import font as tkFont

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_dpm import zynthian_gui_dpm
from zyngine import zynthian_controller

# ------------------------------------------------------------------------------
# Zynthian Base GUI Class: Status Bar + Basic layout & events
# ------------------------------------------------------------------------------


class zynthian_gui_base(tkinter.Frame):
    # Default buttonbar config (touchwidget)
    buttonbar_config = []

    def __init__(self, has_backbutton=True):
        tkinter.Frame.__init__(self,
                               zynthian_gui_config.top,
                               width=zynthian_gui_config.display_width,
                               height=zynthian_gui_config.display_height)
        self.grid_propagate(False)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self.shown = False
        self.zyngui = zynthian_gui_config.zyngui

        self.topbar_allowed = True
        self.topbar_height = zynthian_gui_config.topbar_height
        self.sidebar_shown = True
        self.buttonbar_button = []

        # Geometry vars
        self.buttonbar_height = zynthian_gui_config.display_height // 7
        self.width = zynthian_gui_config.display_width
        # TODO: Views should use current height if they need dynamic changes else grow rows to fill main_frame
        if zynthian_gui_config.enable_touch_navigation and self.buttonbar_config:
            self.height = zynthian_gui_config.display_height - \
                self.topbar_height - self.buttonbar_height
        else:
            self.height = zynthian_gui_config.display_height - self.topbar_height

        # Status Area Parameters
        self.status_l = int(self.width * 0.25)
        self.status_h = self.topbar_height
        self.status_rh = max(2, int(self.status_h / 4))
        self.status_fs = int(0.36 * self.status_h)
        self.status_lpad = self.status_fs

        # Backbutton parameters
        if zynthian_gui_config.enable_touch_navigation:
            self.backbutton_width = self.topbar_height
            self.backbutton_height = self.topbar_height - 1
        else:
            self.backbutton_width = 0
            self.backbutton_height = 0

        # Title Area parameters
        self.title_canvas_width = zynthian_gui_config.display_width - \
            self.backbutton_width - self.status_l - self.status_lpad - 2
        self.select_path_font = tkFont.Font(
            family=zynthian_gui_config.font_topbar[0], size=zynthian_gui_config.font_topbar[1])
        self.select_path_width = 0
        self.select_path_offset = 0
        self.select_path_dir = 2

        self.status_error = None
        self.status_recplay = None
        self.status_midi = None
        self.status_midi_clock = None

        # Topbar's frame
        self.tb_frame = tkinter.Frame(self,
                                      width=zynthian_gui_config.display_width,
                                      height=self.topbar_height,
                                      bg=zynthian_gui_config.color_bg)
        self.tb_frame.grid_propagate(False)
        self.tb_frame.grid(row=0)
        col = 0

        # Canvas for menu button
        self.backbutton_canvas = tkinter.Canvas(self.tb_frame,
                                                width=self.backbutton_width,
                                                height=self.backbutton_height,
                                                bd=0,
                                                highlightthickness=0,
                                                relief='flat',
                                                bg=zynthian_gui_config.color_panel_bg)
        if has_backbutton and self.backbutton_width > 0:
            self.backbutton_canvas.grid(row=0, column=col, sticky="wn", padx=(0, self.status_lpad))
            self.backbutton_canvas.grid_propagate(False)
        self.backbutton_canvas.bind('<Button-1>', self.cb_backbutton)
        self.backbutton_canvas.bind(
            '<ButtonRelease-1>', self.cb_backbutton_release)
        self.backbutton_timer = None
        col += 1
        # Add back-arrow symbol
        self.label_backbutton = tkinter.Label(self.backbutton_canvas,
                                              font=zynthian_gui_config.font_topbar,
                                              text="<",
                                              bg=zynthian_gui_config.color_panel_bg,
                                              fg=zynthian_gui_config.color_tx)
        self.label_backbutton.place(relx=0.3, rely=0.5, anchor='w')
        self.label_backbutton.bind('<Button-1>', self.cb_backbutton)
        self.label_backbutton.bind(
            '<ButtonRelease-1>', self.cb_backbutton_release)

        # Title
        self.title = ""
        # font = tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=int(self.height * 0.05)),
        self.title_fg = zynthian_gui_config.color_panel_tx
        self.title_bg = zynthian_gui_config.color_header_bg
        self.title_canvas = tkinter.Canvas(self.tb_frame,
                                           height=self.topbar_height,
                                           bd=0,
                                           highlightthickness=0,
                                           bg=self.title_bg)
        self.tb_frame.grid_columnconfigure(col, weight=1)
        self.title_canvas.grid(row=0, column=col, sticky='ew')
        self.title_canvas.grid_propagate(False)
        # Setup Topbar's Callback
        if zynthian_gui_config.enable_touch_navigation:
            self.title_canvas.bind("<Button-1>", self.cb_topbar_press)
            self.title_canvas.bind("<ButtonRelease-1>", self.cb_topbar_release)
        self.path_canvas = self.title_canvas
        self.topbar_timer = None
        self.title_timer = None
        self.status_timer = None
        col += 1

        # Topbar's Select Path
        self.select_path = tkinter.StringVar()
        self.select_path.trace(tkinter.W, self.cb_select_path)
        self.label_select_path = tkinter.Label(self.title_canvas,
                                               font=zynthian_gui_config.font_topbar,
                                               textvariable=self.select_path,
                                               bg=zynthian_gui_config.color_header_bg,
                                               fg=zynthian_gui_config.color_header_tx)
        self.label_select_path.place(x=0, rely=0.5, anchor='w')
        # Setup Topbar's Callback
        if zynthian_gui_config.enable_touch_navigation:
            self.label_select_path.bind('<Button-1>', self.cb_topbar_press)
            self.label_select_path.bind('<ButtonRelease-1>', self.cb_topbar_release)

        # Canvas for displaying status
        self.status_canvas = tkinter.Canvas(self.tb_frame,
                                            width=self.status_l + 2,
                                            height=self.status_h,
                                            bd=0,
                                            highlightthickness=0,
                                            relief='flat',
                                            bg=zynthian_gui_config.color_bg)
        self.status_canvas.grid(row=0, column=col, sticky="ens", padx=(self.status_lpad, 0))
        # Set Status Callaback
        if zynthian_gui_config.enable_touch_navigation:
            self.status_canvas.bind('<Button-1>', self.cb_status_press)
            self.status_canvas.bind('<ButtonRelease-1>', self.cb_status_release)

        # Topbar parameter editor
        self.param_editor_zctrl = None

        # Main Frame
        self.main_frame = tkinter.Frame(self, bg=zynthian_gui_config.color_bg)
        self.main_frame.propagate(False)
        self.main_frame.grid(row=1, sticky='news')

        # Init touchbar
        self.buttonbar_frame = None
        self.bg_color = zynthian_gui_config.color_panel_bg
        self.fg_color = zynthian_gui_config.color_header_tx
        self.init_buttonbar()

        self.button_push_ts = 0

        self.main_mute = 0
        self.init_status()
        self.init_dpmeter()

        # Update Title
        self.set_select_path()
        self.cb_scroll_select_path()

        # TODO: Consolidate set_title and set_select_path, etc.
        self.disable_param_editor()
        self.bind("<Configure>", self.on_size)

    def show_back_button(self, show=True):
        if show:
            self.backbutton_canvas.grid(
                row=0, column=0, sticky="wn", padx=(0, self.status_lpad))
            self.backbutton_canvas.grid_propagate(False)
        else:
            self.backbutton_canvas.grid_remove()

    # Function to update title
    # title: Title to display in topbar
    # fg: Title foreground colour [Default: Do not change]
    # bg: Title background colour [Default: Do not change]
    # timeout: If set, title is shown for this period (seconds) then reverts to previous title

    def set_title(self, title, fg=None, bg=None, timeout=None):
        if self.title_timer:
            self.title_timer.cancel()
            self.title_timer = None
        if timeout:
            self.title_timer = Timer(timeout, self.on_title_timeout)
            self.title_timer.start()
        else:
            self.title = title
            if fg:
                self.title_fg = fg
            if bg:
                self.title_bg = bg
        self.select_path.set(title)
        # self.title_canvas.itemconfig("lblTitle", text=title, fill=self.title_fg)
        if fg:
            self.label_select_path.config(fg=fg)
        else:
            self.label_select_path.config(fg=self.title_fg)
        if bg:
            self.title_canvas.configure(bg=bg)
            self.label_select_path.config(bg=bg)
        else:
            self.title_canvas.configure(bg=self.title_bg)
            self.label_select_path.config(bg=self.title_bg)

    # Function called when frame resized
    def on_size(self, event):
        self.update_layout()
        # self.width = self.main_frame.winfo_width()
        # self.height = self.main_frame.winfo_height()

    # Function to revert title after toast
    def on_title_timeout(self):
        if self.title_timer:
            self.title_timer.cancel()
            self.title_timer = None
        self.set_title(self.title)

    # Initialise button bar
    # config: Buttonbar config (default is None to use default configuration hardcoded per view)
    def init_buttonbar(self, config=None):
        if self.buttonbar_frame:
            self.buttonbar_frame.grid_forget()
        if config is None:
            config = self.buttonbar_config
        if not zynthian_gui_config.enable_touch_navigation or not config:
            return

        self.buttonbar_frame = tkinter.Frame(self,
                                             width=zynthian_gui_config.display_width,
                                             height=self.buttonbar_height,
                                             bg=zynthian_gui_config.color_bg)
        self.buttonbar_frame.grid(row=2, padx=(0, 0), pady=(0, 0))
        self.buttonbar_frame.grid_propagate(False)
        self.buttonbar_frame.grid_rowconfigure(
            0, minsize=self.buttonbar_height, pad=0)
        for i in range(max(4, len(config))):
            self.buttonbar_frame.grid_columnconfigure(
                i,
                weight=1,
                uniform='buttonbar',
                pad=0)
            try:
                self.add_button(i, config[i][0], config[i][1])
            except Exception as e:
                logging.error(e)

    # Set the label for a button in the buttonbar
    # column: Column / button index
    # label: Text to show on label
    def set_buttonbar_label(self, column, label):
        if len(self.buttonbar_button) > column and self.buttonbar_button[column]:
            self.buttonbar_button[column]['text'] = label

    # Add a button to the buttonbar
    # column: Column / button index
    # cuia: Action to trigger when button pressed
    # label: Text to show on button
    def add_button(self, column, cuia, label):
        # Touchbar frame
        padx = (0, 0)
        for col in range(column):
            if col == 0:
                self.buttonbar_button[col].grid(row=0, column=col, padx=(0, 1))
            elif col < len(self.buttonbar_button):
                self.buttonbar_button[col].grid(row=0, column=col, padx=(1, 1))
            padx = (1, 0)
        self.buttonbar_button.append(None)
        self.buttonbar_button[column] = select_button = tkinter.Button(
            self.buttonbar_frame,
            bg=self.bg_color,
            fg=self.fg_color,
            activebackground=self.bg_color,
            activeforeground=self.fg_color,
            highlightbackground=self.bg_color,
            highlightcolor=self.bg_color,
            highlightthickness=0,
            bd=0,
            relief='flat',
            font=zynthian_gui_config.font_buttonbar,
            text=label)
        select_button.cuia = cuia
        select_button.grid(row=0, column=column, sticky='nswe', padx=padx)
        select_button.bind('<ButtonPress-1>', self.cb_button_push)
        select_button.bind('<ButtonRelease-1>', self.cb_button_release)

    # Handle buttonbar button press
    # event: Button event (not used)
    def cb_button_push(self, event):
        self.button_push_ts = time.monotonic()

    # Handle buttonbar button release
    # cuia: Action to trigger
    # event: Button event (not used)
    def cb_button_release(self, event):
        cuia = event.widget.cuia
        if isinstance(cuia, int):
            t = 'S'
            if self.button_push_ts:
                dts = (time.monotonic() - self.button_push_ts)
                if dts < zynthian_gui_config.zynswitch_bold_seconds:
                    t = 'S'
                elif zynthian_gui_config.zynswitch_bold_seconds <= dts < zynthian_gui_config.zynswitch_long_seconds:
                    t = 'B'
                elif dts >= zynthian_gui_config.zynswitch_long_seconds:
                    t = 'L'
            self.zyngui.callable_ui_action("zynswitch", (cuia, t))
        else:
            self.zyngui.callable_ui_action_params(cuia)

    # Invert BG & FG colors depending of returned status
    def set_button_status(self, column, status=False):
        if 0 <= column < len(self.buttonbar_button):
            if status:
                self.buttonbar_button[column].config(bg=self.fg_color,
                                                     fg=self.bg_color,
                                                     activebackground=self.fg_color,
                                                     activeforeground=self.bg_color,
                                                     highlightbackground=self.fg_color,
                                                     highlightcolor=self.fg_color)
            else:
                self.buttonbar_button[column].config(bg=self.bg_color,
                                                     fg=self.fg_color,
                                                     activebackground=self.bg_color,
                                                     activeforeground=self.fg_color,
                                                     highlightbackground=self.bg_color,
                                                     highlightcolor=self.bg_color)

    # Default topbar touch callback
    def cb_topbar_press(self, params=None):
        self.topbar_timer = Timer(
            zynthian_gui_config.zynswitch_long_seconds, self.cb_topbar_long)
        self.topbar_timer.start()
        self.topbar_press_time = time.monotonic()

    # Default topbar release callback
    def cb_topbar_release(self, params=None):
        if self.topbar_timer:
            self.topbar_timer.cancel()
            self.topbar_timer = None
            if time.monotonic() - self.topbar_press_time > zynthian_gui_config.zynswitch_bold_seconds:
                self.topbar_bold_touch_action()
            else:
                self.topbar_short_touch_action()

    # Default topbar long press callback
    def cb_topbar_long(self, params=None):
        if self.topbar_timer:
            self.topbar_timer.cancel()
            self.topbar_timer = None
            self.topbar_long_touch_action()

    # Default topbar short touch action
    def topbar_short_touch_action(self):
        self.zyngui.callable_ui_action("menu")

    # Default topbar bold touch action
    def topbar_bold_touch_action(self):
        self.zyngui.callable_ui_action('screen_zynpad')

    # Default topbar long touch action
    def topbar_long_touch_action(self):
        self.zyngui.callable_ui_action('screen_admin')

    # Default status touch callback
    def cb_status_press(self, params=None):
        self.status_timer = Timer(
            zynthian_gui_config.zynswitch_long_seconds, self.cb_status_long)
        self.status_timer.start()
        self.status_press_time = time.monotonic()

    # Default status release callback
    def cb_status_release(self, params=None):
        if self.status_timer:
            self.status_timer.cancel()
            self.status_timer = None
            if time.monotonic() - self.status_press_time > zynthian_gui_config.zynswitch_bold_seconds:
                self.status_bold_touch_action()
            else:
                self.status_short_touch_action()

    # Default status long press callback
    def cb_status_long(self, params=None):
        if self.status_timer:
            self.status_timer.cancel()
            self.status_timer = None
            self.status_long_touch_action()

    # Default status short touch action
    def status_short_touch_action(self):
        self.zyngui.callable_ui_action('tempo')

    # Default status bold touch action
    def status_bold_touch_action(self):
        self.zyngui.callable_ui_action('screen_zs3')

    # Default status long touch action
    def status_long_touch_action(self):
        # self.zyngui.callable_ui_action('screen_snapshot')
        self.zyngui.callable_ui_action('all_sounds_off')

    # ---------------------------------
    # Backbutton touch event management
    # ---------------------------------

    # Default menu button touch callback
    def cb_backbutton(self, params=None):
        self.backbutton_timer = Timer(
            zynthian_gui_config.zynswitch_long_seconds, self.cb_backbutton_long)
        self.backbutton_timer.start()
        self.backbutton_press_time = time.monotonic()

    # Default menu button release callback
    def cb_backbutton_release(self, params=None):
        if self.backbutton_timer:
            self.backbutton_timer.cancel()
            self.backbutton_timer = None
            if time.monotonic() - self.backbutton_press_time > zynthian_gui_config.zynswitch_bold_seconds:
                self.backbutton_bold_touch_action()
            else:
                self.backbutton_short_touch_action()

    # Default backbutton long press callback
    def cb_backbutton_long(self, params=None):
        if self.backbutton_timer:
            self.backbutton_timer.cancel()
            self.backbutton_timer = None
            self.backbutton_long_touch_action()

    # Default backbutton short touch action
    def backbutton_short_touch_action(self):
        self.zyngui.callable_ui_action('zynswitch', (1, 'S'))

    # Default backbutton bold touch action
    def backbutton_bold_touch_action(self):
        self.zyngui.callable_ui_action('zynswitch', (1, 'B'))

    # Default backbutton long touch action
    def backbutton_long_touch_action(self):
        self.zyngui.callable_ui_action('zynswitch', (1, 'L'))

    # ---------------------------------
    # Layout managing methods
    # ---------------------------------

    # Draw screen ready to display (like double buffer) - Override in subclass
    def build_view(self):
        return True

    # Show the view
    def show(self):
        if not self.shown:
            if self.zyngui.test_mode:
                logging.warning("TEST_MODE: {}".format(
                    self.__class__.__module__))
            self.shown = True
            self.refresh_status()
            self.grid(row=0, column=0, sticky='nsew')
            self.propagate(False)
        self.main_frame.focus()

    # Hide the view
    def hide(self):
        if self.shown:
            if self.param_editor_zctrl:
                self.disable_param_editor()
            self.shown = False
            self.grid_remove()

    # Show topbar (if allowed)
    # show: True to show, False to hide
    def show_topbar(self, show):
        if self.topbar_allowed:
            if show:
                self.topbar_height = zynthian_gui_config.topbar_height
                self.tb_frame.grid()
            else:
                self.topbar_height = 0
                self.tb_frame.grid_remove()
            self.update_layout()

    # Show buttonbar (if configured)
    # show: True to show, False to hide
    def show_buttonbar(self, show):
        if show:
            self.init_buttonbar()
        elif self.buttonbar_frame:
            self.buttonbar_frame.grid_remove()
        self.update_layout()

    # Show sidebar (override in derived classes if required)
    # show: True to show, False to hide
    def show_sidebar(self, show):
        pass

    def init_status(self):
        self.status_mute = self.status_canvas.create_text(
            int(self.status_l - self.status_fs * 1.3), 0,
            anchor=tkinter.NE,
            fill=zynthian_gui_config.color_status_error,
            font=("forkawesome", self.status_fs),
            text="\uf32f",
            state=tkinter.HIDDEN)

        self.status_error = self.status_canvas.create_text(
            self.status_l, 0,
            anchor=tkinter.NE,
            fill=zynthian_gui_config.color_bg,
            font=("forkawesome", self.status_fs),
            text="")

        self.status_audio_rec = self.status_canvas.create_text(
            0,
            self.status_h - 2,
            anchor=tkinter.SW,
            fill=zynthian_gui_config.color_status_record,
            font=("forkawesome", self.status_fs),
            text="\uf111",
            state=tkinter.HIDDEN)

        self.status_audio_play = self.status_canvas.create_text(
            int(self.status_fs * 1.3),
            self.status_h - 2,
            anchor=tkinter.SW,
            fill=zynthian_gui_config.color_status_play,
            font=("forkawesome", self.status_fs),
            text="\uf04b",
            state=tkinter.HIDDEN)

        self.status_midi_rec = self.status_canvas.create_text(
            int(self.status_fs * 2.6),
            self.status_h - 2,
            anchor=tkinter.SW,
            fill=zynthian_gui_config.color_status_play_midi,
            font=("forkawesome", self.status_fs),
            text="\uf111",
            state=tkinter.HIDDEN)

        self.status_midi_play = self.status_canvas.create_text(
            int(self.status_fs * 3.9),
            self.status_h - 2,
            anchor=tkinter.SW,
            fill=zynthian_gui_config.color_status_play_midi,
            font=("forkawesome", self.status_fs),
            text="\uf04b",
            state=tkinter.HIDDEN
        )

        self.status_seq_rec = self.status_canvas.create_text(
            int(self.status_fs * 5.2),
            self.status_h - 2,
            anchor=tkinter.SW,
            fill=zynthian_gui_config.color_status_play_seq,
            font=("forkawesome", self.status_fs),
            text="\uf111",
            state=tkinter.HIDDEN
        )

        self.status_seq_play = self.status_canvas.create_text(
            int(self.status_fs * 6.5),
            self.status_h - 2,
            anchor=tkinter.SW,
            fill=zynthian_gui_config.color_status_play_seq,
            font=("forkawesome", self.status_fs),
            text="\uf04b",
            state=tkinter.HIDDEN)

        self.status_midi = self.status_canvas.create_text(
            self.status_l,
            self.status_h - 2,
            anchor=tkinter.SE,
            fill=zynthian_gui_config.color_status_midi,
            font=("forkawesome", self.status_fs),
            text="m",
            state=tkinter.HIDDEN)

        self.status_midi_clock = self.status_canvas.create_line(
            int(self.status_l - self.status_fs * 1.3),
            int(self.status_h * 0.9),
            int(self.status_l),
            int(self.status_h * 0.9),
            fill=zynthian_gui_config.color_status_midi,
            state=tkinter.HIDDEN)

    def init_dpmeter(self):
        width = int(self.status_l - 2 * self.status_rh - 1)
        height = int(self.status_h / 4 - 2)
        self.dpm_a = zynthian_gui_dpm(self.zyngui.state_manager.zynmixer, self.zyngui.state_manager.zynmixer.MAX_NUM_CHANNELS -
                                      1, 0, self.status_canvas, 0, 0, width, height, False, ("status_dpm"))
        self.dpm_b = zynthian_gui_dpm(self.zyngui.state_manager.zynmixer, self.zyngui.state_manager.zynmixer.MAX_NUM_CHANNELS -
                                      1, 1, self.status_canvas, 0, height + 2, width, height, False, ("status_dpm"))

    def refresh_status(self):
        if self.shown:
            mute = self.zyngui.state_manager.zynmixer.get_mute(
                self.zyngui.state_manager.zynmixer.MAX_NUM_CHANNELS - 1)
            if True:  # mute != self.main_mute:
                self.main_mute = mute
                if mute:
                    self.status_canvas.itemconfigure(
                        self.status_mute, state=tkinter.NORMAL)
                    if self.dpm_a:
                        self.status_canvas.itemconfigure(
                            'status_dpm', state=tkinter.HIDDEN)
                else:
                    self.status_canvas.itemconfigure(
                        self.status_mute, state=tkinter.HIDDEN)
                    if self.dpm_a:
                        self.status_canvas.itemconfigure(
                            'status_dpm', state=tkinter.NORMAL)
            if not mute and self.dpm_a:
                state = self.zyngui.state_manager.zynmixer.get_dpm_states(
                    self.zyngui.state_manager.zynmixer.MAX_NUM_CHANNELS - 1, self.zyngui.state_manager.zynmixer.MAX_NUM_CHANNELS - 1)[0]
                self.dpm_a.refresh(state[0], state[2], state[4])
                self.dpm_b.refresh(state[1], state[3], state[4])

            # status['xrun'] = True;

            # Display error flags
            flags = ""
            color = zynthian_gui_config.color_status_error
            if self.zyngui.state_manager.status_xrun:
                color = zynthian_gui_config.color_status_error
                # flags = "\uf00d"
                flags = "\uf071"
            elif self.zyngui.state_manager.status_undervoltage:
                flags = "\uf0e7"
            elif self.zyngui.state_manager.status_overtemp:
                color = zynthian_gui_config.color_status_error
                # flags = "\uf2c7"
                flags = "\uf769"
            else:
                cpu_load = self.zyngui.state_manager.status_cpu_load
                if cpu_load < 50:
                    cr = 0
                    cg = 0xCC
                elif cpu_load < 75:
                    cr = int((cpu_load - 50) * 0XCC / 25)
                    cg = 0xCC
                else:
                    cr = 0xCC
                    cg = int((100 - cpu_load) * 0xCC / 25)
                color = "#%02x%02x%02x" % (cr, cg, 0)
                if self.zyngui.state_manager.update_available:
                    flags = "\u21bb"
                else:
                    flags = "\u2665"

            self.status_canvas.itemconfig(
                self.status_error, text=flags, fill=color)

            # Display Audio Rec flag
            flags = ""
            color = zynthian_gui_config.color_bg
            if self.zyngui.state_manager.audio_recorder.status:
                self.status_canvas.itemconfig(
                    self.status_audio_rec, state=tkinter.NORMAL)
            else:
                self.status_canvas.itemconfig(
                    self.status_audio_rec, state=tkinter.HIDDEN)

            # Display Audio Play flag
            flags = ""
            color = zynthian_gui_config.color_bg
            if self.zyngui.state_manager.status_audio_player:
                self.status_canvas.itemconfig(
                    self.status_audio_play, state=tkinter.NORMAL)
            else:
                self.status_canvas.itemconfig(
                    self.status_audio_play, state=tkinter.HIDDEN)

            # Display MIDI Rec flag
            flags = ""
            color = zynthian_gui_config.color_status_midi
            if self.zyngui.state_manager.status_midi_recorder:
                self.status_canvas.itemconfig(
                    self.status_midi_rec, state=tkinter.NORMAL)
            else:
                self.status_canvas.itemconfig(
                    self.status_midi_rec, state=tkinter.HIDDEN)

            # Display MIDI Play flag
            if self.zyngui.state_manager.status_midi_player:
                self.status_canvas.itemconfig(
                    self.status_midi_play, state=tkinter.NORMAL)
            else:
                self.status_canvas.itemconfig(
                    self.status_midi_play, state=tkinter.HIDDEN)
            # Display SEQ Rec flag
            if self.zyngui.state_manager.zynseq.libseq.isMidiRecord():
                self.status_canvas.itemconfig(
                    self.status_seq_rec, state=tkinter.NORMAL)
            else:
                self.status_canvas.itemconfig(
                    self.status_seq_rec, state=tkinter.HIDDEN)

            # Display SEQ Play flag
            if self.zyngui.state_manager.zynseq.libseq.getPlayingSequences() > 0:
                self.status_canvas.itemconfig(
                    self.status_seq_play, state=tkinter.NORMAL)
            else:
                self.status_canvas.itemconfig(
                    self.status_seq_play, state=tkinter.HIDDEN)

            # Display MIDI activity flag
            if self.zyngui.state_manager.status_midi:
                self.status_canvas.itemconfig(
                    self.status_midi, state=tkinter.NORMAL)
            else:
                self.status_canvas.itemconfig(
                    self.status_midi, state=tkinter.HIDDEN)

            # Display MIDI clock flag
            if self.zyngui.state_manager.status_midi_clock:
                self.status_canvas.itemconfig(
                    self.status_midi_clock, state=tkinter.NORMAL)
            else:
                self.status_canvas.itemconfig(
                    self.status_midi_clock, state=tkinter.HIDDEN)

    def refresh_loading(self):
        pass

    # --------------------------------------------------------------------------
    # Zynpot Callbacks (rotaries!) & CUIA
    # --------------------------------------------------------------------------

    def zynpot_cb(self, i, dval):
        if self.param_editor_zctrl:
            ctrl_order = zynthian_gui_config.layout['ctrl_order']
            if i == ctrl_order[3]:
                self.param_editor_zctrl.nudge(dval)
            elif i == ctrl_order[2]:
                self.param_editor_zctrl.nudge(dval * 10)
            else:
                return True
            self.update_param_editor()
            return True

    def zctrl_touch(self, switch):
        pass

    # Function to handle switch press
    #   switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
    #   typ: Press type ["S"=Short, "B"=Bold, "L"=Long]
    #   returns True if action fully handled or False if parent action should be triggered
    # Default implementation does nothing. Override to implement bespoke behaviour for legacy switches
    def switch(self, switch, typ):
        return False

    # Function to handle SELECT button press
    # typ: Button press duration ["S"=Short, "B"=Bold, "L"=Long]
    def switch_select(self, typ='S'):
        if self.param_editor_zctrl:
            if typ == 'S':
                if self.param_editor_assert_cb:
                    self.param_editor_assert_cb(self.param_editor_zctrl.value)
                self.disable_param_editor()
                return True
            elif typ == 'B':
                self.param_editor_zctrl.set_value(
                    self.param_editor_zctrl.value_default)
            self.update_param_editor()
            return True

    def back_action(self):
        if self.param_editor_zctrl:
            self.disable_param_editor()
            return True
        return False

    # --------------------------------------------------------------------------
    # MIDI learning
    # --------------------------------------------------------------------------

    def enter_midi_learn(self):
        pass

    def exit_midi_learn(self):
        pass

    # --------------------------------------------------------------------------
    # Mouse/Touch Callbacks
    # --------------------------------------------------------------------------

    def cb_select_path(self, *args):
        self.select_path_width = self.select_path_font.measure(self.select_path.get())
        self.select_path_offset = 0
        self.select_path_dir = 2
        self.label_select_path.place(x=0, rely=0.5, anchor='w')

    def cb_scroll_select_path(self):
        if self.shown:
            if self.dscroll_select_path():
                zynthian_gui_config.top.after(1000, self.cb_scroll_select_path)
                return
        zynthian_gui_config.top.after(100, self.cb_scroll_select_path)

    def dscroll_select_path(self):
        if self.shown:
            if self.select_path_width > self.title_canvas_width:
                # Scroll label
                self.select_path_offset += self.select_path_dir
                self.label_select_path.place(x=-self.select_path_offset, rely=0.5, anchor='w')

                # Change direction ...
                if self.select_path_offset > (self.select_path_width - self.title_canvas_width):
                    self.select_path_dir = -2
                    return True
                elif self.select_path_offset <= 0:
                    self.select_path_dir = 2
                    return True

            elif self.select_path_offset != 0:
                self.select_path_offset = 0
                self.select_path_dir = 2
                self.label_select_path.place(x=0, rely=0.5, anchor='w')
        return False

    def set_select_path(self):
        pass

    # Function to update display, e.g. after geometry changes
    # Override if required
    def update_layout(self):
        if zynthian_gui_config.enable_touch_navigation and self.buttonbar_config:
            self.height = zynthian_gui_config.display_height - \
                self.topbar_height - self.buttonbar_height
        else:
            self.height = zynthian_gui_config.display_height - self.topbar_height

    # Function to enable the top-bar parameter editor
    #  engine: Object to recieve send_controller_value callback
    #  symbol: String identifying the parameter
    #  options: zctrl options dictionary
    #  assert_cb: Optional function to call when editor closed with assert: fn(self,value)
    #  Populates button bar with up/down buttons
    def enable_param_editor(self, engine, symbol, options, assert_cb=None):
        self.disable_param_editor()
        if self.param_editor_zctrl:
            self.param_editor_zctrl.reset(engine, symbol, options)
        else:
            self.param_editor_zctrl = zynthian_controller(
                engine, symbol, options)
        self.param_editor_assert_cb = assert_cb
        if not self.param_editor_zctrl.is_integer:
            if self.param_editor_zctrl.nudge_factor < 0.1:
                self.format_print = "{}: {:.2f}"
            else:
                self.format_print = "{}: {:.1f}"
        else:
            self.format_print = "{}: {}"

        self.label_select_path.config(
            bg=zynthian_gui_config.color_panel_tx, fg=zynthian_gui_config.color_header_bg)
        self.init_buttonbar([("ZYNPOT 3,-1", "-1"), ("ZYNPOT 3,+1", "+1"),
                            ("ZYNPOT 3,-10", "-10"), ("ZYNPOT 3,+10", "+10"), (3, "OK")])
        self.update_param_editor()
        self.update_layout()

    # Function to disable paramter editor
    def disable_param_editor(self):
        if not self.param_editor_zctrl:
            return
        del self.param_editor_zctrl
        self.param_editor_zctrl = None
        self.param_editor_assert_cb = None
        self.init_buttonbar()
        self.set_title(self.title)
        try:
            self.update_layout()
        except:
            pass

    # Function to display label in parameter editor
    def update_param_editor(self):
        if self.param_editor_zctrl:
            if self.param_editor_zctrl.labels:
                self.select_path.set("{}: {}".format(
                    self.param_editor_zctrl.name, self.param_editor_zctrl.get_value2label()))
            else:
                self.select_path.set(self.format_print.format(
                    self.param_editor_zctrl.name, self.param_editor_zctrl.value))

# ------------------------------------------------------------------------------
