#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Base Class: Status Bar + Basic layout & events
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
import time
import logging
import tkinter
from threading import Timer
from tkinter import font as tkFont

# Zynthian specific modules
from zyngine import zynthian_controller
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_dpm import zynthian_gui_dpm

# ------------------------------------------------------------------------------
# Zynthian Base GUI Class: Basic layout & events + Status Bar (optional!)
# ------------------------------------------------------------------------------


class zynthian_gui_base(tkinter.Frame):

    ui_dir = os.environ.get('ZYNTHIAN_UI_DIR', "/zynthian/zynthian-ui")

    def __init__(self, parent=None, topbar=None):
        if parent:
            self.parent = parent
            self.parent_frame = parent.main_frame
        else:
            self.parent = None
            self.parent_frame = zynthian_gui_config.root_frame

        tkinter.Frame.__init__(self, self.parent_frame)
        self.grid_propagate(False)
        self.shown = False
        self.sidebar_shown = True
        self.title = ""
        self.tts_title = self.__class__.__name__[13:].replace("_", " ")

        self.zyngui = zynthian_gui_config.zyngui
        self.state_manager = self.zyngui.state_manager
        self.chain_manager = self.zyngui.chain_manager
        self.alt_mode = False

        # Setup topbar, autodetecting from parent object
        if topbar is not None:
            self.topbar_allowed = topbar
        else:
            if self.parent:
                self.topbar_allowed = False
            else:
                self.topbar_allowed = True

        # Geometry vars
        if self.topbar_allowed:
            self.topbar_width = zynthian_gui_config.screen_width
            self.topbar_height = zynthian_gui_config.topbar_height
            self.main_row = 1
        else:
            self.topbar_width = 0
            self.topbar_height = 0
            self.main_row= 0

        if self.parent:
            self.width = 1
            self.height = 1
            # Use parent's Breadcrumb
            self.select_path = self.parent.select_path
        else:
            self.width = zynthian_gui_config.screen_width
            self.height = zynthian_gui_config.screen_height - self.topbar_height
            # Breadcrumb path
            self.select_path = tkinter.StringVar()

        # Configure columns
        self.columnconfigure(0, weight=1)
        self.rowconfigure(self.main_row, weight=1)

        # Main Frame
        self.main_frame = tkinter.Frame(self, bg=zynthian_gui_config.color_bg)
        self.main_frame.grid_propagate(False)
        self.main_frame.grid(row=self.main_row, sticky='NEWS')

        # Parameter editor
        self.param_editor_zctrl = None
        self.param_editor_assert_cb = None

        if self.topbar_allowed:
            self.main_mute = 0

            # Status Area Parameters
            self.status_l = int(self.topbar_width * 0.25)
            self.status_h = self.topbar_height
            self.status_rh = max(2, int(self.status_h / 4))
            self.status_fs = int(0.36 * self.status_h)
            self.status_lpad = self.status_fs

            # Title Area parameters
            self.title_canvas_width = self.topbar_width - self.status_l - self.status_lpad - 2
            self.select_path_width = 0
            self.select_path_offset = 0
            self.select_path_dir = 2
            self.select_path_font = tkFont.Font(family=zynthian_gui_config.font_topbar[0],
                                                size=zynthian_gui_config.font_topbar[1])

            # Topbar's frame
            self.tb_frame = tkinter.Frame(self,
                                        width=self.topbar_width,
                                        height=self.topbar_height,
                                        bg=zynthian_gui_config.color_bg)
            self.tb_frame.grid_propagate(False)
            self.tb_frame.grid(row=0, sticky="ew")
            col = 0

            # Title
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
            self.title_canvas.bind("<Button-1>", self.cb_topbar_press)
            self.title_canvas.bind("<ButtonRelease-1>", self.cb_topbar_release)
            self.path_canvas = self.title_canvas
            self.topbar_timer = None
            self.title_timer = None
            self.status_timer = None
            self.set_title_ts = 0
            col += 1

            # Topbar's Select Path
            self.select_path.trace(tkinter.W, self.cb_select_path)
            self.label_select_path = tkinter.Label(self.title_canvas,
                                                font=zynthian_gui_config.font_topbar,
                                                textvariable=self.select_path,
                                                bg=zynthian_gui_config.color_header_bg,
                                                fg=zynthian_gui_config.color_header_tx)
            self.label_select_path.place(x=0, rely=0.5, anchor='w')
            # Setup Topbar's Callback
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
            self.status_canvas.bind('<Button-1>', self.cb_status_press)
            self.status_canvas.bind('<ButtonRelease-1>', self.cb_status_release)

            # Init status area
            self.init_status()
            self.init_dpmeter()

            # Update Title
            self.set_select_path()
            self.cb_scroll_select_path()

        self.bind("<Configure>", self.on_size)

    # -------------------------------------------------------------------------
    # Initialization & Layout managing methods
    # -------------------------------------------------------------------------

    # Function called when frame resized
    def on_size(self, event=None):
        self.update_layout()

    # Function to update display, e.g. after geometry changes
    # Override if required
    def update_layout(self):
        if self.parent:
            self.width = self.winfo_width()
            self.height = self.winfo_height() - self.topbar_height
        else:
            self.width = zynthian_gui_config.screen_width
            self.height = zynthian_gui_config.screen_height - self.topbar_height
        #logging.debug(f"[{self.__class__.__module__}] => WIDTH={self.width}, HEIGHT={self.height}")
        # TODO Resize topbar elements

    # Draw screen ready to display (like double buffer) - Override in subclass
    def build_view(self):
        return True

    # Show the view
    def show(self):
        if not self.shown:
            self.parent_frame.grid_main(self)
            self.shown = True
            self.refresh_status()
            if self.tts_title and self.zyngui.tts:
                self.zyngui.tts.announce(f"View: {self.tts_title}", replace=True, interrupt=True)
        self.main_frame.focus()

    # Hide the view
    def hide(self):
        if self.shown:
            if self.param_editor_zctrl:
                self.disable_param_editor()
            self.grid_remove()
            self.shown = False

    # Show topbar (if allowed)
    # show: True to show, False to hide
    def show_topbar(self, show):
        if self.topbar_allowed:
            if show:
                self.topbar_height = zynthian_gui_config.topbar_height
                self.tb_frame.grid(row=0, sticky="EW")
            else:
                self.topbar_height = 0
                self.tb_frame.grid_remove()
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
        self.dpm_a = zynthian_gui_dpm(self.status_canvas, 0, 0, width, height, False, ("status_dpm"), True)
        self.dpm_b = zynthian_gui_dpm(self.status_canvas, 0, height + 2, width, height, False, ("status_dpm"), True)

    # -------------------------------------------------------------------------
    # Refresh & Update methods
    # -------------------------------------------------------------------------

    def refresh_status(self):
        if self.shown and self.topbar_allowed:
            mute = self.state_manager.zynmixer_bus.get_mute(0)
            if mute != self.main_mute:
                self.main_mute = mute
                if mute:
                    self.status_canvas.itemconfigure(
                        self.status_mute, state=tkinter.NORMAL)
                    self.status_canvas.itemconfigure(
                        'status_dpm', state=tkinter.HIDDEN)
                else:
                    self.status_canvas.itemconfigure(
                        self.status_mute, state=tkinter.HIDDEN)
                    self.status_canvas.itemconfigure(
                        'status_dpm', state=tkinter.NORMAL)
            if not mute and self.dpm_a:
                self.state_manager.zynmixer_bus.update_dpm_states(1)
                dpm = self.state_manager.zynmixer_bus.dpm[0]
                self.dpm_a.refresh(dpm.a, dpm.a_hold, dpm.mono)
                self.dpm_b.refresh(dpm.b, dpm.b_hold, dpm.mono)

            # status['xrun'] = True;

            # Display error flags
            flags = ""
            color = zynthian_gui_config.color_status_error
            if self.state_manager.status_xrun == 2:
                color = zynthian_gui_config.color_status_error
                # flags = "\uf00d"
                flags = "\uf071"
            elif self.state_manager.status_xrun == 1:
                color = zynthian_gui_config.color_status_warn
                # flags = "\uf00d"
                flags = "\uf071"
            elif self.state_manager.status_undervoltage:
                flags = "\uf0e7"
            elif self.state_manager.status_overtemp:
                color = zynthian_gui_config.color_status_error
                # flags = "\uf2c7"
                flags = "\uf769"
            else:
                cpu_load = self.state_manager.status_cpu_load
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
                if self.state_manager.update_available:
                    flags = "\u21bb"
                else:
                    flags = "\u2665"

            self.status_canvas.itemconfig(
                self.status_error, text=flags, fill=color)

            # Display Audio Rec flag
            flags = ""
            color = zynthian_gui_config.color_bg
            if self.state_manager.audio_recorder.status:
                self.status_canvas.itemconfig(
                    self.status_audio_rec, state=tkinter.NORMAL)
            else:
                self.status_canvas.itemconfig(
                    self.status_audio_rec, state=tkinter.HIDDEN)

            # Display Audio Play flag
            flags = ""
            color = zynthian_gui_config.color_bg
            if self.state_manager.status_audio_player:
                self.status_canvas.itemconfig(
                    self.status_audio_play, state=tkinter.NORMAL)
            else:
                self.status_canvas.itemconfig(
                    self.status_audio_play, state=tkinter.HIDDEN)

            # Display MIDI Rec flag
            flags = ""
            color = zynthian_gui_config.color_status_midi
            if self.state_manager.status_midi_recorder:
                self.status_canvas.itemconfig(
                    self.status_midi_rec, state=tkinter.NORMAL)
            else:
                self.status_canvas.itemconfig(
                    self.status_midi_rec, state=tkinter.HIDDEN)

            # Display MIDI Play flag
            if self.state_manager.status_midi_player:
                self.status_canvas.itemconfig(
                    self.status_midi_play, state=tkinter.NORMAL)
            else:
                self.status_canvas.itemconfig(
                    self.status_midi_play, state=tkinter.HIDDEN)
            # Display SEQ Rec flag
            if self.state_manager.zynseq.libseq.isMidiRecord():
                self.status_canvas.itemconfig(
                    self.status_seq_rec, state=tkinter.NORMAL)
            else:
                self.status_canvas.itemconfig(
                    self.status_seq_rec, state=tkinter.HIDDEN)

            # Display SEQ Play flag
            if self.state_manager.zynseq.playing_sequences > 0:
                self.status_canvas.itemconfig(
                    self.status_seq_play, state=tkinter.NORMAL)
            else:
                self.status_canvas.itemconfig(
                    self.status_seq_play, state=tkinter.HIDDEN)

            # Display MIDI activity flag
            if self.state_manager.status_midi:
                self.status_canvas.itemconfig(
                    self.status_midi, state=tkinter.NORMAL)
            else:
                self.status_canvas.itemconfig(
                    self.status_midi, state=tkinter.HIDDEN)

            # Display MIDI clock flag
            if self.state_manager.status_midi_clock:
                self.status_canvas.itemconfig(
                    self.status_midi_clock, state=tkinter.NORMAL)
            else:
                self.status_canvas.itemconfig(
                    self.status_midi_clock, state=tkinter.HIDDEN)

    def refresh_loading(self):
        pass

    # TODO: Consolidate set_title and set_select_path, etc.

    # Function to update title
    # title: Title to display in topbar
    # fg: Title foreground colour [Default: Do not change]
    # bg: Title background colour [Default: Do not change]
    # timeout: If set, title is shown for this period (seconds) then reverts to previous title

    def set_title(self, title, fg=None, bg=None, timeout=None):
        # Limit title update rate (30fps)
        ts = time.monotonic()
        if ts -self.set_title_ts < 0.0333:
            return
        self.set_title_ts = ts

        if self.title_timer:
            self.title_timer.cancel()
            self.title_timer = None
        elif timeout:
            self.title = self.select_path.get()

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

    # Function to revert title after toast
    def on_title_timeout(self):
        if self.title_timer:
            self.title_timer.cancel()
            self.title_timer = None
        self.set_title(self.title)

    def set_select_path(self):
        pass

    def tts_info(self):
        """ Narrate view status - override to provide more context"""
        if self.tts_title and self.zyngui.tts:
            self.zyngui.tts.announce(f"View: {self.tts_title}", replace=True, interrupt=True)

    # --------------------------------------------------------------------------
    # CUIA and Zynpot Callbacks (rotaries!)
    # --------------------------------------------------------------------------

    # By default, screens have no ALT mode.
    # To implement ALT mode, child classes have to redefine get_alt_mode() returning self.alt_mode
    def get_alt_mode(self):
        #return self.alt_mode
        return False

    def cuia_toggle_alt_mode(self, params=None):
        self.alt_mode = not self.alt_mode
        return True

    def arrow_up(self, nudge=1):
        """ Function to handle CUIA ARROW_UP
        """
        if self.param_editor_zctrl:
            self.zynpot_cb(zynthian_gui_config.layout['ctrl_order'][3], nudge)
            return True

    def arrow_down(self, nudge=-1):
        """ Function to handle CUIA ARROW_DOWN
        """
        if self.param_editor_zctrl:
            self.zynpot_cb(zynthian_gui_config.layout['ctrl_order'][3], nudge)
            return True

    def zynpot_cb(self, i, val):
        if self.param_editor_zctrl:
            ctrl_order = zynthian_gui_config.layout['ctrl_order']
            if i == ctrl_order[3]:
                value = self.param_editor_zctrl.value_min + val * (self.param_editor_zctrl.value_range)
                # TODO: Implement pickup
                self.param_editor_zctrl.set_value(value)
            else:
                return True
            self.update_param_editor()
            return True

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
                self.param_editor_zctrl.set_value(self.param_editor_zctrl.value_default)
                self.update_param_editor()
                return True

    def back_action(self):
        if self.param_editor_zctrl:
            self.disable_param_editor()
            return True
        return False

    # --------------------------------------------------------------------------
    # Param editor
    # --------------------------------------------------------------------------

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
            self.param_editor_zctrl = zynthian_controller(engine, symbol, options)
        self.param_editor_assert_cb = assert_cb
        if not self.param_editor_zctrl.is_integer:
            if self.param_editor_zctrl.nudge_factor < 0.1:
                self.format_print = "{}: {:.2f}"
            else:
                self.format_print = "{}: {:.1f}"
        else:
            self.format_print = "{}: {}"

        self.label_select_path.config(bg=zynthian_gui_config.color_panel_tx, fg=zynthian_gui_config.color_header_bg)
        if self.zyngui.tts:
            self.zyngui.tts.announce("Enabled param editor")
        self.update_param_editor(True)
        self.update_layout()

    # Function to disable paramter editor
    def disable_param_editor(self):
        if not self.param_editor_zctrl:
            return
        del self.param_editor_zctrl
        self.param_editor_zctrl = None
        self.param_editor_assert_cb = None
        self.set_title(self.title)
        try:
            self.update_layout()
        except:
            pass
        if self.zyngui.tts:
            self.zyngui.tts.announce("Disabled param editor")

    # Function to display label in parameter editor
    def update_param_editor(self, first_show=False):
        if self.param_editor_zctrl:
            if self.param_editor_zctrl.labels:
                value = self.param_editor_zctrl.get_value2label()
                text = f"{self.param_editor_zctrl.name}: {value}"
            else:
                value = self.param_editor_zctrl.value
                text = self.format_print.format(self.param_editor_zctrl.name, value)
            self.select_path.set(text)
            if self.zyngui.tts:
                if first_show:
                    self.zyngui.tts.announce(text, False, False, False)
                else:
                    self.zyngui.tts.announce(str(value))

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

    # Default topbar touch callback
    def cb_topbar_press(self, params=None):
        self.topbar_timer = Timer(zynthian_gui_config.zynswitch_long_seconds, self.cb_topbar_long)
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
        self.zyngui.callable_ui_action('show_screen', ('root',))

    # Default topbar bold touch action
    def topbar_bold_touch_action(self):
        self.zyngui.cuia_main_menu()

    # Default topbar long touch action
    def topbar_long_touch_action(self):
        self.topbar_bold_touch_action()

    # Default status touch callback
    def cb_status_press(self, params=None):
        self.status_timer = Timer(zynthian_gui_config.zynswitch_long_seconds, self.cb_status_long)
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
        if zynthian_gui_config.touch_keypad:
            zynthian_gui_config.toggle_touch_keypad()
            self.on_size()
            return

    # Default status bold touch action
    def status_bold_touch_action(self):
        self.status_short_touch_action()

    # Default status long touch action
    def status_long_touch_action(self):
        # self.zyngui.callable_ui_action('screen_snapshot')
        self.zyngui.callable_ui_action('all_sounds_off')

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
        zynthian_gui_config.top.after(50, self.cb_scroll_select_path)

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

# ------------------------------------------------------------------------------
