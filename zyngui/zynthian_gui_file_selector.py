#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI File Selector Class
#
# Copyright (C) 2015-2025 Fernando Moyano <jofemodo@zynthian.org>
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

# Zynthian specific modules
from zyngine.zynthian_engine import zynthian_engine
from zyngui.zynthian_gui_selector_info import zynthian_gui_selector_info

# ------------------------------------------------------------------------------
# Zynthian File Selector GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_file_selector(zynthian_gui_selector_info):

    fext2dirname = {
        "aidax": ["Neural Models", "file_model.png"],
        "aidadspmodel": ["Neural Models", "file_model.png"],
        "nam": ["Neural Models", "file_model.png"],
        "nammodel": ["Neural Models", "file_model.png"],
        "json": ["Neural Models", "file_model.png"],
        "wav": ["IRs", "file_audio.png"],
        "scl": ["Tuning", "file.png"]
    }

    def __init__(self):
        self.cb_func = None
        self.root_dirs = []
        self.fexts = []
        self.path = None
        self.dirpath = None
        super().__init__('File', default_icon="folder.png")

    @classmethod
    def get_root_dirnames(cls, fexts):
        dirnames = []
        for fext in fexts:
            try:
                dirnames.append(cls.fext2dirname[fext.lower()][0])
            except:
                pass
        return set(dirnames)

    @staticmethod
    def get_dirpath(path):
        if path:
            if os.path.isfile(path):
                (dirpath, fname) = os.path.split(path)
                return dirpath
            elif os.path.isdir(path):
                return path

    def config(self, cb_func, fexts=None, root_dirs=None, path=None):
        self.list_data = []
        self.cb_func = cb_func
        if fexts:
            self.fexts = fexts
        else:
            self.fexts = ["wav"]
        if root_dirs:
            self.root_dirs = root_dirs
        else:
            self.root_dirs = []
            dirnames = self.get_root_dirnames(self.fexts)
            for dirname in dirnames:
                self.root_dirs.append((f"User {dirname}", zynthian_engine.my_data_dir + "/files/" + dirname))
            for dirname in dirnames:
                self.root_dirs.append((f"System {dirname}", zynthian_engine.data_dir + "/files/" + dirname))
            if "wav" in self.fexts:
                self.root_dirs.append(("System Audio", zynthian_engine.my_data_dir + "/audio"))
        if path:
            self.path = path
            self.dirpath = self.get_dirpath(self.path)
        else:
            self.path = None
            self.dirpath = None
        self.set_select_path()

    def fill_list(self):
        # Get dir/file list
        if self.dirpath:
            self.list_data = zynthian_engine.get_filelist(self.dirpath, self.fexts)
        else:
            self.list_data = zynthian_engine.get_bank_dirlist(recursion=0, fexts=self.fexts, root_bank_dirs=self.root_dirs)
        # Add info and find selected index
        self.index = 0
        for i, item in enumerate(self.list_data):
            if len(item) == 6:
                item.append(["", self.fext2dirname[item[5]][1]])
            else:
                item.append(["", "folder.png"])
            if item[0] == self.path:
                self.index = i
        super().fill_list()

    def show(self):
        super().show()
        if (autosel_i := self.get_auto_select()) >= 0:
            if self.dirpath:
                self.path = self.dirpath
                self.dirpath = None
                self.update_list()
                self.set_select_path()
            else:
                self.select_action(autosel_i)

    def get_auto_select(self):
        """ Return the index of a solitary list entry or -1 if there are zero or > 1 entries"""
        sel_i = -1
        for i, item in enumerate(self.list_data):
            if item[0] is not None:
                if sel_i >= 0:
                    return -1
                else:
                    sel_i = i
        return sel_i

    def select_action(self, i, t='S'):
        if self.list_data and i < len(self.list_data):
            path = self.list_data[i][0]
            if os.path.isdir(path):
                self.path = path
                self.dirpath = self.get_dirpath(path)
                self.update_list()
                self.set_select_path()
                if (autosel_i := self.get_auto_select()) >= 0 and os.path.isdir(self.list_data[autosel_i][0]):
                    # Drill down empty directories
                    self.select_action(autosel_i)
            elif os.path.isfile(path):
                self.path = path
                self.cb_func(path)
                self.zyngui.close_screen()
            else:
                self.zyngui.close_screen()

    def back_action(self):
        if self.dirpath:
            self.path = self.dirpath
            self.dirpath = None
            self.update_list()
            self.set_select_path()
            if self.get_auto_select() < 0:
                return True
        return False

    def set_selector(self, zs_hidden=False):
        super().set_selector(zs_hidden)

    def set_select_path(self):
        if self.dirpath:
            parts = os.path.split(self.dirpath)
            self.select_path.set(f"File Selector> {parts[1]}")
        else:
            self.select_path.set("File Selector")

# -------------------------------------------------------------------------------
