# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Widget Class for "Organelle OLED"
#
# Copyright (C) 2025 Ronald Summers <ronfsum@gmail.com>
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
# ******************************************************************************

import liblo
import tkinter as tk
import sys
import os
import math

# Zynthian specific modules
sys.path.append("/zynthian/zynthian-ui/")
from zyngui import zynthian_gui_config, zynthian_widget_base


class OscButton(tk.Canvas):
    """
    Custom touchable button that sends OSC messages when pressed.
    """

    def __init__(self, parent, diameter=70, osc_target=None, label="",
                 osc_path="/button", **kwargs):
        super().__init__(parent, width=diameter, height=diameter,
                         bg="turquoise", highlightthickness=0, **kwargs)
        self.diameter = diameter
        self.osc_target = osc_target
        self.osc_path = osc_path

        # Draw the circular button.
        self.button = self.create_oval(
            2, 2, diameter - 2, diameter - 2,
            fill="sandy brown", outline="black", width=2
        )
        # Place the label at the center.
        self.create_text(diameter // 2, diameter // 2,
                         text=label, font=("Arial", 12), fill="black")

        # Bind press and release events.
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<ButtonRelease-1>", self.on_release)

    def on_press(self, event):
        """Handle button press: change color and send OSC 'press' message."""
        self.itemconfig(self.button, fill="lightgrey")
        self.send_osc(1)

    def on_release(self, event):
        """Handle button release: revert color and send OSC 'release' message."""
        self.itemconfig(self.button, fill="sandy brown")
        self.send_osc(0)

    def send_osc(self, value):
        """Send an OSC message with the specified value."""
        if self.osc_target:
            try:
                liblo.send(self.osc_target, self.osc_path, value)
            except Exception as e:
                print(f"Error sending OSC message: {e}")


class LedIndicator(tk.Canvas):
    """
    LED indicator widget controlled via OSC messages.
    """
    COLORS = {
        0: "black", 1: "red", 2: "green", 3: "blue",
        4: "yellow", 5: "purple", 6: "cyan", 7: "white"
    }

    def __init__(self, parent, diameter=15, osc_target=None, **kwargs):
        super().__init__(parent, width=diameter, height=diameter,
                         bg="turquoise", highlightthickness=0, **kwargs)
        self.osc_target = osc_target
        self.led = self.create_oval(
            2, 2, diameter - 2, diameter - 2,
            fill=self.COLORS[0], outline="black", width=1
        )
        self.current_state = 0

    def set_state(self, state):
        """
        Set the LED state (color) based on an integer value (0-7).
        """
        try:
            state_int = int(state)
            if 0 <= state_int <= 7:
                self.current_state = state_int
                self.itemconfig(self.led, fill=self.COLORS[state_int])
                return True
            else:
                print(f"LED state out of range (0-7): {state_int}")
        except ValueError:
            print(f"Invalid LED state value: {state}")
        return False


class VolumeSlider(tk.Frame):
    """
    Vertical volume slider widget that sends OSC messages on value change.
    """

    def __init__(self, parent, osc_target=None, height=200, width=60, **kwargs):
        super().__init__(parent, bg="black", **kwargs)
        self.osc_target = osc_target

        # Create and pack the label.
        self.label = tk.Label(self, text="   Volume", bg="black",
                              fg="white", font=("Arial", 12))
        self.label.pack(side="bottom", pady=5)

        # Create and pack the slider.
        self.slider = tk.Scale(
            self, from_=1.0, to=0.0, resolution=0.1, orient=tk.VERTICAL,
            length=height, width=width // 2, sliderlength=30, showvalue=True,
            bg="black", fg="white", highlightthickness=0, troughcolor="gray",
            command=self.on_value_change
        )
        self.slider.pack(pady=5)
        self.slider.set(0.7)
        self.on_value_change(0.7)

    def on_value_change(self, value):
        """
        Handle slider value changes by sending an OSC volume message.
        """
        if self.osc_target:
            try:
                vol = float(value)
                liblo.send(self.osc_target, "/vol", vol)
            except Exception as e:
                print(f"Error sending OSC volume message: {e}")

    def get_value(self):
        """Return the current slider value."""
        return self.slider.get()

    def set_value(self, value):
        """Set the slider to the specified value."""
        self.slider.set(value)


