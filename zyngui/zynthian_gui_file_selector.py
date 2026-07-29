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
import oyaml as yaml

# Zynthian specific modules
from zyngine.zynthian_engine import zynthian_engine
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector_info import zynthian_gui_selector_info


# ------------------------------------------------------------------------------
# Zynthian File Selector GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_file_selector(zynthian_gui_selector_info):

    collections_dpath = zynthian_engine.data_dir + "/collections/"

    fext2dirname = {
        "aidax": [["Neural Models"], "file_model.png"],
        "aidadspmodel": [["Neural Models"], "file_model.png"],
        "nam": [["Neural Models"], "file_model.png"],
        "nammodel": [["Neural Models"], "file_model.png"],
        "json": [["Neural Models"], "file_model.png"],
        "wav": [["IRs", "Samples", "Audio"], "file_audio.png"],
        "flac": [["IRs", "Samples", "Audio"], "file_audio.png"],
        "aiff": [["IRs", "Samples", "Audio"], "file_audio.png"],
        "ogg": [["Samples", "Audio"], "file_audio.png"],
        "mp3": [["Samples", "Audio"], "file_audio.png"],
        "mid": [["Midi"], "file_midi.png"],
        "scl": [["Tuning"], "file.png"],
        "zpat": [["Patterns"], "file_midi.png"],
    }

    def __init__(self):
        self.cb_func = None
        self.root_dirs = []
        self.fexts = []
        self.collection_info = {}
        self.path = None
        self.dirpath = None
        self.init_path = None
        self.sel_path = None
        self.preload = False
        self.preload_timer_id = None
        self.preload_timer_ms = 200
        super().__init__('File', default_icon="folder.png", zsel_hidden=True)

    @classmethod
    def get_root_dirnames(cls, fexts):
        dirnames = []
        for fext in fexts:
            try:
                for dirname in cls.fext2dirname[fext.lower()][0]:
                    dirnames.append(dirname)
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

    def is_confined_to_root_dirs(self, path):
        for row in self.root_dirs:
            if path.startswith(row[1]):
                return True
        return False

    def get_relative_path(self, path):
        for row in self.root_dirs:
            if len(path) > len(row[1]) and path.startswith(row[1]):
                return row[0] + path[len(row[1]):]
        return ""

    def is_root_dir(self, path):
        for row in self.root_dirs:
            if path == row[1]:
                return True
        return False

    def get_collection_icon(self, dpath):
        for de in os.scandir(dpath + "/Art"):
            if de.is_file() and os.path.splitext(de.name)[-1] in (".jpg", ".png"):
                return de.path

    def get_collection_info(self, path):
        if path and path.startswith(self.collections_dpath):
            try:
                dname = path[len(self.collections_dpath):].split("/")[0]
                return self.collection_info[dname]
            except:
                return None

    def load_collection_info(self, dname):
        dpath = self.collections_dpath + "/" + dname
        try:
            fh = open(f"{dpath}/info.yml", "r")
        except:
            logging.info(f"No yaml info file for collection '{dpath}'")
            self.default_collection_info(dname)
            return False
        try:
            yml = fh.read()
            #logging.info(f"Loading yaml info file for collection '{dpath}' =>\n{yml}")
            info = yaml.load(yml, Loader=yaml.SafeLoader)
            info["icon"] = dpath + "/" + info["icon"]
            self.collection_info[dname] = info
            return True
        except Exception as e:
            logging.error(f"Bad yaml info file for collection '{dpath}' => {e}")
            self.default_collection_info(dname)
            return False

    def default_collection_info(self, dname):
        dpath = self.collections_dpath + "/" + dname
        self.collection_info[dname] = {
            "title": dname,
            "icon": self.get_collection_icon(dpath),
            "author": "Unknown",
            "license": "Unknown",
            "description": ""
        }

    def show_details(self, path=None):
        if not path:
            path = self.list_data[self.index][0]
        info = self.get_collection_info(path)
        if info:
            description = info["description"].replace("\n", "</p>\n<p>")
            html = f"""<html>
 <head>
  <link rel="stylesheet" href="style_details.css">
 </head>
 <body class="help_ui">
 <div class="details_container">
  <img class="icon" src="{info['icon']}">
  <h1>{info['title']}</h1>
  <div class="author"><b>Author:</b> {info["author"]}</div>
  <div class="license"><b>License:</b> {info["license"]}</div>
  <p class="description">{description}</p>
 </body>
</html>
"""
            self.path = path
            self.zyngui.screens['help'].set_html(html)

    def config(self, cb_func, fexts=None, dirnames=None, path=None, preload=False):
        self.list_data = []
        self.root_dirs = []
        self.cb_func = cb_func
        self.preload = preload
        if fexts:
            self.fexts = fexts
        else:
            self.fexts = ["wav"]
        if path:
            self.init_path = path
            self.sel_path = path
            self.path = path
            self.dirpath = self.get_dirpath(self.path)
        else:
            self.init_path = None
            self.sel_path = None
            self.path = None
            self.dirpath = None
        # Config root dirs
        if dirnames is None:
            dirnames = self.get_root_dirnames(self.fexts)
        # User files
        for dirname in dirnames:
            self.root_dirs.append((f"User {dirname}", zynthian_engine.my_data_dir + "/files/" + dirname))
        # Collections
        for de in os.scandir(self.collections_dpath):
            if de.is_dir():
                self.load_collection_info(de.name)
                for dirname in dirnames:
                    self.root_dirs.append((f"{de.name} {dirname}", de.path + "/" + dirname))
        # System files
        for dirname in dirnames:
            self.root_dirs.append((f"System {dirname}", zynthian_engine.data_dir + "/files/" + dirname))
        if self.dirpath and not self.is_confined_to_root_dirs(self.dirpath):
            dpbname = os.path.basename(self.dirpath)
            self.root_dirs.append((f"Current ({dpbname})", self.dirpath))

        self.set_select_path()

    def hide(self):
        # Restore initial selection if it was changed while preloading
        if self.shown and self.cb_func and self.init_path and self.sel_path != self.init_path and os.path.isfile(self.init_path):
            self.cb_func(self.init_path)
        super().hide()

    def fill_list(self):
        # Get dir/file list
        if self.dirpath and not self.is_root_dir(self.dirpath):
            self.list_data = zynthian_engine.get_filelist(self.dirpath, self.fexts, include_dirs=True)
        else:
            self.list_data = zynthian_engine.get_dir_file_list(fexts=self.fexts,
                                                               root_dirs=self.root_dirs,
                                                               recursion=1)
        # Add info and find selected index
        self.index = 0
        for i, item in enumerate(self.list_data):
            if not item[0]:
                continue
            if item[0] == self.path:
                self.index = i
            colinfo = self.get_collection_info(item[0])
            if colinfo:
                text = "\n"
                if colinfo['author']:
                    text += "Author: " + colinfo['author'] + "\n"
                if colinfo['license']:
                    text += "License: " + colinfo['license'] + "\n"
                text += "\n" + colinfo['description']
                item.append([text, colinfo['icon']])
            elif len(item) == 6:
                try:
                    fticon = self.fext2dirname[item[5]][1]
                except:
                    logging.warning(f"File type '{item[5]}' not supported")
                    continue
                item.append(["", fticon])
            else:
                item.append(["Folder", "folder.png"])
        super().fill_list()

    def update_list(self):
        if self.shown:
            self.fill_list()
            self.set_selector()
            self.set_select_path()
            self.select()

    def switch(self, i, t):
        if i == 2 and t == 'S':
            self.show_details()
            return True

    def cuia_v5_zynpot_switch(self, params):
        i = params[0]
        t = params[1].upper()
        if i == 2 and t == 'S':
            self.show_details()
            return True
        return False

    def select_action(self, i, t='S'):
        if self.list_data and i < len(self.list_data):
            path = self.list_data[i][0]
            if os.path.isdir(path):
                self.path = path
                self.dirpath = self.get_dirpath(path)
                self.update_list()
            elif os.path.isfile(path):
                self.path = path
                self.sel_path = path
                self.init_path = path
                self.zyngui.close_screen()
                self.cb_func(path)
            else:
                self.zyngui.close_screen()

    def back_action(self):
        if self.dirpath:
            parts = os.path.split(self.dirpath)
            if self.is_confined_to_root_dirs(parts[0]):
                self.path = self.dirpath
                self.dirpath = parts[0]
                self.update_list()
                return True
        return False

    def select_listbox(self, index, see=True):
        super().select_listbox(index, see=True)
        if self.preload:
            try:
                zynthian_gui_config.top.after_cancel(self.preload_timer_id)
            except:
                pass
            self.preload_timer_id = zynthian_gui_config.top.after(self.preload_timer_ms, self.preload_file)

    def preload_file(self):
        self.preload_timer_id = None
        if self.list_data and self.index < len(self.list_data):
            path = self.list_data[self.index][0]
            if os.path.isfile(path):
                self.sel_path = path
                self.cb_func(path)

    def set_select_path(self):
        if self.dirpath:
            #path = os.path.split(self.dirpath)[1]
            path = self.get_relative_path(self.dirpath)
            self.select_path.set(f"File Selector > {path}")
        else:
            self.select_path.set("File Selector")

# -------------------------------------------------------------------------------
