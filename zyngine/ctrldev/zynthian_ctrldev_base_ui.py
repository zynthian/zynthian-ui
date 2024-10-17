#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Control Device Mode Handler classes
#
# Copyright (C) 2024 Oscar Acena <oscaracena@gmail.com>
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

# FIXME: This implementation is coupled with the graphical user interface, and it
#        should not! Move the implementation to its proper location (gui) and/or
#        provide access to it by CUIA handlers.

from threading import Thread

from zyngui import zynthian_gui_config
from . import zynthian_ctrldev_base_extended


# --------------------------------------------------------------------------
# Extended Base class for mode handlers, with UI related methods
# --------------------------------------------------------------------------
class ModeHandlerBase(zynthian_ctrldev_base_extended.ModeHandlerBase):

    # FIXME: This way avoids to show Zynpad every time, BUT is coupled to UI!
    def _show_pattern_editor(self, seq=None, skip_arranger=False):
        if self._current_screen != 'pattern_editor':
            self._state_manager.send_cuia("SCREEN_ZYNPAD")
        if seq is not None:
            self._select_pad(seq)
        if not skip_arranger:
            zynthian_gui_config.zyngui.screens["zynpad"].show_pattern_editor()
        else:
            zynthian_gui_config.zyngui.show_screen("pattern_editor")

    # FIXME: This SHOULD be a CUIA, not this hack! (is coupled with UI)
    def _select_pad(self, pad):
        zynthian_gui_config.zyngui.screens["zynpad"].select_pad(pad)

    # This SHOULD not be coupled to UI! This is needed because when the pattern is changed in
    # zynseq, it is not reflected in pattern editor.
    def _refresh_pattern_editor(self):
        index = self._zynseq.libseq.getPatternIndex()
        zynthian_gui_config.zyngui.screens["pattern_editor"].load_pattern(
            index)

    # FIXME: This SHOULD not be coupled to UI!
    def _get_selected_sequence(self):
        return zynthian_gui_config.zyngui.screens["zynpad"].selected_pad

    # FIXME: This SHOULD not be coupled to UI!
    def _get_selected_step(self):
        pe = zynthian_gui_config.zyngui.screens["pattern_editor"]
        return pe.keymap[pe.selected_cell[1]]['note'], pe.selected_cell[0]

    # FIXME: This SHOULD be a CUIA, not this hack! (is coupled with UI)
    # NOTE: It runs in a thread to avoid lagging the hardware interface
    def _update_ui_arranger(self, cell_selected=(None, None)):
        def run():
            arranger = zynthian_gui_config.zyngui.screens["arranger"]
            arranger.select_cell(*cell_selected)
            if cell_selected[1] is not None:
                arranger.draw_row(cell_selected[1])
        Thread(target=run, daemon=True).start()

# --------------------------------------------------------------------------
