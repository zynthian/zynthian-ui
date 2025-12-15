#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Chain View Class
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
from time import monotonic
from tkinter import font

from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base


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
        super().__init__('Chain View')
        
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
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False
        self.drag_threshold = 5  # pixels to detect drag vs click 
        self.press_time = None # Time of touch used for bold press detection
        self.font = (zynthian_gui_config.font_family, int(0.026 * self.height))
        self.BLOCK_WIDTH = 120 # Width of each processor block in pixels
        self.BLOCK_HEIGHT = 40 # Height of each processor block in pixels
        self.H_SPACING = 10 # Horizontal spacing between processor blocks in pixels
        self.V_SPACING = 10 # Vertical spacing between processor blocks in pixels

        self.last_active_proc = None # The last processor to be selected

    def start_move_mode(self):
        """
        Enter 'Move Mode' for a specific processor.

        Args:
            processor: The processor object to be moved.
        """
        chain = self.zyngui.chain_manager.active_chain
        if chain.chain_id == 0:
            return
        self.moving_proc = chain.current_processor
        self.select_node(proc=self.moving_proc)

    def build_view(self):
        """
        Set up the view for the current chain.

        Sets the title, binds input events (mouse/touch), draws the initial graph,
        and sets the initial selection.

        Returns:
            bool: Always True.
        """
        self.set_title(f"Chain: {self.zyngui.chain_manager.active_chain.get_name()}")

        if zynthian_gui_config.enable_touch_navigation and self.moving_chain or self.moving_proc:
            self.show_back_button()

        # Bind Mouse Events
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-4>", self.on_wheel)
        self.canvas.bind("<Button-5>", self.on_wheel)
        if self.selected_node[0] != self.zyngui.chain_manager.get_chain_index(self.zyngui.chain_manager.active_chain.chain_id) or self.zyngui.get_current_processor() != self.last_active_proc:
            self.build_graph(self.zyngui.chain_manager.active_chain.current_processor)
        else:
            self.build_graph()
        return True

    def hide(self):
        if self.shown:
            self.end_moving_chain()
            self.last_active_proc = self.zyngui.get_current_processor()
            super().hide()

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
        press_type = "S"
        if self.press_time:
            if monotonic() > self.press_time + 0.4:
                self.press_time = None
                press_type = "B"
        # If dragging, stop.
        if self.is_dragging:
            self.is_dragging = False
            return

        # Handle Click Selection
        # Use canvasx/y to account for scrolling
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        
        # Find clicked node
        items = self.canvas.find_overlapping(x, y, x, y)
        node = None
        for obj_id in items:
            try:
                node = self.node2pos[obj_id]
            except:
                pass
        if node is None:
            return
        self.select_node(node["pos"])
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
            "title": title, # Title shown in GUI
            "chain_id": chain_id, # zynthian chain_id (not necessarily display position)
            "proc": proc, # Processor object or symbol for non-processor nodes
            "slot": slot, # Processor slot
            "idx": idx, # Index of (parallel) processor within slot
            "pos": [chain_idx, row, len(self.nodes[chain_idx][row])], # Position of node within graph
            "is_dst": proc_type in ("MIDI Synth", "Audio Effect", "MIDI Tool", "midi_key_range", "midi_output", "audio_out"),
            "is_src": proc_type in ("MIDI Synth", "Audio Generator", "Audio Effect", "MIDI Tool", "midi_key_range", "midi_input", "audio_in")
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

        chain_ids = self.zyngui.chain_manager.ordered_chain_ids + [0]
        self.rows = 0
        for chain_idx in range(len(chain_ids)):
            chain_id = chain_ids[chain_idx]
            chain = self.zyngui.chain_manager.chains[chain_id]
            row = 0

            # Add chain option button
            name = self._get_name(chain.get_name(), self.BLOCK_WIDTH)
            self._add_node(chain_idx, row, f"{name}\nOptions", chain_id, "chain_options")
            row += 1
            # Add MIDI input
            if chain.is_midi():
                self._add_node(chain_idx, row, "MIDI Input", chain_id, "midi_input")
                row += 1
                self._add_node(chain_idx, row, "Key Range & Transpose", chain_id, "midi_key_range")
                row += 1
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

    def _draw_node(self, node, x, y):
        """ Draw a single node on the canvas.

        Args:
            node: The node object to be drawn.
        """
        # Colors
        c_midi = "#805050" 
        c_synth = "#32a893"
        c_audio = "#505080"

        # Draw node background
        proc = node.get("proc")
        color = "#505050"
        title = node.get("title")
        if type(proc) is str:
            match proc:
                case "midi_input" | "note_range" | "midi_output" | "midi_key_range":
                    color = c_midi
                case "audio_in" | "audio_out":
                    color = c_audio
        else:
            match proc.type:
                case "MIDI Input" | "MIDI Output" | "MIDI Tool":
                    color = c_midi
                case "MIDI Synth" | "Audio Generator":
                    color = c_synth
                case "Audio Input" | "Audio Output" | "Audio Effect":
                    color = c_audio
        node["id"] = self.canvas.create_rectangle(
            x, y, x + self.BLOCK_WIDTH, y + self.BLOCK_HEIGHT,
            fill=color, outline=color, tags="node"
        )
        # Draw node text
        text_id = self.canvas.create_text(
            x + self.BLOCK_WIDTH / 2, y + self.BLOCK_HEIGHT / 2,
            text=title, fill="white",
            font=self.font,
            width=self.BLOCK_WIDTH,
            justify=tkinter.CENTER
        )
        while True:
            x0, y0, x1, y1 = self.canvas.bbox(text_id)
            if y1 - y0 < self.BLOCK_HEIGHT:
                break
            title = title[:-1].strip()
            self.canvas.itemconfig(text_id, text=f"{title}...")
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
            return # Not yet resized
        self.canvas.delete("all")
        self.node2pos = {} # Dict of nodes, mapped by gui object (background rectangle)
        divider_height = self.rows * (self.BLOCK_HEIGHT + self.V_SPACING)
        chain_offset = 0
        for chain_idx, chain in enumerate(self.nodes):
            start_id = end_id = None
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
            self.canvas.create_line(x, 0, x, divider_height, fill="#666666", width=1, tags="lines")
            chain_offset += (self.BLOCK_WIDTH + self.H_SPACING) * cols_in_chain

        # Background for main mixbus
        main_bg = self.canvas.create_rectangle(
            x, 0, x + self.BLOCK_WIDTH + self.H_SPACING, divider_height,
            outline="",
            width=0,
            fill="#666666"
        )

        self.canvas.lower("lines")
        self.canvas.lower(main_bg)

        # Configure scroll region
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=(bbox[0], bbox[1] - 5, bbox[2], bbox[3] + 5))
        else:
            self.canvas.configure(scrollregion=(0,0,100,100))
        self.select_node(proc=sel_proc)

    def _draw_selection(self):
        """
        Draw selection cursor.
        """
        self.canvas.itemconfig("node", outline="")
        if self.moving_chain:
            return
        if not self.selected_node:
            self.selected_node = [0, 0, 0]
        if self.moving_proc:
            color = "red"
        else:
            color = "yellow"
        try:
            chain_idx, col_idx, row_idx = self.selected_node
            node_id = self.nodes[chain_idx][col_idx][row_idx]["id"]
            self.canvas.itemconfig(node_id, outline=color, width=2)
        except:
            pass

        #Scroll the canvas to ensure the selected node is visible.
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
            self.canvas.xview_moveto((x0 - b0 - 0.2 * self.BLOCK_WIDTH) / w)
        elif x1 > vx1:
            self.canvas.xview_moveto((x1 - vw + 0.2 * self.BLOCK_WIDTH) / w)
        # Scroll vertically
        if y0 < vy0:
            self.canvas.yview_moveto((y0 - b1 - 0.3 * self.BLOCK_HEIGHT) / h)
        elif y1 > vy1:
            self.canvas.yview_moveto((y1 - vh + 0.3 * self.BLOCK_HEIGHT + self.V_SPACING) / h)

    def _get_node(self, node_pos):
        try:
            chain_idx, row, col = node_pos
            return self.nodes[chain_idx][row][col]
        except:
            pass
        return None

    def select_node(self, node_pos=None, proc=None):
        if proc:
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
        if chain_idx > len(self.zyngui.chain_manager.ordered_chain_ids):
            chain_idx = len(self.zyngui.chain_manager.ordered_chain_ids) - 1
        if row >= len(self.nodes[chain_idx]):
            row = len(self.nodes[chain_idx]) - 1
        if col >= len(self.nodes[chain_idx][row]):
            col = len(self.nodes[chain_idx][row]) - 1
        self.selected_node = [chain_idx, row, col]
        if not proc:
            proc = self.nodes[chain_idx][row][col]["proc"]

        node = self._get_node(self.selected_node)
        chain_id = node.get("chain_id")
        self.zyngui.chain_manager.set_active_chain_by_id(chain_id)
        if type(proc) != str:
            self.zyngui.set_current_processor(proc)
        self._draw_selection()
        chain = self.zyngui.chain_manager.chains[chain_id]
        self.set_title(f"Chain: {chain.get_name()}")

    def move_processor(self, chain_idx, chain_offset):
        if self.moving_proc.eng_code in ["MI", "MR"]:
            return
        try:
            node = self._get_node(self.selected_node)
            ordered_chains = self.zyngui.chain_manager.ordered_chain_ids + [0]
            chain_id = ordered_chains[chain_idx]
            chain = self.zyngui.chain_manager.chains[chain_id]
            chain_dest_id = ordered_chains[chain_idx + chain_offset]
            chain_dst = self.zyngui.chain_manager.chains[chain_dest_id]
            #TODO: Constrain which chains a process may be moved to
            chain.remove_processor(self.moving_proc)
            chain_dst.insert_processor(self.moving_proc, node.get("slot"))
        except:
            pass
        self.build_graph(self.moving_proc)

    def start_moving_chain(self):
        self.moving_chain = True
        if zynthian_gui_config.enable_touch_navigation:
            self.show_back_button(True)
        self._draw_graph(self.moving_proc)

    def end_moving_chain(self):
        if not self.moving_chain:
            return
        if zynthian_gui_config.enable_touch_navigation:
            self.show_back_button(False)
        self.moving_chain = False
        self.strip_drag_start = None
        self.canvas.delete("chain_move")
        self.select_node()

    def arrow_down(self):
        """
        Handle arrow down action.
        Moves selection down or nudges processor if in move mode.
        """
        if self.moving_chain:
            return
        if self.moving_proc:
            proc = self.moving_proc
            self.zyngui.chain_manager.nudge_processor(self.zyngui.chain_manager.active_chain.chain_id, proc, False)
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
        if self.moving_chain:
            return
        if self.moving_proc:
            proc = self.moving_proc
            self.zyngui.chain_manager.nudge_processor(self.zyngui.chain_manager.active_chain.chain_id, proc, True)
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
            self.move_processor(chain_idx, -1)
        elif self.moving_chain:
            self.selected_node[0] = self.zyngui.chain_manager.move_chain(-1)
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
            self.selected_node[0] = self.zyngui.chain_manager.move_chain(1)
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
            self.selected_node[0] = self.zyngui.chain_manager.move_chain(dval)
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
                self.arrow_right()
            elif dval < 0:
                self.arrow_left()

    def back_action(self):
        if self.moving_proc:
            self.moving_proc = None
            self.select_node()
            return True # Consumed
        if self.moving_chain:
            self.end_moving_chain()
            return True
        return False

    def switch_select(self, t='S'):
        # Pass type to on_select
        return self.on_select(t)

    def on_select(self, t='S'):
        """
        Handle selection event (Select/Enter key or Click).

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
            self.moving_proc = None
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
        if type(proc) == str:
            if t == "B":
                chain = self.zyngui.chain_manager.active_chain
                if proc == "chain_options":
                    if chain.chain_id != 0:
                        self.start_moving_chain()
                    return True
                if proc in ("midi_output", "audio_out"):
                    slot = None
                elif proc in ("midi_input", "audio_in"):
                    slot = -1
                else:
                    slot = 0
                if proc.startswith("midi"):
                    proc_type = "MIDI Tool"
                else:
                    proc_type = "Audio Effect"
                self.zyngui.modify_chain({
                    "chain_id": chain.chain_id,
                    "type": proc_type,
                    "midi_thru": chain.midi_chan is not None,
                    "audio_thru": proc_type == "Audio Effect",
                    "slot": slot
                })
                return True
            match(proc):
                case "chain_options":
                    pass
                case "midi_key_range":
                    self.zyngui.screens['midi_key_range'].config(self.zyngui.chain_manager.active_chain)
                case "midi_input":
                    self.zyngui.screens['midi_config'].set_chain(self.zyngui.chain_manager.active_chain)
                    self.zyngui.screens['midi_config'].input = True
                    proc = 'midi_config'
                case "midi_output":
                    self.zyngui.screens['midi_config'].set_chain(self.zyngui.chain_manager.active_chain)
                    self.zyngui.screens['midi_config'].input = False
                    proc = 'midi_config'
                case "audio_in":
                    pass
                case "audio_out":
                    pass
            self.zyngui.show_screen(proc)
        else:
            if t == 'S':
                zynthian_gui_config.zyngui.chain_control(self.zyngui.chain_manager.active_chain.chain_id, proc)
            elif t == 'B':
                self.zyngui.show_screen("processor_options")
        return True

    def on_size(self, event):
        super().on_size(event)
        self.font = (zynthian_gui_config.font_family, int(0.026 * self.height))
        # Formual 2 * (x // y) ensures even values which helps with spacing and dividers
        self.BLOCK_WIDTH = 2 * (self.width // 12)
        self.BLOCK_HEIGHT = 2 * (self.height // 16)
        self.H_SPACING = 2 * (self.BLOCK_WIDTH // 28)
        self.V_SPACING = 2 * (self.BLOCK_HEIGHT // 8)
        self._draw_graph()
