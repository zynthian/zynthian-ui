#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Side Chain class (canvas): Side chain view => integrated in Chain Control
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

from zyngui import zynthian_gui_config
from zyngine.zynthian_signal_manager import zynsigman

DRAG_THRESHOLD = 5


class zynthian_side_chain(tkinter.Canvas):
    """
    Side chain view for integrating inside Chain Control class.

    This class handles the graphical representation of a chain and their processors.
    It supports navigation via encoders/keys and mouse/touch interactions for
    scrolling, selecting and operating on processors.
    """

    def __init__(self, parent_gui, width=1, height=1):
        """
        Initialize the Chain View.

        Sets up the canvas, data structures for nodes and grid navigation,
        and initializes mouse drag state variables.
        """

        self.zyngui = zynthian_gui_config.zyngui
        self.state_manager = self.zyngui.state_manager
        self.chain_manager = self.zyngui.chain_manager

        self.chain = None               # The chain to display/manage
        self.chain_control = parent_gui
        self.width = width
        self.height = height

        super().__init__(parent_gui.main_frame, width=width, height=height,
                         bg=zynthian_gui_config.color_panel_bg,
                         highlightthickness=0)

        # Node mapping:
        self.nodes = []                 # Node list
        self.node2pos = {}              # Dict of nodes, mapped by gui object (background rectangle)
        self.bypass2node = {}           # Dict of bypassed processor => nodes
        self.selected_index = None      # Selected node index
        self.moving_proc = None         # The processor object being moved
        self.rows = 0                   # Quantity of rows

        # Mouse Drag State
        self.press_event = None
        self.dragging = False
        self.long_press_id = None
        self.clicked_node = None
        self.released_node = None

        # Bind Events
        self.bind("<Button-1>", self.on_press)
        self.bind("<B1-Motion>", self.on_motion)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Button-4>", self.on_wheel)
        self.bind("<Button-5>", self.on_wheel)
        self.bind("<Configure>", self.on_size)

        self.update_layout()

    def set_chain(self, chain_id=None):
        try:
            self.chain = self.chain_manager.chains[chain_id]
            self.chain_id = chain_id
        except:
            self.chain_id = self.chain_manager.active_chain.chain_id
            self.chain = self.chain_manager.chains[chain_id]

        # Save current selection across node graph rebuild => proc string
        try:
            proc = self.nodes[self.selected_index]["proc"]
            if type(proc) != str:
                proc = None
        except:
            proc = None

        self.selected_index = None
        self.build_graph()

        # Select initial node, trying to restore saved selection
        self.select_node(proc=proc, action=True, action_force=True)

    def update_layout(self):
        self.width = self.winfo_width()
        self.height = self.winfo_height()
        #logging.debug(f"UDPATE_LAYOUT => {self.width}x{self.height}")
        self.font = (zynthian_gui_config.font_family, int(0.026 * self.height))
        self.BLOCK_WIDTH =  2 * int(0.45 * self.width)
        self.BLOCK_HEIGHT = int(0.12 * self.height)
        self.BLOCK_TEXT_WIDTH = int(0.9 * self.BLOCK_WIDTH)
        self.BLOCK_TEXT_HEIGHT = int(0.9 * self.BLOCK_HEIGHT)
        self.H_SPACING = self.width - self.BLOCK_WIDTH
        self.V_SPACING = 2 * (self.BLOCK_HEIGHT // 10)
        self._draw_graph()

    # Function called when frame resized
    def on_size(self, event=None):
        self.update_layout()

    def build_view(self):
        """
        Set up the view for the current chain.
        Draws the initial graph and sets the initial selection.

        Returns:
            bool: Always True.
        """
        zynsigman.register_queued(zynsigman.S_PROCESSOR, zynsigman.SS_PROCESSOR_BYPASS, self.bypass_cb)
        return True

    def hide(self):
        zynsigman.unregister(zynsigman.S_PROCESSOR, zynsigman.SS_PROCESSOR_BYPASS, self.bypass_cb)
        self.moving_proc = None

    def grid_remove(self):
        super().grid_remove()
        #self.hide()

    def bypass_cb(self, zctrl):
        processor = zctrl.processor
        col = "#808080" if zctrl.value else "#ffffff"
        for proc, node in self.bypass2node.items():
            if proc == processor:
                self.itemconfigure(node["text_id"], fill=col)
                break

    # --------------------------------------------------------------------------
    # Drawing
    # --------------------------------------------------------------------------

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
            "title": title,     # Title shown in GUI
            "proc": proc,       # Processor object or string for non-processor nodes
            "slot": slot,       # Processor slot
            "idx": idx,         # Index of (parallel) processor within slot
            "row": row,         # Position of node within graph
            "is_dst": proc_type in ("chain_controllers", "MIDI Synth", "Audio Effect", "MIDI Tool", "Special", "midi_output", "audio_out"),
            "is_src": proc_type in ("chain_controllers", "MIDI Synth", "Audio Effect", "MIDI Tool", "Special", "Audio Generator", "midi_input", "audio_in")
        })

    def fit_text_to_box(self, text, min_font_size=6):
        """ Ensure wrapped text fits inside a rectangle.

        Rules:
        - Keep the original font size if at least one line fits horizontally.
        - If even a single line cannot fit, reduce the font size until it can.
        - Truncate text from the end and append "..." until the wrapped
        text fits within the rectangle height.

        Returns:
            (final_text, final_font_size)
        """

        size = self.font[1]
        while size >= min_font_size:
            f = font.Font(family=self.font[0], size=size)
            line_height = f.metrics("linespace")
            single_line_width = f.measure("W")
            width_ok = single_line_width <= self.BLOCK_TEXT_WIDTH
            height_ok = line_height <= self.BLOCK_TEXT_HEIGHT
            if width_ok and height_ok:
                break
            size -= 1
        size = max(size, min_font_size)
        f = font.Font(family=self.font[0], size=size)

        def wrapped_height(s):
            words = s.split()
            if not words:
                return f.metrics("linespace")
            lines = []
            current = words[0]
            for word in words[1:]:
                trial = current + " " + word
                if f.measure(trial) <= self.BLOCK_TEXT_WIDTH:
                    current = trial
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
            line_height = f.metrics("linespace")
            return len(lines) * line_height

        fitted = text
        while fitted:
            h = wrapped_height(fitted)
            if h <= self.BLOCK_TEXT_HEIGHT:
                break
            fitted = fitted[:-1].rstrip()
            if len(fitted) > 3:
                fitted = fitted[:-3].rstrip() + "..."
            else:
                fitted = "..."
        return fitted, size


    def build_graph(self, proc=None):
        """
        Draw the entire processor chain graph on the canvas.

        Clears the canvas and rebuilds the node structure based on each
        chain's configuration (Inputs -> MIDI Tools -> Synths ->
        Audio Effects -> Outputs). Updates the scroll region.

        Args:
            proc: The processor to select. (None to use current selection)
        """

        # Reset node list
        self.nodes = []

        if self.chain:
            # Add chain option button
            title = "Chain Options"
            if self.chain.title:
                title += "\n" + self.chain.title
            self._add_node(title, "chain_options")
            # Add MIDI input
            if self.chain.is_midi():
                if self.chain.midi_chan < 16:
                    midi_chan = f"CH#{self.chain.midi_chan + 1:02}"
                else:
                    midi_chan = f"CH#ALL"
                self._add_node(f"MIDI Input\n{midi_chan}", "midi_input")
            # Add Chain Controllers block
            if self.chain.zctrls:
                self._add_node(f"Chain\nControllers", "chain_controllers")
            # Add MIDI processors
            for slot_idx, slot in enumerate(self.chain.midi_slots):
                for proc_idx, processor in enumerate(slot):
                    self._add_node(processor.get_name(), processor, slot_idx, proc_idx)
            if self.chain.synth_slots:
                # Add synth
                for slot_idx, slot in enumerate(self.chain.synth_slots):
                    for proc_idx, processor in enumerate(slot):
                        self._add_node(processor.get_name(), processor, slot_idx, proc_idx)
            elif self.chain.is_midi():
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
                case "midi_input" | "midi_output" | "chain_controllers":
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
        node["id"] = self.create_rectangle(
            x, y, x + self.BLOCK_WIDTH, y + self.BLOCK_HEIGHT,
            fill=bg_col, outline=bg_col, tags="node"
        )
        title, size = self.fit_text_to_box(title)
        # Draw node text
        node["text_id"] = self.create_text(
            x + self.BLOCK_WIDTH / 2, y + self.BLOCK_HEIGHT / 2,
            text=title, fill=fg_col,
            font=(self.font[0],size),
            width=self.BLOCK_TEXT_WIDTH,
            justify=tkinter.CENTER
        )
        self.node2pos[node["id"]] = node

    def _draw_graph(self, sel_proc=None):
        if self.width == 1:
            return  # Not yet resized
        self.delete("all")
        self.node2pos = {}
        self.bypass2node = {}
        x = self.H_SPACING // 2
        y = self.V_SPACING // 2
        for row, node in enumerate(self.nodes):
            proc = node["proc"]
            self._draw_node(node, x, y)
            try:
                node_next = self.nodes[row + 1]
                proc_next = node_next["proc"]
            except:
                node_next = None
                proc_next = None
            # Create interconnect lines
            y += self.BLOCK_HEIGHT
            if type(proc) != str and type(proc_next) != str and proc.type == proc_next.type and node["slot"] == node_next["slot"]:
                x0 = x + self.BLOCK_WIDTH // 8
                self.create_line(x0, y, x0, y + self.V_SPACING, fill="#AAAAAA", width=4, tags="lines")
                x0 = x + 7 * self.BLOCK_WIDTH // 8
                self.create_line(x0, y, x0, y + self.V_SPACING, fill="#AAAAAA", width=4, tags="lines")
            else:
                is_src = node.get("is_src", False)
                if node_next:
                    is_dst = node_next.get("is_dst", False)
                else:
                    is_dst = False
                if is_src:
                    x0 = x + self.BLOCK_WIDTH // 2
                    if is_dst:
                        self.create_line(x0, y, x0, y + self.V_SPACING, fill="#AAAAAA", width=4, tags="lines")
                    else:
                        self.create_line(x0, y, x0, y + self.V_SPACING // 2, fill="#AAAAAA", width=4, tags="lines")

            # TODO Manage parallel processors!!

            y += self.V_SPACING

        # Configure scroll region
        bbox = self.bbox("all")
        if bbox:
            self.configure(scrollregion=(0, bbox[1] - 5, self.width, bbox[3] + 5))
        else:
            self.configure(scrollregion=(0, 0, self.width, self.height))
        self.select_node(proc=sel_proc)

    def _draw_selection(self):
        """
        Draw selection cursor.
        """
        self.itemconfig("node", outline="")
        if self.selected_index is None:
            self.selected_index = 0
        if self.moving_proc:
            color = "yellow"
        else:
            color = "white"
        try:
            node_id = self.nodes[self.selected_index]["id"]
            self.itemconfig(node_id, outline=color, width=2)
        except:
            return

        #Scroll the canvas to ensure the selected node is visible.
        self.update_idletasks() # Ensure all redrawing has completed
        # Get node's coords
        try:
            x0, y0, x1, y1 = self.bbox(node_id)
        except Exception as e:
            logging.error(e)
            return
        # Get view coords
        vh = self.height
        vy0 = self.canvasy(0)
        vy1 = self.canvasy(vh)
        b0, b1, b2, b3 = self.bbox("all")
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
        #    self.yview_moveto(target_y)

    def smooth_scroll_to(self, target_y=None, steps=30, delay=10):
        start_y = self.yview()[0]
        dy = 0
        if target_y is not None:
            dy = (target_y - start_y) / steps
        def step(i=0):
            if i >= steps:
                return
            if target_y is not None:
                self.yview_moveto(start_y + dy * i)
            self.after(delay, step, i + 1)
        step()

    # --------------------------------------------------------------------------
    # Node management
    # --------------------------------------------------------------------------

    def get_node_pos(self, node):
        try:
            return self.nodes.index(node)
        except:
            return 0

    def get_proc_pos(self, proc):
        for row, node in enumerate(self.nodes):
            if node.get("proc") == proc:
                return row
        return None

    def select_node(self, row=None, node=None, proc=None, action=False, action_force=False):
        if not self.nodes:
            return
        # Argument priority is from left to right
        if row is not None:
            pass
        elif node:
            row = self.get_node_pos(node)
        elif proc:
            row = self.get_proc_pos(proc)
        elif self.selected_index is not None:
            row = self.selected_index

        try:
            proc = self.nodes[row]["proc"]
        except:
            proc = self.chain.current_processor
            row = self.get_proc_pos(proc)

        # Range check
        if row is None or row < 0:
            row = 0
        elif row >= len(self.nodes):
            row = len(self.nodes) - 1

        self.selected_index = row
        if type(proc) != str:
            self.zyngui.set_current_processor(proc)

        self._draw_selection()
        if action and proc:
            self.node_action(proc, force=action_force)

    def select_current_processor(self, action=False):
        self.select_node(proc=self.chain.current_processor, action=action)

    def select_processor(self, proc, action=False):
        if not proc and self.chain.zctrls:
            self.select_node(proc="chain_controllers", action=action)
        elif proc:
            self.select_node(proc=proc, action=action)

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
        self.select_node()

    # --------------------------------------------------------------------------
    # Touch & Mouse event callbacks
    # --------------------------------------------------------------------------

    def get_node_at(self, x, y):
        for obj_id in self.find_overlapping(x, y, x, y):
            try:
                return self.node2pos[obj_id]
            except:
                pass
        return None

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
        x, y = self.canvasx(event.x), self.canvasy(event.y)
        self.start_xview = self.xview()[0]
        self.start_yview = self.yview()[0]
        self.clicked_node = self.get_node_at(x, y)
        if self.clicked_node:
            self.select_node(node=self.clicked_node, action=True)
            self.long_press_id = self.after(zynthian_gui_config.zynswitch_bold_us // 1000, self.on_long_press)

    def on_long_press(self):
        """ Handle press and hold"""

        if not self.long_press_id:
            return
        self.long_press_id = None
        try:
            node_proc = self.nodes[self.selected_index]["proc"]
        except:
            return
        if type(node_proc) != str:
            self.start_moving_processor(node_proc)

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
                    self.after_cancel(self.long_press_id)
                    self.long_press_id = None

        if self.dragging:
            if self.moving_proc:
                x, y = self.canvasx(event.x), self.canvasy(event.y)
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
                    sr = self.cget("scrollregion")
                    if isinstance(sr, str):
                        sr = [float(x) for x in sr.split()]
                    sr_h = sr[3] - sr[1]
                    can_h = self.winfo_height()

                    # Vertical Move
                    if sr_h > can_h:
                        d_fract_y = dy / float(sr_h)
                        self.yview_moveto(self.start_yview + d_fract_y)

                except Exception as e:
                    logging.warning(f"Can't drag scroll => {e}")

    def on_release(self, event):
        """
        Handle mouse button release.
        Args:
            event: Mouse event
        """

        if self.long_press_id:
            self.after_cancel(self.long_press_id)
            self.long_press_id = None
        else:
            return

        # If dragging, stop.
        if self.dragging:
            self.dragging = False
            return

        if not self.press_event:
            return

        # Handle release event
        x, y = self.canvasx(event.x), self.canvasy(event.y)
        # Find reseased node
        node = self.get_node_at(x, y)
        if node is None:
            return

        # If released node == clicked node =>
        if self.clicked_node and node == self.clicked_node:
            # Bold press
            if event.time > self.press_event.time + zynthian_gui_config.zynswitch_bold_us // 1000:
                self.switch_select(t="B")
                self.released_node = node
            # Short press
            else:
                # Second click release => select action!
                if self.released_node == node:
                    self.switch_select(t="S")
                else:
                    self.released_node = node

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

    # --------------------------------------------------------------------------
    # Zynpot & zynswitch callbacks
    # --------------------------------------------------------------------------

    def back_action(self):
        if self.moving_proc:
            self.end_moving_processor()
            return True  # Consumed
        return False

    def node_action(self, node_proc=None, force=False):
        if node_proc is None:
            try:
                node_proc = self.nodes[self.selected_index]["proc"]
            except:
                logging.warning("Can´t perform node action. Not node selected!")
                return
        if type(node_proc) == str:
            ssname = node_proc
            node_proc = None
        else:
            ssname = "control"
        self.chain_control.show_subscreen(ssname, node_proc, force=force)

    def switch_select(self, t='S'):
        """ Handle selection event (Select/Enter key or Click).
        Args:
            t (str): Press type ('S' for short, 'B' for bold/long).
        Returns:
            bool: True if event consumed.
        """

        if self.moving_proc:
            self.end_moving_processor()
            if t == "S":
                return True

        if self.selected_index is None:
            self.select_node()
        proc = self.nodes[self.selected_index].get("proc")
        if type(proc) == str:
            return True
        else:
            if t == "S":
                self.zyngui.show_screen("processor_options")
            elif t == "B":
                self.start_moving_processor(proc)

    # --------------------------------------------------------------------------
    # CUIA
    # --------------------------------------------------------------------------

    def arrow_down(self):
        """
        Handle arrow down action.
        Moves selection down or nudges processor if in move mode.
        """

        if self.moving_proc:
            proc = self.moving_proc
            self.chain_manager.nudge_processor(self.chain_manager.active_chain.chain_id, proc, False)
            self.build_graph(proc)
            self.chain_control.refresh_subscreen()
        else:
            row = self.selected_index + 1
            if row < len(self.nodes):
                self.select_node(row, action=True)
        return True

    def arrow_up(self):
        """
        Handle arrow up action.
        Moves selection up or nudges processor if in move mode.
        """

        if self.moving_proc:
            proc = self.moving_proc
            self.chain_manager.nudge_processor(self.chain_manager.active_chain.chain_id, proc, True)
            self.build_graph(proc)
            self.chain_control.refresh_subscreen()
        else:
            row = self.selected_index - 1
            if row >= 0:
                self.select_node(row, action=True)
        return True

