#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Chain View Class
#
# Copyright (C) 2025-2026 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <riban@zynthian.org>
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
from tkinter import font

import zynautoconnect
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base
from zyngine.zynthian_signal_manager import zynsigman

DRAG_THRESHOLD = 5


class zynthian_gui_chain_manager(zynthian_gui_base):
    """
    View of chains.

    This class handles the graphical representation of chains and their processors.
    It supports navigation via encoders/keys and mouse/touch interactions for
    scrolling, selecting and operating on processors.
    """

    def __init__(self):
        """
        Initialize the Chain View.

        Sets up the canvas, data structures for nodes and grid navigation,
        and initializes mouse drag state variables.
        """
        super().__init__()

        # Canvas for drawing the graph
        self.canvas = tkinter.Canvas(self.main_frame,
            bg=zynthian_gui_config.color_panel_bg,
            highlightthickness=0)
        self.canvas.pack(fill=tkinter.BOTH, expand=True)

        # Nodes mapping:
        self.nodes = [] # Node graph - [chain_idx, row_idx, col_idx]
        self.selected_node = [0, 0, 0] # [chain_idx, row_idx, col_idx]
        self.moving_proc = None # The processor object being moved
        self.moving_chain = False  # True if moving a chain left/right
        self.rows = 0 # Quantity of rows in longest chain

        # Mouse Drag State
        self.press_event = None
        self.dragging = False
        self.font = (zynthian_gui_config.font_family, int(0.026 * self.height))
        self.BLOCK_WIDTH = 120 # Width of each processor block in pixels
        self.BLOCK_HEIGHT = 40 # Height of each processor block in pixels
        self.H_SPACING = 10 # Horizontal spacing between processor blocks in pixels
        self.V_SPACING = 10 # Vertical spacing between processor blocks in pixels

        self.last_active_proc = None # The last processor to be selected
        self.long_press_id = None

    def build_view(self):
        """
        Set up the view for the current chain.

        Sets the title, binds input events (mouse/touch), draws the initial graph,
        and sets the initial selection.

        Returns:
            bool: Always True.
        """
        self.set_title(f"Chain: {self.chain_manager.active_chain.get_name()}")

        zynsigman.register_queued(zynsigman.S_PROCESSOR, zynsigman.SS_PROCESSOR_BYPASS, self.bypass_cb)

        # Bind Mouse Events
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-4>", self.on_wheel)
        self.canvas.bind("<Button-5>", self.on_wheel)
        #self.build_graph(self.zyngui.get_current_processor())
        if (self.nodes and self.selected_node[0] != self.chain_manager.get_active_chain_index()) or self.zyngui.get_current_processor() != self.last_active_proc:
            self.build_graph(self.zyngui.get_current_processor())
        else:
            self.build_graph()
        return True

    def show(self):
        super().show()
        self.tts()

    def update_layout(self):
        super().update_layout()
        self.font = (zynthian_gui_config.font_family, int(0.026 * self.height))
        # Formual 2 * (x // y) ensures even values which helps with spacing and dividers
        self.BLOCK_WIDTH = 2 * (self.width // 12)
        self.BLOCK_HEIGHT = 2 * (self.height // 16)
        self.H_SPACING = 2 * (self.BLOCK_WIDTH // 28)
        self.V_SPACING = 2 * (self.BLOCK_HEIGHT // 8)
        shown = self.shown
        self.shown = False
        self._draw_graph()
        self.shown = shown

    def hide(self):
        if self.shown:
            zynsigman.unregister(zynsigman.S_PROCESSOR, zynsigman.SS_PROCESSOR_BYPASS, self.bypass_cb)
            self.end_moving_chain()
            self.end_moving_processor()
            self.last_active_proc = self.zyngui.get_current_processor()
            super().hide()

    def on_press(self, event):
        """
        Handle mouse button press. Initializes drag state.
        Args:
            event: Mouse event
        """

        # Record start position for drag
        self.press_event = event
        self.dragging = False
        # Find clicked node
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.start_xview = self.canvas.xview()[0]
        self.start_yview = self.canvas.yview()[0]
        self.clicked_node = self.get_node_at(x, y)
        if self.clicked_node:
            self.select_node(node=self.clicked_node)
            self.long_press_id = self.canvas.after(800, self.on_long_press)

    def on_long_press(self):
        """ Handle press and hold"""

        if not self.long_press_id:
            return
        self.long_press_id = None
        node = self._get_node(self.selected_node)

        if "proc" in node:
            proc = node["proc"]
        if proc == "chain_options":
            if node["chain_id"] == 0:
                self.zyngui.screens["chain_options"].set_chain(0)
                self.zyngui.show_screen(proc)
            else:
                self.start_moving_chain()
        elif type(proc) != str:
            self.start_moving_processor(node["proc"])

    def get_node_at(self, x, y):
        for obj_id in self.canvas.find_overlapping(x, y, x, y):
            try:
                return self.node2pos[obj_id]
            except:
                pass
        return None

    def on_motion(self, event):
        """
        Handle mouse drag event. Scrolls the canvas.
        Args:
            event: Mouse event
        """

        # Calculate pixel delta
        dx = self.press_event.x - event.x
        dy = self.press_event.y - event.y

        # Check threshold
        if not self.dragging:
            if abs(dx) > DRAG_THRESHOLD or abs(dy) > DRAG_THRESHOLD:
                self.dragging = True
                if self.long_press_id:
                    self.canvas.after_cancel(self.long_press_id)
                    self.long_press_id = None

        if self.dragging:
            if self.moving_chain:
                x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
                node = self.get_node_at(x, y)
                if node and node["chain_id"] != self.clicked_node["chain_id"]:
                    if event.x > self.press_event.x:
                        self.arrow_right()
                    else:
                        self.arrow_left()
                    self.press_event.x = event.x
                    self.clicked_node = node
            elif self.moving_proc:
                x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
                node = self.get_node_at(x, y)
                if not node:
                    # Dragged into space
                    pass
                if node and self.clicked_node and node != self.clicked_node:
                    if node["chain_id"] != self.clicked_node["chain_id"]:
                        if event.x > self.press_event.x:
                            self.arrow_right()
                        else:
                            self.arrow_left()
                    elif dy > self.BLOCK_HEIGHT:
                        if self.chain_manager.nudge_processor(self.chain_manager.active_chain.chain_id, self.moving_proc, True):
                            self.build_graph(self.moving_proc)
                            self.press_event.y = event.y
                    elif dy < -self.BLOCK_HEIGHT:
                        if self.chain_manager.nudge_processor(self.chain_manager.active_chain.chain_id, self.moving_proc, False):
                            self.build_graph(self.moving_proc)
                            self.press_event.y = event.y
                    else:
                        return
                    self.clicked_node = node
            else:
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
                    logging.warning(f"Can't drag scroll => {e}")

    def on_release(self, event):
        """
        Handle mouse button release.
        Args:
            event: Mouse event
        """
        if self.long_press_id:
            self.canvas.after_cancel(self.long_press_id)
            self.long_press_id = None
        else:
            return
        press_type = "S"
        if self.press_event:
            if event.time > self.press_event.time + 400:
                self.press_time = None
                press_type = "B"
        self.clicked_node = None
        # If dragging, stop.
        if self.dragging:
            self.dragging = False
            return

        # Handle Click Selection
        # Use canvasx/y to account for scrolling
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

        # Find clicked node
        node = self.get_node_at(x, y)
        if node is None:
            return
        #self.select_node(node["pos"])
        self.on_select(t=press_type)

    def _add_node(self, chain_idx, row, title, chain_id, proc="", slot=None, idx=None):
        """ Adds a node to the graph

        Args:
            chain_idx: The chain where the node will be added.
            row: The row where the node will be added.
            title: The title of the node.
            chain_id: The chain id of the node.
            proc_id: The processor of the node or string describing node type. None for non-processor nodes.
        """
        while len(self.nodes) <= chain_idx:
            self.nodes.append([])
        while len(self.nodes[chain_idx]) <= row:
            self.nodes[chain_idx].append([])
        if type(proc) == str:
            proc_type = proc
        else:
            proc_type = proc.type
        self.nodes[chain_idx][row].append({
            "title": title,  # Title shown in GUI
            "chain_id": chain_id,  # zynthian chain_id (not necessarily display position)
            "proc": proc,  # Processor object or symbol for non-processor nodes
            "slot": slot,  # Processor slot
            "idx": idx,  # Index of (parallel) processor within slot
            "pos": [chain_idx, row, len(self.nodes[chain_idx][row])],  # Position of node within graph
            "is_dst": proc_type in ("MIDI Synth", "Audio Effect", "MIDI Tool", "Special", "midi_key_range", "add_midi_proc", "midi_output", "audio_out"),
            "is_src": proc_type in ("MIDI Synth", "Audio Generator", "Audio Effect", "MIDI Tool", "Special", "midi_key_range", "midi_input", "add_midi_proc", "audio_in")
        })

    def _get_name(self, text, max_width):
        """
        Trim text so that its pixel width fits within max_width.
        Adds an ellipsis (…) if trimmed.
        """
        node_font = font.Font(family=self.font[0], size=self.font[1])
        if node_font.measure(text) <= max_width:
            return text  # already fits

        ellipsis = "…"
        ellipsis_width = node_font.measure(ellipsis)

        # Start trimming from the end
        for i in range(len(text), 0, -1):
            sub = text[:i]
            if node_font.measure(sub) + ellipsis_width <= max_width:
                return sub.strip() + ellipsis
        return ellipsis  # fallbackpass

    def build_graph(self, proc=None):
        """
        Draw the entire processor chain graph on the canvas.

        Clears the canvas and rebuilds the node structure based on each
        chain's configuration (Inputs -> MIDI Tools -> Synths ->
        Audio Effects -> Outputs). Updates the scroll region.

        Args:
            proc: The processor to select. (None to use current selection)
        """
        self.nodes = []

        self.rows = 0
        for chain_idx, chain in enumerate(self.chain_manager.chains.values()):
            chain_id = chain.chain_id
            row = 0

            # Add chain option button
            name = self._get_name(chain.get_name(), self.BLOCK_WIDTH)
            self._add_node(chain_idx, row, f"{name}", chain_id, "chain_options")
            row += 1
            # Add MIDI input
            if chain.is_midi():
                self._add_node(chain_idx, row, "MIDI Input", chain_id, "midi_input")
                row += 1
                #self._add_node(chain_idx, row, "Key Range & Transpose", chain_id, "midi_key_range")
                #row += 1
            # Add MIDI processors
            for slot_idx, slot in enumerate(chain.midi_slots):
                for proc_idx, processor in enumerate(slot):
                    self._add_node(chain_idx, row, processor.get_name(), chain_id, processor, slot_idx, proc_idx)
                if self.nodes[chain_idx][row]:
                    row += 1
            # Add MIDI output
            if chain.synth_slots:
                # Add synth
                for slot_idx, slot in enumerate(chain.synth_slots):
                    for proc_idx, processor in enumerate(slot):
                        self._add_node(chain_idx, row, processor.get_name(), chain_id, processor, slot_idx, proc_idx)
                    if self.nodes[chain_idx][row]:
                        row += 1
            elif chain.is_midi():
                #if not chain.midi_slots:
                #    self._add_node(chain_idx, row, "+", chain_id, "add_midi_proc")
                #    row += 1
                self._add_node(chain_idx, row, "MIDI Output", chain_id, "midi_output")
                row += 1
            # Add audio input
            if chain.audio_thru and chain.zynmixer_proc and chain.zynmixer_proc.eng_code != "MR":
                self._add_node(chain_idx, row, "Audio Input", chain_id, "audio_in")
                row += 1
            # Add audio processors
            for slot_idx, slot in enumerate(chain.audio_slots):
                for proc_idx, processor in enumerate(slot):
                    self._add_node(chain_idx, row, processor.get_name(), chain_id, processor, slot_idx, proc_idx)
                if self.nodes[chain_idx][row]:
                    row += 1
            # Add audio output
            if chain.is_audio():
                self._add_node(chain_idx, row, "Audio Output", chain_id, "audio_out")
                row += 1
            self.rows = max(self.rows, row)
        self._draw_graph(proc)

    def bypass_cb(self, zctrl):
        processor = zctrl.processor
        col = "#808080" if zctrl.value else "#ffffff"
        for proc, node in self.bypass2node.items():
            if proc == processor:
                self.canvas.itemconfigure(node["text_id"], fill=col)
                break

    def _draw_node(self, node, x, y):
        """ Draw a single node on the canvas.

        Args:
            node: The node object to be drawn.
        """
        # Colors
        c_midi = "#805050"
        c_synth = "#32a893"
        c_audio = "#505080"
        c_special = "#708050"

        # Draw node background
        proc = node.get("proc")
        bg_col = "#505050"
        fg_col = "#ffffff"
        try:
            disabled = proc.controllers_dict['bypass'].value
            self.bypass2node[proc] = node
        except:
            disabled = 0
        title = node.get("title")
        if type(proc) is str:
            match proc:
                case "midi_input" | "note_range" | "add_midi_proc" | "midi_output" | "midi_key_range":
                    bg_col = c_midi
                case "audio_in" | "audio_out":
                    bg_col = c_audio
        else:
            match proc.type:
                case "MIDI Input" | "MIDI Output" | "MIDI Tool":
                    bg_col = c_midi
                case "MIDI Synth" | "Audio Generator":
                    bg_col = c_synth
                case "Audio Input" | "Audio Output" | "Audio Effect":
                    bg_col = c_audio
                case "Special":
                    bg_col = c_special
            if proc.type == "Audio Effect":
                try:
                    if proc.controllers_dict["bypass"].value:
                        disabled = True
                        fg_col = "#808080"
                except:
                    pass
        node["id"] = self.canvas.create_rectangle(
            x, y, x + self.BLOCK_WIDTH, y + self.BLOCK_HEIGHT,
            fill=bg_col, outline=bg_col, tags="node"
        )
        # Draw node text
        node["text_id"] = self.canvas.create_text(
            x + self.BLOCK_WIDTH / 2, y + self.BLOCK_HEIGHT / 2,
            text=title, fill=fg_col,
            font=self.font,
            width=self.BLOCK_WIDTH,
            justify=tkinter.CENTER
        )
        while True:
            x0, y0, x1, y1 = self.canvas.bbox(node["text_id"])
            if y1 - y0 < self.BLOCK_HEIGHT:
                break
            title = title[:-1].strip()
            self.canvas.itemconfig(node["text_id"], text=f"{title}...")
        self.node2pos[node["id"]] = node

    def _draw_line(self, start_id, end_id):
        xa, ya, xb, yb = self.canvas.bbox(start_id)
        x0 = xa + (xb - xa) // 2
        y0 = ya + (yb - ya) // 2
        xa, ya, xb, yb = self.canvas.bbox(end_id)
        x1 = xa + (xb - xa) // 2
        y1 = ya + (yb - ya) // 2
        self.canvas.create_line(x0, y0, x1, y1, fill="#AAAAAA", width=2, tags="lines")

    def _draw_graph(self, sel_proc=None):
        if self.width == 1:
            return  # Not yet resized
        div = self.chain_manager.get_pinned_pos()
        self.canvas.delete("all")
        self.node2pos = {} # Dict of nodes, mapped by gui object (background rectangle)
        divider_height = self.rows * (self.BLOCK_HEIGHT + self.V_SPACING)
        chain_offset = 0
        self.bypass2node = {}
        for chain_idx, chain in enumerate(self.nodes):
            y = self.H_SPACING // 2
            cols_in_chain = 1 # max number of parallel processors
            for row_idx, row in enumerate(chain):
                x = chain_offset
                for col, node in enumerate(row):
                    self._draw_node(node, x, y)
                    # Create interconnect lines
                    if row_idx > 0:
                        x0 = x + self.BLOCK_WIDTH // 2
                        is_dst = node.get("is_dst", False)
                        if col < len(chain[row_idx - 1]):
                            is_src = chain[row_idx - 1][col].get("is_src", False)
                        else:
                            is_src = False
                        if is_dst:
                            y0 = y - self.V_SPACING // 2
                            if is_src:
                                self.canvas.create_line(x0, y, x0, y - self.V_SPACING, fill="#AAAAAA", width=2, tags="lines")
                            else:
                                self.canvas.create_line(x0, y, x0, y0, fill="#AAAAAA", width=2, tags="lines")
                            if col > 0:
                                self.canvas.create_line(x0, y0, x0 - self.BLOCK_WIDTH - self.H_SPACING, y0, width=2, fill="#AAAAAA", tags="lines")
                        if row_idx < len(chain) - 1 and col >= len(chain[row_idx + 1]):
                            y0 = y + self.BLOCK_HEIGHT
                            y1 = y0 + self.V_SPACING // 2
                            self.canvas.create_line(x0, y0, x0, y1, fill="#AAAAAA", width=2, tags="lines")
                            self.canvas.create_line(x0, y1, x0 - self.BLOCK_WIDTH - self.H_SPACING, y1, width=2, fill="#AAAAAA", tags="lines")

                    x += self.BLOCK_WIDTH + self.H_SPACING
                    if col >= cols_in_chain:
                        cols_in_chain = col + 1
                y += self.BLOCK_HEIGHT + self.V_SPACING

            if self.moving_chain and self.selected_node[0] == chain_idx:
                # Highlight chain being moved
                self.canvas.create_rectangle(
                    chain_offset - 1, 0, chain_offset + 1 + self.BLOCK_WIDTH, divider_height,
                    outline="yellow",
                    width=3,
                    fill="",
                    tags="chain_move"
                )

            x = chain_offset - self.H_SPACING / 2
            if chain_idx == div:
                x_div = x
            self.canvas.create_line(x, 0, x, divider_height, fill="#666666", width=1, tags="lines")
            chain_offset += (self.BLOCK_WIDTH + self.H_SPACING) * cols_in_chain

        # Background for pinned chains
        try:
            x = x_div
        except:
            pass
        main_bg = self.canvas.create_rectangle(
            x, 0, chain_offset, divider_height,
            outline="",
            width=0,
            fill="#333333"
        )

        self.canvas.lower("lines")
        self.canvas.lower(main_bg)

        # Configure scroll region
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=(bbox[0], bbox[1] - 5, bbox[2], bbox[3] + 5))
        else:
            self.canvas.configure(scrollregion=(0, 0, 100, 100))
        self.select_node(proc=sel_proc)

    def _draw_selection(self):
        """
        Draw selection cursor.
        """
        self.canvas.itemconfig("node", outline="")
        if not self.selected_node:
            self.selected_node = [0, 0, 0]
        if self.moving_proc:
            color = "yellow"
        else:
            color = "white"
        try:
            chain_idx, col_idx, row_idx = self.selected_node
            node_id = self.nodes[chain_idx][col_idx][row_idx]["id"]
            if not self.moving_chain:
                self.canvas.itemconfig(node_id, outline=color, width=2)
        except:
            pass

        #Scroll the canvas to ensure the selected node is visible.
        self.canvas.update_idletasks() # Ensure all redrawing has completed
        # Get node's coords
        x0, y0, x1, y1 = self.canvas.bbox(node_id)
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
        # Scroll horizontally to show selected block plus 20% of next block to indicate if more scrolling possible
        if x0 < vx0:
            target_x = (x0 - b0 - 0.2 * self.BLOCK_WIDTH) / w
        elif x1 > vx1:
            target_x = (x1 - vw + 0.2 * self.BLOCK_WIDTH) / w
        else:
            target_x = None
        # Scroll vertically
        if y0 < vy0:
            target_y = target_y=(y0 - b1 - 0.3 * self.BLOCK_HEIGHT) / h
        elif y1 > vy1:
            target_y = target_y=(y1 - vh + 0.3 * self.BLOCK_HEIGHT + self.V_SPACING) / h
        else:
            target_y = None
        if target_x or target_y:
            if self.shown:
                self.smooth_scroll_to(target_x, target_y)
            else:
                if target_x is not None:
                    self.canvas.xview_moveto(target_x)
                if target_y is not None:
                    self.canvas.yview_moveto(target_y)

    def smooth_scroll_to(self, target_x=None, target_y=None, steps=30, delay=10):
        start_x, start_y = self.canvas.xview()[0], self.canvas.yview()[0]
        dx = dy = 0
        if target_x is not None:
            dx = (target_x - start_x) / steps
        if target_y is not None:
            dy = (target_y - start_y) / steps

        def step(i=0):
            if i >= steps:
                return
            if target_x is not None:
                self.canvas.xview_moveto(start_x + dx * i)
            if target_y is not None:
                self.canvas.yview_moveto(start_y + dy * i)
            self.canvas.after(delay, step, i + 1)

        step()

    def _get_node(self, node_pos):
        try:
            chain_idx, row, col = node_pos
            return self.nodes[chain_idx][row][col]
        except:
            pass
        return None

    def select_chain_options_node(self):
        chain_idx = self.chain_manager.get_chain_index(self.chain_manager.active_chain.chain_id)
        self.selected_node = [chain_idx, 0, 0]

    def get_node_pos(self, node):
        for chain_idx, c in enumerate(self.nodes):
            for row_idx, r in enumerate(c):
                for col_idx, n in enumerate(r):
                    if n == node:
                        return [chain_idx, row_idx, col_idx]
        return [0, 0, 0]

    def select_node(self, node_pos=None, node=None, proc=None):
        prev_node = self.selected_node
        if not self.nodes:
            return
        if node:
            self.selected_node = self.get_node_pos(node)
        elif proc:
            for chain_idx, chain in enumerate(self.nodes):
                for row_idx, row in enumerate(chain):
                    for node_idx, node in enumerate(row):
                        if node.get("proc") == proc:
                            node_pos = [chain_idx, row_idx, node_idx]
                            break
        if node_pos:
            self.selected_node = node_pos
        elif not self.selected_node:
            self.selected_node = [0, 0, 0]
        chain_idx, row, col = self.selected_node
        # Range check
        if chain_idx >= len(self.chain_manager.chains):
            chain_idx = len(self.chain_manager.chains) - 1
        if row >= len(self.nodes[chain_idx]):
            row = len(self.nodes[chain_idx]) - 1
        if col >= len(self.nodes[chain_idx][row]):
            col = len(self.nodes[chain_idx][row]) - 1
        self.selected_node = [chain_idx, row, col]
        if not proc:
            proc = self.nodes[chain_idx][row][col]["proc"]

        node = self._get_node(self.selected_node)
        chain_id = node.get("chain_id")
        self.chain_manager.set_active_chain_by_id(chain_id)
        if type(proc) != str:
            self.zyngui.set_current_processor(proc)
        self._draw_selection()
        chain = self.chain_manager.chains[chain_id]
        self.set_title(f"Chain: {chain.get_name()}")

        if self.selected_node[0] == prev_node[0]:
            self.state_manager.tts(node.get('title'))
        else:
            self.state_manager.tts(f"Chain {chain.get_title()} {node.get('title')}")

    def tts(self):
        node = self._get_node(self.selected_node)
        chain_id = node.get("chain_id")
        chain = self.chain_manager.chains[chain_id]
        self.state_manager.tts(f"Chain {chain.get_title()} {node.get('title')}")

    def move_processor(self, chain_idx, chain_offset):
        if self.moving_proc.eng_code in ["MI", "MR"]:
            return
        try:
            node = self._get_node(self.selected_node)
            ordered_chains = list(self.chain_manager.chains)
            chain_id = ordered_chains[chain_idx]
            chain = self.chain_manager.chains[chain_id]
            chain_dest_id = ordered_chains[chain_idx + chain_offset]
            chain_dst = self.chain_manager.chains[chain_dest_id]
            # Constrain which chains a process may be moved to
            if self.moving_proc.type == "MIDI Tool":
                if not chain_dst.is_midi():
                    return
            elif self.moving_proc.type == "Audio Effect":
                if not chain_dst.is_audio():
                    return
            chain.remove_processor(self.moving_proc)
            chain_dst.insert_processor(self.moving_proc, node.get("slot"))
            # Rebuild routing in both chains
            if self.moving_proc.type == "MIDI Tool":
                chain.rebuild_midi_graph()
                chain_dst.rebuild_midi_graph()
                zynautoconnect.request_midi_connect(True)
            elif self.moving_proc.type == "Audio Effect":
                chain.rebuild_audio_graph()
                chain_dst.rebuild_audio_graph()
                zynautoconnect.request_audio_connect(True)
        except Exception as e:
            logging.error(f"Can't move processor! => {e}")
        self.build_graph(self.moving_proc)

    def start_moving_processor(self, processor=None):
        """
        Enter 'Move Mode' for a specific processor.

        Args:
            processor: The processor object to be moved. Default: Current processor of current chain.
        """

        if processor:
            self.moving_proc = processor
        else:
            chain = self.chain_manager.active_chain
            if chain.chain_id == 0:
                return
            self.moving_proc = chain.current_processor
        if self.moving_proc and not self.chain_manager.can_move_processor(self.moving_proc):
            self.moving_proc = None
        self.select_node(proc=self.moving_proc)

    def end_moving_processor(self):
        """ Exit processor move mode
        """

        self.moving_proc = None

    def start_moving_chain(self):
        self.moving_chain = True
        self._draw_graph(self.moving_proc)

    def end_moving_chain(self):
        if not self.moving_chain:
            return
        self.moving_chain = False
        self.strip_drag_start = None
        self.canvas.delete("chain_move")
        self.select_node()

    def arrow_down(self):
        """
        Handle arrow down action.
        Moves selection down or nudges processor if in move mode.
        """

        if self.moving_chain or super().arrow_down():
            return
        if self.moving_proc:
            proc = self.moving_proc
            self.chain_manager.nudge_processor(self.chain_manager.active_chain.chain_id, proc, False)
            self.build_graph(proc)
        else:
            chain_idx, row, col = self.selected_node
            row += 1
            if row >= len(self.nodes[chain_idx]):
                return
            self.select_node([chain_idx, row, col])

    def arrow_up(self):
        """
        Handle arrow up action.
        Moves selection up or nudges processor if in move mode.
        """

        if self.moving_chain or super().arrow_up():
            return
        if self.moving_proc:
            proc = self.moving_proc
            self.chain_manager.nudge_processor(self.chain_manager.active_chain.chain_id, proc, True)
            self.build_graph(proc)
        else:
            chain_idx, row, col = self.selected_node
            row -= 1
            if row < 0:
                return
            self.select_node([chain_idx, row, col])

    def arrow_left(self):
        """
        Handle arrow left action.
        Moves selection left or nudges processor if in move mode.
        """
        chain_idx, row, col = self.selected_node
        if self.moving_proc:
            if chain_idx:
                self.move_processor(chain_idx, -1)
        elif self.moving_chain:
            self.selected_node[0] = self.chain_manager.nudge_chain(-1)
            self.build_graph()
        else:
            col -= 1
            if col < 0:
                # Beginning of row, try previous chain
                if chain_idx == 0:
                    return
                chain_idx -= 1
                row = min(row, len(self.nodes[chain_idx]) - 1)
                col = len(self.nodes[chain_idx][row]) - 1
            self.select_node([chain_idx, row, col])

    def arrow_right(self):
        """
        Handle arrow right action.
        Moves selection right or nudges processor if in move mode.
        """
        chain_idx, row, col = self.selected_node
        if self.moving_proc:
            self.move_processor(chain_idx, 1)
        elif self.moving_chain:
            self.selected_node[0] = self.chain_manager.nudge_chain(1)
            self.build_graph()
        else:
            col += 1
            if col >= len(self.nodes[chain_idx][row]):
                # End of row, try next chain
                chain_idx += 1
                if chain_idx >= len(self.nodes):
                    return
                col = 0
                # Check we're not beyond end of chain
                row = min(row, len(self.nodes[chain_idx]) - 1)
            self.select_node([chain_idx, row, col])

    def select_offset(self, dval):
        if self.moving_proc:
            if dval > 0:
                self.arrow_down()
            elif dval < 0:
                self.arrow_up()
            return
        if self.moving_chain:
            self.selected_node[0] = self.chain_manager.nudge_chain(dval)
            self.build_graph()
            return

        chain_idx, row, col = self.selected_node
        col += dval
        if col >= len(self.nodes[chain_idx][row]):
            # End of row, try next row
            row += 1
            if row >= len(self.nodes[chain_idx]):
                return
            col = 0
        elif col < 0:
            row -= 1
            if row < 0:
                return
            col = len(self.nodes[chain_idx][row]) - 1
        self.select_node([chain_idx, row, col])

    def on_wheel(self, event):
        """
        Handle mouse wheel events to navigate the graph.

        Args:
            event: The mouse wheel event.
        """
        if event.state:
            if event.num == 5:
                self.arrow_right()
            else:
                self.arrow_left()
        else:
            if event.num == 5:
                self.arrow_up()
            else:
                self.arrow_down()

    def zynpot_cb(self, i, dval):
        if super().zynpot_cb(i, dval):
            return True
        if i == 2:
            self.select_offset(dval)
            return True
        elif i == 3:
            if dval > 0:
                self.arrow_right()
            elif dval < 0:
                self.arrow_left()

    def back_action(self):
        if self.moving_proc:
            self.end_moving_processor()
            self.select_node()
            return True  # Consumed
        if self.moving_chain:
            self.end_moving_chain()
            return True
        return False

    def switch_select(self, t='S'):
        # Pass type to on_select
        return self.on_select(t)

    def on_select(self, t='S'):
        """ Handle selection event (Select/Enter key or Click).
        Args:
            t (str): Press type ('S' for short, 'B' for bold/long).
        Returns:
            bool: True if event consumed.
        """

        # If moving, consume event and exit
        if self.moving_chain:
            self.end_moving_chain()
            if t == "S":
                return True

        if self.moving_proc:
            self.end_moving_processor()
            self.select_node()
            if t == "S":
                return True

        if not self.selected_node:
            self.selected_node = [0, 0, 0]
            self.select_node()
            return True

        chain_idx, col_idx, row_idx = self.selected_node
        node = self.nodes[chain_idx][col_idx][row_idx]
        proc = node.get("proc")
        if t == "B":
            if type(proc) == str:
                chain = self.chain_manager.active_chain
                if proc == "chain_options":
                    if chain.chain_id != 0:
                        self.start_moving_chain()
                return True
            else:
                self.start_moving_processor(proc)
        elif t == "S":
            if type(proc) == str:
                match proc:
                    case "chain_options":
                        self.zyngui.screens["chain_options"].set_chain(self.chain_manager.active_chain)
                        pass
                    case "midi_key_range":
                        self.zyngui.screens['midi_key_range'].config()
                    case "midi_input":
                        self.zyngui.screens['midi_config'].set_chain(self.chain_manager.active_chain)
                        self.zyngui.screens['midi_config'].midi_input = True
                        proc = 'midi_config'
                    case "add_midi_proc":
                        self.zyngui.modify_chain({
                            "chain_id": self.chain_manager.active_chain.chain_id,
                            "type": "MIDI Tool",
                            "midi_thru": True,
                            "audio_thru": False,
                            "slot": None
                        })
                        return True
                    case "midi_output":
                        self.zyngui.screens['midi_config'].set_chain(self.chain_manager.active_chain)
                        self.zyngui.screens['midi_config'].midi_input = False
                        proc = 'midi_config'
                    case "audio_in":
                        pass
                    case "audio_out":
                        pass
                self.zyngui.show_screen(proc)
            else:
                self.zyngui.show_screen("processor_options")
            return True

    def switch(self, swi, t):
        """ Function to handle switches press
        swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
        t: Press type ["S"=Short, "B"=Bold, "L"=Long]

        returns True if action fully handled or False if parent action should be triggered
        """
        if swi == 1 and t == 'B':
            self.zyngui.show_screen('main_menu')
            return True
        elif swi == 2 and t == "S":
            self.zyngui.screens["chain_options"].insert_chain()
            return True
        elif swi == 3:
            return self.on_select(t)
        return False

    def cuia_v5_zynpot_switch(self, params):
        i = params[0]
        t = params[1].upper()
        if t == 'B' and i == 2:
            self.zyngui.screens["chain_options"].set_chain(self.chain_manager.active_chain)
            self.zyngui.show_screen("chain_options")
            return True
        return self.switch(i, t)
