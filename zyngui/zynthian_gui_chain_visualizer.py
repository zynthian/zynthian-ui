#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Chain Visualizer Class
#
# ******************************************************************************

import logging
import tkinter
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base

class zynthian_gui_chain_visualizer(zynthian_gui_base):
    
    # Visual constants
    BLOCK_WIDTH = 120
    BLOCK_HEIGHT = 40
    H_SPACING = 30
    V_SPACING = 10
    INIT_X = 20
    INIT_Y = 20
    
    def __init__(self):
        super().__init__('Chain Visualizer')
        self.selected_node = None # Format: (type, slot, index)
        self.moving_proc = None # The processor object being moved
        
        # Canvas for drawing the graph
        self.canvas = tkinter.Canvas(self.main_frame,
                                     bg=zynthian_gui_config.color_panel_bg,
                                     highlightthickness=0)
        self.canvas.pack(fill=tkinter.BOTH, expand=True)
        
        # Nodes mapping:
        self.nodes = {} 
        # Grid structure for navigation: list of lists of node_keys
        # grid_cols[col_idx] = [key1, key2, ...] where keys are vertically ordered
        self.grid_cols = [] 
        
        # Mouse Drag State
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False
        self.drag_threshold = 5  # pixels to detect drag vs click 

    def start_move_mode(self, processor):
        self.moving_proc = processor
        self.draw_graph() 
        self._sync_selection_to_moving_proc()

    def _sync_selection_to_obj(self, obj):
        if not obj: return
        found_key = None
        for key, node in self.nodes.items():
            if node.get('obj') == obj:
                found_key = key
                break
        if found_key:
            self.selected_node = found_key
            self._draw_selection()

    def _sync_selection_to_moving_proc(self):
        if self.moving_proc:
            self._sync_selection_to_obj(self.moving_proc)
        else:
            # Fallback if lost
            pass 

    def build_view(self):
        self.set_title(f"Chain: {self.zyngui.chain_manager.active_chain.get_name()}")
        
        # Bind Mouse Events
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        
        self.draw_graph()
        
        if self.moving_proc:
            self._sync_selection_to_moving_proc()
        elif not self.selected_node:
            # Try setting selected node from chain.current_processor
            if self.zyngui.chain_manager.active_chain.current_processor:
                self._sync_selection_to_obj(self.zyngui.chain_manager.active_chain.current_processor)
            
            # Fallback to first node if still nothing
            if not self.selected_node and self.grid_cols:
                if self.grid_cols[0]:
                    self.selected_node = self.grid_cols[0][0]
                    self._draw_selection()
        
        return True

    def draw_graph(self):
        self.canvas.delete("all")
        self.nodes = {}
        self.grid_cols = []
        synth_proc_count = self.zyngui.chain_manager.active_chain.get_processor_count("Synth")
        midi_proc_count = self.zyngui.chain_manager.active_chain.get_processor_count("MIDI Tool")
        audio_proc_count = max(0, self.zyngui.chain_manager.active_chain.get_processor_count("Audio Effect") - 1)

        current_x = self.INIT_X
        last_out_point = None
        
        # Colors (Lighter Pastel)
        c_midi = "#805050" 
        c_synth = "#508050" 
        c_audio = "#505080"
        c_input = "#606060" # Grey for Input/Output? Or maybe distinct?
        c_output = "#606060" 

        # Decide Input / Output Sections based on Chain Type
        # Logic assumptions:
        # MIDI Chain: [MIDI In] -> Tools -> [MIDI Out] (Only is_midi())
        # Synth Chain: [MIDI In] -> Tools -> Synths -> Audio FX -> [Audio Out]
        # Audio Chain: [Audio In] -> FX -> [Audio Out]
        
        is_audio_chain = self.zyngui.chain_manager.active_chain.is_audio()
        # is_midi_chain check might need inspection of slots. 
        # But generally if it has chunks of types.
        
        # --- INPUT STAGE ---
        if self.zyngui.chain_manager.active_chain.chain_id != 0 and self.zyngui.chain_manager.active_chain.audio_thru and self.zyngui.chain_manager.active_chain.zynmixer_proc and self.zyngui.chain_manager.active_chain.zynmixer_proc.eng_code!="MR":
            # Audio Input
            current_x, last_out_point = self._layout_io_stage("Audio Input", current_x, last_out_point)
        
        if self.zyngui.chain_manager.active_chain.is_midi():
             # MIDI Input
             current_x, last_out_point = self._layout_io_stage("MIDI Input", current_x, last_out_point)

        # --- MIDI TOOLS ---
        current_x, last_out_point = self._layout_stage("MIDI Tool", current_x, last_out_point, 
                                                       bg_col=c_midi, add_pos='end')
        
        # --- SYNTH ---
        current_x, last_out_point = self._layout_stage("Synth", current_x, last_out_point, 
                                                       is_synth=True, bg_col=c_synth)
        
        # --- AUDIO EFFECTS ---
        current_x, last_out_point = self._layout_stage("Audio Effect", current_x, last_out_point, 
                                                       bg_col=c_audio, add_pos='start')
        
        # --- OUTPUT STAGE ---
        if self.zyngui.chain_manager.active_chain.is_audio():
            current_x, last_out_point = self._layout_io_stage("Audio Output", current_x, last_out_point, is_output=True)
            
        if self.zyngui.chain_manager.active_chain.midi_thru:
             current_x, last_out_point = self._layout_io_stage("MIDI Output", current_x, last_out_point, is_output=True)

        self._draw_nodes()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._draw_selection()

    def _layout_io_stage(self, name, start_x, prev_out_point, is_output=False):
        # Draw a single box for Input/Output
        # Maybe varying color?
        bg_col = "#444444" 
        
        current_x = start_x
        stage_start_x = current_x
        
        node_key = ('IO', name)
        
        slot_y = self.INIT_Y
        slot_center_y = slot_y + self.BLOCK_HEIGHT / 2
        
        # Input line
        slot_in_point = (current_x, slot_center_y)
        if prev_out_point:
             self.canvas.create_line(prev_out_point[0], prev_out_point[1], 
                                    slot_in_point[0], slot_in_point[1],
                                    fill="#AAAAAA", width=2, tags="lines")
        
        node_data = {
            'x': current_x, 'y': slot_y, 'w': self.BLOCK_WIDTH, 'h': self.BLOCK_HEIGHT,
            'text': name, 'obj': None, 'action': 'io', 'key': node_key, 'io_type': name,
            'col_idx': len(self.grid_cols), 'row_idx': 0
        }
        
        self.nodes[node_key] = node_data
        self.grid_cols.append([node_key])
        
        # Output point
        new_out_point = (current_x + self.BLOCK_WIDTH, slot_center_y)
        if is_output: new_out_point = None
        
        final_x = current_x + self.BLOCK_WIDTH + self.H_SPACING
        
        # Background
        # Fixed padding logic
        padding = 10
        bg_left = stage_start_x - (self.H_SPACING/2) if prev_out_point else stage_start_x - padding
        bg_right = final_x - (self.H_SPACING/2) if not is_output else final_x - self.H_SPACING + padding
        
        self.canvas.create_rectangle(bg_left, 0, bg_right, 1000, fill=bg_col, outline="", tags="bg")
        self.canvas.tag_lower("bg")
        
        return final_x, new_out_point

    def _layout_stage(self, ptype, start_x, prev_out_point, is_synth=False, bg_col="#000000", add_pos=None):
        if is_synth:
            slots = self.zyngui.chain_manager.active_chain.synth_slots
            num_slots = len(slots)
            # Synths don't usually have "Add" in this context unless via menu
        else:
            num_slots = self.zyngui.chain_manager.active_chain.get_slot_count(ptype)
            
        current_x = start_x
        my_out_point = prev_out_point
        stage_start_x = current_x
        
        # Keep track if we actually added anything to adjust background
        items_added = False
        
        # Helper to add "Add" node
        def add_special_node(c_x, m_out_p):
            # Special Node for Adding
            node_key = (ptype, 'ADD')
            
            # Center vertically in the "stage" or align top?
            # User said "box at right end". Let's align with top row like others.
            slot_y = self.INIT_Y
            slot_center_y = slot_y + self.BLOCK_HEIGHT / 2
            
            # Connection (Horizontal)
            slot_in_point = (c_x, slot_center_y)
            if m_out_p:
                self.canvas.create_line(m_out_p[0], m_out_p[1], 
                                        slot_in_point[0], slot_in_point[1],
                                        fill="#AAAAAA", width=2, tags="lines")
            
            node_data = {
                'x': c_x,
                'y': slot_y,
                'w': self.BLOCK_WIDTH,
                'h': self.BLOCK_HEIGHT,
                'text': "+",
                'obj': None,
                'action': 'add',
                'key': node_key,
                'col_idx': len(self.grid_cols),
                'row_idx': 0 # Single item
            }
            self.nodes[node_key] = node_data
            self.grid_cols.append([node_key])
            
            # Output point
            new_out_point = (c_x + self.BLOCK_WIDTH, slot_center_y)
            return c_x + self.BLOCK_WIDTH + self.H_SPACING, new_out_point

        # START Add Node
        if add_pos == 'start':
            current_x, my_out_point = add_special_node(current_x, my_out_point)
            items_added = True
 
        for slot_idx in range(num_slots):
            if is_synth:
                processors = slots[slot_idx]
            else:
                processors = self.zyngui.chain_manager.active_chain.get_processors(ptype, slot_idx)
            
            if not processors and not is_synth:
                 continue
                 
            items_added = True
            current_col_keys = []
            
            start_y = self.INIT_Y
            # Use top processor for connection
            slot_center_y = start_y + self.BLOCK_HEIGHT / 2
            
            slot_y = start_y
            
            # Connection Point Input
            slot_in_point = (current_x, slot_center_y)
            
            # Connect from Previous Slot Output (Horizontal Line Only)
            if my_out_point:
                self.canvas.create_line(my_out_point[0], my_out_point[1], 
                                        slot_in_point[0], slot_in_point[1],
                                        fill="#AAAAAA", width=2, tags="lines")
            
            for proc_idx, proc in enumerate(processors):
                node_key = (ptype, slot_idx, proc_idx)
                name = proc.get_name() if proc else "Empty"
                
                node_data = {
                    'x': current_x,
                    'y': slot_y,
                    'w': self.BLOCK_WIDTH,
                    'h': self.BLOCK_HEIGHT,
                    'text': name,
                    'obj': proc,
                    'key': node_key,
                    'col_idx': len(self.grid_cols),
                    'row_idx': len(current_col_keys)
                }
                
                self.nodes[node_key] = node_data
                current_col_keys.append(node_key)
                
                slot_y += self.BLOCK_HEIGHT + self.V_SPACING
                
            if current_col_keys:
                self.grid_cols.append(current_col_keys)
                my_out_point = (current_x + self.BLOCK_WIDTH, slot_center_y)
                current_x += self.BLOCK_WIDTH + self.H_SPACING

        # END Add Node
        if add_pos == 'end':
            current_x, my_out_point = add_special_node(current_x, my_out_point)
            items_added = True
            
        # Draw Background for this Stage
        # Consistency Logic:
        # Left Edge: If we are not first, StartX - Spacing/2. If we are first?, well, we are connected to IO.
        # Right Edge: CurrentX - Spacing/2.
        
        if items_added:
            bg_left = stage_start_x - (self.H_SPACING/2)
            bg_right = current_x - (self.H_SPACING / 2)
            
            self.canvas.create_rectangle(bg_left, 0, 
                                         bg_right, 1000,
                                         fill=bg_col, outline="", tags="bg")
            self.canvas.tag_lower("bg")
            
        return current_x, my_out_point

    def _draw_nodes(self):
        for key, node in self.nodes.items():
            x, y, w, h = node['x'], node['y'], node['w'], node['h']
            text = node['text']
            
            self.canvas.create_rectangle(x, y, x+w, y+h, 
                                         outline=zynthian_gui_config.color_tx,
                                         fill=zynthian_gui_config.color_panel_bg,
                                         tags=f"node_{key}")
            
            self.canvas.create_text(x + w/2, y + h/2,
                                    text=text,
                                    fill=zynthian_gui_config.color_tx,
                                    font=("Audiowide", 10),
                                    tags=f"text_{key}")

    def _draw_selection(self):
        self.canvas.delete("selection")
        if self.selected_node and self.selected_node in self.nodes:
            node = self.nodes[self.selected_node]
            x, y, w, h = node['x'], node['y'], node['w'], node['h']
            
            # Check if moving
            is_moving = self.moving_proc and (node['obj'] == self.moving_proc)
            color = "#FF0000" if is_moving else zynthian_gui_config.color_hl
            
            self.canvas.create_rectangle(x-2, y-2, x+w+2, y+h+2,
                                         outline=color,
                                         width=3, tags="selection")
            self._ensure_visible(node)

    def _ensure_visible(self, node):
        # Margin for scrolling
        MARGIN = 20
        
        # Convert node coords
        x, y, w, h = node['x'], node['y'], node['w'], node['h']
        
        # Get canvas total scrolling area
        bbox = self.canvas.bbox("all")
        if not bbox: return
        scroll_w = max(1, bbox[2] - bbox[0])
        scroll_h = max(1, bbox[3] - bbox[1])
        
        # Current view fractions
        xView = self.canvas.xview()
        yView = self.canvas.yview()
        
        # Calculate currently visible pixel range in scroll coordinates
        # xView[0] is start fraction, xView[1] is end fraction
        visible_left = xView[0] * scroll_w
        visible_right = xView[1] * scroll_w
        visible_width = visible_right - visible_left
        
        visible_top = yView[0] * scroll_h
        visible_bottom = yView[1] * scroll_h
        visible_height = visible_bottom - visible_top
        
        # Check X (Horizontal)
        if x < (visible_left + MARGIN):
             # Scroll Left: Align left edge + MARGIN
             new_left = max(0, x - MARGIN)
             self.canvas.xview_moveto(new_left / scroll_w)
             
        elif (x + w) > (visible_right - MARGIN):
             # Scroll Right: Align right edge + MARGIN
             # We want the new right visible edge to be at x + w + MARGIN
             # So new left edge = (x + w + MARGIN) - visible_width
             new_right = x + w + MARGIN
             new_left = new_right - visible_width
             self.canvas.xview_moveto(new_left / scroll_w)

        # Check Y (Vertical)
        if y < (visible_top + MARGIN):
            new_top = max(0, y - MARGIN)
            self.canvas.yview_moveto(new_top / scroll_h)
            
        elif (y + h) > (visible_bottom - MARGIN):
            new_bottom = y + h + MARGIN
            new_top = new_bottom - visible_height
            self.canvas.yview_moveto(new_top / scroll_h)

    def on_size(self, event):
        super().on_size(event)
        if self.selected_node and self.selected_node in self.nodes:
            self._ensure_visible(self.nodes[self.selected_node])

    # Navigation Logic
    
    def _get_current_grid_pos(self):
        if not self.selected_node or self.selected_node not in self.nodes: return 0, 0
        node = self.nodes[self.selected_node]
        return node.get('col_idx', 0), node.get('row_idx', 0)

    def _select_grid_node(self, col_idx, row_idx):
        if not self.grid_cols: return
        
        # Clamp column
        if col_idx < 0: col_idx = 0
        if col_idx >= len(self.grid_cols): col_idx = len(self.grid_cols) - 1
        
        col_nodes = self.grid_cols[col_idx]
        if not col_nodes: return # Should not happen based on logic
        
        # Clamp row to new column height
        if row_idx < 0: row_idx = 0
        if row_idx >= len(col_nodes): row_idx = len(col_nodes) - 1
        
        self.selected_node = col_nodes[row_idx]
        self._draw_selection()

    def arrow_right(self):
        if self.moving_proc:
            # Persistent Move Mode: Nudge, Refresh, Keep moving_proc
            proc = self.moving_proc
            self.zyngui.chain_manager.nudge_processor(self.zyngui.chain_manager.active_chain.chain_id, proc, False)
            self.moving_proc = proc # Restore moving state
            self.draw_graph()
            self._sync_selection_to_moving_proc()
        else:
            c, r = self._get_current_grid_pos()
            self._select_grid_node(c + 1, r)
        
    def arrow_left(self):
        if self.moving_proc:
            # Persistent Move Mode: Nudge, Refresh, Keep moving_proc
            proc = self.moving_proc
            self.zyngui.chain_manager.nudge_processor(self.zyngui.chain_manager.active_chain.chain_id, proc, True)
            self.moving_proc = proc # Restore moving state
            self.draw_graph()
            self._sync_selection_to_moving_proc()
        else:
            c, r = self._get_current_grid_pos()
            self._select_grid_node(c - 1, r)
        
    def arrow_up(self):
        if not self.moving_proc:
            c, r = self._get_current_grid_pos()
            self._select_grid_node(c, r - 1)

    def arrow_down(self):
        if not self.moving_proc:
            c, r = self._get_current_grid_pos()
            self._select_grid_node(c, r + 1)

    def switch_select(self, t='S'):
        return self.on_select()
    
    def on_select(self):
        # If moving, consume event and exit (User request: Select cancels move)
        if self.moving_proc:
            self.moving_proc = None
            self._draw_selection()
            return True
            
        if self.selected_node and self.selected_node in self.nodes:
            node = self.nodes[self.selected_node]
            
            # Check for Add Action
            if node.get('action') == 'add':
                ptype = node['key'][0]
                if ptype == "MIDI Tool":
                    self.zyngui.modify_chain({"type": "MIDI Tool", "chain_id": self.zyngui.chain_manager.active_chain.chain_id})
                elif ptype == "Audio Effect":
                    self.zyngui.modify_chain({"type": "Audio Effect", "chain_id": self.zyngui.chain_manager.active_chain.chain_id})
                return True
                
            # Check for IO Action
            if node.get('action') == 'io':
                io_type = node.get('io_type')
                if io_type == "MIDI Input":
                    # Navigate to MIDI In config
                    self.zyngui.midi_in_config(self.zyngui.chain_manager.active_chain)
                elif io_type == "Audio Input":
                    self.zyngui.show_screen("audio_in")
                elif io_type == "Audio Output":
                    self.zyngui.show_screen("audio_out")
                elif io_type == "MIDI Output":
                    self.zyngui.midi_out_config(self.zyngui.chain_manager.active_chain)
                return True
            
            proc = node['obj']
            if proc:
                self.zyngui.screens['processor_options'].setup(self.zyngui.chain_manager.active_chain.chain_id, proc)
                self.zyngui.show_screen("processor_options")
        return True

    def back_action(self):
        if self.moving_proc:
            self.moving_proc = None
            self._draw_selection()
            return True # Consumed
        return False
        
    def on_click(self, event):
        # Record start position for drag
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.is_dragging = False

    def on_drag(self, event):
        # Calculate delta
        dx = self.drag_start_x - event.x
        dy = self.drag_start_y - event.y
        
        # Check threshold to avoid jitter clicks
        if not self.is_dragging:
            if abs(dx) > self.drag_threshold or abs(dy) > self.drag_threshold:
                self.is_dragging = True
        
        if self.is_dragging:
            # Scroll Canvas
            # tkinter canvas scan_dragto can be used, or xview_scroll
            # scan_dragto is simpler for "hand grab" feel.
            self.canvas.scan_mark(self.drag_start_x, self.drag_start_y)
            self.canvas.scan_dragto(event.x, event.y, gain=1)
            
            # Update start point for next relative move if manual?
            # scan_mark / scan_dragto works by setting anchor then dragging.
            # We should set mark ONCE at start of drag? 
            # Actually standard usage: 
            # 1. Press -> scan_mark(event.x, event.y)
            # 2. Motion -> scan_dragto(event.x, event.y)
            # So we should call scan_mark in on_click?
            pass

    def on_release(self, event):
        # If dragging, stop.
        if self.is_dragging:
            self.is_dragging = False
            return

        # Handle Click Selection
        # Use canvasx/y to account for scrolling
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        
        # Find closest node or clicked node
        for key, node in self.nodes.items():
            if (node['x'] <= x <= node['x'] + node['w']) and \
               (node['y'] <= y <= node['y'] + node['h']):
                
                self.selected_node = key
                self._draw_selection()
                
                if self.moving_proc:
                    # If they click while moving, cancel move?
                    self.moving_proc = None
                    self._draw_selection()
                    return
                self.on_select()

