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
from time import monotonic

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
        self.press_time = None

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
        self.canvas.bind("<Button-4>", self.cb_listbox_wheel)
        self.canvas.bind("<Button-5>", self.cb_listbox_wheel)

        self.draw_graph()
        
        if self.moving_proc:
            self._sync_selection_to_moving_proc()
        elif not self.selected_node:
            # Try setting selected node from chain.current_processor
            if self.zyngui.chain_manager.active_chain.current_processor:
                self._sync_selection_to_obj(self.zyngui.chain_manager.active_chain.current_processor)
            
            # Fallback to first node if still nothing
            if not self.selected_node and self.grid_rows:
                if self.grid_rows[0]:
                    self.selected_node = self.grid_rows[0][0]
                    self._draw_selection()
        
        return True

    def cb_listbox_wheel(self, event):
        if event.num == 5 or event.delta == -120:
            self.arrow_down()
        elif event.num == 4 or event.delta == 120:
            self.arrow_up()
        return "break"  # Consume event to stop scrolling of listbox

    def draw_graph(self):
        self.canvas.delete("all")
        self.nodes = {}
        # Grid structure: grid_rows[row_idx] = [key1, key2, ...] (Items in a row)
        self.grid_rows = [] 
        
        # ... (Existing Logic for counts) ...
        current_y = self.INIT_Y
        last_out_point = None

        # Colors
        c_midi = "#805050" 
        c_synth = "#508050" 
        c_audio = "#505080"
        
        # --- INPUT ROW ---
        inputs = []
        if self.zyngui.chain_manager.active_chain.chain_id != 0 and self.zyngui.chain_manager.active_chain.audio_thru and self.zyngui.chain_manager.active_chain.zynmixer_proc and self.zyngui.chain_manager.active_chain.zynmixer_proc.eng_code!="MR":
            inputs.append("Audio Input")
        
        if self.zyngui.chain_manager.active_chain.is_midi(): 
            inputs.append("MIDI Input")
            
        inputs.append("Chain Options")

        if inputs:
            current_y, _ = self._layout_row(inputs, current_y, None, bg_col="#444444")
            last_out_point = None 
            
        # Note Range Row (if needed)
        if self.zyngui.chain_manager.active_chain.is_midi():
             current_y, last_out_point = self._layout_row(["Note Range"], current_y, last_out_point, bg_col=c_midi, action="note_range")

        # --- MIDI TOOLS ---
        current_y, last_out_point = self._layout_stage_vertical("MIDI Tool", current_y, last_out_point, 
            bg_col=c_midi, add_pos='end')
        
        # --- SYNTH ---
        current_y, last_out_point = self._layout_stage_vertical("Synth", current_y, last_out_point, 
            is_synth=True, bg_col=c_synth)
        
        # --- AUDIO EFFECTS ---
        if self.zyngui.chain_manager.active_chain.is_audio():
            current_y, last_out_point = self._layout_stage_vertical("Audio Effect", current_y, last_out_point, 
                bg_col=c_audio, add_pos='start')

        # --- OUTPUT ROW ---
        outputs = []
        if self.zyngui.chain_manager.active_chain.is_audio():
            outputs.append("Audio Output")
        if self.zyngui.chain_manager.active_chain.midi_thru:
            outputs.append("MIDI Output")
            
        if outputs:
            self._layout_row(outputs, current_y, None, bg_col="#444444") 

        self._draw_nodes()

        # Configure scroll region
        # Use updatedbbox after drawing
        self.canvas.update_idletasks() # Ensure bbox is fresh?
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=(bbox[0]-20, bbox[1]-20, bbox[2]+20, bbox[3]+20))
        else:
            self.canvas.configure(scrollregion=(0,0,100,100))
            
        self._draw_selection()
        
    def _layout_row(self, items, start_y, prev_out_point, bg_col="#000000", action="io"):
        current_x = self.INIT_X
        slot_height = self.BLOCK_HEIGHT
        row_keys = []
        
        total_content_width = len(items) * self.BLOCK_WIDTH + (len(items)-1) * self.H_SPACING
        
        # Start X might want to be centered? 
        # But left alignment is standard.
        
        for item in items:
            key_suffix = item
            node_key = ('SPECIAL', item)
            
            act = action
            if item in ["Audio Input", "MIDI Input", "Chain Options", "Audio Output", "MIDI Output"]:
                act = 'io'
                
            node_data = {
                'x': current_x, 'y': start_y, 'w': self.BLOCK_WIDTH, 'h': self.BLOCK_HEIGHT,
                'text': item, 'obj': None, 'action': act, 'key': node_key, 'io_type': item,
                'row_idx': len(self.grid_rows), 'col_idx': len(row_keys)
            }
            
            self.nodes[node_key] = node_data
            row_keys.append(node_key)
            current_x += self.BLOCK_WIDTH + self.H_SPACING
            
        self.grid_rows.append(row_keys)
        
        # Background
        # Extend full width or just content?
        # User complained drag is bad and bounds wrong.
        # Maybe background rect is too big?
        # "2000" in my previous code was hardcoded width!
        # BAD.
        
        max_width = max(total_content_width + self.INIT_X*2, 600) # Min width 600
        
        bg_top = start_y - 5
        bg_bottom = start_y + self.BLOCK_HEIGHT + 5
        self.canvas.create_rectangle(0, bg_top, max_width, bg_bottom, fill=bg_col, outline="", tags="bg")
        self.canvas.tag_lower("bg")
        
        center_x = self.INIT_X + (self.BLOCK_WIDTH / 2)
        out_point = (center_x, start_y + self.BLOCK_HEIGHT)
        
        if prev_out_point:
             self.canvas.create_line(prev_out_point[0], prev_out_point[1], 
                                     center_x, start_y,
                                     fill="#AAAAAA", width=2, tags="lines")
                                     
        return start_y + self.BLOCK_HEIGHT + self.V_SPACING, out_point

    def _layout_stage_vertical(self, ptype, start_y, prev_out_point, is_synth=False, bg_col="#000000", add_pos=None):
        if is_synth:
            slots = self.zyngui.chain_manager.active_chain.synth_slots
            num_slots = len(slots)
        else:
            num_slots = self.zyngui.chain_manager.active_chain.get_slot_count(ptype)
            
        current_y = start_y
        my_out_point = prev_out_point
        stage_start_y = current_y
        items_added = False
        max_row_width = 0
        
        def add_special_node(c_y, m_out_p):
            node_key = (ptype, 'ADD')
            current_x = self.INIT_X
            if m_out_p:
                self.canvas.create_line(m_out_p[0], m_out_p[1], 
                                        current_x + self.BLOCK_WIDTH/2, c_y,
                                        fill="#AAAAAA", width=2, tags="lines")
            
            node_data = {
                'x': current_x, 'y': c_y, 'w': self.BLOCK_WIDTH, 'h': self.BLOCK_HEIGHT,
                'text': "+", 'obj': None, 'action': 'add', 'key': node_key,
                'row_idx': len(self.grid_rows), 'col_idx': 0
            }
            self.nodes[node_key] = node_data
            self.grid_rows.append([node_key])
            return c_y + self.BLOCK_HEIGHT + self.V_SPACING, (current_x + self.BLOCK_WIDTH/2, c_y + self.BLOCK_HEIGHT)

        if add_pos == 'start':
            current_y, my_out_point = add_special_node(current_y, my_out_point)
            items_added = True

        for slot_idx in range(num_slots):
            if is_synth:
                processors = slots[slot_idx]
            else:
                processors = self.zyngui.chain_manager.active_chain.get_processors(ptype, slot_idx)
            
            if not processors and not is_synth: continue
            items_added = True
            
            current_row_keys = []
            current_x = self.INIT_X
            in_x = current_x + self.BLOCK_WIDTH/2
            if my_out_point:
                self.canvas.create_line(my_out_point[0], my_out_point[1], 
                                        in_x, current_y,
                                        fill="#AAAAAA", width=2, tags="lines")

            for proc_idx, proc in enumerate(processors):
                node_key = (ptype, slot_idx, proc_idx)
                name = proc.get_name() if proc else "Empty"
                node_data = {
                    'x': current_x, 'y': current_y, 'w': self.BLOCK_WIDTH, 'h': self.BLOCK_HEIGHT,
                    'text': name, 'obj': proc, 'key': node_key,
                    'row_idx': len(self.grid_rows), 'col_idx': len(current_row_keys)
                }
                self.nodes[node_key] = node_data
                current_row_keys.append(node_key)
                current_x += self.BLOCK_WIDTH + self.H_SPACING
                
            if current_x > max_row_width: max_row_width = current_x
            
            if current_row_keys:
                self.grid_rows.append(current_row_keys)
                my_out_point = (self.INIT_X + self.BLOCK_WIDTH/2, current_y + self.BLOCK_HEIGHT)
                current_y += self.BLOCK_HEIGHT + self.V_SPACING
        
        if add_pos == 'end':
            current_y, my_out_point = add_special_node(current_y, my_out_point)
            items_added = True
            
        if items_added:
            bg_top = stage_start_y - 5
            bg_bottom = current_y - 5
            bg_w = max(max_row_width, 600)
            self.canvas.create_rectangle(0, bg_top, bg_w, bg_bottom, fill=bg_col, outline="", tags="bg")
            self.canvas.tag_lower("bg")
            
        return current_y, my_out_point

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
        if not self.grid_rows: return
        
        # Clamp Row
        if row_idx < 0: row_idx = 0
        if row_idx >= len(self.grid_rows): row_idx = len(self.grid_rows) - 1
        
        row_nodes = self.grid_rows[row_idx]
        if not row_nodes: return
        
        # Clamp Col
        if col_idx < 0: col_idx = 0
        if col_idx >= len(row_nodes): col_idx = len(row_nodes) - 1
        
        self.selected_node = row_nodes[col_idx]
        self._draw_selection()

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
        if not self.grid_rows: return

        # Clamp row
        if row_idx < 0: row_idx = 0
        if row_idx >= len(self.grid_rows): row_idx = len(self.grid_rows) - 1

        row_nodes = self.grid_rows[row_idx]
        if not row_nodes: return # Should not happen based on logic

        # Clamp column
        if col_idx < 0: col_idx = 0
        if col_idx >= len(row_nodes): col_idx = len(row_nodes) - 1
        
        self.selected_node = row_nodes[col_idx]
        self._draw_selection()

    def zynpot_cb(self, i, dval):
        # Parameter editor implemented in base class!
        if super().zynpot_cb(i, dval):
            return True
        if i == 3:
            if dval > 0:
                self.arrow_down()
            elif dval < 0:
                self.arrow_up()
            return True
        return False

    def arrow_down(self):
        if self.moving_proc:
            # Persistent Move Mode: Nudge, Refresh, Keep moving_proc
            proc = self.moving_proc
            self.zyngui.chain_manager.nudge_processor(self.zyngui.chain_manager.active_chain.chain_id, proc, False)
            self.moving_proc = proc # Restore moving state
            self.draw_graph()
            self._sync_selection_to_moving_proc()
        else:
            c, r = self._get_current_grid_pos()
            self._select_grid_node(c, r + 1)
        
    def arrow_up(self):
        if self.moving_proc:
            # Persistent Move Mode: Nudge, Refresh, Keep moving_proc
            proc = self.moving_proc
            self.zyngui.chain_manager.nudge_processor(self.zyngui.chain_manager.active_chain.chain_id, proc, True)
            self.moving_proc = proc # Restore moving state
            self.draw_graph()
            self._sync_selection_to_moving_proc()
        else:
            c, r = self._get_current_grid_pos()
            self._select_grid_node(c, r - 1)
        
    def arrow_left(self):
        if not self.moving_proc:
            c, r = self._get_current_grid_pos()
            self._select_grid_node(c - 1, r)

    def arrow_right(self):
        if not self.moving_proc:
            c, r = self._get_current_grid_pos()
            self._select_grid_node(c + 1, r)

    def switch_select(self, t='S'):
        # Pass type to on_select
        return self.on_select(t)
    
    def on_select(self, t='S'):
        # If moving, consume event and exit (User request: Select cancels move)
        if self.moving_proc:
            self.moving_proc = None
            self._draw_selection()
            return True
            
        if self.selected_node and self.selected_node in self.nodes:
            node = self.nodes[self.selected_node]
            
            # Check for Add Action
            if node.get('action') == 'add':
                if t == 'S': # Only select triggers add
                    ptype = node['key'][0]
                    if ptype == "MIDI Tool":
                        self.zyngui.modify_chain({"type": "MIDI Tool", "chain_id": self.zyngui.chain_manager.active_chain.chain_id})
                    elif ptype == "Audio Effect":
                        self.zyngui.modify_chain({"type": "Audio Effect", "chain_id": self.zyngui.chain_manager.active_chain.chain_id})
                return True
            
            # Check for Special Actions
            if node.get('action') == 'note_range':
                if t == 'S':
                    # "Short press ... navigates"
                    self.zyngui.screens['midi_key_range'].config(self.zyngui.chain_manager.active_chain)
                    self.zyngui.show_screen('midi_key_range')
                return True
                
            # Check for IO Action
            if node.get('action') == 'io':
                if t == 'S':
                    io_type = node.get('io_type')
                    if io_type == "MIDI Input":
                        self.zyngui.midi_in_config(self.zyngui.chain_manager.active_chain)
                    elif io_type == "Audio Input":
                        self.zyngui.show_screen("audio_in")
                    elif io_type == "Audio Output":
                        self.zyngui.show_screen("audio_out")
                    elif io_type == "MIDI Output":
                        self.zyngui.midi_out_config(self.zyngui.chain_manager.active_chain)
                    elif io_type == "Chain Options":
                        self.zyngui.screens['chain_options'].setup(self.zyngui.chain_manager.active_chain.chain_id)
                        self.zyngui.show_screen('chain_options')
                return True
            
            proc = node.get('obj')
            if proc:
                if t == 'S':
                    # Short press: Control View
                    # We need to set the processor as selected in control?
                    # The control screen usually works on active_chain + current_processor ??
                    # Zynthian GUI chain_control can set generic selection.
                    # Or simpler:
                    zynthian_gui_config.zyngui.chain_control(self.zyngui.chain_manager.active_chain.chain_id, proc)
                elif t == 'B':
                    # Bold press: Options
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
        self.start_xview = self.canvas.xview()[0]
        self.start_yview = self.canvas.yview()[0]
        self.is_dragging = False
        self.press_time = monotonic()

    def on_drag(self, event):
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
                else:
                    self.on_select(t=press_type)