class MarkedEncoder(tk.Canvas):
    """
    Marked encoder knob with tick marks and a rotating pointer indicator.
    """

    def __init__(self, parent, diameter=120, osc_target=None, label="Enc", **kwargs):
        super().__init__(parent, width=diameter, height=diameter,
                         bg="turquoise", highlightthickness=0, **kwargs)
        self.diameter = diameter
        self.osc_target = osc_target
        self.rotation_steps = 4  # Quantized OSC events
        self.last_step = 0

        # Define rotation limits (in radians).
        self.min_angle = 0
        self.max_angle = (360 * math.pi) / 180

        self.current_angle = 0
        self.prev_angle = 0
        self.at_min_limit = False
        self.at_max_limit = False

        # Draw the knob base.
        self.knob = self.create_oval(
            2, 2, diameter - 2, diameter - 2,
            fill="blue4", outline="black", width=2
        )

        self.draw_tick_marks()

        # Draw pointer indicator (initially pointing upward).
        center = self.diameter / 2
        pointer_length = self.diameter / 2 - 2
        self.pointer = self.create_line(
            center, center, center, center - pointer_length,
            fill="red", width=8
        )

        # Draw center circle for aesthetics.
        self.create_oval(
            center - diameter / 3.75, center - diameter / 3.75,
            center + diameter / 3.75, center + diameter / 3.75,
            fill="black", outline="white", width=1
        )

        # Add label below the knob.
        self.create_text(center, center, text=label,
                         font=("Arial", 12), fill="white")

        # Bind events for interaction.
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.is_pressed = False

    def draw_tick_marks(self):
        """Draw tick marks around the knob edge."""
        center = self.diameter / 2
        outer_radius = self.diameter / 2
        inner_radius = outer_radius - 6  # Tick length
        num_ticks = 16
        for i in range(num_ticks):
            angle = 2 * math.pi * i / num_ticks
            x1 = center + inner_radius * math.cos(angle)
            y1 = center + inner_radius * math.sin(angle)
            x2 = center + outer_radius * math.cos(angle)
            y2 = center + outer_radius * math.sin(angle)
            self.create_line(x1, y1, x2, y2, fill="white", width=2)

    def on_press(self, event):
        """
        Handle press event. If the center is pressed, send an encoder select message.
        """
        self.is_pressed = True
        center = self.diameter / 2
        center_radius = self.diameter / 5
        distance = math.hypot(event.x - center, event.y - center)
        if distance <= center_radius and self.osc_target:
            try:
                liblo.send(self.osc_target, "/enc_sel", 1)
                self.after(100, lambda: liblo.send(self.osc_target, "/enc_sel", 0))
            except Exception as e:
                print(f"Error sending OSC message: {e}")

    def on_drag(self, event):
        """
        Handle drag events by updating the pointer based on the drag angle
        and sending quantized OSC rotation events.
        """
        if not self.is_pressed:
            return

        center = self.diameter / 2
        raw_angle = math.atan2(event.y - center, event.x - center)
        angle = raw_angle if raw_angle >= 0 else raw_angle + 2 * math.pi

        self.prev_angle = self.current_angle

        # Check for boundary crossing.
        crossing_clockwise = self.prev_angle > 1.5 * math.pi and angle < 0.5 * math.pi
        crossing_counterclockwise = self.prev_angle < 0.5 * math.pi and angle > 1.5 * math.pi

        rotating_clockwise = crossing_clockwise or (angle > self.prev_angle and not crossing_counterclockwise)
        rotating_counterclockwise = crossing_counterclockwise or (angle < self.prev_angle and not crossing_clockwise)

        # Apply rotation limits.
        if rotating_clockwise and (angle < self.min_angle or
                                   (self.prev_angle >= self.max_angle and angle <= self.min_angle + 0.5)):
            angle = self.max_angle
            self.at_max_limit = True
        elif rotating_counterclockwise and angle > self.max_angle and self.prev_angle <= self.min_angle + 0.5:
            angle = self.min_angle
            self.at_min_limit = True
        elif rotating_clockwise and angle > self.max_angle:
            angle = self.max_angle
            self.at_max_limit = True
        elif rotating_counterclockwise and angle < self.min_angle:
            angle = self.min_angle
            self.at_min_limit = True
        else:
            self.at_min_limit = False
            self.at_max_limit = False

        self.current_angle = angle

        # Update pointer indicator.
        pointer_length = self.diameter / 2 - 2
        end_x = center + pointer_length * math.cos(angle)
        end_y = center + pointer_length * math.sin(angle)
        self.coords(self.pointer, center, center, end_x, end_y)

        # Quantize angle into steps and send OSC events if step changes.
        #new_step = int(angle / (3.8 * math.pi) * self.rotation_steps) % self.rotation_steps
        new_step = int(angle / (2 * math.pi) * self.rotation_steps) % self.rotation_steps

        if new_step != self.last_step and self.osc_target:
            try:
                if rotating_clockwise and not self.at_max_limit:
                    liblo.send(self.osc_target, "/enc_down", 1)
                    self.after(50, lambda: liblo.send(self.osc_target, "/enc_down", 0))
                elif rotating_counterclockwise and not self.at_min_limit:
                    liblo.send(self.osc_target, "/enc_up", 1)
                    self.after(50, lambda: liblo.send(self.osc_target, "/enc_up", 0))
            except Exception as e:
                print(f"Error sending OSC message: {e}")
            self.last_step = new_step

    def on_release(self, event):
        """Reset flags when the pointer is released."""
        self.is_pressed = False
        self.at_min_limit = False
        self.at_max_limit = False


