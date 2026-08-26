#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Instrument-Control Class
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

import logging
import importlib
from pathlib import Path

# Zynthian specific modules
import zynautoconnect
from zyngine.zynthian_signal_manager import zynsigman
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base
from zyngui.zynthian_gui_selector import zynthian_gui_selector
from zyngui.zynthian_gui_controller import zynthian_gui_controller

# ------------------------------------------------------------------------------
# Zynthian Instrument Controller GUI Class
# ------------------------------------------------------------------------------

MIDI_LEARNING_DISABLED = 0
MIDI_LEARNING_CHAIN = 1
MIDI_LEARNING_GLOBAL = 2


class zynthian_gui_control(zynthian_gui_selector):

    def __init__(self, parent=None, topbar=None):
        self.mode = "control"

        self.processors = []
        self.zcontrollers = []
        self.zgui_controllers = []
        self.midi_learning = MIDI_LEARNING_DISABLED

        self.modules = {}
        self.widgets = {}
        self.current_widget = None
        self.widget_zctrl = None

        self.screen_info = None
        self.screen_name = None
        self.screen_type = None
        self.screen_title = None
        self.n_screens_chain_ctrls = 0

        super().__init__(selcap="Control Page", loading_anim=False, tiny_ctrls=False, parent=parent, topbar=topbar)

        # Create zgui controllers
        for i in range(4):
            pos = self.layout['ctrl_pos'][i]
            zgui_ctrl = zynthian_gui_controller(i, self.main_frame)
            zgui_ctrl.grid(row=pos[0], column=pos[1], pady=(0, 1), sticky='news')
            self.zgui_controllers.append(zgui_ctrl)

        self.update_layout()

    def update_layout(self):
        zynthian_gui_base.update_layout(self)
        # Reconfigure ctrl columns
        ctrlheight = self.height // self.layout['rows']
        #ctrlwidth = int((self.width * self.layout['ctrl_width'] - 1) * self.sidebar_shown)
        ctrlwidth = int((zynthian_gui_config.screen_width * self.layout['ctrl_width'] - 1) * self.sidebar_shown)
        cols = set()
        rows = set()
        for pos in self.layout['ctrl_pos']:
            rows.add(pos[0])
            cols.add(pos[1])
        for row in rows:
            self.main_frame.rowconfigure(row, minsize=ctrlheight, weight=1)
        for col in cols:
            self.main_frame.columnconfigure(col, minsize=ctrlwidth, weight=self.sidebar_shown, uniform='ctrl_col')
        # Reconfigure Listbox
        if self.wide:
            lbwidth = self.width - ctrlwidth
            lbweight = 3
        else:
            lbwidth = self.width - 2 * ctrlwidth
            lbweight = 2
        self.main_frame.columnconfigure(self.layout['list_pos'][1], minsize=lbwidth, weight=lbweight)

    def build_view(self):
        #curproc = self.zyngui.get_current_processor()
        super().build_view()
        if not self.shown:
            zynsigman.register_queued(zynsigman.S_STATE_MAN, zynsigman.SS_LOAD_ZS3, self.cb_load_zs3)
            zynsigman.register_queued(zynsigman.S_PROCESSOR, zynsigman.SS_PROCESSOR_CTRL_SCREENS, self.cb_ctrl_screens)
            zynsigman.register_queued(zynsigman.S_MIDI, zynsigman.SS_MIDI_PC, self.cb_midi_pc)
            zynsigman.register(zynsigman.S_MIDI, zynsigman.SS_MIDI_CC, self.cb_midi_cc)
        #if self.mode == "select":
        #    self.set_mode_control()
        return True

    def hide(self):
        if self.shown:
            self.exit_midi_learn()
            zynsigman.unregister(zynsigman.S_STATE_MAN, zynsigman.SS_LOAD_ZS3, self.cb_load_zs3)
            zynsigman.unregister(zynsigman.S_PROCESSOR, zynsigman.SS_PROCESSOR_CTRL_SCREENS, self.cb_ctrl_screens)
            zynsigman.unregister(zynsigman.S_MIDI, zynsigman.SS_MIDI_PC, self.cb_midi_pc)
            zynsigman.unregister(zynsigman.S_MIDI, zynsigman.SS_MIDI_CC, self.cb_midi_cc)
        super().hide()

    def show_sidebar(self, show):
        self.sidebar_shown = show
        for zctrl in self.zgui_controllers:
            if self.sidebar_shown:
                zctrl.grid()
            else:
                zctrl.grid_remove()
        self.update_layout()

    def refresh(self):
        self.update_list()
        self.exit_midi_learn()
        # TODO anything else??

    def cb_load_zs3(self, zs3_id):
        # Refresh control list and screen after loading ZS3
        self.refresh()

    def cb_ctrl_screens(self, proc):
        # Refresh control screens
        curproc = self.zyngui.get_current_processor()
        if curproc and proc and proc == curproc:
            self.refresh()

    def cb_midi_pc(self, izmip, chan, num):
        curproc = self.zyngui.get_current_processor()
        if not zynthian_gui_config.midi_prog_change_zs3 and self.curproc and \
            self.curproc.midi_chan is not None and self.curproc.midi_chan == chan:
            # Refresh control screen after changing preset with program change
            self.refresh()

    def configure_processors(self, curproc=None):
        if not curproc:
            curproc = self.zyngui.get_current_processor()
        if not curproc:
            self.processors = []
        else:
            # Special processors: ALSA Mixer ,Global Audio Player, Tempo Screen
            if curproc and curproc.id < -1:
                self.processors = [curproc]
            else:
                self.processors = self.chain_manager.get_processors(curproc.chain_id)

    def fill_list(self):
        self.list_data = []
        # Configure processors if needed
        curproc = self.zyngui.get_current_processor()
        self.configure_processors(curproc)

        self.n_screens_chain_ctrls = 0
        if not self.processors:
            self.list_data.append((None, None, "NO PROCESSORS!"))
        else:
            i = 0
            # Chain controllers => favorite processor controllers
            # Some processors have no chain => I.e. global audio player
            if self.processors[0].chain:
                chain_zctrls = self.processors[0].chain.zctrls
                if chain_zctrls:
                    self.list_data.append((None, None, "> CHAIN", None))
                    j = 0
                    i += 1
                    page_zctrls = []
                    for zctrl in chain_zctrls:
                        page_zctrls.append(zctrl)
                        if len(page_zctrls) == 4:
                            self.list_data.append((f"CHAIN_{j}", -1, f"Controllers {j + 1}", self.processors[0], j, page_zctrls))
                            page_zctrls = []
                            j += 1
                            i += 1
                    if len(page_zctrls) > 0:
                        self.list_data.append((f"CHAIN_{j}", -1, f"Controllers {j + 1}", self.processors[0], j, page_zctrls))
                        j += 1
                        i += 1
                    self.n_screens_chain_ctrls = j
            # Processor Controllers
            for processor in self.processors:
                j = 0
                screen_list = processor.get_ctrl_screens()
                procname = processor.engine.name.split('/')[-1]
                self.list_data.append((None, None, f"> {procname}", processor))
                i += 1
                if processor == curproc:
                    self.index = i + curproc.get_current_screen_index()
                for cscr in screen_list:
                    try:
                        self.list_data.append((screen_list[cscr][0].group_symbol, i, cscr, processor, j))
                        i += 1
                        j += 1
                    except Exception as e:
                        logging.error(f"Can't add control page '{cscr}' for processor '{procname}' => {e}")
                self.get_screen_info()
        super().fill_list()

    def get_screen_info(self):
        if 0 <= self.index < len(self.list_data):
            self.screen_info = self.list_data[self.index]
            while self.screen_info and self.screen_info[0] is None:
                if self.index + 1 < len(self.list_data):
                    self.index += 1
                    self.screen_info = self.list_data[self.index]
                else:
                    self.screen_info = None
            if self.screen_info:
                if len(self.screen_info) >= 5:
                    self.screen_title = self.screen_info[2]
                    self.screen_type = None
                    return True
            else:
                pass
                # logging.info("Can't get screen info!!")
        self.screen_title = ""
        self.screen_type = None
        return False

    def get_screen_type(self):
        self.widget_zctrl = None
        for zctrl in self.zcontrollers:
            if hasattr(zctrl, "envelope"):
                self.screen_type = "envelope"
                break
            elif hasattr(zctrl, "filter"):
                self.screen_type = "filter"
                break
            elif zctrl.is_path and zctrl.path_file_types and (set(zctrl.path_file_types) & {"wav", "aiff", "flac", "mp3", "ogg"}):
                self.screen_type = "audio_file"
                self.widget_zctrl = zctrl
                break
        return self.screen_type

    def fill_listbox(self):
        super().fill_listbox()
        for i, val in enumerate(self.list_data):
            if val[0] is None:
                # self.listbox.itemconfig(i, {'bg': zynthian_gui_config.color_off,'fg': zynthian_gui_config.color_tx_off})
                self.listbox.itemconfig(i, {'bg': zynthian_gui_config.color_panel_hl, 'fg': zynthian_gui_config.color_tx_off})

    def set_selector(self, zs_hiden=True):
        if self.mode == 'select':
            super().set_selector(zs_hiden)

    def show_widget(self, processor):
        self.purge_widgets()

        if processor.engine.custom_gui_fpath:
            module_path = processor.engine.custom_gui_fpath
        elif self.screen_type:  # and not module_path
            module_path = f"/zynthian/zynthian-ui/zyngui/zynthian_widget_{self.screen_type}.py"
        else:
            self.zyngui.after_idle(self.hide_widgets)
            return

        module_name = Path(module_path).stem
        if module_name.startswith("zynthian_widget_"):
            try:
                module = self.modules[module_name]
            except:
                # Load module if not loaded
                try:
                    spec = importlib.util.spec_from_file_location(module_name, module_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    self.modules[module_name] = module
                except Exception as e:
                    logging.error(f"Can't load custom widget module '{module_name}' => {e}")
                    self.zyngui.after_idle(self.hide_widgets)
                    return

            # Create new widget if needed
            widget_name = module_name[len("zynthian_widget_"):]
            try:
                multi_instance = getattr(module, "MULTI_INSTANCE")
                if multi_instance:
                    widget_name += f"#{processor.id}"
            except:
                pass
            if widget_name not in self.widgets:
                try:
                    module_class = getattr(module, module_name)
                    self.widgets[widget_name] = module_class(self)
                except Exception as e:
                    logging.error(f"Can't create custom widget instance '{widget_name}' => {e}")
                    self.zyngui.after_idle(self.hide_widgets)
                    return

            # Configure widget's processor
            self.widgets[widget_name].set_processor(processor)

            # Display widget
            self.zyngui.after_idle(self.display_widget, widget_name)

        else:
            self.zyngui.after_idle(self.hide_widgets)

    # Display widget and hide other ones
    def display_widget(self, widget_name):
        # Display widget and hide other ones
        for k, widget in self.widgets.items():
            if k == widget_name:
                self.listbox.grid_remove()
                lb_rows = self.layout['rows'] - widget.rows
                if lb_rows > 0:
                    self.listbox.grid(rowspan=lb_rows)
                    self._select_listbox(self.index, see=True)
                widget.grid(row=self.layout['list_pos'][0] + lb_rows,
                            column=self.layout['list_pos'][1],
                            rowspan=widget.rows, padx=self.padx, sticky="news")
                widget.show()
                self.set_current_widget(widget)
            else:
                widget.grid_remove()
                widget.hide()

    # Hide all widgets
    def hide_widgets(self):
        for k, widget in self.widgets.items():
            widget.grid_remove()
            widget.hide()
        self.set_current_widget(None)
        self.listbox.grid_remove()
        self.listbox.grid(rowspan=4)

    def purge_widgets(self):
        """
            Clean widget instances of removed processors (multi-instance modules only)
        """
        # multi_instances = [k for k, v in self.widgets.items() if k.startswith(widget_name)]
        for k in list(self.widgets.keys()):
            parts = k.split("#")
            try:
                proc_id = int(parts[1])
            except:
                continue
            if proc_id not in self.chain_manager.processors:
                logging.debug(f"Deleting orphaned widget: {k}")
                if self.widgets[k] == self.current_widget:
                    self.hide_widgets()
                del self.widgets[k]

    def set_current_widget(self, widget):
        if widget is None and self.current_widget is None:
            return
        if widget is not None and widget == self.current_widget:
            return
        self.current_widget = widget

    def update_wsleds(self, leds):
        if self.current_widget:
            try:
                self.current_widget.update_wsleds(leds)
            except (AttributeError, TypeError):
                pass


    # TODO: Should this be refactored so current_processor is not a zyngui variable?
    # Should current_processor be a chain_control variable?

    def set_current_processor(self, proc):
        if proc != self.zyngui.get_current_processor():
            self.zyngui.set_current_processor(proc)
            if self.parent:
                self.parent.chain_canvas.select_processor(proc=proc)

    def get_current_processor(self):
        return self.zyngui.get_current_processor()

    def set_controller_screen(self):
        # Get screen info
        if self.get_screen_info():
            try:
                self.set_current_processor(self.screen_info[3])
            except Exception as e:
                logging.warning(f"Failed to set current processor {e}")
            curproc = self.get_current_processor()

            # Get controllers for the current screen
            # Chain controllers
            if self.screen_info[1] == -1:
                curproc.set_current_screen_index(self.screen_info[4] - self.n_screens_chain_ctrls - 1)
                self.zcontrollers = self.screen_info[5]
            # Processor controllers
            else:
                curproc.set_current_screen_index(self.screen_info[4])
                self.zcontrollers = curproc.get_ctrl_screen(self.screen_title)
                # Show the widget for the current processor (NOT for chain controllers pages!)
                self.get_screen_type()
                if self.mode == 'control':
                    self.show_widget(curproc)
        else:
            self.zcontrollers = []
            self.screen_title = ""
            self.screen_type = None
            self.hide_widgets()

        # Setup GUI Controllers
        logging.debug(self.screen_title)
        # Configure zgui_controllers
        for i in range(4):
            if i < len(self.zcontrollers):
                ctrl = self.zcontrollers[i]
                try:
                    # logging.debug(f"CONTROLLER ARRAY {i} => {ctrl.symbol} ({ctrl.short_name})")
                    self.set_zcontroller(i, ctrl)
                    continue
                except Exception as e:
                    logging.exception("Controller %s (%d) => %s" %(ctrl.short_name, i, e))
                    #self.zgui_controllers[i].hide()
            self.set_zcontroller(i, None)

    def set_zcontroller(self, i, ctrl):
        if i < len(self.zgui_controllers):
            self.zgui_controllers[i].config(ctrl)
            self.zgui_controllers[i].show()

    def get_zcontroller(self, i):
        if i < len(self.zgui_controllers):
            return self.zgui_controllers[i].zctrl
        else:
            return None

    def set_mode_select(self):
        self.exit_midi_learn()
        self.mode = 'select'
        if self.zyngui.tts:
            self.zyngui.tts.announce("Select mode enabled")
        if self.current_widget and self.current_widget.hide_on_select_mode():
            self.hide_widgets()
        #self.listbox.config(selectbackground=zynthian_gui_config.color_ctrl_bg_off,
        #                    selectforeground=zynthian_gui_config.color_ctrl_tx,
        #                    fg=zynthian_gui_config.color_ctrl_tx_off)
        self.set_selector()
        for i in range(0, len(self.zgui_controllers)):
            self.zgui_controllers[i].enable(False)

    def set_mode_control(self):
        self.mode = 'control'
        if self.zyngui.tts:
            self.zyngui.tts.announce("Control mode enabled")
        self.show_widget(self.get_current_processor())
        #self.listbox.config(selectbackground=zynthian_gui_config.color_ctrl_bg_on,
        #                    selectforeground=zynthian_gui_config.color_ctrl_tx,
        #                    fg=zynthian_gui_config.color_ctrl_tx)
        for i in range(0, len(self.zgui_controllers)):
            self.zgui_controllers[i].enable(True)

    def select_processor(self, proc):
        if not self.processors:
            return
        # Chain controllers
        if not proc and self.processors[0].chain.zctrls:
            if self.index != 1:
                self.select(1)
        # Processor controllers
        elif proc in self.processors:
            for i, row in enumerate(self.list_data):
                if row[1] and row[1] > 0 and row[3] == proc:
                    index = i + proc.current_screen_index
                    if self.index != index:
                        self.select(index)
                    return

    def get_selected_processor(self):
        row = self.list_data[self.index]
        if row[1] and row[1] > 0:
            return row[3]
        else:
            return None

    def select_mixer_processor(self, page=0):
        for i, row in enumerate(self.list_data):
            if row[1] and row[1] > 0 and row[3].eng_code in ("MI", "MR"):
                self.select(i + page)
                return

    # --------------------------------------------------------------------------
    # Zynpot & zynswitch callbacks
    # --------------------------------------------------------------------------

    def show_menu(self):
        #curproc = self.zyngui.get_current_processor()
        self.zyngui.show_screen("processor_options")
        return True

    # Function to handle *all* switch presses.
    #  swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
    #  t: Press type ["S"=Short, "B"=Bold, "L"=Long]
    #  returns True if action fully handled or False if parent action should be triggered
    def switch(self, swi, t='S'):
        if t == 'B' and self.midi_learning:
            self.controller_options(swi)
            return True

        if self.current_widget:
            try:
                if self.current_widget.switch(swi, t):
                    return True
            except:
                # TODO Fix this to catch exceptions from widget!!
                pass

        # V4's bank/preset
        if swi == 3 and t == 'B':
            self.zyngui.cuia_bank_preset()
            return True

        return False

    def cuia_v5_zynpot_switch(self, params):
        i = params[0]
        t = params[1].upper()
        if self.mode == 'control':
            if t == 'S':
                if len(self.zcontrollers) > i and self.zcontrollers[i] and self.zcontrollers[i].is_path:
                    self.zcontrollers[i].nudge(0)
                else:
                    self.toggle_midi_learn(i)
                return True
            elif t == 'B' or t == 'L':
                self.controller_options(i)
                return True
        return False

    def switch_select(self, t):
        if t == 'S':
            if self.mode == 'control':
                self.set_mode_select()
            elif self.mode == 'select':
                self.set_mode_control()
        elif t == 'B':
            self.show_menu()
        return True

    def select(self, index=None, set_zctrl=True):
        super().select(index, set_zctrl)
        #if self.mode == 'select':
        self.set_controller_screen()
        self.set_select_path()

    def back_action(self):
        # If in MIDI-learn mode, back to instrument control
        if self.midi_learning:
            self.exit_midi_learn()
            return True
        else:
            return False

    def zynpot_abs(self, i, val):
        if self.mode == 'control':
            self.zgui_controllers[i].zynpot_abs(val)

    def zynpot_cb(self, i, dval):
        if self.current_widget:
            try:
                if self.current_widget.zynpot_cb(i, dval):
                    return
            except:
                pass
        if self.mode == 'control' and self.zcontrollers:
            if self.zgui_controllers[i].zynpot_cb(dval):
                if self.midi_learning:
                    self.midi_learn(i, self.midi_learning)
                    if self.zyngui.tts:
                        self.zyngui.tts.announce(f"MIDI learning: {self.zgui_controllers[i].zctrl.name}")
                elif self.zyngui.tts:
                    zctrl = self.zgui_controllers[i].zctrl
                    self.zyngui.tts.announce(f"{zctrl.name}: {zctrl.get_value2label()}")
                return True
        elif self.mode == 'select':
            return super().zynpot_cb(i, dval)

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
        #if self.mode == 'select':
        #    super().plot_zctrls()
        if self.zgui_controllers:
            self.swipe_update()
            for zgui_ctrl in self.zgui_controllers:
                if zgui_ctrl.zctrl and zgui_ctrl.zctrl.is_dirty or force:
                    zgui_ctrl.calculate_plot_values()
                    zgui_ctrl.plot_value()
                    zgui_ctrl.zctrl.is_dirty = False
        if self.mode == 'control':
            for k, widget in self.widgets.items():
                widget.update()

    # --------------------------------------------------------------------------
    # CUIA => Pass CUIA to widget
    # --------------------------------------------------------------------------

    def callable_ui_action(self, cuia, params=None):
        if self.current_widget:
            logging.debug("CUIA '{}' => {}".format(cuia, params))
            # Try widget-defined specific cuia function
            cuia_func_name = "cuia_" + cuia.lower()
            cuia_func = getattr(self.current_widget, cuia_func_name, None)
            if callable(cuia_func) and cuia_func(params):
                return True
            else:
                # Else call default CUIA function (defined in this class)
                cuia_func = getattr(self, cuia_func_name, None)
                if callable(cuia_func):
                    return cuia_func(params)
        return False

    def get_alt_mode(self):
        return self.alt_mode

    # --------------------------------------------------------------------------
    # MIDI learn management
    # --------------------------------------------------------------------------

    def enter_midi_learn(self, mlmode=MIDI_LEARNING_CHAIN, preselect=True):
        if mlmode > MIDI_LEARNING_DISABLED:
            self.midi_learning = mlmode
            self.refresh_midi_bind(preselect)
            self.set_select_path()
            if self.zyngui.tts:
                if mlmode == MIDI_LEARNING_CHAIN:
                    self.zyngui.tts.announce("Chain MIDI learn enabled")
                else:
                    self.zyngui.tts.announce("Global MIDI learn enabled")

    def exit_midi_learn(self):
        if self.midi_learning != MIDI_LEARNING_DISABLED:
            self.midi_learning = MIDI_LEARNING_DISABLED
            self.zyngui.state_manager.disable_learn_cc()
            self.refresh_midi_bind()
            self.set_select_path()
            if self.zyngui.tts:
                self.zyngui.tts.announce("MIDI learn disabled", False, False, False)

    def toggle_midi_learn(self, i=None):
        if self.mode != 'control':
            return

        # Handle alsa mixer
        default_midi_learning_mode = MIDI_LEARNING_CHAIN
        try:
            if self.zyngui.get_current_processor().eng_code == "MX":
                default_midi_learning_mode = MIDI_LEARNING_GLOBAL
        except:
            pass

        if i is not None:
            # Restart MIDI learn with a new controller
            if self.zgui_controllers[i].zctrl is None:
                self.exit_midi_learn()
                return self.midi_learn
            if self.zgui_controllers[i].zctrl != self.zyngui.state_manager.get_midi_learn_zctrl():
                self.midi_learn(i, default_midi_learning_mode)
                return self.midi_learning

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
                self.enter_midi_learn(default_midi_learning_mode, False)
            else:
                self.enter_midi_learn(default_midi_learning_mode, True)

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
            self.chain_manager.add_midi_learn(chan, midi_cc, self.zyngui.state_manager.get_midi_learn_zctrl())
        elif self.midi_learning == MIDI_LEARNING_GLOBAL:
            self.chain_manager.add_midi_learn(chan, midi_cc, self.zyngui.state_manager.get_midi_learn_zctrl(), zmip)
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
            #self.zyngui.show_current_screen()

    def midi_unlearn(self, param=None):
        if param:
            self.chain_manager.clean_midi_learn(param)
        else:
            self.chain_manager.clean_midi_learn(self.zyngui.get_current_processor())
        self.refresh_midi_bind()

    def midi_unlearn_action(self):
        curproc = self.zyngui.get_current_processor()
        if curproc:
            engine_name = curproc.get_name()
            if engine_name:
                question_str = f"Do you want to clean MIDI-learn for ALL controls in {engine_name}"
                if curproc.midi_chan is not None and 0 <= curproc.midi_chan < 16:
                    question_str += f" on MIDI channel {curproc.midi_chan + 1}"
                self.zyngui.show_confirm(question_str + "?", self.midi_unlearn)
            else:
                logging.error("Can't get processor name.")

    def controller_options(self, i, keep_selection=False, unlearn_only=False):
        self.exit_midi_learn()
        if len(self.zgui_controllers) > i and self.zgui_controllers[i] and self.zgui_controllers[i].zctrl:
            zctrl = self.zgui_controllers[i].zctrl
        else:
            #logging.debug("No GUI zctrl#{i}!")
            return
        try:
            options = {}
            if zctrl.is_path:
                title = f"Control options: {zctrl.name}"
                if self.processors[0].chain:
                    if zctrl in self.processors[0].chain.zctrls:
                        options["\u2612 Chain Controller"] = zctrl
                    else:
                        options["\u2610 Chain Controller"] = zctrl

                options["Clear"] = zctrl

                self.zyngui.screens['option'].config(title, options, self.controller_options_cb)
                self.zyngui.show_screen('option')
                return

            ml = self.chain_manager.get_midi_learn_from_zctrl(zctrl, abs=True, chain=True, zynstep=False)
            if not unlearn_only:
                title = f"Control options: {zctrl.name}"

                if self.processors[0].chain:
                    if zctrl in self.processors[0].chain.zctrls:
                        options["\u2612 Chain Controller"] = zctrl
                    else:
                        options["\u2610 Chain Controller"] = zctrl

                if not zctrl.is_toggle:
                    options["X-Y touchpad"] = None
                    # Only show X-Y if both zctrl are valid
                    if self.zyngui.state_manager.zctrl_x and self.zyngui.state_manager.zctrl_y:
                        options["Show touchpad"] = True
                    if self.zyngui.state_manager.zctrl_x:
                        xinfo = f" => {self.zyngui.state_manager.zctrl_x.name}"
                    else:
                        xinfo = ""
                    if zctrl == self.zyngui.state_manager.zctrl_x:
                        options[f"\u2612 X-axis{xinfo}"] = i
                    else:
                        options[f"\u2610 X-axis{xinfo}"] = i
                    if self.zyngui.state_manager.zctrl_y:
                        yinfo = f" => {self.zyngui.state_manager.zctrl_y.name}"
                    else:
                        yinfo = ""
                    if zctrl == self.zyngui.state_manager.zctrl_y:
                        options[f"\u2612 Y-axis{yinfo}"] = i
                    else:
                        options[f"\u2610 Y-axis{yinfo}"] = i

                options["MIDI learn"] = None
                if zctrl.is_toggle:
                    if zctrl.midi_cc_momentary_switch:
                        options["\u2612 Momentary => Latch"] = i
                    else:
                        options["\u2610 Momentary => Latch"] = i
                    if zctrl.midi_cc_debounce:
                        options["\u2612 Debounce"] = i
                    else:
                        options["\u2610 Debounce"] = i
                elif ml:
                    match zctrl.midi_cc_mode:
                        case -1:
                            options["Relative Mode learning..."] = i
                            options["CC Value Range"] = i
                        case 0:
                            if zctrl.range_reversed:
                                options["Absolute Reverse"] = i
                            else:
                                options["Absolute Mode"] = i
                            options["CC Value Range"] = i
                        case _:
                            options[f"Relative Mode {zctrl.midi_cc_mode}"] = i
                if zctrl.processor:
                    options[f"Chain learn..."] = i
                options[f"Global learn..."] = i
                zynstep_ml = self.chain_manager.get_midi_learn_from_zctrl(zctrl, abs=False, chain=False, zynstep=True)
                if zynstep_ml:
                    ccnum = zynstep_ml[0] & 0x7f
                else:
                    ccnum = "NONE"
                options[f"ZynStep CC [{ccnum}]"] = i
            else:
                title = "Control unlearn"

            if ml:
                cc = ml[0] & 0x7f
                chan = (ml[0] >> 8) & 0xff
                if chan < 16:
                    ml_text = f"CH{chan + 1}, CC{cc}"
                else:
                    ml_text = f"CC{cc}"
                match ml[1]:
                    case "abs":
                        zmip = (ml[0] >> 16) & 0xff
                        dev_name = zynautoconnect.get_midi_in_devid(zmip)
                        options[f"Unlearn [{dev_name}, {ml_text}]"] = zctrl
                    case "chain":
                        options[f"Unlearn [{ml_text}]"] = zctrl
            options["Unlearn all controls"] = ""

            if keep_selection:
                index = None
            else:
                index = 0
            self.zyngui.screens['option'].config(title, options, self.controller_options_cb, index=index)
            self.zyngui.show_screen('option')
        except Exception as e:
            logging.error(f"Can't show control options for GUI zctrl#{i} => {e}")

    def controller_options_cb(self, option, param):
        if option[2:] == "Chain Controller":
            if self.processors[0].chain:
                self.processors[0].chain.toggle_zctrl(param)
                self.update_list()
        elif option == "Show touchpad":
            self.show_xy()
        elif option == "Clear":
            param.set_value("")
            self.select()
        elif option == "CC Value Range":
            self.zyngui.screens["midi_cc_range"].config(self.zgui_controllers[param].zctrl)
            self.zyngui.show_screen('midi_cc_range')
        else:
            parts = option.split(" ")
            if parts[1] == "X-axis":
                zctrl = self.zgui_controllers[param].zctrl
                if self.zyngui.state_manager.zctrl_x == zctrl:
                    self.zyngui.state_manager.zctrl_x = None
                else:
                    self.zyngui.state_manager.zctrl_x = zctrl
                if self.zyngui.state_manager.zctrl_y == zctrl:
                    self.zyngui.state_manager.zctrl_y = None
                #self.refresh_midi_bind()
                self.controller_options(param, keep_selection=True)
            elif parts[1] == "Y-axis":
                zctrl = self.zgui_controllers[param].zctrl
                if self.zyngui.state_manager.zctrl_y == zctrl:
                    self.zyngui.state_manager.zctrl_y = None
                else:
                    self.zyngui.state_manager.zctrl_y = zctrl
                if self.zyngui.state_manager.zctrl_x == zctrl:
                    self.zyngui.state_manager.zctrl_x = None
                #self.refresh_midi_bind()
                self.controller_options(param, keep_selection=True)
            elif parts[0] == "Chain":
                self.midi_learn(param, MIDI_LEARNING_CHAIN)
            elif parts[0] == "Global":
                self.midi_learn(param, MIDI_LEARNING_GLOBAL)
            elif parts[0] == "ZynStep":
                try:
                    ccnum = int(parts[2][1:-1])
                except:
                    ccnum = None
                self.zyngui.screens['midi_cc_single'].config(self.zynstep_midi_cc_cb, ccnum, param)
                self.zyngui.show_screen('midi_cc_single')
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
                self.controller_options(param, keep_selection=True)
            elif parts[1] == "Debounce":
                if parts[0] == '\u2612':
                    self.zgui_controllers[param].zctrl.midi_cc_debounce = 0
                else:
                    self.zgui_controllers[param].zctrl.midi_cc_debounce = 1
                self.controller_options(param, keep_selection=True)
            elif parts[0] in ["Relative", "Absolute"]:
                options = {
                    "Absolute Mode": (param, 0),
                    "Absolute Reverse": (param, 0),
                    "Relative Mode 1": (param, 1),
                    "Relative Mode 2": (param, 2),
                    "Relative Mode 3": (param, 3),
                    "Relative Mode 4": (param, 4),
                    "Learn Relative Mode": (param, -1)
                }
                self.zyngui.screens['option'].config("Select CC mode", options, self.set_cc_mode)
                self.zyngui.show_screen('option')

    def set_cc_mode(self, option, param):
        self.zgui_controllers[param[0]].zctrl.midi_cc_mode_set(param[1])
        self.zgui_controllers[param[0]].zctrl.range_reversed = "Reverse" in option
        self.controller_options(param[0], keep_selection=True)

    def zynstep_midi_cc_cb(self, ccnum, i):
        zctrl = self.zgui_controllers[i].zctrl
        self.chain_manager.add_zynstep_midi_learn(ccnum, zctrl)
        self.controller_options(i, keep_selection=True)

    def show_xy(self, params=None):
        self.zyngui.show_screen("control_xy")

    # -------------------------------------------------------------------------
    # Touch & Mouse callbacks
    # --------------------------------------------------------------------------

    def cb_listbox_click(self, t):
        # Override listbox click - we don't want short/bold press
        return

    def cb_listbox_motion(self, event):
        return super().cb_listbox_motion(event)

    def cb_listbox_wheel(self, event):
        # Override with default listbox behaviour to allow scrolling of listbox without selection (expected UX)
        return

    # -------------------------------------------------------------------------
    # GUI Callback function
    # --------------------------------------------------------------------------

    def set_select_path(self):
        processor = self.zyngui.get_current_processor()
        if processor:
            if self.mode == 'control' and self.midi_learning:
                if self.midi_learning == MIDI_LEARNING_CHAIN:
                    self.select_path.set(processor.get_basepath() + "/CHAIN Control MIDI-Learn")
                elif self.midi_learning == MIDI_LEARNING_GLOBAL:
                    self.select_path.set(processor.get_basepath() + "/GLOBAL Control MIDI-Learn")
                else:
                    self.select_path.set(processor.get_basepath() + "/CHAIN Control MIDI-Learn")
            else:
                self.select_path.set(processor.get_presetpath())
        else:
            self.select_path.set(self.chain_manager.get_active_chain().get_title())

    def get_help_fpath(self):
        try:
            return self.zyngui.get_current_processor().name.lower() + ".html"
        except:
            return super().get_help_fpath()

    # --------------------------------------------------------------------------
    # ZynVoice TTS
    # --------------------------------------------------------------------------

    def tts_info(self):
        if not self.zyngui.tts:
            return
        self.zyngui.tts.announce(f"View: {self.tts_title}")
        self.zyngui.tts.announce(f"Page: {self.list_data[self.index][2]}", False, False, False)
        for i, zgui_ctrl in enumerate(self.zgui_controllers):
            if zgui_ctrl and zgui_ctrl.zctrl:
                self.zyngui.tts.announce(f"Control {i+1}: {zgui_ctrl.zctrl.name}: {zgui_ctrl.zctrl.get_value2label()}", False, False, False)

# ------------------------------------------------------------------------------
