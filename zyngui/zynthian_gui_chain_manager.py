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

    # Visual constants
    BLOCK_WIDTH = 120 # Width of each processor block in pixels
    BLOCK_HEIGHT = 40 # Height of each processor block in pixels
    H_SPACING = 10 # Horizontal spacing between processor blocks in pixels
    V_SPACING = 10 # Vertical spacing between processor blocks in pixels

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
        self.selected_node = None # [chain_idx, row_idx, col_idx]
        self.moving_proc = None # The processor object being moved
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

    def start_move_mode(self, processor):
        """
        Enter 'Move Mode' for a specific processor.

        Args:
            processor: The processor object to be moved.
        """
        self.moving_proc = processor
        self.select_node(proc=processor) 

    def build_view(self):
        """
        Set up the view for the current chain.

        Sets the title, binds input events (mouse/touch), draws the initial graph,
        and sets the initial selection.

        Returns:
            bool: Always True.
        """
        self.set_title(f"Chain: {self.zyngui.chain_manager.active_chain.get_name()}")
        
        # Bind Mouse Events
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-4>", self.on_wheel)
        self.canvas.bind("<Button-5>", self.on_wheel)
        self.build_graph()
        return True

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
        
        # Find closest node or clicked node
        items = self.canvas.find_overlapping(x, y, x, y)
        try:
            node = self.node2pos[items[0]]
        except:
            return
        self.select_node(node["pos"])
        self.on_select(t=press_type)

    def add_node(self, chain_idx, row, title, chain_id, proc=None, slot=None, idx=None):
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
        self.nodes[chain_idx][row].append({
            "title": title,
            "chain_id": chain_id,
            "proc": proc,
            "slot": slot,
            "idx": idx,
            "pos": [chain_idx, row, len(self.nodes[chain_idx][row])]
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
            self.add_node(chain_idx, row, f"Chain Options", chain_id)
            row += 1
            # Add MIDI input
            if chain.is_midi():
                self.add_node(chain_idx, row, "MIDI Input", chain_id)
                row += 1
                self.add_node(chain_idx, row, "Note Range & Transpose", chain_id)
                row += 1
            # Add MIDI processors
            for slot_idx, slot in enumerate(chain.midi_slots):
                for proc_idx, processor in enumerate(slot):
                    self.add_node(chain_idx, row, processor.get_name(), chain_id, processor, slot_idx, proc_idx)
                    row += 1
            # Add MIDI output
            if chain.synth_slots:
                # Add synth
                for slot_idx, slot in enumerate(chain.synth_slots):
                    for proc_idx, processor in enumerate(slot):
                        self.add_node(chain_idx, row, processor.get_name(), chain_id, processor, slot_idx, proc_idx)
                    row += 1
            elif chain.is_midi():
                self.add_node(chain_idx, row, "MIDI Output", chain_id)
                row += 1
            # Add audio input
            if chain.audio_thru and chain.zynmixer_proc and chain.zynmixer_proc.eng_code != "MR":
                self.add_node(chain_idx, row, "Audio Input", chain_id)
                row += 1
            # Add audio processors
            for slot_idx, slot in enumerate(chain.audio_slots):
                for proc_idx, processor in enumerate(slot):
                    self.add_node(chain_idx, row, processor.get_name(), chain_id, processor, slot_idx, proc_idx)
                row += 1
            # Add audio output
            if chain.is_audio():
                self.add_node(chain_idx, row, "Audio Output", chain_id)
                row += 1
            self.rows = max(self.rows, row)
        self._draw_graph()
        self.select_node(proc=proc)

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
        if proc:
            match proc.type:
                case "MIDI Input" | "MIDI Output" | "MIDI Effect":
                    color = c_midi
                case "MIDI Synth":
                    color = c_synth
                case "Audio Input" | "Audio Output" | "Audio Effect":
                    color = c_audio
        else:
            match title:
                case "MIDI Input" | "Note Range & Transpose" | "MIDI Output":
                    color = c_midi
                case "Audio Input" | "Audio Output":
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
            width=self.BLOCK_WIDTH
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

    def _draw_graph(self):
        self.canvas.delete("all")
        self.node2pos = {} # Dict of nodes, mapped by gui object (background rectangle)
        divider_height = self.rows * (self.BLOCK_HEIGHT + self.V_SPACING) - self.V_SPACING
        chain_offset = 0
        for chain in self.nodes:
            start_id = end_id = None
            y = 0
            max_cols = 0
            for row in chain:
                x = chain_offset
                for col, node in enumerate(row):
                    self._draw_node(node, x, y)
                    x += self.BLOCK_WIDTH + self.H_SPACING
                    if col > max_cols:
                        max_cols = col
                y += self.BLOCK_HEIGHT + self.V_SPACING

                # Look for nodes for lines
                proc = row[0].get("proc")
                if proc and proc.type == "MIDI Synth":
                    pass
                if start_id is None:
                    if row[0].get("title") in ("MIDI Synth", "MIDI Input", "Audio Input", "AudioMixer"):
                        start_id = row[0].get("id")
                elif end_id is None:
                    if row[0].get("title") in ("MIDI Synth", "MIDI Output", "Audio Output"):
                        end_id = row[0].get("id")
                if start_id and end_id:
                    self._draw_line(start_id, end_id)
                    start_id = end_id = None
            max_cols += 1
            chain_offset += (self.BLOCK_WIDTH + self.H_SPACING + 1) * max_cols
            x = chain_offset - self.H_SPACING // 2
            self.canvas.create_line(x, 0, x, divider_height, fill="#AAAAAA", width=1, tags="lines")
        self.canvas.lower("lines")

        # Configure scroll region
        # Use updatedbbox after drawing
        self.canvas.update_idletasks() # Ensure bbox is fresh?
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=(bbox[0], bbox[1] - 5, bbox[2], bbox[3] + 5))
        else:
            self.canvas.configure(scrollregion=(0,0,100,100))

    def _draw_selection(self):
        """
        Draw selection on the canvas.

        Args:
            proc: The processor to select. (None to use current selection)
        """
        self.canvas.itemconfig("node", outline="")
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
        self._ensure_visible()

    def get_node(self, node_pos):
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
        if not proc:
            proc = self.nodes[self.selected_node[0]][self.selected_node[1]][self.selected_node[2]]["proc"]
        if proc:
            self.zyngui.chain_manager.active_chain.set_current_processor(proc)
        self._draw_selection()
        chain_idx, row, col = self.selected_node
        node = self.get_node(self.selected_node)
        chain_id = node.get("chain_id")
        chain = self.zyngui.chain_manager.chains[chain_id]
        self.set_title(f"Chain: {chain.get_name()}")

    def arrow_down(self):
        """
        Handle arrow down action.
        Moves selection down or nudges processor if in move mode.
        """
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
        if self.moving_proc:
            proc = self.moving_proc
            self.zyngui.chain_manager.nudge_processor(self.zyngui.chain_manager.active_chain.chain_id, proc, True)
            self.build_graph(proc)
        else:
            chain_idx, row, col = self.selected_node
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
        if self.moving_proc:
            proc = self.moving_proc
            self.zyngui.chain_manager.nudge_processor(self.zyngui.chain_manager.active_chain.chain_id, proc, False)
            self.build_graph(proc)
        else:
            chain_idx, row, col = self.selected_node
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

    def back_action(self):
        if self.moving_proc:
            self.moving_proc = None
            self.select_node()
            return True # Consumed
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
        if proc:
            if t == 'S':
                zynthian_gui_config.zyngui.chain_control(self.zyngui.chain_manager.active_chain.chain_id, proc)
            elif t == 'B':
                self.zyngui.show_screen("processor_options")
        else:
            title = node.get("title")
            match(title):
                case "Chain Options":
                    self.zyngui.screens['chain_options'].setup(self.zyngui.chain_manager.active_chain.chain_id)
                    self.zyngui.show_screen('chain_options')
                case "Note Range & Transpose":
                    self.zyngui.screens['midi_key_range'].config(self.zyngui.chain_manager.active_chain)
                    self.zyngui.show_screen('midi_key_range')
                case "MIDI Input":
                    self.zyngui.midi_in_config(self.zyngui.chain_manager.active_chain)
                case "MIDI Output":
                    self.zyngui.midi_out_config(self.zyngui.chain_manager.active_chain)
                case "Audio Input":
                    self.zyngui.show_screen("audio_in")
                case "Audio Output":
                    self.zyngui.show_screen("audio_out")
                case "Key Range":
                    self.zyngui.screens['midi_key_range'].config(self.zyngui.chain_manager.active_chain)
                    self.zyngui.show_screen('midi_key_range')
        return True

    def on_size(self, event):
        super().on_size(event)
        self.font = (zynthian_gui_config.font_family, int(0.026 * self.height))
        self.BLOCK_WIDTH = self.width // 6
        self.BLOCK_HEIGHT = self.height // 8
        self.H_SPACING = self.BLOCK_WIDTH // 14
        self.V_SPACING = self.BLOCK_HEIGHT // 4
        self._draw_graph()

    def _ensure_visible(self):
        """
        Scroll the canvas to ensure the selected node is visible.
        """
        
        # Get node's coords
        chain_idx, row, col = self.selected_node
        node = self.nodes[chain_idx][row][col]
        x0, y0, x1, y1 = self.canvas.bbox(node["id"])

        # Get view coords
        vw = self.canvas.winfo_width()
        vh = self.canvas.winfo_height()
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
