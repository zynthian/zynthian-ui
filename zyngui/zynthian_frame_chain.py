#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Frame Chain class: Side chain view for integrating inside GUI classes.
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
from zyngine.zynthian_signal_manager import zynsigman

DRAG_THRESHOLD = 5


class zynthian_frame_chain(tkinter.Frame):
    """
    Side chain view for integrating inside GUI classes.

    This class handles the graphical representation of a chain and their processors.
    It supports navigation via encoders/keys and mouse/touch interactions for
    scrolling, selecting and operating on processors.
    """

    def __init__(self, master, width=1, height=1):
        """
        Initialize the Chain View.

        Sets up the canvas, data structures for nodes and grid navigation,
        and initializes mouse drag state variables.
        """
        tkinter.Frame.__init__(self, master, width=width, height=height)
        #self.grid_propagate(False)
        #self.rowconfigure(1, weight=1)
        #self.columnconfigure(0, weight=1)

        self.width = width
        self.height = height

        self.zyngui = zynthian_gui_config.zyngui
        self.state_manager = self.zyngui.state_manager
        self.chain_manager = self.zyngui.chain_manager

        self.chain = None           # The chain to display/manage

        # Nodes mapping:
        self.nodes = []                 # Node list
        self.node2pos = {}              # Dict of nodes, mapped by gui object (background rectangle)
        self.bypass2node = {}           # Dict of bypassed processor => nodes
        self.selected_node = 0          # Selected node index
        self.moving_proc = None         # The processor object being moved
        self.rows = 0                   # Quantity of rows

        # Mouse Drag State
        self.press_event = None
        self.dragging = False
        self.long_press_id = None

        # Canvas for drawing the graph
        self.canvas = tkinter.Canvas(self,
            bg=zynthian_gui_config.color_panel_bg,
            highlightthickness=0)
        self.canvas.pack(fill=tkinter.BOTH, expand=True)

        # Bind Mouse Events
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-4>", self.on_wheel)
        self.canvas.bind("<Button-5>", self.on_wheel)

        self.update_layout()

    def set_chain_id(self, chain_id):
        try:
            self.chain = self.chain_manager.chains[chain_id]
        except:
            self.chain = None

    def set_chain(self, chain):
        self.chain = chain

    def update_layout(self):
        #self.configure(width=self.width, height=self.height)
        self.font = (zynthian_gui_config.font_family, int(0.026 * self.height))
        self.BLOCK_WIDTH =  2 * int(0.45 * self.width)
        self.BLOCK_HEIGHT = int(0.12 * self.height)
        self.H_SPACING = self.width - self.BLOCK_WIDTH
        self.V_SPACING = 2 * (self.BLOCK_HEIGHT // 10)
        self._draw_graph()

    # Function called when frame resized
    def on_size(self, event=None):
        super().on_size(event)
        self.update_layout()

    def build_view(self):
        """
        Set up the view for the current chain.
        Draws the initial graph and sets the initial selection.

        Returns:
            bool: Always True.
        """
        zynsigman.register_queued(zynsigman.S_PROCESSOR, zynsigman.SS_PROCESSOR_BYPASS, self.bypass_cb)
        self.build_graph(self.zyngui.get_current_processor())
        return True

    def hide(self):
        zynsigman.unregister(zynsigman.S_PROCESSOR, zynsigman.SS_PROCESSOR_BYPASS, self.bypass_cb)
        self.end_moving_processor()

    def grid_remove(self):
        super().grid_remove()
        #self.hide()

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
            self.zyngui.show_screen(proc)
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
        dy = self.press_event.y - event.y

        # Check threshold
        if not self.dragging:
            if abs(dy) > DRAG_THRESHOLD:
                self.dragging = True
                if self.long_press_id:
                    self.canvas.after_cancel(self.long_press_id)
                    self.long_press_id = None

        if self.dragging:
            if self.moving_proc:
                x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
                node = self.get_node_at(x, y)
                if not node:
                    # Dragged into space
                    pass
                if node and self.clicked_node and node != self.clicked_node:
                    if dy > self.BLOCK_HEIGHT:
                        if self.chain_manager.nudge_processor(self.chain.chain_id, self.moving_proc, True):
                            self.build_graph(self.moving_proc)
                            self.press_event.y = event.y
                    elif dy < -self.BLOCK_HEIGHT:
                        if self.chain_manager.nudge_processor(self.chain.chain_id, self.moving_proc, False):
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
                    sr_h = sr[3] - sr[1]
                    can_h = self.canvas.winfo_height()

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

    def _add_node(self, title, proc, slot=None, idx=None):
        """ Adds a node to the graph

        Args:
            title: The title of the node.
            proc: The processor object of the node or string describing node type for non-processor nodes.
            slot: Processot slot
            idx:  Index of (parallel) processor within slot
        """
        row = len(self.nodes)
        if type(proc) == str:
            proc_type = proc
        else:
            proc_type = proc.type
        self.nodes.append({
            "title": title,  # Title shown in GUI
            "proc": proc,    # Processor object or string for non-processor nodes
            "slot": slot,    # Processor slot
            "idx": idx,      # Index of (parallel) processor within slot
            "row": row,      # Position of node within graph
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

        if self.chain:
            # Add chain option button
            title = "Chain Options"
            #name = self._get_name(self.chain.get_name(), self.BLOCK_WIDTH)
            if self.chain.title:
                title += "\n" + self._get_name(self.chain.title, self.BLOCK_WIDTH)
            self._add_node(title, "chain_options")
            # Add MIDI input
            if self.chain.is_midi():
                if self.chain.midi_chan < 16:
                    midi_chan = f"CH#{self.chain.midi_chan + 1:02}"
                else:
                    midi_chan = f"CH#ALL"
                self._add_node(f"MIDI Input\n{midi_chan}", "midi_input")
                self._add_node("Key Range & Transpose", "midi_key_range")
            # Add MIDI processors
            for slot_idx, slot in enumerate(self.chain.midi_slots):
                for proc_idx, processor in enumerate(slot):
                    self._add_node(processor.get_name(), processor, slot_idx, proc_idx)
            # Add MIDI output
            if self.chain.synth_slots:
                # Add synth
                for slot_idx, slot in enumerate(self.chain.synth_slots):
                    for proc_idx, processor in enumerate(slot):
                        self._add_node(processor.get_name(), processor, slot_idx, proc_idx)
            elif self.chain.is_midi():
                if not self.chain.midi_slots:
                    self._add_node("+", "add_midi_proc")
                self._add_node("MIDI Output", "midi_output")
            # Add audio input
            if self.chain.audio_thru and self.chain.zynmixer_proc and self.chain.zynmixer_proc.eng_code != "MR":
                self._add_node("Audio Input", "audio_in")
            # Add audio processors
            for slot_idx, slot in enumerate(self.chain.audio_slots):
                for proc_idx, processor in enumerate(slot):
                    self._add_node(processor.get_name(), processor, slot_idx, proc_idx)
            # Add audio output
            if self.chain.is_audio():
                self._add_node("Audio Output", "audio_out")

        self.rows = len(self.nodes)
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

    def _draw_graph(self, sel_proc=None):
        if self.width == 1:
            return  # Not yet resized
        self.canvas.delete("all")
        self.node2pos = {}
        self.bypass2node = {}

        x = self.H_SPACING // 2
        y = self.V_SPACING // 2
        for row, node in enumerate(self.nodes):
            self._draw_node(node, x, y)
            y += self.BLOCK_HEIGHT
            # Create interconnect lines
            x0 = x + self.BLOCK_WIDTH // 2
            is_src = node.get("is_src", False)
            is_dst = node.get("is_dst", False)
            if is_dst:
                if is_src:
                    self.canvas.create_line(x0, y, x0, y + self.V_SPACING, fill="#AAAAAA", width=2, tags="lines")
                else:
                    self.canvas.create_line(x0, y, x0, y + self.V_SPACING // 2, fill="#AAAAAA", width=2, tags="lines")

            # TODO Manage parallel processors!!

            y += self.V_SPACING

        # Configure scroll region
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=(0, bbox[1] - 5, self.width, bbox[3] + 5))
        else:
            self.canvas.configure(scrollregion=(0, 0, self.width, self.height))
        self.select_node(proc=sel_proc)

    def _draw_selection(self):
        """
        Draw selection cursor.
        """
        self.canvas.itemconfig("node", outline="")
        if not self.selected_node:
            self.selected_node = 0
        if self.moving_proc:
            color = "yellow"
        else:
            color = "white"
        try:
            node_id = self.nodes[self.selected_node]["id"]
            self.canvas.itemconfig(node_id, outline=color, width=2)
        except:
            return

        #Scroll the canvas to ensure the selected node is visible.
        self.canvas.update_idletasks() # Ensure all redrawing has completed
        # Get node's coords
        x0, y0, x1, y1 = self.canvas.bbox(node_id)
        # Get view coords
        vh = self.height
        vy0 = self.canvas.canvasy(0)
        vy1 = self.canvas.canvasy(vh)
        b0, b1, b2, b3 = self.canvas.bbox("all")
        h = b3 - b1
        # Scroll vertically
        if y0 < vy0:
            target_y = target_y=(y0 - b1 - 0.3 * self.BLOCK_HEIGHT) / h
        elif y1 > vy1:
            target_y = target_y=(y1 - vh + 0.3 * self.BLOCK_HEIGHT + self.V_SPACING) / h
        else:
            target_y = None
        if target_y:
            self.smooth_scroll_to(target_y)
        #if target_y is not None:
        #    self.canvas.yview_moveto(target_y)

    def smooth_scroll_to(self, target_y=None, steps=30, delay=10):
        start_y = self.canvas.yview()[0]
        dy = 0
        if target_y is not None:
            dy = (target_y - start_y) / steps
        def step(i=0):
            if i >= steps:
                return
            if target_y is not None:
                self.canvas.yview_moveto(start_y + dy * i)
            self.canvas.after(delay, step, i + 1)
        step()

    def _get_node(self, row):
        try:
            return self.nodes[row]
        except:
            pass
        return None

    def select_chain_options_node(self):
        self.selected_node = 0

    def get_node_pos(self, node):
        try:
            return self.nodes.index(node)
        except:
            return 0

    def select_node(self, row=None, node=None, proc=None):
        if not self.nodes:
            return
        # Argument priority is from left to right
        if row is not None:
            self.selected_node = row
        elif node:
            row = self.get_node_pos(node)
        elif proc:
            for row, node in enumerate(self.nodes):
                if node.get("proc") == proc:
                    break
        # Range check
        if row is None or row < 0:
            row = 0
        elif row >= len(self.nodes):
            row = len(self.nodes) - 1
        self.selected_node = row
        if not proc:
            proc = self.nodes[row]["proc"]
        if type(proc) != str:
            self.zyngui.set_current_processor(proc)
        self._draw_selection()

    def start_moving_processor(self, processor=None):
        """
        Enter 'Move Mode' for a specific processor.

        Args:
            processor: The processor object to be moved. Default: Current processor of current chain.
        """
        if processor:
            self.moving_proc = processor
        if self.moving_proc and not self.chain_manager.can_move_processor(self.moving_proc):
            self.moving_proc = None
        self.select_node(proc=self.moving_proc)

    def end_moving_processor(self):
        """ Exit processor move mode
        """
        self.moving_proc = None

    def bypass_cb(self, zctrl):
        processor = zctrl.processor
        col = "#808080" if zctrl.value else "#ffffff"
        for proc, node in self.bypass2node.items():
            if proc == processor:
                self.canvas.itemconfigure(node["text_id"], fill=col)
                break

    def arrow_down(self):
        """
        Handle arrow down action.
        Moves selection down or nudges processor if in move mode.
        """

        if self.moving_proc:
            proc = self.moving_proc
            self.chain_manager.nudge_processor(self.chain_manager.active_chain.chain_id, proc, False)
            self.build_graph(proc)
        else:
            row = self.selected_node + 1
            if row >= len(self.nodes):
                return
            self.select_node(row)

    def arrow_up(self):
        """
        Handle arrow up action.
        Moves selection up or nudges processor if in move mode.
        """

        if self.moving_proc:
            proc = self.moving_proc
            self.chain_manager.nudge_processor(self.chain_manager.active_chain.chain_id, proc, True)
            self.build_graph(proc)
        else:
            row = self.selected_node - 1
            if row < 0:
                return
            self.select_node(row)

    def on_wheel(self, event):
        """
        Handle mouse wheel events to navigate the graph.

        Args:
            event: The mouse wheel event.
        """
        if not event.state:
            if event.num == 5:
                self.arrow_up()
            else:
                self.arrow_down()

    def toggle_menu(self):
        pass

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

        if self.moving_proc:
            self.end_moving_processor()
            self.select_node()
            if t == "S":
                return True

        if self.selected_node is None:
            self.select_node()

        node = self.nodes[self.selected_node]
        proc = node.get("proc")
        if t == "B":
            if type(proc) == str:
                return True
            else:
                self.start_moving_processor(proc)
        elif t == "S":
            if type(proc) == str:
                match proc:
                    case "chain_options":
                        pass
                    case "midi_key_range":
                        self.zyngui.screens['midi_key_range'].config(self.chain)
                    case "midi_input":
                        self.zyngui.screens['midi_config'].set_chain(self.chain)
                        self.zyngui.screens['midi_config'].input = True
                        proc = 'midi_config'
                    case "add_midi_proc":
                        self.zyngui.modify_chain({
                            "chain_id": self.chain.chain_id,
                            "type": "MIDI Tool",
                            "midi_thru": True,
                            "audio_thru": False,
                            "slot": None
                        })
                        return True
                    case "midi_output":
                        self.zyngui.screens['midi_config'].set_chain(self.chain)
                        self.zyngui.screens['midi_config'].input = False
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

        if swi == 2:
            if t == "S":
                self.zyngui.screens["chain_options"].insert_chain()
                return True
        elif swi == 3:
            return self.on_select(t)
        return False

    def cuia_v5_zynpot_switch(self, params):
        i = params[0]
        t = params[1].upper()
        if t == 'B' and i == 2:
            self.zyngui.show_screen("chain_options")
            return True
        return self.switch(i, t)
