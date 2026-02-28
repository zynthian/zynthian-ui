#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Widget Class for filter screen type
#
# Copyright (C) 2025 Ronald Summers <ronfsum@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
# ******************************************************************************


import tkinter
import math
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base


class zynthian_widget_filter(zynthian_widget_base.zynthian_widget_base):

    def __init__(self, parent):
        super().__init__(parent)
        self.fg_color = zynthian_gui_config.color_tx
        self.font_small = ("sans", 10)


        # Take only half height
        self.rows //= 2

        self.widget_canvas = tkinter.Canvas(self, highlightthickness=0, relief='flat', bg=zynthian_gui_config.color_bg)
        self.widget_canvas.grid(sticky='news')

        # Theme Colors
        self.fill_color = zynthian_gui_config.color_variant(zynthian_gui_config.color_on, -90)
        self.outline_color = zynthian_gui_config.color_on
        self.grid_color = zynthian_gui_config.color_hl

        # Persistent Polygon for performance
        self.filter_poly = self.widget_canvas.create_polygon(0, 0, fill=self.fill_color, outline=self.outline_color, width=2)

        self.grid_items = []
        self.label_items = []

        # XY-Pad Bindings
        self.widget_canvas.bind('<ButtonPress-1>', self.on_canvas_press)
        self.widget_canvas.bind('<B1-Motion>', self.on_canvas_drag)
        self.widget_canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

        self.cutoff_param = None
        self.resonance_param = None
        self.last_values = []

        self.click_cutoff_val = 0.5
        self.click_res_val = 0.0
        self.is_dragging = False

        # Vertical Scale Configuration (-48 to +24 dB)
        #self.db_min = -48
        #self.db_max = 24
        #self.db_range = self.db_max - self.db_min

        # Vertical Scale Configuration (-24 to +18 dB)
        self.db_min = -32
        self.db_max = 16
        self.db_range = self.db_max - self.db_min

        # Margins
        self.m_l, self.m_r, self.m_t, self.m_b = 45, 10, 20, 35

        self.draw_grid()

    def show(self):
        for zctrl in self.processor.get_group_zctrls(self.zyngui_control.screen_info[0]):
            try:
                if zctrl.filter == "cutoffFrequency":
                    self.cutoff_param = zctrl
                elif zctrl.filter == "resonance":
                    self.resonance_param = zctrl
            except:
                pass
        super().show()

    def draw_grid(self):
        # 0. Precalculate some geometric values
        maxy = self.height - self.m_b
        gw, gh = self.width - self.m_l - self.m_r, maxy - self.m_t
        if gw < 10:
            return

        # Redraw Grid
        for item in self.grid_items + self.label_items:
            self.widget_canvas.delete(item)
        self.grid_items = []
        self.label_items = []

        # dB Grid Lines
        for db in [16, 8, 0, -8, -16, -24, -32]:
        #for db in [24, 12, 0, -24, -48]:
            y = self.m_t + gh * (1.0 - (db - self.db_min) / self.db_range)
            self.grid_items.append(self.widget_canvas.create_line(self.m_l, y, self.width - self.m_r, y, fill=self.grid_color, dash=(2, 2)))
            #self.label_items.append(self.widget_canvas.create_text(5, y, text=f"{db} dB", fill=zynthian_gui_config.color_tx, anchor="w", font=("sans", 8)))

         # Evenly spaced vertical gridlines (linear spacing)
        num_vlines = 8  # adjust to taste
        for i in range(num_vlines + 1):
            x = self.m_l + (gw * i / num_vlines)
            self.grid_items.append(
                self.widget_canvas.create_line(
                    x, self.m_t, x, self.height - self.m_b,
                    fill=self.grid_color, dash=(2, 2)
                )
            )

        # Single axis labels
        self.widget_canvas.create_text(
            10, 80,
            text="dB",
            anchor="nw",
            fill=self.fg_color,
            font=self.font_small
        )
        self.widget_canvas.create_text(
            self.width - 270, self.height - 10,
            text="Hz",
            anchor="se",
            fill=self.fg_color,
            font=self.font_small
        )


    def on_size(self, event):
        super().on_size(event)
        self.draw_grid()
        self.refresh_gui()

    def refresh_gui(self):
        # 1. Normalize for math consistency across engines
        norm_cutoff = (self.cutoff_param.value - self.cutoff_param.value_min) / self.cutoff_param.value_range if self.cutoff_param else 0.5
        norm_res = (self.resonance_param.value - self.resonance_param.value_min) / self.resonance_param.value_range if self.resonance_param else 0.0
        if [norm_cutoff, norm_res] == self.last_values and not self.is_dragging:
            return

        # 2. Precalculate some geometric values
        maxy = self.height - self.m_b
        gw, gh = self.width - self.m_l - self.m_r, maxy - self.m_t
        if gw < 10:
            return

        # 3. SMOOTH CURVE: Calculate point for every horizontal pixel
        closed = False
        coords = [self.m_l, maxy]
        display_cutoff = 20.0 * (20000.0 / 20.0) ** norm_cutoff
        for px_offset in range(int(gw) + 1):
            log_pos = px_offset / gw
            freq = 20.0 * (20000.0 / 20.0) ** log_pos

            f_ratio = freq / max(1.0, display_cutoff)
            resp = 1.0 / math.sqrt(1.0 + math.pow(f_ratio, 8))
            db_val = 20.0 * math.log10(resp + 1e-10)  # Base is ~ -3dB at cutoff

            # Apply Resonance (Updated to 18.0 for a ~15dB total peak)
            if norm_res > 0:
                peak = math.exp(-pow(math.log(f_ratio + 1e-10), 2) / 0.05)
                #db_val += (norm_res * 18.0 * peak)
                db_val += (norm_res * 12.0 * peak)

            px = self.m_l + px_offset
            py = self.m_t + gh * (1.0 - (db_val - self.db_min) / self.db_range)
            if py < maxy:
                coords.extend([px, max(self.m_t, py)])
            else:
                coords.extend([px, max(self.m_t, maxy)])
                closed = True
                break

        # 4. Close polygon when slope cross 0 beyond display area
        if not closed:
            coords.extend([self.width - self.m_r, maxy])

        self.widget_canvas.coords(self.filter_poly, *coords)
        self.last_values = [norm_cutoff, norm_res]

    def on_canvas_press(self, event):
        self.last_click = event
        self.is_dragging = True
        if self.cutoff_param:
            self.click_cutoff_val = (self.cutoff_param.value - self.cutoff_param.value_min) / self.cutoff_param.value_range
        if self.resonance_param:
            self.click_res_val = (self.resonance_param.value - self.resonance_param.value_min) / self.resonance_param.value_range

    def on_canvas_drag(self, event):
        """Pure XY-Pad: X=Cutoff, Y=Resonance regardless of start position"""
        if not self.is_dragging: return

        dx = (event.x - self.last_click.x) / self.width
        dy = (event.y - self.last_click.y) / self.height

        if self.cutoff_param:
            new_norm_x = max(0.0, min(1.0, self.click_cutoff_val + dx))
            self.cutoff_param.set_value(self.cutoff_param.value_min + (new_norm_x * self.cutoff_param.value_range))

        if self.resonance_param:
            new_norm_y = max(0.0, min(1.0, self.click_res_val - dy)) # Drag up to increase
            self.resonance_param.set_value(self.resonance_param.value_min + (new_norm_y * self.resonance_param.value_range))

    def on_canvas_release(self, event):
        self.is_dragging = False
