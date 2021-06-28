#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian Qt GUI Base Class: Base qtobject all gui logic uses
# 
# Copyright (C) 2021 Marco Martin <mart@kde.org>
#
#******************************************************************************
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
#******************************************************************************

from PySide2.QtCore import Qt, QObject, Slot, Signal, Property

class ZynGui(QObject):
    def __init__(self, parent=None):
        super(ZynGui, self).__init__(parent)
        self.zyngui = zynthian_gui_config.zyngui
        self.select_path = ""

    def set_select_path(self):
        pass

#------------------------------------------------------------------------------
