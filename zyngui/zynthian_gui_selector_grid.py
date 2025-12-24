#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI New Chain Class
#
# Copyright (C) 2025 Fernando Moyano <jofemodo@zynthian.org>
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
import tkinter
from PIL import Image, ImageTk
from time import monotonic
from tkinter import font

from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base

class zynthian_gui_selector_grid(zynthian_gui_base):
    """
    Selector presented as a grid of buttons.
    """
    def __init__(self):
        """
        Initialize the Chain View.

        Sets up the canvas, data structures for nodes and grid navigation,
        and initializes mouse drag state variables.
        """
        super().__init__('Chain View')
        
        # Canvas for drawing the graph
        self.canvas = tkinter.Canvas(self.main_frame,
            bg=zynthian_gui_config.color_panel_bg,
            highlightthickness=0)
        self.canvas.pack(fill=tkinter.BOTH, expand=True)
        self.columns = 4
        self.BLOCK_WIDTH = 120 # Width of each processor block in pixels
        self.BLOCK_HEIGHT = 40 # Height of each processor block in pixels
        self.SPACING = 10 # Horizontal spacing between processor blocks in pixels
        self.font = (zynthian_gui_config.font_family, int(0.024 * self.height))
        self.config = [] # List of dictionaries, each describing a button
        self.selected_node = 0 # Selected node id
        self.icon_size = (8, 8)

        # Mouse Drag State
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False
        self.drag_threshold = 5  # pixels to detect drag vs click 
        self.press_time = None # Time of touch used for bold press detection

    def update_layout(self):
        super().update_layout()
        self.font = (zynthian_gui_config.font_family, int(0.024 * self.height))
        # Formual 2 * (x // y) ensures even values which helps with spacing and dividers
        self.SPACING = 2 * (self.width // (self.columns * 16))
        self.BLOCK_WIDTH = 2 * ((self.width - self.SPACING) // (self.columns * 2)) - self.SPACING
        self.BLOCK_HEIGHT = 2* (self.BLOCK_WIDTH // 4)
        self.icon_size = (self.BLOCK_HEIGHT - 4, self.BLOCK_HEIGHT - 4)
        self._draw_nodes()

    def build_view(self):
        # Bind Mouse Events
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-4>", self.on_wheel)
        self.canvas.bind("<Button-5>", self.on_wheel)
        self._draw_nodes()
        return True

    def setup(self, config):
        """
        Configure the buttons
        
        :param config: List of dictionaries, each describing a button
        """
        self.config = config

    def get_icon(self, icon_fname):
        if not icon_fname:
            icon_fname = self.default_icon
        if icon_fname not in self.icons:
            try:
                img = Image.open(f"{self.ui_dir}/icons/{icon_fname}")
                icon = ImageTk.PhotoImage(img.resize(self.icon_size))
                self.icons[icon_fname] = icon
                return icon
            except Exception as e:
                logging.error(f"Can't load info icon {icon_fname} => {e}")
                return None
        else:
            return self.icons[icon_fname]

    def _draw_nodes(self):
        if self.width == 1:
            return # Not yet resized
        self.canvas.delete("all")
        self.icons = {}
        x = self.SPACING
        y = self.SPACING
        for idx, node in enumerate(self.config):
            self.canvas.create_rectangle(x, y, x + self.BLOCK_WIDTH, y + self.BLOCK_HEIGHT,
            fill="#666666",
            outline="#666666",
            tags=("node", f"node_{idx}"))
            if "icon" in node:
                img = self.get_icon(node["icon"])
                if img:
                    self.canvas.create_image(x, y, image=img, anchor="nw")
            self.canvas.create_text(
                x + 3 * self.BLOCK_WIDTH / 4, y + self.BLOCK_HEIGHT / 2,
                text=node["title"],
                fill="white",
                font=self.font,
                width=self.BLOCK_WIDTH // 2,
                justify=tkinter.CENTER
            )
            x += self.BLOCK_WIDTH + self.SPACING
            if x + self.BLOCK_WIDTH + self.SPACING > self.width:
                x = self.SPACING
                y += self.BLOCK_HEIGHT + self.SPACING

        # Configure scroll region
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=(bbox[0] - self.SPACING, bbox[1] - self.SPACING, bbox[2] + self.SPACING, bbox[3] + self.SPACING))
        else:
            self.canvas.configure(scrollregion=(0,0,100,100))
        
        self._draw_selection()

    def _draw_selection(self):
        """
        Draw selection cursor.
        """
        self.canvas.itemconfig("node", outline="")
        node_tag = f"node_{self.selected_node}"
        self.canvas.itemconfig(node_tag, outline="yellow", width=2)

        #Scroll the canvas to ensure the selected node is visible.
        # Get node's coords
        x0, y0, x1, y1 = self.canvas.bbox(node_tag)
        # Get view coords
        vw = self.width
        vh = self.height
        vx0 = self.canvas.canvasx(0)
        vy0 = self.canvas.canvasy(0)
        vx1 = self.canvas.canvasx(vw)
        vy1 = self.canvas.canvasy(vh)
        b0, b1, b2, b3 = self.canvas.bbox("all")
        w = b2 - b0
        h = b3 - b1
        # Scroll horizontally
        if x0 < vx0:
            self.canvas.xview_moveto((x0 - b0) / w)
        elif x1 > vx1:
            self.canvas.xview_moveto((x1 - vw) / w)
        # Scroll vertically
        if y0 < vy0:
            self.canvas.yview_moveto((y0 - b1) / h)
        elif y1 > vy1:
            self.canvas.yview_moveto((y1 - vh) / h)

    def arrow_left(self):
        """
        Handle arrow left action.
        """

        idx = self.selected_node - 1
        if idx < 0:
            return
        self.selected_node = idx
        self._draw_selection()

    def arrow_right(self):
        """
        Handle arrow right action.
        """

        idx = self.selected_node + 1
        if idx >= len(self.config):
            return
        self.selected_node = idx
        self._draw_selection()

    def arrow_up(self):
        """
        Handle arrow up action
        """
        idx = self.selected_node - self.columns
        if idx < 0:
            return
        self.selected_node = idx
        self._draw_selection()

    def arrow_down(self):
        """
        Handle arrow down action
        """
        idx = self.selected_node + self.columns
        if idx >= len(self.config):
            return
        self.selected_node = idx
        self._draw_selection()

    def select_offset(self, dval):
        idx = self.selected_node + dval
        if idx < 0 or idx >= len(self.config):
            return
        self.selected_node = idx
        self._draw_selection()

    def on_wheel(self, event):
        """
        Handle mouse wheel events to navigate the graph.

        Args:
            event: The mouse wheel event.
        """
        if event.num == 5 or event.delta == -120:
            self.select_offset(1)
        elif event.num == 4 or event.delta == 120:
            self.select_offset(-1)

    def zynpot_cb(self, i, dval):
        if super().zynpot_cb(i, dval):
            return True
        if i == 3:
            self.select_offset(dval)
            return True
        elif i == 2:
            if dval > 0:
                self.arrow_down()
            elif dval < 0:
                self.arrow_up()

    def on_press(self, event):
        """
        Handle mouse button press. Initializes drag state.
        Args:
            event: Mouse event
        """
        # Record start position for drag
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.start_xview = self.canvas.xview()[0]
        self.start_yview = self.canvas.yview()[0]
        self.is_dragging = False
        self.press_time = monotonic()

    def on_drag(self, event):
        """
        Handle mouse drag event. Scrolls the canvas.
        Args:
            event: Mouse event
        """
        # Calculate pixel delta
        dx = self.drag_start_x - event.x
        dy = self.drag_start_y - event.y
        
        # Check threshold
        if not self.is_dragging:
            if abs(dx) > self.drag_threshold or abs(dy) > self.drag_threshold:
                self.is_dragging = True
        
        if self.is_dragging:
            # Scroll Canvas manually using moveto
            # We need the total scrollable size to convert pixels to fraction
            try:
                # scrollregion is "x1 y1 x2 y2" string or tuple
                sr = self.canvas.cget("scrollregion")
                if isinstance(sr, str):
                    sr = [float(x) for x in sr.split()]
                sr_w = sr[2] - sr[0]
                sr_h = sr[3] - sr[1]
                can_w = self.canvas.winfo_width()
                can_h = self.canvas.winfo_height()
                # Horizontal Move
                if sr_w > can_w:
                    d_fract_x = dx / float(sr_w)
                    self.canvas.xview_moveto(self.start_xview + d_fract_x)                
                # Vertical Move
                if sr_h > can_h:
                    d_fract_y = dy / float(sr_h)
                    self.canvas.yview_moveto(self.start_yview + d_fract_y)                    
            except Exception as e:
                logging.warning(f"Drag scroll error: {e}")
                pass

    def on_release(self, event):
        """
        Handle mouse button release.
        Args:
            event: Mouse event
        """
        # Use canvasx/y to account for scrolling
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)        
        # Find closest node or clicked node
        items = self.canvas.find_overlapping(x, y, x, y)
        try:
            tags = self.canvas.gettags(items[0])
            self.selected_node = int(tags[1].split("_")[1])
        except:
            return
        self._draw_selection()
        press_type = "S"
        if self.press_time:
            if monotonic() > self.press_time + 0.4:
                self.press_time = None
                press_type = "B"
        self.switch_select(press_type)

    def switch_select(self, press_type="S"):
        config = self.config[self.selected_node]
        if press_type == "B":
            action_fn = config.get("bold_action")
            if action_fn:
                action_params = config.get("action_bold_params")
                if action_params:
                    action_fn(*action_params)
                else:
                    action_fn()
                return
        action_fn = config.get("action")
        if action_fn:
            action_params = config.get("action_params")
            if action_params:
                action_fn(*action_params)
            else:
                action_fn()
