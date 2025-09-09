# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Widget Class for "Euclidean Sequencer"
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

import liblo
import tkinter as tk
from tkinter import font as tkFont
import sys
import os
import math

# Zynthian specific modules
sys.path.append("/zynthian/zynthian-ui/")
from zyngui import zynthian_gui_config, zynthian_widget_base


class zynthian_widget_euclidseq(zynthian_widget_base.zynthian_widget_base, tk.Frame):
    """
    Widget class for Euclidean Sequencer display.
    """
    def __init__(self, parent):
        tk.Frame.__init__(self, parent, bg="#000000")
        zynthian_widget_base.zynthian_widget_base.__init__(self, parent)

        # --- Early & Stable Attribute Initialization ---
        self.shown = False
        self.debug = True
        self.update_pending = False
        self.batch_update_after = 1

        self.channels = 6
        self.max_steps = 16
        self.max_channel_length = 32
        self.max_hits = 32
        self.max_note = 128


        self.hits = [3, 4, 5, 3, 2, 4]
        self.offset = [0, 2, 0, 8, 3, 9]
        self.mute = [False] * self.channels
        self.limit = [16] * self.channels
        self.playing_step = [0] * self.channels
        self.note_numbers = [36, 38, 40, 42, 44, 48]
        
        self.display_mode = "euclidean"
        self.allowed_intervals = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]

        self.interval_value = [self.allowed_intervals[0]] * self.channels

        self.euclidean_patterns = self._generate_euclidean_patterns(self.max_steps)
        self.offset_buf = [[False] * self.max_steps for _ in range(self.channels)]
        
        self.select_ch = 0
        self.zyngui = zynthian_gui_config.zyngui
        
        # --- UI Layout Dimensions ---
        self.canvas_width = 420
        self.canvas_height = 350 
        self.control_panel_width = 160
        self.scale = 2 

        self.graph_x = [4, 77, 150, 4, 77, 150]
        self.graph_y = [20, 20, 20, 110, 110, 110]

        self.x16 = [25, 31, 36, 39, 40, 39, 36, 31, 25, 19, 14, 11, 10, 11, 14, 19]  
        self.y16 = [10, 11, 14, 19, 25, 31, 36, 39, 40, 39, 36, 31, 25, 19, 14, 11]
        
        # --- Drag Interaction State Variables ---
        self.dragging_param = None
        self.dragging_note_ch = None # Specifically for tracking which circle is dragged
        self.drag_start_y = 0
        self.drag_last_y_for_threshold = 0
        self.drag_threshold = 15 
        self.did_drag = False


        # --- UI Widget Creation ---
        self.app_container = tk.Frame(self, bg="black")
        self.app_container.pack(expand=True, fill='both')

        self.sequencer_frame = tk.Frame(self.app_container, bg="black")
        self.sequencer_frame.pack(side=tk.LEFT, expand=True, fill='both', padx=5) 

        self.canvas = tk.Canvas(self.sequencer_frame, width=self.canvas_width, height=self.canvas_height, 
                               bg='black', highlightthickness=0)
        self.canvas.pack(padx=5, pady=5)

        self.controls_frame = tk.Frame(self.app_container, bg="#181818", width=self.control_panel_width)
        self.controls_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(0,5), pady=5)
        self.controls_frame.pack_propagate(False) 

        self._create_control_panel_widgets()
        
        # Bind drag/click events to the main canvas
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.circle_hit_areas = []

        # --- OSC and Final Setup ---
        try:
            self.osc_server = liblo.ServerThread(9001)
            self.osc_target = liblo.Address("localhost", 9000)
            self.setup_osc_handlers()
            self.osc_server.start()
        except liblo.AddressError as err:
            print(f"OSC initialization error: {err}")
            self.osc_server = None
            self.osc_target = None
        
        self.update_offset_buffers()
        self.draw_sequencer()
        self.update_animation()

    def _get_scaled_euclidean_canvas_xy(self, model_x, model_y, base_x_for_channel, base_y_for_channel):
        MODEL_CENTER_COORD = 25.0
        MODEL_EFFECTIVE_RADIUS = 15.0
        TARGET_EFFECTIVE_RADIUS_UNITS = 25.0

        coord_rescale_factor = TARGET_EFFECTIVE_RADIUS_UNITS / MODEL_EFFECTIVE_RADIUS
        rel_x_model = model_x - MODEL_CENTER_COORD
        rel_y_model = model_y - MODEL_CENTER_COORD
        rescaled_rel_x = rel_x_model * coord_rescale_factor
        rescaled_rel_y = rel_y_model * coord_rescale_factor
        
        canvas_circle_center_x = base_x_for_channel + (TARGET_EFFECTIVE_RADIUS_UNITS * self.scale)
        canvas_circle_center_y = base_y_for_channel + (TARGET_EFFECTIVE_RADIUS_UNITS * self.scale)
        final_canvas_x = (rescaled_rel_x * self.scale) + canvas_circle_center_x
        final_canvas_y = (rescaled_rel_y * self.scale) + canvas_circle_center_y
        
        return final_canvas_x, final_canvas_y

    def _create_control_panel_widgets(self):
        self.control_widgets = {}
        parent = self.controls_frame
        
        label_font = tkFont.Font(family="TkFixedFont", size=10)
        button_font = tkFont.Font(family="TkFixedFont", size=10, weight="bold")
        channel_label_font = tkFont.Font(family="TkFixedFont", size=12, weight="bold")

        self.selected_channel_disp_label = tk.Label(parent, text=f"Channel: {self.select_ch + 1}", 
                                                 font=channel_label_font, fg="white", bg=parent["bg"])
        self.selected_channel_disp_label.pack(pady=0)

        param_configs = [
            {"label": "Mode", "key": "mode"},
            {"label": "Length", "key": "length"},
            {"label": "Hits", "key": "hits"},
            {"label": "Offset", "key": "offset"},
            {"label": "Interval", "key": "interval"}
        ]

        for config in param_configs:
            param_key = config['key']
            row_frame = tk.Frame(parent, bg=parent["bg"])
            row_frame.pack(fill=tk.X, pady=14)

            tk.Label(row_frame, text=f"{config['label']}:", font=label_font, fg="#cccccc", bg=parent["bg"], width=7, anchor="w").pack(side=tk.LEFT, padx=(0,10))
            
            value_button = tk.Button(row_frame, text="--", font=button_font, width=8, relief=tk.GROOVE,
                                     bg="#333333", fg="#00ff00", activebackground="#444444", activeforeground="#00ff00")
            value_button.pack(side=tk.LEFT, padx=(0,10))

            if param_key == "mode":
                value_button.config(width=12)
            
            value_button.bind("<ButtonPress-1>", lambda e, k=param_key: self._on_value_button_press(e, k))
            value_button.bind("<B1-Motion>", lambda e, k=param_key: self._on_value_button_drag(e, k))
            value_button.bind("<ButtonRelease-1>", lambda e, k=param_key: self._on_value_button_release(e, k))
            
            self.control_widgets[param_key] = value_button
        
        self._update_control_panel_display()

        mute_button = tk.Button(parent, text="Mute", font=button_font, width=12, relief=tk.GROOVE,
                                bg="#552222", fg="white", activebackground="#663333")
        mute_button.pack(side=tk.BOTTOM, fill=tk.X, padx=0, pady=0)       
        mute_button.bind("<Button-1>", lambda e: self.toggle_mute())
        self.control_widgets["mute"] = mute_button

    def _update_control_panel_display(self):
        if not hasattr(self, 'control_widgets'): return

        self.selected_channel_disp_label.config(text=f"Channel: {self.select_ch + 1}")
        ch = self.select_ch

        self.control_widgets["mode"].config(text=self.display_mode.capitalize())
        self.control_widgets["length"].config(text=str(self.limit[ch]))
        self.control_widgets["hits"].config(text=str(self.hits[ch]))
        self.control_widgets["offset"].config(text=str(self.offset[ch]))

        interval_button = self.control_widgets["interval"]
        interval_row = interval_button.master
        if self.display_mode == "interval":
            interval_button.config(text=str(self.interval_value[ch]))
            interval_row.pack(fill=tk.X, pady=14)
        else:
            interval_row.pack_forget()

        mute_button = self.control_widgets.get("mute")
        if mute_button:
            if self.mute[ch]:
                mute_button.config(text="Unmute", bg="#225522")
            else:
                mute_button.config(text="Mute", bg="#552222")

    def on_canvas_press(self, event):
        x, y = event.x, event.y
        clicked_ch = None
        for i, (cx, cy, radius) in enumerate(self.circle_hit_areas):
            if math.sqrt((x - cx) ** 2 + (y - cy) ** 2) <= radius:
                clicked_ch = i
                break
        
        if clicked_ch is not None:
            self.dragging_param = "note"
            self.dragging_note_ch = clicked_ch
            self.drag_start_y = event.y
            self.drag_last_y_for_threshold = event.y
            self.did_drag = False

    def on_canvas_drag(self, event):
        if self.dragging_param != "note": return
        self.did_drag = True

        delta_y = event.y - self.drag_last_y_for_threshold
        if abs(delta_y) >= self.drag_threshold:
            direction = 1 if delta_y > 0 else -1
            ch = self.dragging_note_ch
            
            new_val = self.note_numbers[ch] + direction
            self.note_numbers[ch] = max(1, min(new_val, self.max_note))
            if self.osc_target:
                liblo.send(self.osc_target, "/euclid/note_num", self.note_numbers[ch])
            
            self.draw_sequencer()
            self.drag_last_y_for_threshold = event.y

    def on_canvas_release(self, event):
        if self.dragging_param == "note":
            if not self.did_drag:
                ch = self.dragging_note_ch
                if self.select_ch != ch:
                    self.select_ch = ch
                    self._update_control_panel_display()
                    self.draw_sequencer()
            
            self.dragging_param = None
            self.dragging_note_ch = None
    
    def _on_value_button_press(self, event, param_key):
        self.dragging_param = param_key
        self.drag_start_y = event.y
        self.drag_last_y_for_threshold = event.y
        self.did_drag = False
        event.widget.config(relief=tk.SUNKEN, bg="#555555")

    def _on_value_button_drag(self, event, param_key):
        if self.dragging_param != param_key: return
        self.did_drag = True
        
        delta_y = event.y - self.drag_last_y_for_threshold
        if abs(delta_y) >= self.drag_threshold:
            direction = 1 if delta_y > 0 else -1
            self._adjust_param_value(param_key, direction)
            self.drag_last_y_for_threshold = event.y

    def _on_value_button_release(self, event, param_key):
        if self.dragging_param == param_key:
            if not self.did_drag:
                self._adjust_param_value(param_key, 1)
            
            event.widget.config(relief=tk.GROOVE, bg="#333333")
            self.dragging_param = None
    
    def _adjust_param_value(self, param_key, direction):
        ch = self.select_ch
        
        if param_key == "mode":
            modes = ["polygon", "euclidean", "interval"]
            current_idx = modes.index(self.display_mode)
            self.display_mode = modes[(current_idx + direction + len(modes)) % len(modes)]
            if self.osc_target: liblo.send(self.osc_target, "/euclid/mode", self.display_mode)
     
        elif param_key == "length":
            new_val = self.limit[ch] + direction
            self.limit[ch] = max(1, min(new_val, self.max_channel_length))
            if self.osc_target: liblo.send(self.osc_target, "/euclid/limit", self.limit[ch])
        
        elif param_key == "hits":
            new_val = self.hits[ch] + direction
            self.hits[ch] = max(0, min(new_val, self.max_hits))
            self.update_offset_buffers()
            if self.osc_target: liblo.send(self.osc_target, "/euclid/hits", self.hits[ch])

        elif param_key == "offset":
            new_val = self.offset[ch] + direction
            self.offset[ch] = (new_val + self.max_steps) % self.max_steps
            self.update_offset_buffers()
            if self.osc_target: liblo.send(self.osc_target, "/euclid/offset", self.offset[ch])

        elif param_key == "interval" and self.display_mode == "interval":
            current_idx = self.allowed_intervals.index(self.interval_value[ch])
            new_idx = (current_idx + direction + len(self.allowed_intervals)) % len(self.allowed_intervals)
            self.interval_value[ch] = self.allowed_intervals[new_idx]
            if self.osc_target: liblo.send(self.osc_target, "/euclid/interval_val", self.interval_value[ch])

        self._update_control_panel_display()
        self.draw_sequencer()

    def toggle_mute(self):
        ch = self.select_ch
        self.mute[ch] = not self.mute[ch]
        if self.osc_target: liblo.send(self.osc_target, "/euclid/mute", int(self.mute[ch]))
        self._update_control_panel_display()
        self.draw_sequencer()

    def setup_osc_handlers(self):
        self.osc_server.add_method("/euclid/mode", 's', self.handle_mode)
        self.osc_server.add_method("/euclid/ch", 'i', self.handle_channel_select)
        self.osc_server.add_method("/euclid/hits", 'i', self.handle_hits)
        self.osc_server.add_method("/euclid/offset", 'i', self.handle_offset)
        self.osc_server.add_method("/euclid/limit", 'i', self.handle_limit)
        self.osc_server.add_method("/euclid/mute", 'i', self.handle_mute)
        self.osc_server.add_method("/euclid/trigger", 'i', self.handle_trigger)
        self.osc_server.add_method("/euclid/interval_val", 'i', self.handle_interval_value)
        self.osc_server.add_method("/euclid/note_num", 'i', self.handle_note_num)
        self.osc_server.add_method(None, None, self.handle_fallback)

    def handle_mode(self, path, args):
            mode_name = args[0]
            if mode_name in ["polygon", "euclidean", "interval"]:
                self.display_mode = mode_name
                self._update_control_panel_display()
                self.draw_sequencer()

    def handle_channel_select(self, path, args):
        ch = args[0]
        if 0 <= ch < self.channels:
            self.select_ch = ch
            self._update_control_panel_display(); self.draw_sequencer()

    def handle_hits(self, path, args):
        val = args[0]
        if 0 <= val <= self.max_hits: self.hits[self.select_ch] = val
        self.update_offset_buffers()
        self._update_control_panel_display(); self.draw_sequencer()
        
    def handle_offset(self, path, args):
        val = args[0]
        if 0 <= val < self.max_steps: self.offset[self.select_ch] = val
        self.update_offset_buffers()
        self._update_control_panel_display(); self.draw_sequencer()

    def handle_limit(self, path, args):
        val = args[0]
        if 0 < val <= self.max_channel_length: self.limit[self.select_ch] = val
        self._update_control_panel_display(); self.draw_sequencer()

    def handle_mute(self, path, args):
        self.mute[self.select_ch] = bool(args[0])
        self._update_control_panel_display()
        self.draw_sequencer()
    
    def handle_note_num(self, path, args):
        val = args[0]
        if 1 <= val <= self.max_note:
            self.note_numbers[self.select_ch] = val
            self._update_control_panel_display()
            self.draw_sequencer()

    def handle_interval_value(self, path, args):
        val = args[0]
        if val in self.allowed_intervals: self.interval_value[self.select_ch] = val
        self._update_control_panel_display(); self.draw_sequencer()

    def handle_trigger(self, path, args):
        if not hasattr(self, 'display_mode'): return

        if args and args[0] == 1:
            for i in range(self.channels):
                if self.limit[i] > 0: self.playing_step[i] = (self.playing_step[i] + 1) % self.limit[i]

            for k in range(self.channels):
                if self.mute[k]: continue
                
                is_active = False
                step = self.playing_step[k]
                if self.display_mode == "polygon": is_active = step in self.get_polygon_vertex_steps(k)
                elif self.display_mode == "euclidean": is_active = self.offset_buf[k][step % self.max_steps]
                elif self.display_mode == "interval": is_active = step in self.get_interval_hit_steps(k)
                
                if is_active:
                    if self.osc_target:
                        liblo.send(self.osc_target, f"/euclid/note/{k}", self.note_numbers[k], 100)
            
            self.draw_sequencer()

    def handle_fallback(self, path, args): pass

    def _generate_euclidean_patterns(self, num_steps):
        all_patterns = [[0] * num_steps]
        for hits in range(1, num_steps + 1):
            pattern = [0] * num_steps
            if hits > 0:
                for i in range(num_steps):
                    if math.floor(i * hits / num_steps) != math.floor((i - 1) * hits / num_steps): pattern[i] = 1
            all_patterns.append(pattern)
        return all_patterns

    def update_offset_buffers(self):
        for k in range(self.channels):
            hits, offset = self.hits[k], self.offset[k]
            safe_hits_idx = max(0, min(hits, self.max_steps))
            base_pattern = self.euclidean_patterns[safe_hits_idx]
            self.offset_buf[k] = [bool(base_pattern[(i - offset + self.max_steps) % self.max_steps]) for i in range(self.max_steps)]

    def get_polygon_vertex_steps(self, k):
        hits, limit, offset = self.hits[k], self.limit[k], self.offset[k]
        if hits <= 0 or limit <= 0: return set()
        rotation = (2*math.pi / self.max_steps) * offset
        angle_per_v = (2*math.pi / hits)
        return {int(round((((angle_per_v*n - math.pi/2 - rotation) + math.pi/2) % (2*math.pi)) / (2*math.pi) * limit)) % limit for n in range(hits)}

    def get_interval_hit_steps(self, k):
        hits, limit, offset, interval = self.hits[k], self.limit[k], self.offset[k], self.interval_value[k]
        if hits <= 0 or limit <= 0: return set()
        rotation = (2*math.pi / self.max_steps) * offset
        angle_per_s = (2*math.pi / limit)
        return {int(round(((((angle_per_s * ((i*interval)%limit)) - math.pi/2 - rotation) + math.pi/2) % (2*math.pi)) / (2*math.pi) * limit)) % limit for i in range(hits)}

    def draw_sequencer(self):
        if self.update_pending: return
        self.update_pending = True
        self.after(self.batch_update_after, self.perform_draw)

    def perform_draw(self):
        if not self.shown: self.update_pending=False; return
        self.update_pending = False
        self.canvas.delete("all")
        self.calculate_circle_hit_areas()
        self.draw_step_dots()
        self.draw_hit_connections()
        self.draw_play_positions()
        self.draw_labels()
        self.canvas.update_idletasks()

    def draw_step_dots(self):
        for k in range(self.channels):
            base_x, base_y, limit = self.graph_x[k]*self.scale, self.graph_y[k]*self.scale, self.limit[k]
            if self.display_mode == "euclidean":
                for j in range(self.max_steps):
                    x,y = self._get_scaled_euclidean_canvas_xy(self.x16[j],self.y16[j],base_x,base_y)
                    self.canvas.create_oval(x-1,y-1,x+1,y+1,fill="white",outline="white")
            elif limit > 0:
                r=25*self.scale; cx,cy=base_x+r,base_y+r
                for j in range(limit):
                    a=(2*math.pi/limit)*j - math.pi/2; x,y=cx+math.cos(a)*r, cy+math.sin(a)*r
                    self.canvas.create_oval(x-1,y-1,x+1,y+1,fill="white",outline="white")

    def draw_hit_connections(self):
        for k in range(self.channels):
            if self.hits[k] <= 0: continue
            base_x,base_y = self.graph_x[k]*self.scale, self.graph_y[k]*self.scale
            coords = []
            target_r = 25*self.scale
            if self.display_mode == "euclidean":
                for m in range(self.max_steps):
                    if self.offset_buf[k][m]: coords.append(self._get_scaled_euclidean_canvas_xy(self.x16[m],self.y16[m],base_x,base_y))
            else:
                cx,cy = base_x+target_r, base_y+target_r
                rotation = (2*math.pi/self.max_steps) * self.offset[k]
                if self.display_mode == "polygon":
                    angle_v = (2*math.pi/self.hits[k])
                    for n in range(self.hits[k]):
                        a = angle_v*n - math.pi/2 - rotation
                        coords.append((cx+math.cos(a)*target_r, cy+math.sin(a)*target_r))
                elif self.display_mode == "interval" and self.limit[k] > 0:
                    angle_s = (2*math.pi/self.limit[k])
                    for i in range(self.hits[k]):
                        step = (i*self.interval_value[k])%self.limit[k]
                        a = angle_s*step - math.pi/2 - rotation
                        coords.append((cx+math.cos(a)*target_r, cy+math.sin(a)*target_r))
            
            if len(coords) > 1: self.canvas.create_polygon(coords,fill="",outline="white",width=1)
            elif len(coords)==1: self.canvas.create_line(base_x+target_r,base_y+target_r,coords[0][0],coords[0][1],fill="white",width=1)
            
            color = "yellow" if k==self.select_ch else "white"
            for x,y in coords: self.canvas.create_oval(x-2,y-2,x+2,y+2,fill=color,outline=color)

    def draw_play_positions(self):
        for k in range(self.channels):
            if self.mute[k] or self.limit[k]<=0: continue
            base_x,base_y,step,limit = self.graph_x[k]*self.scale, self.graph_y[k]*self.scale, self.playing_step[k], self.limit[k]
            x,y,filled = 0,0,False
            if self.display_mode == "euclidean":
                safe_step = step % self.max_steps
                x,y = self._get_scaled_euclidean_canvas_xy(self.x16[safe_step],self.y16[safe_step],base_x,base_y)
                filled = self.offset_buf[k][safe_step]
            else:
                r=25*self.scale; cx,cy=base_x+r,base_y+r
                a=(2*math.pi/limit)*step-math.pi/2; x,y=cx+math.cos(a)*r,cy+math.sin(a)*r
                filled = step in (self.get_polygon_vertex_steps(k) if self.display_mode=="polygon" else self.get_interval_hit_steps(k))
            
            if filled: self.canvas.create_oval(x-8,y-8,x+8,y+8,fill="white",outline="white")
            else: self.canvas.create_oval(x-6,y-6,x+6,y+6,outline="white",width=2)

    def draw_labels(self):
        note_font = ("TkFixedFont",int(10*self.scale/1.5),"bold")
        chan_font = ("TkFixedFont",int(8*self.scale/1.5),"normal")
        radius = 25*self.scale

        for k in range(self.channels):
            cx = self.graph_x[k]*self.scale + radius
            cy = self.graph_y[k]*self.scale + radius
            
            if k == self.select_ch:
                size=10*self.scale*0.8
                self.canvas.create_rectangle(cx-size,cy-size,cx+size,cy+size,fill="#555500",outline="yellow",width=2)
            
            self.canvas.create_text(cx,cy,text=f"{self.note_numbers[k]}",fill="white",font=note_font)

            label_y_pos = cy + radius - 115
            #self.canvas.create_text(cx, label_y_pos, text=f"Ch: {k+1}", fill="red", font=chan_font)
            self.canvas.create_text(cx, label_y_pos, text=f"Ch: {k+1}", fill="red", font=("Arial", 16, "bold"))



    def calculate_circle_hit_areas(self):
        r=25*self.scale; self.circle_hit_areas=[(self.graph_x[k]*self.scale+r, self.graph_y[k]*self.scale+r,r) for k in range(self.channels)]

    def update_animation(self): self.after(50, self.update_animation)
    def show(self): self.shown=True; self.draw_sequencer()
    def hide(self): self.shown=False

# Main block for testing
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Euclidean Sequencer - Final UI")
    root.geometry("600x400")

    class MockZynthianGUIManager:
        def __init__(self): self.screens={'control':None}; self.main_tk=root
    zynthian_gui_config.zyngui = MockZynthianGUIManager()

    widget = zynthian_widget_euclidseq(root)
    widget.pack(expand=True, fill='both')
    widget.show()
    root.mainloop()
