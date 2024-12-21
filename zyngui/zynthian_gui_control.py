#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Instrument-Control Class
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

import logging
import importlib
from pathlib import Path
from time import monotonic

# Zynthian specific modules
import zynautoconnect
from zyngine.zynthian_signal_manager import zynsigman
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_controller import zynthian_gui_controller
from zyngui.zynthian_gui_selector import zynthian_gui_selector


# ------------------------------------------------------------------------------
# Zynthian Instrument Controller GUI Class
# ------------------------------------------------------------------------------

MIDI_LEARNING_DISABLED = 0
MIDI_LEARNING_CHAIN = 1
MIDI_LEARNING_GLOBAL = 2


class zynthian_gui_control(zynthian_gui_selector):
    SS_GUI_CONTROL_MODE = 2

    def __init__(self, selcap='Controllers'):
        self.mode = None

        self.widgets = {}
        self.current_widget = None

        self.processors = []
        self.ctrl_screens = {}
        self.zcontrollers = []
        self.zgui_controllers = []
        self.midi_learning = MIDI_LEARNING_DISABLED

        self.screen_info = None
        self.screen_name = None
        self.screen_type = None
        self.screen_title = None
        self.screen_processor = None  # TODO: Refactor

        self.buttonbar_config = [
            ("arrow_left", '<< Prev'),
            ("zynswitch 1,S", 'Preset'),
            ("zynswitch 3,S", 'Pages'),
            ("arrow_right", 'Next >>')
        ]

        super().__init__(selcap, wide=False, loading_anim=False, info=False)

        # Configure layout
        for ctrl_pos in self.layout['ctrl_pos']:
            self.main_frame.columnconfigure(
                ctrl_pos[1], weight=1, uniform='ctrl_col')
        self.main_frame.columnconfigure(self.layout['list_pos'][1], weight=2)

    def update_layout(self):
        super().update_layout()
        minheight = self.height // self.layout['rows']
        minwidth = int((self.width * 0.25 - 1) * self.sidebar_shown)
        for pos in self.layout['ctrl_pos']:
            self.main_frame.rowconfigure(pos[0], minsize=minheight, weight=1)
            self.main_frame.columnconfigure(
                pos[1], minsize=minwidth, weight=self.sidebar_shown)

    def build_view(self):
        curproc = self.zyngui.get_current_processor()
        if not self.processors or curproc not in self.processors:
            pending_click_listbox = True
        else:
            pending_click_listbox = False
        super().build_view()
        if not self.shown:
            zynsigman.register(zynsigman.S_MIDI, zynsigman.SS_MIDI_CC, self.cb_midi_cc)
            zynsigman.register(zynsigman.S_MIDI, zynsigman.SS_MIDI_PC, self.cb_midi_pc)
            if zynthian_gui_config.enable_touch_navigation:
                zynsigman.register(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_SIDEBAR, self.cb_show_sidebar)
                zynsigman.register(zynsigman.S_GUI, self.SS_GUI_CONTROL_MODE, self.cb_control_mode)
            self.click_listbox()
        elif pending_click_listbox:
            self.click_listbox()
        self.set_mode_control()
        return True

    def hide(self):
        if self.shown:
            self.exit_midi_learn()
            zynsigman.unregister(zynsigman.S_MIDI, zynsigman.SS_MIDI_CC, self.cb_midi_cc)
            zynsigman.unregister(zynsigman.S_MIDI, zynsigman.SS_MIDI_PC, self.cb_midi_pc)
            if zynthian_gui_config.enable_touch_navigation:
                zynsigman.unregister(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_SIDEBAR, self.cb_show_sidebar)
                zynsigman.unregister(zynsigman.S_GUI, self.SS_GUI_CONTROL_MODE, self.cb_control_mode)
        super().hide()

    def cb_midi_pc(self, izmip, chan, num):
        """Handle MIDI_PC signal

        izmip : MIDI input device index
        chan : MIDI channel
        num : CC number
        """

        # Refresh control screen after loading ZS3
        self.zyngui.chain_control()

    def show_sidebar(self, show):
        self.sidebar_shown = show
        for zctrl in self.zgui_controllers:
            if self.sidebar_shown:
                zctrl.grid()
            else:
                zctrl.grid_remove()
        self.update_layout()

    def cb_show_sidebar(self, shown):
        self.set_button_status(2, not shown)

    def backbutton_short_touch_action(self):
        if not self.back_action():
            self.zyngui.back_screen()

    def cb_control_mode(self, mode):
        self.set_button_status(2, (mode == "select"))
        if mode == "control":
            self.set_mode_control()

    def configure_processors(self, curproc=None):
        if not curproc:
            curproc = self.zyngui.get_current_processor()
        if not curproc:
            self.processors = []
        else:
            if curproc in (self.zyngui.state_manager.alsa_mixer_processor, self.zyngui.state_manager.audio_player):
                self.processors = [curproc]
            else:
                self.processors = self.zyngui.chain_manager.get_processors(curproc.chain_id)

    def fill_list(self):
        self.list_data = []

        # Configure processors if needed
        curproc = self.zyngui.get_current_processor()
        self.configure_processors(curproc)

        if not self.processors:
            self.list_data.append((None, None, "NO PROCESSORS!"))
        else:
            i = 0
            for processor in self.processors:
                j = 0
                screen_list = processor.get_ctrl_screens()
                # if len(self.processors) > 1:
                self.list_data.append(
                    (None, None, f"> {processor.engine.name.split('/')[-1]}"))
                for cscr in screen_list:
                    self.list_data.append(
                        (screen_list[cscr][0].group_symbol, i, cscr, processor, j))
                    i += 1
                    j += 1

                self.index = curproc.get_current_screen_index()
                self.get_screen_info()
        super().fill_list()

    def get_screen_info(self):
        if 0 <= self.index < len(self.list_data):
            self.screen_info = self.list_data[self.index]
            if len(self.screen_info) < 5:
                if self.index + 1 < len(self.list_data):
                    self.index += 1
                    self.screen_info = self.list_data[self.index]
                else:
                    self.screen_info = None
            if self.screen_info and len(self.screen_info) == 5:
                self.screen_title = self.screen_info[2]
                self.screen_processor = self.screen_info[3]
                self.screen_type = None
                return True
            else:
                pass
                # logging.info("Can't get screen info!!")
        self.screen_title = ""
        self.screen_type = None
        self.screen_processor = self.zyngui.get_current_processor()
        return False

    def get_screen_type(self):
        """
        if self.screen_title:
                # Some heuristics to detect ADSR control screens ...
                # TODO: This should be improved by marking ADSR groups!!
                if " Env" in self.screen_title or " ADSR" in self.screen_title or\
                                ("attack" in self.zcontrollers[0].name.lower() and
                                "decay" in self.zcontrollers[1].name.lower() and
                                "sustain" in self.zcontrollers[2].name.lower() and
                                "release" in self.zcontrollers[3].name.lower()):
                        self.screen_type = "envelope"
        """
        for zctrl in self.zcontrollers:
            if hasattr(zctrl, "envelope"):
                self.screen_type = "envelope"
                break
        else:
            self.screen_type = None
        return self.screen_type

    def fill_listbox(self):
        super().fill_listbox()
        for i, val in enumerate(self.list_data):
            if val[0] is None:
                # self.listbox.itemconfig(i, {'bg': zynthian_gui_config.color_off,'fg': zynthian_gui_config.color_tx_off})
                self.listbox.itemconfig(
                    i, {'bg': zynthian_gui_config.color_panel_hl, 'fg': zynthian_gui_config.color_tx_off})

    def set_selector(self, zs_hiden=True):
        if self.mode == 'select':
            super().set_selector(zs_hiden)

    def show_widget(self, processor):
        module_path = processor.engine.custom_gui_fpath
        if self.screen_type:  # and not module_path:
            module_path = f"/zynthian/zynthian-ui/zyngui/zynthian_widget_{self.screen_type}.py"
        if module_path:
            module_name = Path(module_path).stem
            if module_name.startswith("zynthian_widget_"):
                widget_name = module_name[len("zynthian_widget_"):]
                if widget_name not in self.widgets:
                    try:
                        spec = importlib.util.spec_from_file_location(
                            module_name, module_path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        class_ = getattr(module, module_name)
                        self.widgets[widget_name] = class_(self.main_frame)
                    except Exception as e:
                        logging.error(
                            f"Can't load custom widget {widget_name} => {e}")

                if widget_name in self.widgets:
                    self.widgets[widget_name].set_processor(processor)
                else:
                    widget_name = None

                if self.wide:
                    padx = (0, 2)
                else:
                    padx = (2, 2)
                for k, widget in self.widgets.items():
                    if k == widget_name:
                        self.listbox.grid_remove()
                        lb_rows = self.layout['rows'] - widget.rows
                        if lb_rows > 0:
                            self.listbox.grid(rowspan=lb_rows)
                            self._select_listbox(self.index, see=True)
                        widget.grid(row=self.layout['list_pos'][0] + lb_rows, column=self.layout['list_pos']
                                    [1], rowspan=widget.rows, padx=padx, sticky="news")
                        widget.show()
                        self.set_current_widget(widget)
                    else:
                        widget.grid_remove()
                        widget.hide()
                return
        self.hide_widgets()

    def hide_widgets(self):
        for k, widget in self.widgets.items():
            widget.grid_remove()
            widget.hide()
        self.set_current_widget(None)
        self.listbox.grid_remove()
        self.listbox.grid(rowspan=4)

    def set_current_widget(self, widget):
        if widget == self.current_widget:
            return
        self.current_widget = widget
        # Clean dynamic CUIA methods from widgets
        for fn in dir(self):
            if fn.startswith('cuia_') or fn == 'update_wsleds':
                delattr(self, fn)
                # logging.debug(f"DELATTR {fn}")
        # Create new dynamix CUIA methods
        if self.current_widget:
            for fn in dir(self.current_widget):
                if fn.startswith('cuia_') or fn == 'update_wsleds':
                    func = getattr(self.current_widget, fn)
                    if callable(func):
                        setattr(self, fn, func)
                        # logging.debug(f"SETATTR {fn}")

    def set_controller_screen(self):
        # Get screen info
        if self.get_screen_info():
            try:
                self.zyngui.chain_manager.get_active_chain().set_current_processor(self.screen_processor)
                self.zyngui.current_processor = self.screen_processor
            except:
                pass

            # Get controllers for the current screen
            self.zyngui.get_current_processor().set_current_screen_index(self.index)
            self.zcontrollers = self.screen_processor.get_ctrl_screen(self.screen_title)

            # Show the widget for the current processor
            if self.mode == 'control':
                self.get_screen_type()
                self.show_widget(self.screen_processor)

        else:
            self.zcontrollers = []
            self.screen_title = ""
            self.screen_type = None
            self.hide_widgets()

        # Setup GUI Controllers
        logging.debug(f"SET CONTROLLER SCREEN {self.screen_title}")
        # Configure zgui_controllers
        for i in range(4):
            if i < len(self.zcontrollers):
                ctrl = self.zcontrollers[i]
                try:
                    # logging.debug(f"CONTROLLER ARRAY {i} => {ctrl.symbol} ({ctrl.short_name})")
                    self.set_zcontroller(i, ctrl)
                except Exception as e:
                    logging.exception("Controller %s (%d) => %s" %(ctrl.short_name, i, e))
                    self.zgui_controllers[i].hide()
            else:
                self.set_zcontroller(i, None)
            pos = self.layout['ctrl_pos'][i]
            self.zgui_controllers[i].grid(
                row=pos[0], column=pos[1], pady=(0, 1), sticky='news')

        self.update_layout()

    def set_zcontroller(self, i, ctrl):
        if i < len(self.zgui_controllers):
            self.zgui_controllers[i].config(ctrl)
            self.zgui_controllers[i].show()
        else:
            self.zgui_controllers.append(zynthian_gui_controller(i, self.main_frame, ctrl))

    def get_zcontroller(self, i):
        if i < len(self.zgui_controllers):
            return self.zgui_controllers[i].zctrl
        else:
            return None

    def set_selector_screen(self):
        for i in range(0, len(self.zgui_controllers)):
            self.zgui_controllers[i].enable(False)
        self.set_selector()

    def set_mode_select(self):
        self.exit_midi_learn()
        self.mode = 'select'
        self.hide_widgets()
        self.set_selector_screen()
        self.listbox.config(selectbackground=zynthian_gui_config.color_ctrl_bg_off,
                            selectforeground=zynthian_gui_config.color_ctrl_tx,
                            fg=zynthian_gui_config.color_ctrl_tx_off)
        self.select(self.index)
        self.set_select_path()
        self.set_button_status(2, True)

    def set_mode_control(self):
        self.mode = 'control'
        if self.zselector:
            self.zselector.hide()
        self.set_controller_screen()
        self.listbox.config(selectbackground=zynthian_gui_config.color_ctrl_bg_on,
                            selectforeground=zynthian_gui_config.color_ctrl_tx,
                            fg=zynthian_gui_config.color_ctrl_tx)
        for i in range(0, len(self.zgui_controllers)):
            self.zgui_controllers[i].enable()
        self.set_select_path()
        self.set_button_status(2, False)

    def previous_page(self, wrap=False):
        i = self.index - 1
        if i < 0:
            i = 0
        self.select(i)
        self.click_listbox()

    def next_page(self, wrap=False):
        i = self.index + 1
        if i >= len(self.list_data):
            if wrap:
                i = 0
            else:
                i = len(self.list_data) - 1
        self.select(i)
        self.click_listbox()

    def back_action(self):
        if self.mode == 'select':
            self.set_mode_control()
            return True
        # If in MIDI-learn mode, back to instrument control
        elif self.midi_learning:
            self.exit_midi_learn()
            return True
        else:
            return False

    def arrow_up(self):
        self.previous_page()
        return True

    def arrow_down(self):
        self.next_page()
        return True

    def arrow_right(self):
        self.exit_midi_learn()
        self.zyngui.chain_manager.next_chain()
        self.zyngui.chain_control()

    def arrow_left(self):
        self.exit_midi_learn()
        self.zyngui.chain_manager.previous_chain()
        self.zyngui.chain_control()

    def rotate_chain(self):
        self.exit_midi_learn()
        self.zyngui.chain_manager.rotate_chain()
        self.zyngui.chain_control()

    # Function to handle *all* switch presses.
    #  swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
    #  t: Press type ["S"=Short, "B"=Bold, "L"=Long]
    #  returns True if action fully handled or False if parent action should be triggered
    def switch(self, swi, t='S'):
        if t == 'B' and self.midi_learning:
            self.midi_learn_options(swi)
            return True

        if swi == 0:
            if t == 'S':
                self.rotate_chain()
                return True

        elif swi == 1:
            if t == 'S':
                if self.back_action():
                    return True
                elif not self.zyngui.is_shown_alsa_mixer():
                    self.zyngui.cuia_bank_preset()
                    return True
            elif t == 'B':
                self.back_action()
                return False

        elif swi == 2:
            if t == 'S':
                if self.mode == 'control':
                    return False
            elif t == 'B':
                if self.midi_learning and self.zyngui.state_manager.midi_learn_zctrl:
                    self.midi_unlearn_action()
                    return True

    def switch_select(self, t):
        if t == 'S':
            if self.mode == 'control':
                if len(self.list_data) > 3:
                    self.set_mode_select()
                else:
                    self.next_page(True)
            elif self.mode == 'select':
                self.click_listbox()
                self.set_mode_control()
        elif t == 'B':
            self.zyngui.cuia_chain_options()

        return True

    def select(self, index=None, set_zctrl=True):
        super().select(index, set_zctrl)
        #if self.mode == 'select':
        self.set_controller_screen()
        #self.set_selector_screen()

    def zynpot_cb(self, i, dval):
        if self.mode == 'control' and self.zcontrollers:
            if self.zgui_controllers[i].zynpot_cb(dval):
                if self.midi_learning:
                    self.midi_learn(i, self.midi_learning)
        elif self.mode == 'select':
            super().zynpot_cb(i, dval)

    def get_zgui_controller(self, zctrl):
        for zgui_controller in self.zgui_controllers:
            if zgui_controller.zctrl == zctrl:
                return zgui_controller

    def get_zgui_controller_by_index(self, i):
        return self.zgui_controllers[i]

    def refresh_midi_bind(self, preselect=False):
        for i, zgui_controller in enumerate(self.zgui_controllers):
            if preselect:
                zgui_controller.set_midi_bind(i)
            else:
                zgui_controller.set_midi_bind()

    def plot_zctrls(self, force=False):
        if self.mode == 'select':
            super().plot_zctrls()
        elif self.zgui_controllers:
            self.swipe_update()
            for zgui_ctrl in self.zgui_controllers:
                if zgui_ctrl.zctrl and zgui_ctrl.zctrl.is_dirty or force:
                    zgui_ctrl.calculate_plot_values()
                zgui_ctrl.plot_value()
        for k, widget in self.widgets.items():
            widget.update()

    # --------------------------------------------------------------------------
    # Options Menu
    # --------------------------------------------------------------------------

    def show_menu(self):
        self.zyngui.cuia_chain_options()

    def toggle_menu(self):
        if self.shown:
            self.show_menu()
        elif self.zyngui.current_screen.endswith("_options"):
            self.close_screen()

    # --------------------------------------------------------------------------
    # MIDI learn management
    # --------------------------------------------------------------------------

    def enter_midi_learn(self, mlmode=MIDI_LEARNING_CHAIN, preselect=True):
        if mlmode > MIDI_LEARNING_DISABLED:
            self.midi_learning = mlmode
            self.refresh_midi_bind(preselect)
            self.set_select_path()

    def exit_midi_learn(self):
        if self.midi_learning != MIDI_LEARNING_DISABLED:
            self.midi_learning = MIDI_LEARNING_DISABLED
            self.zyngui.state_manager.disable_learn_cc()
            self.refresh_midi_bind()
            self.set_select_path()

    def toggle_midi_learn(self, i=None):
        if self.mode != 'control':
            return

        if i is not None:
            # Restart MIDI learn with a new controller
            if self.zgui_controllers[i].zctrl != self.zyngui.state_manager.get_midi_learn_zctrl():
                self.midi_learn(i, MIDI_LEARNING_CHAIN)
                return self.midi_learning

        # TODO: Handle alsa mixer
        # if zynthian_gui_config.midi_prog_change_zs3 and not self.zyngui.is_shown_alsa_mixer():

        if self.midi_learning == MIDI_LEARNING_CHAIN:
            self.midi_learning = MIDI_LEARNING_GLOBAL
            if i is not None:
                self.refresh_midi_bind(False)
            else:
                self.refresh_midi_bind(True)
            self.set_select_path()
        elif self.midi_learning == MIDI_LEARNING_GLOBAL:
            self.exit_midi_learn()
        else:
            if i is not None:
                self.enter_midi_learn(MIDI_LEARNING_CHAIN, False)
            else:
                self.enter_midi_learn(MIDI_LEARNING_CHAIN, True)

        return self.midi_learning

    def get_midi_learn(self):
        return self.midi_learning

    def zctrl_touch(self, i):
        if self.midi_learning:
            self.midi_learn(i, self.midi_learning)

    def midi_learn(self, i, mlmode=MIDI_LEARNING_CHAIN):
        if self.mode == 'control' and mlmode > MIDI_LEARNING_DISABLED:
            learn_zctrl = self.zgui_controllers[i].zctrl
            if learn_zctrl:
                self.zyngui.state_manager.enable_learn_cc(learn_zctrl)
                self.enter_midi_learn(mlmode, False)

    def midi_learn_bind(self, zmip, chan, midi_cc):
        if self.midi_learning == MIDI_LEARNING_CHAIN:
            self.zyngui.chain_manager.add_midi_learn(
                chan, midi_cc, self.zyngui.state_manager.get_midi_learn_zctrl())
        elif self.midi_learning == MIDI_LEARNING_GLOBAL:
            self.zyngui.chain_manager.add_midi_learn(
                chan, midi_cc, self.zyngui.state_manager.get_midi_learn_zctrl(), zmip)
        self.exit_midi_learn()

    def cb_midi_cc(self, izmip, chan, num, val):
        """Handle MIDI_CC signal

        izmip : MIDI input device index
        chan : MIDI channel
        num : CC number
        val : CC value
        """

        if self.midi_learning and self.zyngui.state_manager.midi_learn_zctrl and num < 120:
            # Handle MIDI learn for assignable CC
            # TODO Detect CC relative mode, etc.
            self.midi_learn_bind(izmip, chan, num)
            self.zyngui.show_current_screen()

    def midi_unlearn(self, param=None):
        if param:
            self.zyngui.chain_manager.clean_midi_learn(param)
        else:
            self.zyngui.chain_manager.clean_midi_learn(
                self.zyngui.get_current_processor())
        self.refresh_midi_bind()

    def midi_unlearn_action(self):
        curproc = self.zyngui.get_current_processor()
        if curproc:
            engine_name = curproc.get_name()
            if engine_name:
                question_str = f"Do you want to clean MIDI-learn for ALL controls in {engine_name}"
                if curproc.midi_chan is not None and 0 <= curproc.midi_chan < 16:
                    question_str += f"on MIDI channel {curproc.midi_chan + 1}"
                self.zyngui.show_confirm(question_str + "?", self.midi_unlearn)
            else:
                logging.error("Can't get processor name.")

    def midi_learn_options(self, i, unlearn_only=False):
        self.exit_midi_learn()
        try:
            options = {}
            zctrl = self.zgui_controllers[i].zctrl
            if zctrl is None:
                return
            mcparams = self.zyngui.chain_manager.get_midi_learn_from_zctrl(zctrl)
            if not unlearn_only:
                title = "Control options"
                if not zctrl.is_toggle:
                    options["X-Y touchpad"] = None
                    # Only show X-Y if both zctrl are valid
                    if self.zyngui.state_manager.zctrl_x and self.zyngui.state_manager.zctrl_y:
                        options["Control"] = True
                    if self.zyngui.state_manager.zctrl_x:
                        xinfo = f" => {self.zyngui.state_manager.zctrl_x.name}"
                    else:
                        xinfo = ""
                    if zctrl == self.zyngui.state_manager.zctrl_x:
                        options[f"\u2612 X-axis{xinfo}"] = False
                    else:
                        options[f"\u2610 X-axis{xinfo}"] = zctrl
                    if self.zyngui.state_manager.zctrl_y:
                        yinfo = f" => {self.zyngui.state_manager.zctrl_y.name}"
                    else:
                        yinfo = ""
                    if zctrl == self.zyngui.state_manager.zctrl_y:
                        options[f"\u2612 Y-axis{yinfo}"] = False
                    else:
                        options[f"\u2610 Y-axis{yinfo}"] = zctrl

                options["MIDI learn"] = None
                if zctrl.is_toggle:
                    if zctrl.midi_cc_momentary_switch:
                        options["\u2612 Momentary => Latch"] = i
                    else:
                        options["\u2610 Momentary => Latch"] = i
                elif mcparams:
                    if zctrl.midi_cc_mode == 0:
                        options["\u2610 Relative Mode"] = i
                    else:
                        options["\u2612 Relative Mode"] = i
                options[f"Chain learn '{zctrl.name}'..."] = i
                options[f"Global learn '{zctrl.name}'..."] = i
            else:
                title = "Control unlearn"

            if mcparams:
                if mcparams[1]:
                    dev_name = zynautoconnect.get_midi_in_devid(mcparams[0] >> 24)
                    options[f"Unlearn '{zctrl.name}' from {dev_name}"] = zctrl
                else:
                    options[f"Unlearn '{zctrl.name}'"] = zctrl
            options["Unlearn all controls"] = ""

            self.zyngui.screens['option'].config(title, options, self.midi_learn_options_cb)
            self.zyngui.show_screen('option')
        except Exception as e:
            logging.error(f"Can't show control options => {e}")

    def midi_learn_options_cb(self, option, param):
        parts = option.split(" ")
        if option == "Control":
            self.show_xy()
        elif parts[1] == "X-axis":
            self.zyngui.state_manager.zctrl_x = param
            if self.zyngui.state_manager.zctrl_y == param:
                self.zyngui.state_manager.zctrl_y = None
            self.refresh_midi_bind()
        elif parts[1] == "Y-axis":
            self.zyngui.state_manager.zctrl_y = param
            if self.zyngui.state_manager.zctrl_x == param:
                self.zyngui.state_manager.zctrl_x = None
            self.refresh_midi_bind()
        elif parts[0] == "Chain":
            self.midi_learn(param, MIDI_LEARNING_CHAIN)
        elif parts[0] == "Global":
            self.midi_learn(param, MIDI_LEARNING_GLOBAL)
        elif parts[0] == "Unlearn":
            if param:
                self.midi_unlearn(param)
            else:
                self.midi_unlearn_action()
        elif parts[1] == "Momentary":
            if parts[0] == '\u2612':
                self.zgui_controllers[param].zctrl.midi_cc_momentary_switch = 0
            else:
                self.zgui_controllers[param].zctrl.midi_cc_momentary_switch = 1
            self.midi_learn_options(param)
        elif parts[1] == "Relative":
            if parts[0] == '\u2612':
                self.zgui_controllers[param].zctrl.midi_cc_mode_set(0)
            else:
                self.zgui_controllers[param].zctrl.midi_cc_mode_set(-1)



    def show_xy(self, params=None):
        self.zyngui.show_screen("control_xy")

    # -------------------------------------------------------------------------
    # GUI Callback function
    # --------------------------------------------------------------------------

    def cb_listbox_click(self, t):
        # Override listbox click - we don't want short/bold press
        return

    def cb_listbox_motion(self, event):
        return super().cb_listbox_motion(event)

    def cb_listbox_wheel(self, event):
        # Override with default listbox behaviour to allow scrolling of listbox without selection (expected UX)
        return

    def set_select_path(self):
        processor = self.zyngui.get_current_processor()
        if processor:
            if self.mode == 'control' and self.midi_learning:
                if self.midi_learning == MIDI_LEARNING_CHAIN:
                    self.select_path.set(processor.get_basepath() + "/CHAIN Control MIDI-Learn")
                elif self.midi_learning == MIDI_LEARNING_GLOBAL:
                    self.select_path.set(processor.get_basepath() + "/GLOBAL Control MIDI-Learn")
            else:
                self.select_path.set(processor.get_presetpath())
        else:
            self.select_path.set(self.zyngui.chain_manager.get_active_chain().get_title())

# ------------------------------------------------------------------------------