class zynthian_widget_organelle(zynthian_widget_base.zynthian_widget_base, tk.Frame):
    """
    Main widget class for the Organelle OLED display.
    Combines an OLED display, volume slider, control buttons, and encoder.
    """

    def __init__(self, parent):
        tk.Frame.__init__(self, parent, bg="#D3D3D3")
        zynthian_widget_base.zynthian_widget_base.__init__(self, parent)

        self.zyngui = zynthian_gui_config.zyngui
        self.zyngui_control = self.zyngui.screens['control']
        self.shown = False
        self.debug = False  # Debug mode for performance
        self.update_pending = False
        self.last_flip_time = 0
        self.batch_updates = True
        self.batch_update_after = 16  # ms (aim for ~60 fps)

        # OLED display settings.
        self.width = 256  # Doubled from 128
        self.height = 132  # Doubled from 66
        self.scale = 2  # Scaling factor for all components

        # Navigation state.
        self.current_page_index = 0
        self.in_parameter_view = False

        # Top container: holds OLED display and volume slider.
        self.top_container = tk.Frame(self, bg="black")
        self.top_container.pack(pady=10)

        # OLED display container.
        self.display_frame = tk.Frame(self.top_container, bg="black", padx=10, pady=10)
        self.display_frame.pack(side="left")
        self.canvas = tk.Canvas(self.display_frame, width=self.width,
                                height=self.height, bg='black', takefocus=0)
        self.canvas.pack()
        self.bg_rect = self.canvas.create_rectangle(0, 0, self.width, self.height,
                                                      fill="", outline="")
        self.canvas.tag_bind(self.bg_rect, "<ButtonPress-1>", self.on_canvas_touch)
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_touch, add="+")

        # Initialize OSC client.
        try:
            self.osc_target = liblo.Address("localhost", 3001)
        except liblo.AddressError as err:
            print(f"OSC client initialization error: {err}")
            self.osc_target = None

        # Volume slider.
        self.volume_slider = VolumeSlider(self.top_container, osc_target=self.osc_target,
                                          height=120, width=50)
        self.volume_slider.pack(side="left", padx=10, pady=10)

        # Controls frame.
        self.controls_frame = tk.Frame(self, bg="#40E0D0")
        self.controls_frame.pack(expand=True, fill='both', padx=20, pady=20)

        self.line_items = {}          # key: y (int), value: canvas item ID for printed text
        self.inverted_lines = {}      # key: y (int), value: Boolean (True if highlighted)
        self.line_bboxes = {}         # Cached bounding boxes for text lines
        self.pending_batch = []       # List of pending canvas operations
        self.text_items_by_position = {}  # Map text items by (x, y) position

        # Start OSC server for display.
        self.server = liblo.ServerThread(3000)
        self.setup_osc_handlers()
        self.server.start()

        # LED indicator and control buttons.
        self.led_indicator = LedIndicator(self.controls_frame, diameter=20,
                                          osc_target=self.osc_target)
        self.aux_button = OscButton(self.controls_frame, diameter=60,
                                    osc_target=self.osc_target, label="Aux",
                                    osc_path="/aux")
        self.fs_button = OscButton(self.controls_frame, diameter=60,
                                   osc_target=self.osc_target, label="FS",
                                   osc_path="/fs")
        self.led_indicator.place(x=35, y=10)
        self.aux_button.pack(side="left", padx=15)
        self.fs_button.place(x=115, y=34)

        # Marked encoder.
        self.encoder = MarkedEncoder(self.controls_frame, diameter=90,
                                     osc_target=self.osc_target, label="Enc")
        self.encoder.pack(side="right", padx=15)

    def setup_osc_handlers(self):
        """Register OSC handlers for various message paths."""
        self.osc_handlers = {
            "/oled/gFlip": self.handle_gFlip,
            "/oled/gCleanln": self.handle_gCleanln,
            "/oled/gClear": self.handle_gClear,
            "/oled/gSetPixel": self.handle_gSetPixel,
            "/oled/gLine": self.handle_gLine,
            "/oled/gBox": self.handle_gBox,
            "/oled/gFillArea": self.handle_gFillArea,
            "/oled/gCircle": self.handle_gCircle,
            "/oled/gFilledCircle": self.handle_gFilledCircle,
            "/oled/gPrintln": self.handle_gPrintln,
            "/oled/gInvertArea": self.handle_gInvertArea,
            "/oled/ginvertLine": self.handle_ginvertLine,
            "/led": self.handle_led,
        }
        for path, handler in self.osc_handlers.items():
            self.server.add_method(path, None, handler)
        self.server.add_method("/enc_up", None, self.handle_enc_up)
        self.server.add_method("/enc_down", None, self.handle_enc_down)
        self.server.add_method("/enc_sel", None, self.handle_enc_sel)
        self.server.add_method(None, None, self.fallback_handler)

    def handle_led(self, path, args):
        self.log_debug(f"Received OSC LED message: {path} {args}")
        if args:
            state = int(args[0])
            self.led_indicator.set_state(state)

    def handle_enc_up(self, path, args):
        if args and args[0] == 1:
            if self.in_parameter_view:
                self.return_to_menu('up')
            elif self.osc_target:
                liblo.send(self.osc_target, "/enc_up", 1)

    def handle_enc_down(self, path, args):
        if args and args[0] == 1:
            if self.in_parameter_view:
                self.return_to_menu('down')
            elif self.osc_target:
                liblo.send(self.osc_target, "/enc_down", 1)

    def handle_enc_sel(self, path, args):
        if args and args[0] == 1:
            self.in_parameter_view = True
            if self.osc_target:
                liblo.send(self.osc_target, "/enc_sel", 1)

    def return_to_menu(self, direction):
        """
        Change the menu page based on the encoder direction.
        """
        self.in_parameter_view = False
        sorted_keys = sorted(self.line_items.keys())
        max_index = len(sorted_keys) - 1 if sorted_keys else 4

        if direction == 'up':
            new_index = max(0, self.current_page_index - 1)
        elif direction == 'down':
            new_index = min(max_index, self.current_page_index + 1)
        else:
            new_index = self.current_page_index

        self.current_page_index = new_index
        self.handle_ginvertLine("/ginvertLine", [new_index])

    def log_debug(self, message):
        """Log debug messages if debug mode is enabled."""
        if self.debug:
            print(message)
            sys.stdout.flush()

    def fallback_handler(self, path, args):
        self.log_debug(f"Fallback OSC message: {path} {args}")

    def schedule_update(self):
        """
        Schedule a batched canvas update if not already pending.
        """
        if not self.update_pending and self.batch_updates:
            self.update_pending = True
            self.after(self.batch_update_after, self.perform_update)

    def perform_update(self):
        """Perform all batched canvas operations and refresh the canvas."""
        self.update_pending = False
        if self.pending_batch:
            for op, args, kwargs in self.pending_batch:
                op(*args, **kwargs)
            self.pending_batch = []
        self.canvas.update_idletasks()
        self.canvas.update()

    def add_to_batch(self, operation, *args, **kwargs):
        """
        Add an operation to the batch queue or execute immediately if batching is disabled.
        """
        if self.batch_updates:
            self.pending_batch.append((operation, args, kwargs))
            self.schedule_update()
        else:
            operation(*args, **kwargs)

    def handle_gFlip(self, path, args):
        self.log_debug(f"Received OSC: {path} {args}")
        if not self.batch_updates:
            self.canvas.update_idletasks()
            self.canvas.update()
        else:
            self.schedule_update()

    def handle_gCleanln(self, path, args):
        self.log_debug(f"Received OSC gCleanln: {path} {args}")
        if len(args) < 1:
            print("gCleanln message received with insufficient arguments:", args)
            return
        try:
            n = int(args[0])
        except Exception:
            print("Invalid argument for gCleanln:", args)
            return

        fill_params = {
            1: [0, 0, 8, 128, 9, 0],
            2: [0, 0, 20, 128, 9, 0],
            3: [0, 0, 32, 128, 9, 0],
            4: [0, 0, 44, 128, 9, 0],
            5: [0, 0, 54, 128, 10, 0]
        }
        if n in fill_params:
            self.handle_gFillArea(path, fill_params[n])
        else:
            print("gCleanln received an invalid n:", n)

    def handle_gClear(self, path, args):
        self.log_debug(f"Received OSC: {path} {args}")
        self.in_parameter_view = False

        def clear_canvas():
            self.canvas.delete("all")
            self.line_items.clear()
            self.inverted_lines.clear()
            self.line_bboxes.clear()
            self.text_items_by_position = {}

        self.add_to_batch(clear_canvas)

    def handle_gLine(self, path, args):
        self.log_debug(f"Received OSC: {path} {args}")
        mode, x1, y1, x2, y2, color = args
        x1, y1 = int(x1 * self.scale) + 2, int(y1 * self.scale) + 6
        x2, y2 = int(x2 * self.scale) + 2, int(y2 * self.scale) + 6
        fill_color = "white" if int(color) == 1 else "black"

        def draw_line():
            self.canvas.create_line(x1, y1, x2, y2, fill=fill_color, width=self.scale)

        self.add_to_batch(draw_line)

    def handle_gSetPixel(self, path, args):
        self.log_debug(f"Received OSC: {path} {args}")
        dummy, x, y, c = args
        x, y = int(x * self.scale), int(y * self.scale)
        fill_color = "white" if int(c) == 1 else "black"

        def draw_pixel():
            self.canvas.create_rectangle(
                x, y, x + self.scale, y + self.scale,
                fill=fill_color, outline=fill_color
            )

        self.add_to_batch(draw_pixel)

    def handle_gBox(self, path, args):
        self.log_debug(f"Received OSC: {path} {args}")
        mode, x, y, w, h, color = args
        x, y = int(x * self.scale), int(y * self.scale)
        w, h = int(w * self.scale), int(h * self.scale)
        outline_color = "white" if int(color) == 1 else "black"
        y += 4

        def draw_box():
            self.canvas.create_rectangle(x, y, x + w, y + h,
                                         outline=outline_color,
                                         width=self.scale, fill="")

        self.add_to_batch(draw_box)

    def handle_gFillArea(self, path, args):
        self.log_debug(f"Received OSC: {path} {args}")
        if len(args) >= 6:
            mode, x, y, w, h, color = args[:6]
            x, y = int(x * self.scale), int(y * self.scale)
            w, h = int(w * self.scale), int(h * self.scale)
            fill_color = 'black' if int(color) == 0 else 'white'
            y += 4

            def draw_filled_area():
                self.canvas.create_rectangle(x, y, x + w, y + h,
                                             fill=fill_color, outline=fill_color)

            self.add_to_batch(draw_filled_area)
        else:
            print("gFillArea message received with insufficient arguments:", args)

    def handle_gCircle(self, path, args):
        self.log_debug(f"Received OSC: {path} {args}")
        mode, x, y, r, color = args
        x, y, r = int(x * self.scale), int(y * self.scale), int(r * self.scale)
        outline_color = "white" if int(color) == 1 else "black"

        def draw_circle():
            self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                    outline=outline_color, width=self.scale, fill="")

        self.add_to_batch(draw_circle)

    def handle_gFilledCircle(self, path, args):
        self.log_debug(f"Received OSC: {path} {args}")
        mode, x, y, r, color = args
        x, y, r = int(x * self.scale), int(y * self.scale), int(r * self.scale)
        outline_color = "white" if int(color) == 1 else "black"

        def draw_filled_circle():
            self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                    outline=outline_color, fill=outline_color, width=self.scale)

        self.add_to_batch(draw_filled_circle)

    def handle_gPrintln(self, path, args):
        self.log_debug(f"Received OSC gPrintln - {len(args)} args: {args}")
        if len(args) < 6:
            print("gPrintln message received with insufficient arguments:", args)
            return
        mode, x, y, font_size, color, *text_words = args
        try:
            x_unscaled = int(x)
            y_unscaled = int(y)
        except ValueError:
            return
        x_scaled = x_unscaled * self.scale
        y_scaled = y_unscaled * self.scale
        try:
            fs = int(font_size) * self.scale
        except Exception:
            fs = 8 * self.scale
        text = " ".join(map(str, text_words)).strip()
        if not text:
            return
        fill_color = "white" if int(color) == 1 else "black"
        tag = f"line_{x_unscaled}_{y_unscaled}"
        y_tag = f"y_{y_unscaled}"

        def draw_text():
            self.canvas.delete(tag)
            text_id = self.canvas.create_text(
                x_scaled, y_scaled,
                anchor='nw', text=text, fill=fill_color,
                font=('TkFixedFont', fs),
                tags=[tag, y_tag]
            )
            self.text_items_by_position[(x_unscaled, y_unscaled)] = text_id
            if x_unscaled <= 10:
                self.line_items[y_unscaled] = text_id
                self.line_bboxes[y_unscaled] = self.canvas.bbox(text_id)
            bbox = self.canvas.bbox(text_id)
            if bbox:
                touch_rect = self.canvas.create_rectangle(
                    0, bbox[1], self.width, bbox[3],
                    fill="", outline="", tags=[tag]
                )
                self.canvas.tag_lower(touch_rect, text_id)
                self.canvas.tag_bind(touch_rect, "<ButtonPress-1>", self.on_text_touch)
            self.canvas.tag_bind(text_id, "<ButtonPress-1>", self.on_text_touch)

        self.add_to_batch(draw_text)

    def handle_ginvertLine(self, path, args):
        self.log_debug(f"Received OSC ginvertLine - {args}")
        if len(args) < 1:
            print("ginvertLine message received with insufficient arguments:", args)
            return
        try:
            page = int(args[0])
            self.current_page_index = page
        except Exception:
            print("Invalid ginvertLine argument:", args)
            return

        sorted_keys = sorted(self.line_items.keys())
        if not sorted_keys:
            self.log_debug("No menu lines present to highlight")
            return
        page = max(0, min(page, len(sorted_keys) - 1))

        def update_highlights():
            self.canvas.delete("highlight")
            for key, text_id in self.line_items.items():
                if key == sorted_keys[page]:
                    bbox = self.canvas.bbox(text_id)
                    if bbox:
                        highlight = self.canvas.create_rectangle(
                            0, bbox[1] - 2, self.width, bbox[3] + 2,
                            fill=zynthian_gui_config.color_ctrl_bg_on,
                            outline="", tags=["highlight"]
                        )
                        self.canvas.tag_lower(highlight, text_id)
                    self.canvas.itemconfig(text_id, fill=zynthian_gui_config.color_ctrl_tx)
                else:
                    self.canvas.itemconfig(text_id, fill=zynthian_gui_config.color_panel_tx)
        self.add_to_batch(update_highlights)

    def on_text_touch(self, event):
        """
        Handle touch selection of menu items by simulating encoder messages.
        """
        current_item = event.widget.find_withtag("current")
        if not current_item:
            return
        item = current_item[0]
        tags = event.widget.gettags(item)
        menu_tag = next((tag for tag in tags if tag.startswith("line_")), None)
        if not menu_tag:
            return
        parts = menu_tag.split("_")
        if len(parts) < 3:
            return
        try:
            y_unscaled = int(parts[2])
        except ValueError:
            return
        sorted_keys = sorted(self.line_items.keys())
        try:
            target_index = sorted_keys.index(y_unscaled)
        except ValueError:
            return

        diff = target_index - self.current_page_index
        if diff > 0:
            for i in range(diff):
                delay = 50 * i
                self.after(delay, lambda: liblo.send(self.osc_target, "/enc_down", 1))
                self.after(delay + 50, lambda: liblo.send(self.osc_target, "/enc_down", 0))
        elif diff < 0:
            for i in range(abs(diff)):
                delay = 50 * i
                self.after(delay, lambda: liblo.send(self.osc_target, "/enc_up", 1))
                self.after(delay + 50, lambda: liblo.send(self.osc_target, "/enc_up", 0))
        self.current_page_index = target_index
        total_delay = abs(diff) * 50 + 100
        self.after(total_delay, lambda: liblo.send(self.osc_target, "/enc_sel", 1))
        self.after(total_delay + 100, lambda: liblo.send(self.osc_target, "/enc_sel", 0))

    def select_page(self, page_index):
        """
        Force selection of a menu item by index.
        """
        self.current_page_index = page_index
        if self.osc_target:
            liblo.send(self.osc_target, "/enc_sel", 1)
            self.after(100, lambda: liblo.send(self.osc_target, "/enc_sel", 0))

    # Needs work.  Return to menu is not working properly
    def on_canvas_touch(self, event):
        """
        Handle OLED touch: simulate enc_down when not in menu view.
        """
        self.log_debug("OLED touched in non-menu view; simulating enc_down")
        if self.in_parameter_view and self.osc_target:
            liblo.send(self.osc_target, "/enc_down", 1)
            self.after(50, lambda: liblo.send(self.osc_target, "/enc_down", 0))

    def handle_gInvertArea(self, path, args):
        self.log_debug(f"Received OSC: {path} {args}")
        mode, x, y, w, h = args
        x, y = int(x * self.scale), int(y * self.scale)
        w, h = int(w * self.scale), int(h * self.scale)

        def invert_area():
            self.canvas.create_rectangle(x, y, x + w, y + h, fill='white')

        self.add_to_batch(invert_area)

    def show(self):
        """Display the widget."""
        if not self.shown:
            self.shown = True

    def hide(self):
        """Hide the widget."""
        if self.shown:
            self.shown = False

    def update(self):
        """Update the widget display if it is currently shown."""
        if self.shown and self.zyngui_control.shown:
            self.refresh_gui()

    def refresh_gui(self):
        """Refresh the OLED canvas."""
        if not self.update_pending:
            self.canvas.update()


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Organelle Interface")
    widget = zynthian_widget_organelle(root)
    widget.pack(expand=True, fill='both')
    root.mainloop()